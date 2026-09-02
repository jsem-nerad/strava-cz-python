"""The Strava.cz API client."""

from __future__ import annotations

import contextlib
import json
from collections.abc import Mapping
from types import TracebackType
from typing import Any

import httpx

from .exceptions import (
    ERROR_CODES,
    AuthenticationError,
    NotLoggedInError,
    StravaAPIError,
)
from .menu import Menu
from .models import User
from .profiles import ProfileStore

__all__ = ["StravaCZ"]

#: Where the web app lives.
DEFAULT_BASE_URL = "https://app.strava.cz"

#: Generous enough for a slow school server, short enough not to hang a script.
DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=10.0)


class StravaCZ:
    """A logged-in session with the Strava.cz canteen system.

    Passing credentials logs you in straight away::

        strava = StravaCZ("your.username", "YourPassword", "3753")
        strava.menu.fetch()
        strava.menu.print()

    It is also a context manager, which closes the underlying connection pool::

        with StravaCZ("your.username", "YourPassword", "3753") as strava:
            strava.menu.fetch()

    Attributes:
        user: The logged-in account. See :class:`~strava_cz.models.User`.
        menu: The canteen menu. See :class:`~strava_cz.Menu`.
    """

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        canteen_number: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: httpx.Timeout | float = DEFAULT_TIMEOUT,
        retries: int = 2,
        language: str = "EN",
        client: httpx.Client | None = None,
    ) -> None:
        """Create a client, logging in when credentials are given.

        Args:
            username: Canteen login name. Logs in immediately when *password* and
                *canteen_number* are given too.
            password: Account password. It is used for the login request and then
                discarded; it is never stored on the client.
            canteen_number: The canteen's number, as shown on strava.cz.
            base_url: Override the API host, mostly useful in tests.
            timeout: Request timeout. Defaults to 15s, 10s to connect.
            retries: How often to retry a connection that never got established.
                Requests that reached the server are never retried.
            language: ``lang`` value sent with every request.
            client: Supply your own ``httpx.Client`` (proxies, custom transport...).
                You are then responsible for closing it.

        Raises:
            TypeError: If only some of the three credentials are given.
            AuthenticationError: If the credentials are rejected.
        """
        self.base_url = base_url.rstrip("/")
        self.language = language
        self.user = User()
        self.menu = Menu(self)

        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers=self._default_headers(),
            transport=httpx.HTTPTransport(retries=retries),
            follow_redirects=True,
        )
        self._session_primed = False

        given = [bool(username), bool(password), bool(canteen_number)]
        if all(given):
            self.login(username, password, canteen_number)  # type: ignore[arg-type]
        elif any(given):
            raise TypeError(
                "username, password and canteen_number must be given together "
                "(or all omitted, to log in later with login())"
            )

    @classmethod
    def from_profile(
        cls,
        name: str | None = None,
        *,
        store: ProfileStore | None = None,
        password: str | None = None,
        allow_prompt: bool = True,
        **kwargs: Any,
    ) -> StravaCZ:
        """Log in using a stored profile, so credentials stay out of your script.

            with StravaCZ.from_profile("skola") as strava:
                strava.menu.fetch()

        Args:
            name: Which profile to use. ``None`` takes the default one.
            store: A :class:`~strava_cz.profiles.ProfileStore` to read from; the
                default reads ``$XDG_CONFIG_HOME/strava-cz/profiles.json``.
            password: Skip the profile's own password lookup and use this instead.
            allow_prompt: Set False when nothing can answer a terminal prompt, so a
                profile that asks for its password fails instead of hanging.
            **kwargs: Passed straight to :class:`StravaCZ`, e.g. ``timeout=30``.
                ``language`` defaults to the profile's.

        Returns:
            A logged-in client.

        Raises:
            ProfileNotFoundError: If the profile is not stored.
            ProfileError: If its password cannot be found.
            AuthenticationError: If the canteen rejects the login.
        """
        store = store if store is not None else ProfileStore()
        profile = store.get(name)
        kwargs.setdefault("language", profile.language)
        if password is None:
            password = store.resolve_password(profile, allow_prompt=allow_prompt)
        return cls(profile.username, password, profile.canteen_number, **kwargs)

    def _default_headers(self) -> dict[str, str]:
        """Headers making the request look like the web app's own.

        ``Accept-Encoding`` is deliberately left to httpx, which advertises only the
        codecs it can actually decode.
        """
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9,cs;q=0.8",
            "Content-Type": "text/plain;charset=UTF-8",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/en/prihlasit-se?jidelna",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        }

    # ------------------------------------------------------------------ session

    def _prime_session(self) -> None:
        """Fetch the login page once, so the API sees a browser-like session.

        Deferred until the first API call: constructing a client should not do I/O.
        """
        if self._session_primed:
            return
        self._session_primed = True
        # Only a warm-up; if it fails, the real request will report the problem.
        with contextlib.suppress(httpx.HTTPError):
            self._client.get("/en/prihlasit-se?jidelna")

    def _request(
        self,
        endpoint: str,
        payload: Mapping[str, Any] | None = None,
        *,
        authenticated: bool = False,
    ) -> Any:
        """POST to an API endpoint and return the decoded body.

        Args:
            endpoint: Path under ``/api``, e.g. ``"objednavky"``.
            payload: JSON body to send.
            authenticated: Require a live session before sending.

        Returns:
            The decoded JSON body. Usually a dict, but ``logOut`` answers ``True``.

        Raises:
            NotLoggedInError: If *authenticated* and no one is logged in.
            AuthenticationError: If the API rejects the credentials or session.
            InsufficientBalanceError: If the account cannot cover an order.
            StravaAPIError: For any other API or transport failure.
        """
        if authenticated and not self.user.is_logged_in:
            raise NotLoggedInError()

        self._prime_session()
        try:
            response = self._client.post(f"/api/{endpoint}", json=payload)
        except httpx.TimeoutException as exc:
            raise StravaAPIError(f"Request to {endpoint!r} timed out") from exc
        except httpx.HTTPError as exc:
            raise StravaAPIError(f"Request to {endpoint!r} failed: {exc}") from exc

        return self._decode(endpoint, response)

    @staticmethod
    def _decode(endpoint: str, response: httpx.Response) -> Any:
        """Decode a response, turning the API's error envelope into an exception.

        Strava.cz signals failure with a non-standard HTTP 555 and a body shaped
        ``{"state": "error", "number": 20, "message": "..."}``, so the status alone
        is not enough to tell success from failure.
        """
        try:
            data = response.json()
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            snippet = response.text[:200].strip().replace("\n", " ")
            raise StravaAPIError(
                f"{endpoint!r} returned {response.status_code} with a non-JSON body: {snippet!r}",
                status_code=response.status_code,
            ) from exc

        if isinstance(data, Mapping) and str(data.get("state", "")).lower() == "error":
            code = data.get("number")
            code = code if isinstance(code, int) else None
            message = str(data.get("message") or f"{endpoint} failed")
            error_class = ERROR_CODES.get(code, StravaAPIError) if code is not None else None
            raise (error_class or StravaAPIError)(
                message, code=code, status_code=response.status_code, payload=data
            )

        if response.status_code >= 400:
            message = ""
            if isinstance(data, Mapping):
                message = str(data.get("message") or "")
            raise StravaAPIError(
                message or f"{endpoint!r} failed with HTTP {response.status_code}",
                status_code=response.status_code,
                payload=data,
            )

        return data

    # -------------------------------------------------------------------- login

    def login(self, username: str, password: str, canteen_number: str) -> User:
        """Log in to a canteen account.

        Args:
            username: Canteen login name.
            password: Account password. Discarded once the request is sent.
            canteen_number: The canteen's number, as shown on strava.cz.

        Returns:
            The populated :class:`~strava_cz.models.User`.

        Raises:
            ValueError: If any argument is empty.
            AuthenticationError: If already logged in, or if the login is rejected.
        """
        if self.user.is_logged_in:
            raise AuthenticationError("Already logged in - call logout() first")
        missing = [
            name
            for name, value in (
                ("username", username),
                ("password", password),
                ("canteen_number", canteen_number),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"Missing required login argument(s): {', '.join(missing)}")

        data = self._request(
            "login",
            {
                "cislo": canteen_number,
                "jmeno": username,
                "heslo": password,
                "zustatPrihlasen": True,
                "environment": "W",
                "lang": self.language,
            },
        )

        if not isinstance(data, Mapping) or not data.get("sid"):
            raise AuthenticationError(
                "Login succeeded but the API returned no session id", payload=data
            )

        account = data.get("uzivatel") or {}
        if not isinstance(account, Mapping):
            account = {}

        self.user.username = username
        self.user.canteen_number = canteen_number
        self.user.sid = str(data["sid"])
        self.user.s5url = str(data.get("s5url") or "")
        self.user.full_name = str(account.get("jmeno") or username)
        self.user.email = str(account.get("email") or "") or None
        self.user.id = str(account.get("id") or "") or None
        self.user.currency = str(account.get("mena") or "Kč")
        self.user.canteen_name = str(account.get("nazevJidelny") or "") or None
        self.user.balance = _to_float(account.get("konto"))
        self.user.is_logged_in = True
        return self.user

    def logout(self) -> bool:
        """Log out and clear the session.

        Returns:
            True. Calling it when already logged out is a no-op.

        Raises:
            StravaAPIError: If the API refuses the request.
        """
        if not self.user.is_logged_in:
            return True

        self._request(
            "logOut",
            {
                "sid": self.user.sid,
                "cislo": self.user.canteen_number,
                "url": self.user.s5url,
                "lang": self.language,
                "ignoreCert": "false",
            },
            authenticated=True,
        )
        # Reset in place, so references held elsewhere do not go stale.
        self.user.reset()
        self.menu._reset()
        return True

    def _update_balance(self, response: Any) -> None:
        """Pick up the new balance that write endpoints return in ``konto``."""
        if isinstance(response, Mapping) and "konto" in response:
            self.user.balance = _to_float(response["konto"], self.user.balance)

    # ----------------------------------------------------------------- lifetime

    def close(self) -> None:
        """Close the connection pool, unless the client was supplied by the caller."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> StravaCZ:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            # Closing must not mask whatever is already propagating.
            with contextlib.suppress(StravaAPIError):
                if self.user.is_logged_in:
                    self.logout()
        finally:
            self.close()

    def __repr__(self) -> str:
        if not self.user.is_logged_in:
            return "StravaCZ(logged out)"
        return f"StravaCZ(user={self.user.username!r}, canteen={self.user.canteen_number!r})"


def _to_float(value: Any, default: float = 0.0) -> float:
    """The API sends money as strings like ``"512.50"``; callers want a number."""
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", ".").strip())
    except (TypeError, ValueError):
        return default
