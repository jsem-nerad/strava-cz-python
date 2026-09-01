"""Stored canteen logins, so a script or a shell does not re-type them every run.

A profile keeps the two harmless halves of a login - the username and the canteen
number - in a JSON file, and says where the password comes from. The password itself
is never written to that file unless you explicitly ask for it with
:attr:`SecretSource.FILE`; by default it lives in the operating system's keyring.

    from strava_cz import Profile, ProfileStore, StravaCZ

    store = ProfileStore()
    store.save(Profile("skola", "your.username", "3753"), password="...")

    with StravaCZ.from_profile("skola") as strava:
        strava.menu.fetch()
"""

from __future__ import annotations

import contextlib
import getpass
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Any

from .exceptions import KeyringUnavailableError, ProfileError, ProfileNotFoundError

__all__ = [
    "DEFAULT_STORE_PATH",
    "KEYRING_SERVICE",
    "Profile",
    "ProfileStore",
    "SecretSource",
    "default_store_path",
]

#: Service name the passwords are filed under in the OS keyring.
KEYRING_SERVICE = "strava-cz"

#: Environment variable consulted for every profile.
PASSWORD_ENV = "STRAVA_CZ_PASSWORD"

_NON_ALNUM = re.compile(r"[^A-Z0-9]+")
_VALID_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def default_store_path() -> Path:
    """Where profiles live: ``$XDG_CONFIG_HOME/strava-cz/profiles.json``.

    Falls back to ``~/.config`` when ``XDG_CONFIG_HOME`` is unset, as the XDG spec
    says to. Read at call time rather than at import, so tests and ``--profile-store``
    can point it somewhere else.
    """
    base = os.environ.get("XDG_CONFIG_HOME") or ""
    root = Path(base) if base else Path.home() / ".config"
    return root / "strava-cz" / "profiles.json"


#: Kept for ``from strava_cz.profiles import DEFAULT_STORE_PATH``; prefer the function,
#: which re-reads the environment.
DEFAULT_STORE_PATH = "$XDG_CONFIG_HOME/strava-cz/profiles.json"


class SecretSource(Enum):
    """Where a profile's password comes from.

    ``KEYRING`` is the default and the only one that both remembers the password and
    keeps it out of any file this library writes.
    """

    KEYRING = "keyring"
    ENV = "env"
    PROMPT = "prompt"
    FILE = "file"

    @property
    def description(self) -> str:
        return {
            SecretSource.KEYRING: "the OS keyring",
            SecretSource.ENV: f"${PASSWORD_ENV}",
            SecretSource.PROMPT: "asked for every time",
            SecretSource.FILE: "PLAINTEXT in the profile file",
        }[self]

    @property
    def stores_password(self) -> bool:
        """Whether saving a profile with this source needs a password up front."""
        return self in (SecretSource.KEYRING, SecretSource.FILE)


@dataclass(frozen=True, slots=True)
class Profile:
    """One stored canteen login.

    Attributes:
        name: What you call it on the command line, e.g. ``"skola"``.
        username: Canteen login name.
        canteen_number: The canteen's number, as shown on strava.cz.
        language: ``lang`` sent with every request for this profile.
        secret: Where the password comes from. See :class:`SecretSource`.
        password: Only ever set when *secret* is :attr:`SecretSource.FILE`. Excluded
            from ``repr()`` so it cannot leak into a traceback or a log line.
    """

    name: str
    username: str
    canteen_number: str
    language: str = "EN"
    secret: SecretSource = SecretSource.KEYRING
    password: str | None = None

    def __post_init__(self) -> None:
        if not _VALID_NAME.match(self.name or ""):
            raise ProfileError(
                f"Invalid profile name {self.name!r}: use letters, digits, dot, dash "
                f"or underscore, starting with a letter or digit"
            )
        if not self.username:
            raise ProfileError("A profile needs a username")
        if not self.canteen_number:
            raise ProfileError("A profile needs a canteen number")

    def __repr__(self) -> str:
        return (
            f"Profile(name={self.name!r}, username={self.username!r}, "
            f"canteen_number={self.canteen_number!r}, secret={self.secret.value!r})"
        )

    @property
    def env_var(self) -> str:
        """The profile-specific environment variable, e.g. ``STRAVA_CZ_PASSWORD_SKOLA``."""
        return f"{PASSWORD_ENV}_{_NON_ALNUM.sub('_', self.name.upper()).strip('_')}"

    def to_json(self) -> dict[str, Any]:
        """The record as written to the store. Holds a password only for ``FILE``."""
        data: dict[str, Any] = {
            "username": self.username,
            "canteen_number": self.canteen_number,
            "language": self.language,
            "secret": self.secret.value,
        }
        if self.secret is SecretSource.FILE and self.password is not None:
            data["password"] = self.password
        return data

    @classmethod
    def from_json(cls, name: str, data: Any) -> Profile:
        """Rebuild a profile from a stored record, tolerating an unknown ``secret``."""
        if not isinstance(data, dict):
            raise ProfileError(f"Profile {name!r} is not an object")
        try:
            secret = SecretSource(str(data.get("secret", SecretSource.KEYRING.value)))
        except ValueError:
            raise ProfileError(
                f"Profile {name!r} has an unknown secret source {data.get('secret')!r}"
            ) from None
        return cls(
            name=name,
            username=str(data.get("username") or ""),
            canteen_number=str(data.get("canteen_number") or ""),
            language=str(data.get("language") or "EN"),
            secret=secret,
            password=data.get("password"),
        )


