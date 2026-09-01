"""Stored canteen logins, so a script or a shell does not re-type them every run.

A profile keeps the two harmless halves of a login - the username and the canteen
number - in a JSON file, and says where the password comes from. The password itself
is never written to that file in the clear unless you explicitly ask for it with
:attr:`SecretSource.FILE`. By default it lives in the operating system's keyring, and
on a machine that has no keyring - a headless server, typically - it can instead be
encrypted into the profile file with a passphrase, which is what
:attr:`SecretSource.ENCRYPTED` does.

    from strava_cz import Profile, ProfileStore, StravaCZ

    store = ProfileStore()
    store.save(Profile("skola", "your.username", "3753"), password="...")

    with StravaCZ.from_profile("skola") as strava:
        strava.menu.fetch()
"""

from __future__ import annotations

import base64
import contextlib
import getpass
import hashlib
import json
import os
import re
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Any

from .exceptions import (
    EncryptionUnavailableError,
    KeyringUnavailableError,
    ProfileError,
    ProfileNotFoundError,
)

__all__ = [
    "DEFAULT_STORE_PATH",
    "KDF_PARAMS",
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

#: Environment variable holding the passphrase that unlocks an encrypted profile.
PASSPHRASE_ENV = "STRAVA_CZ_PASSPHRASE"

#: scrypt parameters for a newly encrypted password. Written into each record, so
#: raising the work factor later still leaves older profiles readable.
#:
#: ``maxmem`` has to be given explicitly: scrypt at n=2**15 wants about 33.5 MB and
#: OpenSSL's default ceiling is 32 MB, so without it the derivation simply fails.
KDF_PARAMS: dict[str, int] = {
    "n": 2**15,
    "r": 8,
    "p": 1,
    "dklen": 32,
    "maxmem": 128 * 1024 * 1024,
}

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

    Two of these remember the password. ``KEYRING`` hands it to the operating system,
    which is the best option when there is an operating system willing to take it.
    ``ENCRYPTED`` keeps it in the profile file under a passphrase, which is what a
    headless server needs, since it has no credential store to hand it to.

    ``ENV`` and ``PROMPT`` store nothing at all, and ``FILE`` stores it in the clear.
    """

    KEYRING = "keyring"
    ENCRYPTED = "encrypted"
    ENV = "env"
    PROMPT = "prompt"
    FILE = "file"

    @property
    def description(self) -> str:
        return {
            SecretSource.KEYRING: "the OS keyring",
            SecretSource.ENCRYPTED: "encrypted in the profile file",
            SecretSource.ENV: f"${PASSWORD_ENV}",
            SecretSource.PROMPT: "asked for every time",
            SecretSource.FILE: "PLAINTEXT in the profile file",
        }[self]

    @property
    def stores_password(self) -> bool:
        """Whether saving a profile with this source needs a password up front."""
        return self in (SecretSource.KEYRING, SecretSource.ENCRYPTED, SecretSource.FILE)

    @property
    def needs_passphrase(self) -> bool:
        """Whether using this source means asking for a passphrase as well."""
        return self is SecretSource.ENCRYPTED

    @classmethod
    def resolve(cls, choice: str) -> SecretSource:
        """Turn a ``--secret`` value into a source, expanding ``"auto"``.

        ``auto`` means "remember the password as safely as this machine allows": the
        OS keyring where one works, an encrypted file otherwise. It is a strategy, not
        a stored value - what gets written to the profile is whichever source was
        actually chosen, so nothing later has to guess.
        """
        if choice != "auto":
            return cls(choice)
        return cls.KEYRING if keyring_available() else cls.ENCRYPTED


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
        secret_data: The encrypted record - salt, nonce, ciphertext and the KDF
            parameters - when *secret* is :attr:`SecretSource.ENCRYPTED`. Also kept
            out of ``repr()``.
    """

    name: str
    username: str
    canteen_number: str
    language: str = "EN"
    secret: SecretSource = SecretSource.KEYRING
    password: str | None = None
    secret_data: dict[str, Any] | None = None

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
    def _suffix(self) -> str:
        return _NON_ALNUM.sub("_", self.name.upper()).strip("_")

    @property
    def env_var(self) -> str:
        """The profile-specific environment variable, e.g. ``STRAVA_CZ_PASSWORD_SKOLA``."""
        return f"{PASSWORD_ENV}_{self._suffix}"

    @property
    def passphrase_env_var(self) -> str:
        """Where an encrypted profile looks for its passphrase without asking."""
        return f"{PASSPHRASE_ENV}_{self._suffix}"

    def to_json(self) -> dict[str, Any]:
        """The record as written to the store.

        Holds a readable password only for ``FILE``, and an encrypted one - which is
        useless without the passphrase - only for ``ENCRYPTED``.
        """
        data: dict[str, Any] = {
            "username": self.username,
            "canteen_number": self.canteen_number,
            "language": self.language,
            "secret": self.secret.value,
        }
        if self.secret is SecretSource.FILE and self.password is not None:
            data["password"] = self.password
        if self.secret is SecretSource.ENCRYPTED and self.secret_data is not None:
            data["encrypted"] = self.secret_data
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
            secret_data=data.get("encrypted"),
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

    def save(
        self,
        profile: Profile,
        password: str | None = None,
        *,
        passphrase: str | None = None,
    ) -> Profile:
        """Store *profile*, putting *password* wherever its ``secret`` says.

        Args:
            profile: The profile to write. Replaces any profile of the same name.
            password: Required for :attr:`SecretSource.KEYRING`,
                :attr:`SecretSource.ENCRYPTED` and :attr:`SecretSource.FILE`, ignored
                for the others.
            passphrase: Required for :attr:`SecretSource.ENCRYPTED`. Taken from
                ``$STRAVA_CZ_PASSPHRASE`` or a prompt when not given.

        Returns:
            The profile as stored.

        Raises:
            ProfileError: If a password or passphrase is needed but not available.
            KeyringUnavailableError: If the keyring is wanted but unusable.
            EncryptionUnavailableError: If encryption is wanted but unavailable.
        """
        if profile.secret.stores_password and not password:
            raise ProfileError(
                f"Profile {profile.name!r} keeps its password in "
                f"{profile.secret.description} and needs one to be given"
            )

        if profile.secret is SecretSource.KEYRING:
            set_keyring_password(profile.name, password or "")
            profile = replace(profile, password=None, secret_data=None)
        elif profile.secret is SecretSource.ENCRYPTED:
            if passphrase is None:
                passphrase = self.resolve_passphrase(profile, confirm=True)
            profile = replace(
                profile,
                password=None,
                secret_data=encrypt_password(password or "", passphrase),
            )
        elif profile.secret is SecretSource.FILE:
            profile = replace(profile, password=password, secret_data=None)
        else:
            profile = replace(profile, password=None, secret_data=None)

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

        if profile.secret is SecretSource.ENCRYPTED:
            if not profile.secret_data:
                raise ProfileError(
                    f"Profile {profile.name!r} is marked encrypted but holds no "
                    f"encrypted password. Re-add it, or set ${profile.env_var}."
                )
            return decrypt_password(
                profile.secret_data,
                self.resolve_passphrase(profile, allow_prompt=allow_prompt),
            )

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

    def resolve_passphrase(
        self,
        profile: Profile,
        *,
        allow_prompt: bool = True,
        confirm: bool = False,
    ) -> str:
        """The passphrase that unlocks *profile*'s encrypted password.

        Looked up the same way the password is: ``$STRAVA_CZ_PASSPHRASE_<NAME>``, then
        ``$STRAVA_CZ_PASSPHRASE``, then the terminal. A service that cannot answer a
        prompt sets one of those variables.

        Args:
            profile: Whose passphrase to find.
            allow_prompt: Set False where nothing can answer, so this fails instead of
                hanging.
            confirm: Ask twice and compare, for when a typo would lock the profile.

        Raises:
            ProfileError: If no passphrase can be found.
        """
        for var in (profile.passphrase_env_var, PASSPHRASE_ENV):
            value = os.environ.get(var)
            if value:
                return value

        if not allow_prompt or not sys.stdin.isatty():
            raise ProfileError(
                f"Profile {profile.name!r} is encrypted and needs its passphrase, but "
                f"there is no terminal to ask at. Set ${profile.passphrase_env_var} "
                f"or ${PASSPHRASE_ENV}."
            )

        passphrase = prompt_password(f"Passphrase for profile {profile.name}: ")
        if confirm and passphrase != prompt_password("Passphrase again: "):
            raise ProfileError("The two passphrases do not match; nothing was saved")
        return passphrase


# --------------------------------------------------------------------- encryption
#
# The password is encrypted with AES-256-GCM under a key derived from a passphrase by
# scrypt. Both come from vetted implementations - scrypt from hashlib, AES-GCM from
# `cryptography` - and nothing here invents a construction of its own.
#
# What this buys: the profile file is safe to back up, sync or copy, because the
# ciphertext is useless without the passphrase, and GCM's tag means a tampered file is
# rejected rather than silently decrypting to nonsense. What it does not buy: any
# protection from someone who can already read your environment or this process's
# memory while it runs. Said plainly in the docs too.


def _crypto() -> Any:
    """Import ``cryptography``'s AES-GCM lazily, as ``_keyring()`` does for keyring.

    Raises:
        EncryptionUnavailableError: If the package is not installed.
    """
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise EncryptionUnavailableError() from exc
    return AESGCM


def encryption_available() -> bool:
    """Whether passwords can be encrypted here, without raising."""
    try:
        _crypto()
    except EncryptionUnavailableError:
        return False
    return True


def _derive_key(passphrase: str, salt: bytes, params: Mapping[str, Any]) -> bytes:
    """Stretch *passphrase* into a 32-byte key with scrypt.

    The parameters come from the stored record rather than from :data:`KDF_PARAMS`, so
    a profile written by an older version still opens after the work factor is raised.
    """
    try:
        return hashlib.scrypt(
            passphrase.encode("utf-8"),
            salt=salt,
            n=int(params.get("n", KDF_PARAMS["n"])),
            r=int(params.get("r", KDF_PARAMS["r"])),
            p=int(params.get("p", KDF_PARAMS["p"])),
            dklen=int(params.get("dklen", KDF_PARAMS["dklen"])),
            maxmem=int(params.get("maxmem", KDF_PARAMS["maxmem"])),
        )
    except (ValueError, OverflowError, TypeError) as exc:
        raise ProfileError(f"Cannot derive a key from the stored parameters: {exc}") from exc


def encrypt_password(password: str, passphrase: str) -> dict[str, Any]:
    """Encrypt *password* under *passphrase*, returning the record to store.

    A fresh salt and nonce are drawn every time, so saving the same password twice
    produces two records that look nothing alike.
    """
    if not passphrase:
        raise ProfileError("An encrypted profile needs a passphrase")

    aesgcm = _crypto()
    params = dict(KDF_PARAMS)
    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = _derive_key(passphrase, salt, params)
    ciphertext = aesgcm(key).encrypt(nonce, password.encode("utf-8"), None)

    return {
        "kdf": {"name": "scrypt", "salt": _b64(salt), **params},
        "cipher": "aes-256-gcm",
        "nonce": _b64(nonce),
        "ciphertext": _b64(ciphertext),
    }


def decrypt_password(record: Mapping[str, Any], passphrase: str) -> str:
    """Recover the password from a record made by :func:`encrypt_password`.

    Raises:
        ProfileError: If the passphrase is wrong, the record is damaged, or it is not
            shaped like something this version wrote.
    """
    from cryptography.exceptions import InvalidTag

    aesgcm = _crypto()
    kdf = record.get("kdf")
    if not isinstance(kdf, Mapping):
        raise ProfileError("The stored password is missing its key-derivation details")
    if str(record.get("cipher", "aes-256-gcm")) != "aes-256-gcm":
        raise ProfileError(f"Unsupported cipher {record.get('cipher')!r} in the profile store")

    salt = _unb64(kdf.get("salt"), "salt")
    nonce = _unb64(record.get("nonce"), "nonce")
    ciphertext = _unb64(record.get("ciphertext"), "ciphertext")

    key = _derive_key(passphrase, salt, kdf)
    try:
        plaintext: bytes = aesgcm(key).decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")
    except InvalidTag:
        raise ProfileError(
            "Wrong passphrase, or the stored password has been damaged. Nothing was "
            "changed; re-add the profile if you no longer have the passphrase."
        ) from None
    except (UnicodeDecodeError, ValueError) as exc:
        raise ProfileError(f"The stored password could not be read back: {exc}") from exc


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _unb64(value: Any, field: str) -> bytes:
    """Decode one base64 field of a stored record, blaming it by name when it is bad."""
    if not isinstance(value, str) or not value:
        raise ProfileError(f"The stored password has no {field}")
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise ProfileError(f"The stored password has an unreadable {field}") from exc


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
