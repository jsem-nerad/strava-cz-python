"""Exception hierarchy for the strava_cz package.

Everything raised by this library derives from :class:`StravaError`, so a single
``except StravaError`` catches all of it. Errors that came back from the Strava.cz
API carry the API's own numeric code in :attr:`StravaAPIError.code`.
"""

from typing import Any

__all__ = [
    "AuthenticationError",
    "DuplicateMealError",
    "EncryptionUnavailableError",
    "InsufficientBalanceError",
    "KeyringUnavailableError",
    "MealNotFoundError",
    "MealNotOrderableError",
    "MenuNotFetchedError",
    "NotLoggedInError",
    "OrderNotConfirmedError",
    "ProfileError",
    "ProfileNotFoundError",
    "StravaAPIError",
    "StravaError",
]


class StravaError(Exception):
    """Base class for every error raised by this library."""


class StravaAPIError(StravaError):
    """The Strava.cz API refused a request or answered with something unusable.

    Attributes:
        message: Human readable message, from the API when it provided one.
        code: The API's own error number (the ``number`` field), if present.
        status_code: HTTP status of the response, if there was one.
        payload: The decoded response body, for debugging.
    """

    def __init__(
        self,
        message: str,
        *,
        code: int | None = None,
        status_code: int | None = None,
        payload: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.payload = payload

    def __str__(self) -> str:
        parts = [self.message]
        if self.code is not None:
            parts.append(f"(API code {self.code})")
        elif self.status_code is not None:
            parts.append(f"(HTTP {self.status_code})")
        return " ".join(parts)


class AuthenticationError(StravaAPIError):
    """Login was rejected, or the session is no longer valid."""


class NotLoggedInError(AuthenticationError):
    """An operation needing a session was attempted before logging in."""

    def __init__(self, message: str = "Not logged in - call login() first") -> None:
        super().__init__(message)


class InsufficientBalanceError(StravaAPIError):
    """The account does not hold enough money to order this meal."""


class OrderNotConfirmedError(StravaAPIError):
    """A change may be on the account, or was accepted and isn't, and which one matters.

    Raised when a save's answer was lost and the menu couldn't be read back, when the save
    went through and the menu couldn't be read back, or when the canteen accepted a change
    the menu doesn't show. Don't assume the order failed: look at the menu first.

    Attributes:
        changed: Meals confirmed as changed, named the way the caller named them.
        unconfirmed: Meals whose state isn't known, or isn't what was asked for.
    """

    def __init__(
        self,
        message: str,
        *,
        changed: tuple[int | str, ...] = (),
        unconfirmed: tuple[int | str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.changed = changed
        self.unconfirmed = unconfirmed


class MealNotFoundError(StravaError):
    """No meal with the given id or key exists in the fetched menu."""

    def __init__(self, meal_id: int | str) -> None:
        hint = (
            ""
            if isinstance(meal_id, str)
            else " Numeric ids only last as long as the login that fetched them."
        )
        super().__init__(f"No meal {meal_id} in the fetched menu.{hint}")
        self.meal_id = meal_id


class MealNotOrderableError(StravaError):
    """The canteen does not allow ordering or cancelling this meal.

    Attributes:
        meal_id: The meal that was refused.
        reason: Why the canteen refuses it, as a :class:`~strava_cz.models.Restriction`.
    """

    def __init__(self, meal_id: int | str, reason: Any, action: str = "order") -> None:
        super().__init__(
            f"Cannot {action} meal {meal_id}: {getattr(reason, 'description', reason)}"
        )
        self.meal_id = meal_id
        self.reason = reason
        self.action = action


class DuplicateMealError(StravaError):
    """Several meals of the same kind on the same day were ordered at once."""


class MenuNotFetchedError(StravaError):
    """The menu was used before it was fetched."""

    def __init__(self, message: str = "Menu has not been fetched yet - call menu.fetch()") -> None:
        super().__init__(message)


class ProfileError(StravaError):
    """Something is wrong with a stored profile or the profile store."""


class ProfileNotFoundError(ProfileError):
    """No profile with this name is stored."""

    def __init__(self, name: str | None, known: tuple[str, ...] = ()) -> None:
        if name is None:
            message = "No default profile is set - run 'strava-cz profile add' first"
        else:
            message = f"No profile named {name!r}"
            if known:
                message += f". Stored profiles: {', '.join(known)}"
        super().__init__(message)
        self.name = name


class KeyringUnavailableError(ProfileError):
    """No usable OS keyring, so a password can be neither stored nor read.

    Headless machines usually have no Secret Service running. The message leads with
    the encrypted profile file, because that is the only alternative that still
    *remembers* the password, and this is the error a first-time user on a server is
    most likely to hit.
    """

    def __init__(self, detail: str = "") -> None:
        super().__init__(
            "No usable OS keyring is available"
            + (f" ({detail})" if detail else "")
            + '. If the keyring package is missing, pip install "strava-cz[cli]"; if '
            "this machine simply has no credential store, use --secret encrypted to "
            "keep the password in an encrypted profile file instead, which needs no "
            "desktop session - or --secret env (reads $STRAVA_CZ_PASSWORD) or "
            "--secret prompt (asks every time) to store no password at all."
        )


class EncryptionUnavailableError(ProfileError):
    """The profile store cannot encrypt, because ``cryptography`` is not installed.

    Kept separate from :class:`KeyringUnavailableError` because the fix is different:
    one is a missing library, the other a machine with no credential store running.
    """

    def __init__(self, detail: str = "") -> None:
        super().__init__(
            "Cannot encrypt the stored password"
            + (f" ({detail})" if detail else "")
            + ': the "cryptography" package is not installed. Install it with: '
            'pip install "strava-cz[cli]" - or store the profile with --secret env '
            "(reads $STRAVA_CZ_PASSWORD) or --secret prompt (asks every time)."
        )


#: Maps the API's ``number`` field onto a specific exception class.
ERROR_CODES: dict[int, type] = {
    15: AuthenticationError,  # the session is over, seen live for a logged-out or unknown sid
    20: AuthenticationError,
    35: InsufficientBalanceError,
}
