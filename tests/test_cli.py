"""The `strava-cz` command, driven through main() against recorded responses.

Nothing here touches the network or the real ~/.config: the autouse guard in
conftest blocks sockets, and the `cli` fixture points the profile store at tmp_path.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from strava_cz.cli import EXIT, build_parser, main
from strava_cz.cli.output import Output, parse_date

from .conftest import BASE_URL, load, renumbered, veta_of, with_ordered


@pytest.fixture
def cli(api, login_route, store_path: Path, monkeypatch):
    """A CLI that can log in as a throwaway profile, with the menu stubbed."""
    from strava_cz import Profile, ProfileStore, SecretSource

    ProfileStore(store_path).save(Profile("test", "test.user", "1234", secret=SecretSource.ENV))
    monkeypatch.setenv("STRAVA_CZ_PASSWORD", "test-password")
    api.post(f"{BASE_URL}/api/objednavky").mock(
        return_value=httpx.Response(200, json=load("menu_live"))
    )
    # A write is read back from the canteen's records, which starts with this reset.
    api.post(f"{BASE_URL}/api/nactiVlastnostiPA").mock(return_value=httpx.Response(200, json={}))
    return api


#: An orderable main and a soup in the recorded menu, by the id the command takes.
MEAL = "2026-09-04:O1"
SOUP = "2026-09-02:PO"


def run(*argv: str) -> int:
    """Invoke the CLI exactly as the console script does."""
    return main(list(argv))


def out_json(capsys) -> dict:
    """Parse stdout as the single JSON object a --json run must produce."""
    captured = capsys.readouterr()
    assert captured.out.strip(), f"nothing on stdout; stderr was: {captured.err}"
    return json.loads(captured.out)


class TestParser:
    def test_version(self, capsys):
        from strava_cz import __version__

        with pytest.raises(SystemExit) as excinfo:
            run("--version")
        assert excinfo.value.code == 0
        assert __version__ in capsys.readouterr().out

    def test_a_command_is_required(self, capsys):
        with pytest.raises(SystemExit) as excinfo:
            run()
        assert excinfo.value.code == EXIT["usage"]

    def test_an_unknown_command_is_a_usage_error(self, capsys):
        with pytest.raises(SystemExit) as excinfo:
            run("nonsense")
        assert excinfo.value.code == EXIT["usage"]

    def test_json_is_shorthand_for_format_json(self):
        assert build_parser().parse_args(["--json", "menu"]).format == "json"

    def test_orderable_defaults_to_no_filtering(self):
        args = build_parser().parse_args(["menu"])
        assert args.orderable is None and args.ordered is None and args.auto_ordered is None

    def test_the_negative_flags_mean_false_not_unset(self):
        args = build_parser().parse_args(["menu", "--not-orderable", "--no-auto-ordered"])
        assert args.orderable is False
        assert args.auto_ordered is False

    def test_contradictory_flags_are_rejected(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["menu", "--orderable", "--not-orderable"])
        with pytest.raises(SystemExit):
            build_parser().parse_args(["menu", "--today", "--week"])

    def test_a_bad_date_is_a_usage_error(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["menu", "--from", "next thursday"])

    def test_a_bad_timeout_is_a_usage_error(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--timeout", "0", "menu"])

    def test_every_subcommand_dispatches(self):
        """Each parser entry must map to a handler, or the command dies at runtime."""
        from strava_cz.cli.commands import COMMANDS

        parser = build_parser()
        for argv, key in (
            (["menu"], "menu"),
            (["ordered"], "ordered"),
            (["order", "2026-09-07:O1"], "order"),
            (["cancel", "2026-09-07:O1"], "cancel"),
            (["balance"], "balance"),
            (["account"], "account"),
            (["raw"], "raw"),
            (["profile", "list"], "profile list"),
            (["profile", "show"], "profile show"),
        ):
            args = parser.parse_args(argv)
            resolved = args.command
            if resolved == "profile":
                resolved = f"profile {args.profile_command}"
            assert resolved == key
            assert key in COMMANDS


class TestDates:
    @pytest.mark.parametrize("word", ["today", "dnes"])
    def test_today(self, word):
        import datetime as dt

        assert parse_date(word, dt.date(2026, 9, 4)) == dt.date(2026, 9, 4)

    def test_tomorrow_and_yesterday(self):
        import datetime as dt

        base = dt.date(2026, 9, 4)
        assert parse_date("tomorrow", base) == dt.date(2026, 9, 5)
        assert parse_date("yesterday", base) == dt.date(2026, 9, 3)

    def test_iso(self):
        import datetime as dt

        assert parse_date("2026-09-07") == dt.date(2026, 9, 7)

    def test_nonsense(self):
        with pytest.raises(ValueError, match="not a date"):
            parse_date("soon")

    @pytest.mark.parametrize(
        "flag, first, last",
        [
            ("--today", "2026-09-04", "2026-09-04"),
            ("--tomorrow", "2026-09-05", "2026-09-05"),
            ("--week", "2026-08-31", "2026-09-06"),
            ("--next-week", "2026-09-07", "2026-09-13"),
        ],
    )
    def test_shortcuts_become_a_range(self, flag, first, last):
        import datetime as dt

        from strava_cz.cli.commands import apply_date_shortcuts

        args = build_parser().parse_args(["menu", flag])
        apply_date_shortcuts(args, dt.date(2026, 9, 4))
        assert args.date_from.isoformat() == first
        assert args.date_to.isoformat() == last


class TestMenu:
    def test_pretty_output(self, cli, capsys):
        assert run("menu") == EXIT["ok"]
        text = capsys.readouterr().out
        assert "Kuřecí kostky" in text or "Oběd 1" in text
        assert "orderable" in text, "the summary line is missing"

    def test_no_ansi_when_stdout_is_not_a_terminal(self, cli, capsys):
        run("menu")
        assert "\033[" not in capsys.readouterr().out

    def test_color_always_forces_ansi(self, cli, capsys):
        run("--color", "always", "menu")
        assert "\033[" in capsys.readouterr().out

    def test_no_color_env_is_honoured(self, cli, capsys, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.setattr("sys.stdout.isatty", lambda: True)
        run("menu")
        assert "\033[" not in capsys.readouterr().out

    def test_json_output_is_one_object(self, cli, capsys):
        assert run("--json", "menu") == EXIT["ok"]
        data = out_json(capsys)
        assert data["ok"] is True
        assert data["command"] == "menu"
        assert data["days"]
        assert data["account"]["canteen_number"] == "1234"

    def test_json_never_carries_the_session_id(self, cli, capsys):
        run("--json", "menu")
        text = json.dumps(out_json(capsys))
        assert "sid" not in text
        assert "s5url" not in text

    def test_json_day_carries_the_auto_ordered_flag(self, cli, capsys):
        run("--json", "menu")
        days = {d["date"]: d for d in out_json(capsys)["days"]}
        friday = days["2026-09-04"]
        assert friday["auto_ordered"] is False
        assert friday["status"] == "not_auto_ordered"
        assert friday["day_code"] == "T"
        assert any(m["can_order"] for m in friday["meals"]), "still orderable by hand"

    def test_date_filters_narrow_the_menu(self, cli, capsys):
        run("--json", "menu", "--from", "2026-09-07", "--to", "2026-09-08")
        assert [d["date"] for d in out_json(capsys)["days"]] == ["2026-09-07", "2026-09-08"]

    def test_type_filter(self, cli, capsys):
        run("--json", "menu", "--type", "soup")
        meals = [m for d in out_json(capsys)["days"] for m in d["meals"]]
        assert meals and all(m["type"] == "soup" for m in meals)

    def test_orderable_filter(self, cli, capsys):
        run("--json", "menu", "--orderable")
        meals = [m for d in out_json(capsys)["days"] for m in d["meals"]]
        assert meals and all(m["can_order"] for m in meals)

    def test_no_auto_ordered_filter_picks_the_skipped_days(self, cli, capsys):
        run("--json", "menu", "--no-auto-ordered")
        dates = [d["date"] for d in out_json(capsys)["days"]]
        assert dates == ["2026-09-04", "2026-09-11", "2026-09-18", "2026-09-25"]

    def test_include_no_school(self, cli, capsys):
        run("--json", "menu", "--include-no-school")
        assert any(d["no_school"] for d in out_json(capsys)["days"])

    def test_allergens_are_shown_on_request(self, cli, capsys):
        run("menu", "--allergens", "--from", "2026-09-07", "--to", "2026-09-07")
        assert "Obiloviny" in capsys.readouterr().out

    def test_an_empty_selection_says_so_rather_than_printing_nothing(self, cli, capsys):
        assert run("menu", "--from", "2030-01-01") == EXIT["ok"]
        assert "no meals match" in capsys.readouterr().out


class TestOrdered:
    def test_lists_only_ordered_meals(self, cli, capsys, api):
        api.post(f"{BASE_URL}/api/objednavky").mock(
            return_value=httpx.Response(200, json=with_ordered(load("menu_live"), 5, 7))
        )
        assert run("--json", "ordered") == EXIT["ok"]
        data = out_json(capsys)
        assert sorted(m["id"] for m in data["meals"]) == ["2026-09-03:O1", "2026-09-04:O1"]
        assert data["count"] == 2
        assert data["total_price"] == pytest.approx(100.0)


class TestBalanceAndAccount:
    def test_balance_prints_just_the_number(self, cli, capsys):
        assert run("balance") == EXIT["ok"]
        assert capsys.readouterr().out.strip() == "512.50 Kč"

    def test_balance_json(self, cli, capsys):
        run("--json", "balance")
        assert out_json(capsys)["currency"] == "Kč"

    def test_account_shows_who_is_logged_in(self, cli, capsys):
        assert run("account") == EXIT["ok"]
        assert "test.user" in capsys.readouterr().out

    def test_raw_dumps_the_untouched_response(self, cli, capsys):
        assert run("raw") == EXIT["ok"]
        assert "table0" in json.loads(capsys.readouterr().out)


class TestDryRun:
    def test_nothing_is_sent(self, cli, capsys, api):
        stage = api.post(f"{BASE_URL}/api/pridejJidloS5")
        save = api.post(f"{BASE_URL}/api/saveOrders")
        assert run("order", MEAL, "--dry-run") == EXIT["ok"]
        assert not stage.called and not save.called
        assert "nothing was sent" in capsys.readouterr().out

    def test_it_reports_what_would_change(self, cli, capsys):
        run("--json", "order", MEAL, "--dry-run")
        data = out_json(capsys)
        assert data["dry_run"] is True
        assert data["would_change"] == [MEAL]
        assert data["balance_change"] == pytest.approx(-50.0)

    def test_a_refusal_is_reported_and_changes_the_exit_code(self, cli, capsys):
        # this canteen's soups carry obj: "I"
        assert run("--json", "order", SOUP, "--dry-run") == EXIT["meal"]
        data = out_json(capsys)
        assert data["refused"][0]["id"] == SOUP
        assert "separately" in data["refused"][0]["reason"]

    def test_an_unknown_id_is_refused_not_crashed_on(self, cli, capsys):
        assert run("--json", "order", "2030-01-01:O1", "--dry-run") == EXIT["meal"]
        assert out_json(capsys)["refused"][0]["reason"] == "not in the fetched menu"

    def test_two_meals_in_one_slot_are_reported_as_duplicates(self, cli, capsys):
        # Both are mains on 2026-09-07, so only one of them can be ordered.
        run("--json", "order", "2026-09-07:O1", "2026-09-07:O2", "--dry-run")
        data = out_json(capsys)
        assert data["would_change"] == ["2026-09-07:O1"]
        assert data["duplicate"] == [{"id": "2026-09-07:O2", "competes_with": "2026-09-07:O1"}]

    def test_already_ordered_meals_are_listed_as_such(self, cli, capsys, api):
        api.post(f"{BASE_URL}/api/objednavky").mock(
            return_value=httpx.Response(200, json=with_ordered(load("menu_live"), 7))
        )
        run("--json", "order", MEAL, "--dry-run")
        data = out_json(capsys)
        assert data["already"] == [MEAL] and data["would_change"] == []

    def test_cancel_dry_run_shows_a_refund(self, cli, capsys, api):
        api.post(f"{BASE_URL}/api/objednavky").mock(
            return_value=httpx.Response(200, json=with_ordered(load("menu_live"), 7))
        )
        run("--json", "cancel", MEAL, "--dry-run")
        assert out_json(capsys)["balance_change"] == pytest.approx(50.0)


class TestOrdering:
    @pytest.fixture
    def writable(self, cli, api):
        """Stage and save succeed, and the confirming re-fetch shows meal 7 ordered."""
        api.post(f"{BASE_URL}/api/pridejJidloS5").mock(
            return_value=httpx.Response(200, json={"produkt": [], "konto": "450.00"})
        )
        api.post(f"{BASE_URL}/api/saveOrders").mock(
            return_value=httpx.Response(200, json={"produkty": [], "konto": "450.00"})
        )
        api.post(f"{BASE_URL}/api/objednavky").mock(
            side_effect=[
                httpx.Response(200, json=load("menu_live")),
                httpx.Response(200, json=with_ordered(load("menu_live"), 7)),
            ]
        )
        return api

    def test_ordering_reports_the_change_and_the_new_balance(self, writable, capsys):
        assert run("order", MEAL) == EXIT["ok"]
        text = capsys.readouterr().out
        assert f"ordered 1: {MEAL}" in text
        assert "450.00" in text

    def test_ordering_json(self, writable, capsys):
        run("--json", "order", MEAL)
        data = out_json(capsys)
        assert data["ok"] is True
        assert data["changed"] == [MEAL]
        assert data["account"]["balance"] == pytest.approx(450.0)

    def test_a_refused_meal_exits_four(self, cli, capsys):
        assert run("order", SOUP) == EXIT["meal"]
        assert "error:" in capsys.readouterr().err

    def test_a_refused_meal_in_json_goes_to_stdout_with_a_reason(self, cli, capsys):
        assert run("--json", "order", SOUP) == EXIT["meal"]
        error = out_json(capsys)["error"]
        assert error["type"] == "MealNotOrderableError"
        assert error["meal_id"] == SOUP
        assert error["reason"] == "unavailable"

    def test_insufficient_balance_exits_five(self, cli, capsys, api):
        api.post(f"{BASE_URL}/api/pridejJidloS5").mock(
            return_value=httpx.Response(555, json=load("error_balance"))
        )
        api.post(f"{BASE_URL}/api/nactiVlastnostiPA").mock(
            return_value=httpx.Response(200, json={"konto": "0.00"})
        )
        assert run("--json", "order", MEAL) == EXIT["balance"]
        assert out_json(capsys)["error"]["type"] == "InsufficientBalanceError"

    def test_continue_on_error_reports_instead_of_raising(self, writable, capsys):
        assert run("--json", "order", MEAL, SOUP, "--continue-on-error") == EXIT["meal"]
        data = out_json(capsys)
        assert data["changed"] == [MEAL]
        assert data["failed"][0]["id"] == SOUP
        assert data["failed"][0]["error"] == "MealNotOrderableError"

    def test_strict_duplicates_is_wired_up(self, cli, capsys):
        assert run("order", "2026-09-07:O1", "2026-09-07:O2", "--strict-duplicates") == EXIT["meal"]
        assert "same kind on one day" in capsys.readouterr().err


class TestIdsAcrossLogins:
    """Every run of the command is a new login, and each login numbers the menu afresh.

    On 2026-11-05 `order 10 18` was refused with a soup's and a past day's restriction
    seconds after a dry run had shown both correctly. That was the lucky direction: in
    the opposite one, a number read from `menu` was an orderable meal on another day,
    and it would have been ordered with exit 0.
    """

    MONDAY_O2 = "2026-09-07:O2"
    SHIFTS = (0, 1, 21, 40)

    def login_sees(self, api, shift, *ordered):
        """The menu this login gets, and the id it gives Monday's Oběd 2."""
        payload = renumbered(with_ordered(load("menu_live"), *ordered), shift)
        api.post(f"{BASE_URL}/api/objednavky").mock(return_value=httpx.Response(200, json=payload))
        return veta_of(payload, "07.09.2026", "O2")

    @pytest.mark.parametrize("value", ["10", "31", " 7 "])
    def test_a_bare_number_is_refused_before_logging_in(self, cli, login_route, capsys, value):
        assert run("order", value) == EXIT["usage"]
        assert "changes at every login" in capsys.readouterr().err
        assert not login_route.called

    def test_cancel_refuses_a_bare_number_too(self, cli, login_route, capsys):
        assert run("cancel", "10") == EXIT["usage"]
        assert not login_route.called

    def test_a_dry_run_refuses_a_bare_number_too(self, cli, login_route, capsys):
        assert run("order", "10", "--dry-run") == EXIT["usage"]
        assert not login_route.called

    def test_one_bare_number_stops_the_whole_batch(self, cli, login_route, capsys):
        assert run("order", self.MONDAY_O2, "10", "--continue-on-error") == EXIT["usage"]
        assert not login_route.called

    def test_a_refused_number_comes_back_as_json_in_json_mode(self, cli, capsys):
        """A script still holding numbers has to get something it can branch on."""
        assert run("--json", "order", "10") == EXIT["usage"]
        data = out_json(capsys)
        assert data["ok"] is False
        assert data["error"]["type"] == "MealIdError"
        assert data["error"]["meal_id"] == "10"

    @pytest.mark.parametrize("value", ["nonsense", "2026-09-07", "2026-13-40:O1", ":O1"])
    def test_a_malformed_id_is_a_usage_error(self, cli, capsys, value):
        assert run("order", value) == EXIT["usage"]
        assert "not a meal id" in capsys.readouterr().err

    def test_a_shared_key_says_why_when_ordering(self, cli, api, capsys):
        payload = load("menu_live")
        rows = [r for t in payload.values() if isinstance(t, list) for r in t]
        other = next(r for r in rows if r["datum"] == "07.09.2026" and r["druh"] == "O2")
        other["druh"] = "O1"
        api.post(f"{BASE_URL}/api/objednavky").mock(return_value=httpx.Response(200, json=payload))
        assert run("order", "2026-09-07:O1", "--dry-run") == EXIT["meal"]
        assert "2026-09-07:O1" in capsys.readouterr().err

    def test_a_json_dry_run_names_the_dish_it_would_order(self, cli, capsys):
        """A slot can be republished with another dish, so the name has to be checkable."""
        run("--json", "order", self.MONDAY_O2, "--dry-run")
        meals = out_json(capsys)["meals"]
        assert [meal["id"] for meal in meals] == [self.MONDAY_O2]
        assert meals[0]["name"]

    def test_lower_case_is_accepted(self, cli, capsys):
        run("--json", "order", "2026-09-07:o2", "--dry-run")
        assert out_json(capsys)["would_change"] == [self.MONDAY_O2]

    def test_the_menu_prints_the_id_the_order_command_takes(self, cli, capsys):
        run("menu", "--from", "2026-09-07", "--to", "2026-09-07")
        assert self.MONDAY_O2 in capsys.readouterr().out

    def test_the_json_id_is_the_stable_one(self, cli, capsys):
        run("--json", "menu", "--from", "2026-09-07", "--to", "2026-09-07")
        day = out_json(capsys)["days"][0]
        assert self.MONDAY_O2 in [meal["id"] for meal in day["meals"]]

    def test_an_id_from_one_login_means_the_same_meal_in_the_next(self, cli, api, capsys):
        self.login_sees(api, 0)
        run("--json", "menu", "--from", "2026-09-07", "--to", "2026-09-07")
        meals = out_json(capsys)["days"][0]["meals"]
        chosen = next(meal for meal in meals if meal["variant"] == "Oběd 2")

        self.login_sees(api, 21)
        run("--json", "order", chosen["id"], "--dry-run")
        assert out_json(capsys)["would_change"] == [chosen["id"]]

    @pytest.mark.parametrize("shift", SHIFTS)
    def test_the_write_sends_the_number_this_login_uses(self, cli, api, capsys, shift):
        veta = self.login_sees(api, shift)
        stage = api.post(f"{BASE_URL}/api/pridejJidloS5").mock(
            return_value=httpx.Response(200, json={"konto": "450.00"})
        )
        api.post(f"{BASE_URL}/api/saveOrders").mock(
            return_value=httpx.Response(200, json={"konto": "450.00"})
        )
        payload = renumbered(load("menu_live"), shift)
        api.post(f"{BASE_URL}/api/objednavky").mock(
            side_effect=[
                httpx.Response(200, json=payload),
                httpx.Response(200, json=with_ordered(payload, veta)),
            ]
        )

        assert run("--json", "order", self.MONDAY_O2) == EXIT["ok"]
        assert out_json(capsys)["changed"] == [self.MONDAY_O2]
        assert json.loads(stage.calls.last.request.read())["veta"] == str(veta)

    @pytest.mark.parametrize("shift", SHIFTS)
    def test_a_batch_works_in_every_numbering(self, cli, api, capsys, shift):
        """The call that failed on 2026-11-05, on every layout."""
        self.login_sees(api, shift)
        assert (
            run(
                "--json",
                "order",
                self.MONDAY_O2,
                "2026-09-09:O2",
                "--dry-run",
                "--continue-on-error",
            )
            == EXIT["ok"]
        )
        data = out_json(capsys)
        assert data["would_change"] == [self.MONDAY_O2, "2026-09-09:O2"]
        assert data["refused"] == []

    @pytest.mark.parametrize("shift", SHIFTS)
    def test_a_meal_already_ordered_is_recognised_in_every_numbering(self, cli, api, capsys, shift):
        stage = api.post(f"{BASE_URL}/api/pridejJidloS5")
        self.login_sees(api, shift, 10)
        assert run("--json", "order", self.MONDAY_O2) == EXIT["ok"]
        assert out_json(capsys)["unchanged"] == [self.MONDAY_O2]
        assert not stage.called

    def test_a_narrow_terminal_keeps_the_id_and_the_price_whole(self, cli, capsys, monkeypatch):
        monkeypatch.setenv("COLUMNS", "48")
        run("menu", "--from", "2026-09-07", "--to", "2026-09-07")
        line = next(ln for ln in capsys.readouterr().out.splitlines() if self.MONDAY_O2 in ln)
        assert "50 Kč" in line

    def test_a_listing_keeps_the_id_and_the_price_whole_too(self, cli, capsys, monkeypatch):
        monkeypatch.setenv("COLUMNS", "48")
        run("order", self.MONDAY_O2, "--dry-run")
        line = next(ln for ln in capsys.readouterr().out.splitlines() if self.MONDAY_O2 in ln)
        assert "50 Kč" in line


