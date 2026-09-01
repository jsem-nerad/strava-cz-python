"""Stored profiles: the file, its permissions, and where passwords come from.

The point of these tests is mostly negative - that the password does not end up
somewhere it should not - so several of them assert on the *absence* of things.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from strava_cz import Profile, ProfileStore, SecretSource
from strava_cz.exceptions import KeyringUnavailableError, ProfileError, ProfileNotFoundError
from strava_cz.profiles import default_store_path

PASSWORD = "not-a-real-password"


@pytest.fixture
def store(store_path: Path) -> ProfileStore:
    return ProfileStore(store_path)


class TestProfile:
    def test_a_name_must_look_like_a_name(self):
        for bad in ("", " ", "-leading", "with space", "sla/sh", ".."):
            with pytest.raises(ProfileError, match="Invalid profile name"):
                Profile(bad, "user", "3753")

    def test_username_and_canteen_are_required(self):
        with pytest.raises(ProfileError, match="needs a username"):
            Profile("skola", "", "3753")
        with pytest.raises(ProfileError, match="needs a canteen number"):
            Profile("skola", "user", "")

    def test_repr_never_shows_the_password(self):
        profile = Profile("skola", "user", "3753", secret=SecretSource.FILE, password=PASSWORD)
        assert PASSWORD not in repr(profile)
        assert "skola" in repr(profile)

    def test_env_var_is_derived_from_the_name(self):
        assert Profile("skola", "u", "1").env_var == "STRAVA_CZ_PASSWORD_SKOLA"
        assert Profile("u.j-2", "u", "1").env_var == "STRAVA_CZ_PASSWORD_U_J_2"

    def test_an_unknown_secret_source_is_rejected_not_guessed(self):
        with pytest.raises(ProfileError, match="unknown secret source"):
            Profile.from_json("skola", {"username": "u", "canteen_number": "1", "secret": "moon"})


class TestStoreFile:
    def test_default_path_follows_xdg(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
        assert default_store_path() == tmp_path / "cfg" / "strava-cz" / "profiles.json"

        monkeypatch.delenv("XDG_CONFIG_HOME")
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
        assert default_store_path() == tmp_path / "home" / ".config" / "strava-cz" / "profiles.json"

    def test_a_missing_store_is_empty_not_an_error(self, store):
        assert store.list() == []
        assert store.names() == ()
        assert store.default_name is None
        assert not store.exists

    def test_the_file_and_its_directory_are_private(self, store, fake_keyring):
        store.save(Profile("skola", "user", "3753"), PASSWORD)
        assert stat.S_IMODE(store.path.stat().st_mode) == 0o600
        assert stat.S_IMODE(store.path.parent.stat().st_mode) == 0o700

    def test_a_failed_write_leaves_no_debris(self, store, fake_keyring, monkeypatch):
        store.save(Profile("skola", "user", "3753"), PASSWORD)
        before = store.path.read_text()

        monkeypatch.setattr(json, "dump", lambda *a, **k: (_ for _ in ()).throw(OSError("full")))
        with pytest.raises(ProfileError, match="Cannot write"):
            store.save(Profile("doma", "user", "1"), PASSWORD)

        assert store.path.read_text() == before, "the old store must survive"
        leftovers = list(store.path.parent.glob(".profiles-*"))
        assert leftovers == [], f"temp files left behind: {leftovers}"

    def test_a_corrupt_store_says_so(self, store):
        store.path.parent.mkdir(parents=True)
        store.path.write_text("{not json")
        with pytest.raises(ProfileError, match="not valid JSON"):
            store.list()

    def test_a_store_holding_a_list_is_rejected(self, store):
        store.path.parent.mkdir(parents=True)
        store.path.write_text("[]")
        with pytest.raises(ProfileError, match="should hold an object"):
            store.list()


class TestSavingAndReading:
    def test_round_trip(self, store, fake_keyring):
        store.save(Profile("skola", "vojtech", "3753", language="CS"), PASSWORD)
        loaded = store.get("skola")
        assert loaded.username == "vojtech"
        assert loaded.canteen_number == "3753"
        assert loaded.language == "CS"
        assert loaded.secret is SecretSource.KEYRING

    def test_the_first_profile_becomes_the_default(self, store, fake_keyring):
        store.save(Profile("skola", "u", "1"), PASSWORD)
        store.save(Profile("doma", "u", "2"), PASSWORD)
        assert store.default_name == "skola"
        assert store.get().name == "skola"

    def test_a_lone_profile_is_the_default_even_if_unmarked(self, store):
        store.path.parent.mkdir(parents=True)
        store.path.write_text(
            json.dumps({"profiles": {"only": {"username": "u", "canteen_number": "1"}}})
        )
        assert store.default_name == "only"

    def test_set_default(self, store, fake_keyring):
        store.save(Profile("skola", "u", "1"), PASSWORD)
        store.save(Profile("doma", "u", "2"), PASSWORD)
        store.set_default("doma")
        assert store.get().name == "doma"

    def test_asking_for_an_unknown_profile_lists_the_known_ones(self, store, fake_keyring):
        store.save(Profile("skola", "u", "1"), PASSWORD)
        with pytest.raises(ProfileNotFoundError, match="skola"):
            store.get("nope")

    def test_no_default_when_nothing_is_stored(self, store):
        with pytest.raises(ProfileNotFoundError, match="No default profile"):
            store.get()

    def test_setting_a_default_that_does_not_exist(self, store):
        with pytest.raises(ProfileNotFoundError):
            store.set_default("ghost")

    def test_delete_removes_the_keyring_entry_too(self, store, fake_keyring):
        store.save(Profile("skola", "u", "1"), PASSWORD)
        assert fake_keyring.entries
        store.delete("skola")
        assert store.names() == ()
        assert fake_keyring.entries == {}

    def test_deleting_the_default_hands_it_to_a_lone_survivor(self, store, fake_keyring):
        store.save(Profile("skola", "u", "1"), PASSWORD)
        store.save(Profile("doma", "u", "2"), PASSWORD)
        store.delete("skola")
        assert store.default_name == "doma"

    def test_deleting_something_that_is_not_there(self, store):
        with pytest.raises(ProfileNotFoundError):
            store.delete("ghost")


class TestPasswordStorage:
    def test_a_keyring_profile_leaves_no_password_in_the_file(self, store, fake_keyring):
        store.save(Profile("skola", "u", "3753"), PASSWORD)
        raw = store.path.read_text()
        assert PASSWORD not in raw
        assert "password" not in json.loads(raw)["profiles"]["skola"]
        assert fake_keyring.entries[("strava-cz", "skola")] == PASSWORD

    def test_env_and_prompt_profiles_store_nothing(self, store):
        for secret in (SecretSource.ENV, SecretSource.PROMPT):
            store.save(Profile(f"p{secret.value}", "u", "1", secret=secret))
        raw = json.loads(store.path.read_text())
        assert all("password" not in rec for rec in raw["profiles"].values())

    def test_only_the_file_source_writes_a_password(self, store):
        store.save(Profile("skola", "u", "1", secret=SecretSource.FILE), PASSWORD)
        assert json.loads(store.path.read_text())["profiles"]["skola"]["password"] == PASSWORD

    def test_a_source_that_stores_a_password_demands_one(self, store, fake_keyring):
        for secret in (SecretSource.KEYRING, SecretSource.FILE):
            with pytest.raises(ProfileError, match="needs one to be given"):
                store.save(Profile("skola", "u", "1", secret=secret))


class TestResolvingPasswords:
    def test_from_the_keyring(self, store, fake_keyring):
        store.save(Profile("skola", "u", "1"), PASSWORD)
        assert store.resolve_password(store.get("skola")) == PASSWORD

    def test_from_the_file(self, store):
        store.save(Profile("skola", "u", "1", secret=SecretSource.FILE), PASSWORD)
        assert store.resolve_password(store.get("skola")) == PASSWORD

    def test_from_the_shared_environment_variable(self, store, monkeypatch):
        store.save(Profile("skola", "u", "1", secret=SecretSource.ENV))
        monkeypatch.setenv("STRAVA_CZ_PASSWORD", "from-shared")
        assert store.resolve_password(store.get("skola")) == "from-shared"

    def test_the_profile_specific_variable_wins(self, store, monkeypatch):
        store.save(Profile("skola", "u", "1", secret=SecretSource.ENV))
        monkeypatch.setenv("STRAVA_CZ_PASSWORD", "shared")
        monkeypatch.setenv("STRAVA_CZ_PASSWORD_SKOLA", "specific")
        assert store.resolve_password(store.get("skola")) == "specific"

    def test_the_environment_overrides_even_a_keyring_profile(
        self, store, fake_keyring, monkeypatch
    ):
        """So a cron job can drive a stored profile without rewriting it."""
        store.save(Profile("skola", "u", "1"), PASSWORD)
        monkeypatch.setenv("STRAVA_CZ_PASSWORD_SKOLA", "override")
        assert store.resolve_password(store.get("skola")) == "override"

    def test_an_env_profile_with_no_variable_set_says_which_one(self, store):
        store.save(Profile("skola", "u", "1", secret=SecretSource.ENV))
        with pytest.raises(ProfileError, match="STRAVA_CZ_PASSWORD_SKOLA"):
            store.resolve_password(store.get("skola"))

    def test_an_empty_keyring_entry_is_not_silently_accepted(self, store, fake_keyring):
        store.save(Profile("skola", "u", "1"), PASSWORD)
        fake_keyring.entries.clear()
        with pytest.raises(ProfileError, match="No password for"):
            store.resolve_password(store.get("skola"))

    def test_a_prompt_profile_fails_rather_than_hanging_without_a_terminal(self, store):
        store.save(Profile("skola", "u", "1", secret=SecretSource.PROMPT))
        with pytest.raises(ProfileError, match="no terminal"):
            store.resolve_password(store.get("skola"), allow_prompt=False)

    def test_a_prompt_profile_asks(self, store, monkeypatch):
        store.save(Profile("skola", "u", "1", secret=SecretSource.PROMPT))
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("strava_cz.profiles.getpass.getpass", lambda prompt="": "typed")
        assert store.resolve_password(store.get("skola")) == "typed"


class TestKeyringUnavailable:
    def test_saving_says_what_to_do_about_it(self, store, no_keyring):
        with pytest.raises(KeyringUnavailableError) as excinfo:
            store.save(Profile("skola", "u", "1"), PASSWORD)
        message = str(excinfo.value)
        assert "strava-cz[cli]" in message
        assert "--secret env" in message

    def test_keyring_available_reports_false_instead_of_raising(self, no_keyring):
        from strava_cz.profiles import keyring_available

        assert keyring_available() is False

    def test_a_keyring_profile_can_still_be_used_through_the_environment(
        self, store, monkeypatch, no_keyring
    ):
        """A profile stored on a laptop must still work on a headless server."""
        store.path.parent.mkdir(parents=True)
        store.path.write_text(
            json.dumps(
                {
                    "default": "skola",
                    "profiles": {
                        "skola": {"username": "u", "canteen_number": "1", "secret": "keyring"}
                    },
                }
            )
        )
        monkeypatch.setenv("STRAVA_CZ_PASSWORD", "from-env")
        assert store.resolve_password(store.get("skola")) == "from-env"


class TestFromProfile:
    def test_from_profile_logs_in(self, api, login_route, store, fake_keyring):
        from strava_cz import StravaCZ

        store.save(Profile("skola", "vojtech", "3753", language="CS"), PASSWORD)
        with StravaCZ.from_profile("skola", store=store) as strava:
            assert strava.user.is_logged_in
            assert strava.language == "CS", "the profile's language is used"

        sent = json.loads(login_route.calls.last.request.content)
        assert sent["jmeno"] == "vojtech"
        assert sent["cislo"] == "3753"
        assert sent["heslo"] == PASSWORD

    def test_from_profile_takes_the_default(self, api, login_route, store, fake_keyring):
        from strava_cz import StravaCZ

        store.save(Profile("skola", "vojtech", "3753"), PASSWORD)
        with StravaCZ.from_profile(store=store) as strava:
            assert strava.user.username == "vojtech"

    def test_an_explicit_password_skips_the_lookup(self, api, login_route, store):
        from strava_cz import StravaCZ

        store.save(Profile("skola", "vojtech", "3753", secret=SecretSource.PROMPT))
        with StravaCZ.from_profile("skola", store=store, password="given") as strava:
            assert strava.user.is_logged_in
        assert json.loads(login_route.calls.last.request.content)["heslo"] == "given"

    def test_kwargs_reach_the_client(self, api, login_route, store, fake_keyring):
        from strava_cz import StravaCZ

        store.save(Profile("skola", "vojtech", "3753"), PASSWORD)
        with StravaCZ.from_profile("skola", store=store, language="EN") as strava:
            assert strava.language == "EN"


def test_the_real_environment_is_not_consulted_by_these_tests(store_path):
    """The store_path fixture must clear inherited STRAVA_CZ_PASSWORD* variables."""
    assert not [v for v in os.environ if v.startswith("STRAVA_CZ_PASSWORD")]