class ProfileStore:
    """Reads and writes the profile file, and resolves passwords.

    The file is created ``0600`` inside a ``0700`` directory and replaced atomically,
    so a crash mid-write cannot leave a half-written store behind.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else default_store_path()

    # ------------------------------------------------------------------ file access

    def _read(self) -> dict[str, Any]:
        """The whole store, or an empty one when the file does not exist."""
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {"default": None, "profiles": {}}
        except OSError as exc:
            raise ProfileError(f"Cannot read {self.path}: {exc}") from exc

        try:
            data = json.loads(text or "{}")
        except json.JSONDecodeError as exc:
            raise ProfileError(f"{self.path} is not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise ProfileError(f"{self.path} should hold an object, not a list")

        profiles = data.get("profiles")
        return {
            "default": data.get("default"),
            "profiles": profiles if isinstance(profiles, dict) else {},
        }

    def _write(self, data: dict[str, Any]) -> None:
        """Replace the store atomically, never widening its permissions."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            # mkdir's mode is ignored when the directory already exists.
            self.path.parent.chmod(0o700)
            fd, tmp_name = tempfile.mkstemp(dir=self.path.parent, prefix=".profiles-")
            tmp = Path(tmp_name)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(data, handle, indent=2, ensure_ascii=False, sort_keys=True)
                    handle.write("\n")
                tmp.chmod(0o600)
                os.replace(tmp, self.path)
            except BaseException:
                tmp.unlink(missing_ok=True)
                raise
        except OSError as exc:
            raise ProfileError(f"Cannot write {self.path}: {exc}") from exc

    @property
    def exists(self) -> bool:
        """Whether a store file is present."""
        return self.path.is_file()

    # -------------------------------------------------------------------- profiles

    def list(self) -> list[Profile]:
        """Every stored profile, sorted by name."""
        data = self._read()
        return [Profile.from_json(name, rec) for name, rec in sorted(data["profiles"].items())]

    def names(self) -> tuple[str, ...]:
        """Just the stored names, for error messages."""
        return tuple(sorted(self._read()["profiles"]))

    @property
    def default_name(self) -> str | None:
        """Name of the default profile, if one is set and still exists."""
        data = self._read()
        name = data.get("default")
        if isinstance(name, str) and name in data["profiles"]:
            return name
        # A single profile is unambiguously the default, whether or not it was marked.
        if len(data["profiles"]) == 1:
            return str(next(iter(data["profiles"])))
        return None

    def get(self, name: str | None = None) -> Profile:
        """One profile by name, or the default when *name* is ``None``.

        Raises:
            ProfileNotFoundError: If it is not stored, or no default is set.
        """
        data = self._read()
        wanted = name if name is not None else self.default_name
        if wanted is None or wanted not in data["profiles"]:
            raise ProfileNotFoundError(name, tuple(sorted(data["profiles"])))
        return Profile.from_json(wanted, data["profiles"][wanted])

    def save(self, profile: Profile, password: str | None = None) -> Profile:
        """Store *profile*, putting *password* wherever its ``secret`` says.

        Args:
            profile: The profile to write. Replaces any profile of the same name.
            password: Required for :attr:`SecretSource.KEYRING` and
                :attr:`SecretSource.FILE`, ignored for the others.

        Returns:
            The profile as stored.

        Raises:
            ProfileError: If a password is needed but not given.
            KeyringUnavailableError: If the keyring is wanted but unusable.
        """
        if profile.secret.stores_password and not password:
            raise ProfileError(
                f"Profile {profile.name!r} keeps its password in "
                f"{profile.secret.description} and needs one to be given"
            )

        if profile.secret is SecretSource.KEYRING:
            set_keyring_password(profile.name, password or "")
            profile = replace(profile, password=None)
        elif profile.secret is SecretSource.FILE:
            profile = replace(profile, password=password)
        else:
            profile = replace(profile, password=None)

        data = self._read()
        data["profiles"][profile.name] = profile.to_json()
        if data.get("default") is None:
            data["default"] = profile.name
        self._write(data)
        return profile

    def delete(self, name: str) -> None:
        """Forget a profile and its keyring entry.

        Raises:
            ProfileNotFoundError: If no such profile is stored.
        """
        data = self._read()
        if name not in data["profiles"]:
            raise ProfileNotFoundError(name, tuple(sorted(data["profiles"])))

        stored = Profile.from_json(name, data["profiles"].pop(name))
        if data.get("default") == name:
            remaining = sorted(data["profiles"])
            data["default"] = remaining[0] if len(remaining) == 1 else None
        self._write(data)

        if stored.secret is SecretSource.KEYRING:
            # Best effort: the profile is gone either way, and a stale keyring entry
            # is not worth failing the command over.
            with contextlib.suppress(ProfileError):
                delete_keyring_password(name)

    def set_default(self, name: str) -> None:
        """Make *name* the profile used when ``--profile`` is not given."""
        data = self._read()
        if name not in data["profiles"]:
            raise ProfileNotFoundError(name, tuple(sorted(data["profiles"])))
        data["default"] = name
        self._write(data)

    # -------------------------------------------------------------------- passwords

    def resolve_password(self, profile: Profile, *, allow_prompt: bool = True) -> str:
        """The password for *profile*, from wherever it lives.

        The environment wins over everything, so a cron job can override a stored
        profile without rewriting it: ``$STRAVA_CZ_PASSWORD_<NAME>`` first, then
        ``$STRAVA_CZ_PASSWORD``.

        Args:
            profile: Whose password to find.
            allow_prompt: Set False in non-interactive contexts to turn a would-be
                prompt into an error instead of a hang.

        Raises:
            ProfileError: If no password can be found.
            KeyringUnavailableError: If the keyring is needed but unusable.
        """
        for var in (profile.env_var, PASSWORD_ENV):
            value = os.environ.get(var)
            if value:
                return value

        if profile.secret is SecretSource.KEYRING:
            password = get_keyring_password(profile.name)
            if not password:
                raise ProfileError(
                    f"No password for {profile.name!r} in the OS keyring. Re-add the "
                    f"profile, or set ${profile.env_var}."
                )
            return password

        if profile.secret is SecretSource.FILE:
            if not profile.password:
                raise ProfileError(f"Profile {profile.name!r} has no stored password")
            return profile.password

        if profile.secret is SecretSource.ENV:
            raise ProfileError(
                f"Profile {profile.name!r} reads its password from ${profile.env_var} "
                f"or ${PASSWORD_ENV}, and neither is set"
            )

        if not allow_prompt or not sys.stdin.isatty():
            raise ProfileError(
                f"Profile {profile.name!r} asks for its password interactively, but "
                f"there is no terminal. Set ${profile.env_var} instead."
            )
        return prompt_password(f"Password for {profile.name} ({profile.username}): ")


