"""Exception hierarchy for the strava_cz package.

Everything raised by this library derives from :class:`StravaError`, so a single
``except StravaError`` catches all of it. Errors that came back from the Strava.cz
API carry the API's own numeric code in :attr:`StravaAPIError.code`.
"""

from typing import Any

__all__ = [
    "AuthenticationError",
    "DuplicateMealError",
    "InsufficientBalanceError",
    "KeyringUnavailableError",
    "MealNotFoundError",
    "MealNotOrderableError",
    "MenuNotFetchedError",
    "NotLoggedInError",
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


class MealNotFoundError(StravaError):
    """No meal with the given id exists in the fetched menu."""

    def __init__(self, meal_id: int) -> None:
        super().__init__(
            f"No meal with id {meal_id} in the fetched menu. "
            f"Ids change whenever the menu changes - re-run menu.fetch()."
        )
        self.meal_id = meal_id


class MealNotOrderableError(StravaError):
    """The canteen does not allow ordering or cancelling this meal.

    Attributes:
        meal_id: The meal that was refused.
        reason: Why the canteen refuses it, as a :class:`~strava_cz.models.Restriction`.
    """

    def __init__(self, meal_id: int, reason: Any, action: str = "order") -> None:
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

    Headless machines usually have no Secret Service running. The message names the
    ways out, because this is the one error a first-time user is most likely to hit.
    """

    def __init__(self, detail: str = "") -> None:
        super().__init__(
            "No usable OS keyring is available"
            + (f" ({detail})" if detail else "")
            + '. Install one with: pip install "strava-cz[cli]" - or store the '
            "profile with --secret env (reads $STRAVA_CZ_PASSWORD) or --secret prompt "
            "(asks every time)."
        )


#: Maps the API's ``number`` field onto a specific exception class.
ERROR_CODES: dict[int, type] = {
    20: AuthenticationError,
    35: InsufficientBalanceError,
}