class TestAuth:
    def test_a_rejected_login_exits_three(self, api, store_path, monkeypatch, capsys):
        from strava_cz import Profile, ProfileStore, SecretSource

        ProfileStore(store_path).save(Profile("test", "u", "1", secret=SecretSource.ENV))
        monkeypatch.setenv("STRAVA_CZ_PASSWORD", "wrong")
        api.post(f"{BASE_URL}/api/login").mock(
            return_value=httpx.Response(555, json=load("login_error"))
        )
        assert run("--json", "balance") == EXIT["auth"]
        assert out_json(capsys)["error"]["code"] == 20

    def test_no_profile_at_all_exits_six(self, store_path, capsys):
        assert run("--json", "balance") == EXIT["profile"]
        assert out_json(capsys)["error"]["type"] == "ProfileNotFoundError"

    def test_username_without_canteen_exits_six(self, store_path, capsys):
        assert run("--username", "someone", "balance") == EXIT["profile"]
        assert "must be given together" in capsys.readouterr().err

    def test_ad_hoc_credentials_work(self, api, login_route, store_path, monkeypatch, capsys):
        monkeypatch.setenv("STRAVA_CZ_PASSWORD", "test-password")
        assert run("--username", "test.user", "--canteen", "1234", "balance") == EXIT["ok"]
        assert json.loads(login_route.calls.last.request.content)["jmeno"] == "test.user"