# ------------------------------------------------------------------------ keyring


def _keyring() -> Any:
    """Import ``keyring`` lazily and make sure it has a backend that works.

    Deferred because the library must stay usable - and importable - without it.

    Raises:
        KeyringUnavailableError: If the module is missing or has no real backend.
    """
    try:
        import keyring
        import keyring.backends.fail
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise KeyringUnavailableError("the keyring package is not installed") from exc

    backend = keyring.get_keyring()
    if isinstance(backend, keyring.backends.fail.Keyring):
        raise KeyringUnavailableError("no backend on this machine")
    return keyring


def keyring_available() -> bool:
    """Whether a usable keyring backend is present, without raising."""
    try:
        _keyring()
    except KeyringUnavailableError:
        return False
    return True


def get_keyring_password(name: str) -> str | None:
    """Read a profile's password from the OS keyring."""
    keyring = _keyring()
    try:
        password = keyring.get_password(KEYRING_SERVICE, name)
    except Exception as exc:  # keyring raises backend-specific errors
        raise KeyringUnavailableError(str(exc)) from exc
    return str(password) if password is not None else None


def set_keyring_password(name: str, password: str) -> None:
    """Write a profile's password to the OS keyring."""
    keyring = _keyring()
    try:
        keyring.set_password(KEYRING_SERVICE, name, password)
    except Exception as exc:
        raise KeyringUnavailableError(str(exc)) from exc


def delete_keyring_password(name: str) -> None:
    """Remove a profile's password from the OS keyring, if it is there."""
    keyring = _keyring()
    try:
        keyring.delete_password(KEYRING_SERVICE, name)
    except Exception as exc:
        # Deleting something that is not there is not worth an error.
        if "not found" in str(exc).lower() or type(exc).__name__ == "PasswordDeleteError":
            return
        raise KeyringUnavailableError(str(exc)) from exc


def prompt_password(prompt: str = "Password: ") -> str:
    """Ask for a password on the terminal without echoing it."""
    try:
        password = getpass.getpass(prompt)
    except (EOFError, KeyboardInterrupt) as exc:
        raise ProfileError("No password given") from exc
    if not password:
        raise ProfileError("No password given")
    return password
