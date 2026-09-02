"""Shared test fixtures.

Every test in this suite runs against recorded API responses. Real network access is
blocked outright: earlier versions of this suite quietly made live requests to
app.strava.cz on every CI run, and the guard below makes that impossible to
reintroduce by accident.
"""

from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any

import httpx
import pytest

from strava_cz import StravaCZ

FIXTURES = Path(__file__).parent / "fixtures"
BASE_URL = "https://app.strava.cz"


def load(name: str) -> Any:
    """Load a recorded API response by file name (without the extension)."""
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def block_real_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any attempt to open a real socket fail loudly."""

    def deny(*args: Any, **kwargs: Any) -> None:
        raise AssertionError(
            "A test tried to open a real network connection. Record the response as "
            "a fixture and route it through respx instead."
        )

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "create_connection", deny)


@pytest.fixture
def api(respx_mock: Any) -> Any:
    """A respx router with the session warm-up and logout already stubbed."""
    respx_mock.get(f"{BASE_URL}/en/prihlasit-se?jidelna").mock(
        return_value=httpx.Response(200, text="<html></html>")
    )
    # The real logOut endpoint answers with the bare JSON literal `true`.
    respx_mock.post(f"{BASE_URL}/api/logOut").mock(return_value=httpx.Response(200, json=True))
    return respx_mock


@pytest.fixture
def login_route(api: Any) -> Any:
    """A successful login."""
    return api.post(f"{BASE_URL}/api/login").mock(
        return_value=httpx.Response(200, json=load("login"))
    )


@pytest.fixture
def menu_payload() -> Any:
    """The recorded 31-day menu from a live canteen."""
    return load("menu_live")


@pytest.fixture
def strava(api: Any, login_route: Any) -> StravaCZ:
    """A logged-in client with no menu fetched yet."""
    return StravaCZ("test.user", "test-password", "1234")


@pytest.fixture
def menu(api: Any, strava: StravaCZ, menu_payload: Any) -> StravaCZ:
    """A logged-in client whose menu has been fetched."""
    api.post(f"{BASE_URL}/api/objednavky").mock(return_value=httpx.Response(200, json=menu_payload))
    strava.menu.fetch()
    return strava


def with_ordered(payload: Any, *meal_ids: int) -> Any:
    """A copy of a menu payload with the given meal ids marked as ordered."""
    import copy

    clone = copy.deepcopy(payload)
    wanted = {str(i) for i in meal_ids}
    for rows in clone.values():
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict) and str(row.get("veta")) in wanted:
                    row["pocet"] = 1
    return clone