class TestProfileCommands:
    def test_listing_an_empty_store(self, store_path, capsys):
        assert run("profile", "list") == EXIT["ok"]
        assert "no profiles yet" in capsys.readouterr().out

    def test_add_list_show_default_remove(self, store_path, fake_keyring, capsys, monkeypatch):
        monkeypatch.setenv("STRAVA_CZ_PASSWORD", "secret-one")
        assert run("profile", "add", "skola", "--username", "u1", "--canteen", "3753") == 0
        assert run("profile", "add", "doma", "--username", "u2", "--canteen", "1234") == 0
        capsys.readouterr()

        assert run("--json", "profile", "list") == EXIT["ok"]
        data = out_json(capsys)
        assert [p["name"] for p in data["profiles"]] == ["doma", "skola"]
        assert data["default"] == "skola"

        assert run("profile", "default", "doma") == EXIT["ok"]
        capsys.readouterr()
        assert run("--json", "profile", "show") == EXIT["ok"]
        assert out_json(capsys)["name"] == "doma"

        assert run("profile", "remove", "doma") == EXIT["ok"]
        capsys.readouterr()
        run("--json", "profile", "list")
        assert [p["name"] for p in out_json(capsys)["profiles"]] == ["skola"]

    def test_the_password_reaches_the_keyring_and_not_the_file(
        self, store_path, fake_keyring, monkeypatch, capsys
    ):
        monkeypatch.setenv("STRAVA_CZ_PASSWORD", "keep-me-secret")
        run("profile", "add", "skola", "--username", "u", "--canteen", "1")
        assert "keep-me-secret" not in store_path.read_text()
        assert fake_keyring.entries[("strava-cz", "skola")] == "keep-me-secret"

    def test_password_stdin(self, store_path, fake_keyring, monkeypatch, capsys):
        monkeypatch.setattr("sys.stdin", __import__("io").StringIO("from-stdin\n"))
        run("profile", "add", "skola", "--username", "u", "--canteen", "1", "--password-stdin")
        assert fake_keyring.entries[("strava-cz", "skola")] == "from-stdin"

    def test_secret_file_warns_loudly_and_writes_the_password(
        self, store_path, monkeypatch, capsys
    ):
        monkeypatch.setenv("STRAVA_CZ_PASSWORD", "on-disk")
        assert (
            run("profile", "add", "s", "--username", "u", "--canteen", "1", "--secret", "file")
            == EXIT["ok"]
        )
        captured = capsys.readouterr()
        assert "PLAINTEXT" in captured.err
        assert "on-disk" in store_path.read_text()

    def test_secret_env_stores_nothing(self, store_path, capsys):
        assert (
            run("profile", "add", "s", "--username", "u", "--canteen", "1", "--secret", "env")
            == EXIT["ok"]
        )
        assert "password" not in json.loads(store_path.read_text())["profiles"]["s"]

    def test_explicit_keyring_refuses_and_points_at_the_alternatives(
        self, store_path, no_keyring, monkeypatch, capsys
    ):
        """--secret keyring means keyring; it must not quietly become something else."""
        monkeypatch.setenv("STRAVA_CZ_PASSWORD", "secret")
        assert (
            run("profile", "add", "s", "--username", "u", "--canteen", "1", "--secret", "keyring")
            == EXIT["profile"]
        )
        err = capsys.readouterr().err
        assert "--secret encrypted" in err, "the option that still remembers the password"
        assert "--secret env" in err
        assert store_path.exists() is False, "nothing may be written when it refuses"

    def test_verify_logs_in_before_storing(
        self, api, login_route, store_path, fake_keyring, monkeypatch, capsys
    ):
        monkeypatch.setenv("STRAVA_CZ_PASSWORD", "test-password")
        assert (
            run(
                "profile",
                "add",
                "skola",
                "--username",
                "test.user",
                "--canteen",
                "1234",
                "--verify",
            )
            == EXIT["ok"]
        )
        assert login_route.called
        assert "checking the credentials" in capsys.readouterr().err

    def test_a_bad_profile_name_is_refused(self, store_path, fake_keyring, monkeypatch, capsys):
        monkeypatch.setenv("STRAVA_CZ_PASSWORD", "x")
        assert (
            run("profile", "add", "bad name", "--username", "u", "--canteen", "1")
            == EXIT["profile"]
        )

    def test_removing_something_that_is_not_there(self, store_path, capsys):
        assert run("profile", "remove", "ghost") == EXIT["profile"]

    def test_profile_commands_never_log_in(self, store_path, fake_keyring, monkeypatch, api):
        """They must work with no network at all - the socket guard proves it."""
        monkeypatch.setenv("STRAVA_CZ_PASSWORD", "x")
        run("profile", "add", "skola", "--username", "u", "--canteen", "1")
        run("profile", "list")
        run("profile", "show", "skola")
        assert not api.calls


class TestOutputPlumbing:
    def test_warnings_go_to_stderr_so_json_stays_parseable(self, capsys):
        out = Output(fmt="json")
        out.warn("something odd")
        out.emit("menu", {"days": []}, lambda: None)
        captured = capsys.readouterr()
        assert json.loads(captured.out)["ok"] is True
        assert "something odd" in captured.err

    def test_lines_are_suppressed_in_json_mode(self, capsys):
        out = Output(fmt="json")
        out.line("human text")
        assert capsys.readouterr().out == ""

    def test_long_names_are_clipped_to_the_width(self, cli, capsys, monkeypatch):
        monkeypatch.setattr(
            "shutil.get_terminal_size",
            lambda fallback=(80, 24): __import__("os").terminal_size((60, 24)),
        )
        run("menu", "--from", "2026-09-07", "--to", "2026-09-07")
        for line in capsys.readouterr().out.splitlines():
            assert len(line) <= 60, f"line overflows the terminal: {line!r}"


def test_python_dash_m_runs_the_cli():
    """`python -m strava_cz` must work, not only the installed console script."""
    result = subprocess.run(
        [sys.executable, "-m", "strava_cz", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.startswith("strava-cz ")


class TestSecretAuto:
    """`--secret auto` is what makes a headless machine able to store a password."""

    def test_auto_uses_the_keyring_when_there_is_one(
        self, store_path, fake_keyring, monkeypatch, capsys
    ):
        monkeypatch.setenv("STRAVA_CZ_PASSWORD", "secret")
        assert run("--json", "profile", "add", "s", "--username", "u", "--canteen", "1") == 0
        assert out_json(capsys)["secret"] == "keyring"

    def test_auto_falls_back_to_encryption(self, store_path, no_keyring, monkeypatch, capsys):
        monkeypatch.setenv("STRAVA_CZ_PASSWORD", "secret")
        monkeypatch.setenv("STRAVA_CZ_PASSPHRASE", "unlock-me")
        assert run("--json", "profile", "add", "s", "--username", "u", "--canteen", "1") == 0
        assert out_json(capsys)["secret"] == "encrypted"

    def test_the_fallback_is_announced_not_silent(
        self, store_path, no_keyring, monkeypatch, capsys
    ):
        monkeypatch.setenv("STRAVA_CZ_PASSWORD", "secret")
        monkeypatch.setenv("STRAVA_CZ_PASSPHRASE", "unlock-me")
        run("profile", "add", "s", "--username", "u", "--canteen", "1")
        err = capsys.readouterr().err
        assert "no OS keyring" in err
        assert "encrypted" in err

    def test_the_profile_records_what_was_chosen_not_auto(
        self, store_path, no_keyring, monkeypatch, capsys
    ):
        monkeypatch.setenv("STRAVA_CZ_PASSWORD", "secret")
        monkeypatch.setenv("STRAVA_CZ_PASSPHRASE", "unlock-me")
        run("profile", "add", "s", "--username", "u", "--canteen", "1")
        assert json.loads(store_path.read_text())["profiles"]["s"]["secret"] == "encrypted"


class TestEncryptedProfileEndToEnd:
    @pytest.fixture
    def encrypted_cli(self, api, login_route, store_path: Path, no_keyring, monkeypatch):
        """A stored, encrypted profile plus a stubbed menu — the headless setup."""
        monkeypatch.setenv("STRAVA_CZ_PASSWORD", "test-password")
        monkeypatch.setenv("STRAVA_CZ_PASSPHRASE", "unlock-me")
        assert run("profile", "add", "test", "--username", "test.user", "--canteen", "1234") == 0
        monkeypatch.delenv("STRAVA_CZ_PASSWORD")  # only the passphrase remains
        api.post(f"{BASE_URL}/api/objednavky").mock(
            return_value=httpx.Response(200, json=load("menu_live"))
        )
        return api

    def test_the_stored_password_decrypts_and_logs_in(
        self, encrypted_cli, login_route, capsys, store_path
    ):
        capsys.readouterr()
        assert run("--json", "menu") == EXIT["ok"]
        assert out_json(capsys)["ok"] is True
        # The canteen password came out of the file, not the environment.
        assert json.loads(login_route.calls.last.request.content)["heslo"] == "test-password"
        assert "test-password" not in store_path.read_text()

    def test_a_wrong_passphrase_fails_cleanly(self, encrypted_cli, monkeypatch, capsys):
        capsys.readouterr()
        monkeypatch.setenv("STRAVA_CZ_PASSPHRASE", "not-it")
        assert run("--json", "balance") == EXIT["profile"]
        error = out_json(capsys)["error"]
        assert error["type"] == "ProfileError"
        assert "Wrong passphrase" in error["message"]

    def test_no_passphrase_at_all_says_which_variable_to_set(
        self, encrypted_cli, monkeypatch, capsys
    ):
        capsys.readouterr()
        monkeypatch.delenv("STRAVA_CZ_PASSPHRASE")
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        assert run("balance") == EXIT["profile"]
        assert "STRAVA_CZ_PASSPHRASE_TEST" in capsys.readouterr().err

    def test_the_password_environment_still_overrides_everything(
        self, encrypted_cli, login_route, monkeypatch, capsys
    ):
        capsys.readouterr()
        monkeypatch.delenv("STRAVA_CZ_PASSPHRASE")
        monkeypatch.setenv("STRAVA_CZ_PASSWORD_TEST", "test-password")
        assert run("balance") == EXIT["ok"], "no passphrase needed when the password is given"

    def test_profile_show_names_the_passphrase_variable(self, encrypted_cli, capsys):
        capsys.readouterr()
        assert run("--json", "profile", "show", "test") == EXIT["ok"]
        data = out_json(capsys)
        assert data["secret"] == "encrypted"
        assert data["passphrase_env"] == "STRAVA_CZ_PASSPHRASE_TEST"

    def test_profile_show_omits_the_passphrase_variable_for_other_sources(self, store_path, capsys):
        assert (
            run("profile", "add", "e", "--username", "u", "--canteen", "1", "--secret", "env")
            == EXIT["ok"]
        )
        capsys.readouterr()
        run("--json", "profile", "show", "e")
        assert out_json(capsys)["passphrase_env"] is None
