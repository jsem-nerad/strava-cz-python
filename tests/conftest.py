"""Shared test fixtures.

Every test in this suite runs against recorded API responses. Real network access is
blocked outright: earlier versions of this suite quietly made live requests to
app.strava.cz on every CI run, and the guard below makes that impossible to
reintroduce by accident.
"""

from __future__ import annotations

import json
import os
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


def renumbered(payload: Any, shift: int) -> Any:
    """The same menu as another login sees it: every meal has moved to a different id.

    The live canteen does this. Numbering is stable within a session and differs between
    sessions, with no change to the menu itself.
    """
    import copy

    clone = copy.deepcopy(payload)
    rows = [
        row
        for table in clone.values()
        if isinstance(table, list)
        for row in table
        if isinstance(row, dict) and "veta" in row
    ]
    ids = sorted(int(row["veta"]) for row in rows)
    moved = {old: ids[(index + shift) % len(ids)] for index, old in enumerate(ids)}
    for row in rows:
        row["veta"] = str(moved[int(row["veta"])])
    return clone


def veta_of(payload: Any, date: str, kind: str) -> int:
    """The id a menu payload gives one day's slot, with the date as the API writes it."""
    for table in payload.values():
        if isinstance(table, list):
            for row in table:
                if isinstance(row, dict) and row.get("datum") == date and row.get("druh") == kind:
                    return int(row["veta"])
    raise AssertionError(f"no {kind} on {date} in this payload")


@pytest.fixture
def store_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An isolated profile store, so no test can touch the real ~/.config."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    for var in list(os.environ):
        if var.startswith(("STRAVA_CZ_PASSWORD", "STRAVA_CZ_PASSPHRASE")):
            monkeypatch.delenv(var, raising=False)
    return tmp_path / "config" / "strava-cz" / "profiles.json"


class FakeKeyring:
    """An in-memory stand-in for the OS keyring.

    The real one cannot be used in tests: CI has no Secret Service, and a developer's
    machine has one that should not collect entries from a test run.
    """

    def __init__(self, working: bool = True) -> None:
        self.entries: dict[tuple[str, str], str] = {}
        self.working = working

    # The bits of the keyring API that strava_cz.profiles uses.
    def get_password(self, service: str, name: str) -> str | None:
        return self.entries.get((service, name))

    def set_password(self, service: str, name: str, password: str) -> None:
        self.entries[(service, name)] = password

    def delete_password(self, service: str, name: str) -> None:
        if (service, name) not in self.entries:
            raise RuntimeError("password not found")
        del self.entries[(service, name)]


@pytest.fixture
def fake_keyring(monkeypatch: pytest.MonkeyPatch) -> FakeKeyring:
    """Route strava_cz.profiles at an in-memory keyring."""
    from strava_cz import profiles

    backend = FakeKeyring()
    monkeypatch.setattr(profiles, "_keyring", lambda: backend)
    return backend


@pytest.fixture
def passphrase(monkeypatch: pytest.MonkeyPatch) -> str:
    """A passphrase in the environment, so encrypted profiles never prompt."""
    value = "test-passphrase"
    monkeypatch.setenv("STRAVA_CZ_PASSPHRASE", value)
    return value


@pytest.fixture
def no_crypto(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate a machine where `cryptography` is not installed."""
    from strava_cz import profiles
    from strava_cz.exceptions import EncryptionUnavailableError

    def fail() -> Any:
        raise EncryptionUnavailableError()

    monkeypatch.setattr(profiles, "_crypto", fail)


@pytest.fixture
def no_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate a machine with no usable keyring, as a headless server has."""
    from strava_cz import profiles
    from strava_cz.exceptions import KeyringUnavailableError

    def fail() -> Any:
        raise KeyringUnavailableError("no backend on this machine")

    monkeypatch.setattr(profiles, "_keyring", fail)


class FakeCanteen:
    """The write path as the live canteen behaved on 2026-11-05, for failures it won't do on demand.

    What it copies, all seen on a real account:

    - Each login works on its **own copy** of the orders. A fetch reads that copy, so a
      staged change shows up in the same session before anything is saved, and a change
      saved by another session doesn't show up at all.
    - ``pridejJidloS5`` changes the copy, and ordering a main unticks that day's other main.
      Only ``saveOrders`` reaches the canteen's records. Logging out drops what wasn't saved.
    - ``nactiVlastnostiPA`` reloads the copy from the records **and renumbers the menu**.
      Stages, saves and plain fetches leave the numbers alone.
    - A number that means nothing is answered with HTTP 555 and API error 9.

    ``fail()`` queues what the next calls to an endpoint do instead of behaving normally.
    """

    #: How far each reset moves the numbers. Hands Monday's Oběd 2's number to Tuesday's Oběd 1.
    RESET_SHIFT = -3

    def __init__(self, api: Any, payload: Any) -> None:
        self.payload = payload
        rows = [r for t in payload.values() if isinstance(t, list) for r in t]
        self.saved = {(r["datum"], r["druh"]): int(r["pocet"]) for r in rows}
        self.table = dict(self.saved)
        self.shift = 0
        self.queued: dict[str, list[str | None]] = {}
        #: Slots a save accepts and quietly doesn't record.
        self.not_recorded: set[tuple[str, str]] = set()
        self.logout = api.post(f"{BASE_URL}/api/logOut").mock(
            return_value=httpx.Response(200, json=True)
        )
        self.routes = {
            name: api.post(f"{BASE_URL}/api/{name}").mock(side_effect=handler)
            for name, handler in (
                ("objednavky", self._objednavky),
                ("pridejJidloS5", self._stage),
                ("saveOrders", self._save),
                ("nactiVlastnostiPA", self._reset),
            )
        }

    def fail(self, endpoint: str, *modes: str | None) -> None:
        """Queue behaviours: timeout, lost, 502, 502-lost, refuse, overload, expired, ignored, funds.

        ``timeout`` and ``502`` do nothing, ``lost`` and ``502-lost`` do the work and lose
        the answer, ``ignored`` answers success and does nothing. None behaves normally.
        """
        self.queued.setdefault(endpoint, []).extend(modes)

    def numbered(self) -> Any:
        """The menu as this session sees it now."""
        import copy

        clone = copy.deepcopy(self.payload)
        for table in clone.values():
            if isinstance(table, list):
                for row in table:
                    row["pocet"] = self.table[(row["datum"], row["druh"])]
        return renumbered(clone, self.shift) if self.shift else clone

    def saved_keys(self) -> set[str]:
        """What is really on the account, as meal keys."""
        return {
            f"{datum[6:]}-{datum[3:5]}-{datum[:2]}:{druh}"
            for (datum, druh), count in self.saved.items()
            if count
        }

    def _outcome(self, endpoint: str, request: httpx.Request, work: Any) -> httpx.Response:
        queue = self.queued.get(endpoint)
        mode = queue.pop(0) if queue else None
        if mode in (None, "lost", "502-lost"):
            answer = work()
            if mode == "lost":
                raise httpx.ReadTimeout("timed out", request=request)
            if mode == "502-lost":
                return httpx.Response(502, text="<html>Bad Gateway</html>")
            return answer
        if mode == "timeout":
            raise httpx.ReadTimeout("timed out", request=request)
        if mode == "502":
            return httpx.Response(502, text="<html>Bad Gateway</html>")
        if mode == "ignored":
            return httpx.Response(200, json={"konto": "0.00"})
        errors = {
            "refuse": (7, "Nope"),
            "overload": (43, "The service is currently overloaded"),
            "expired": (
                15,
                "Because the user has been inactive for a long time, he/she has been logged out",
            ),
        }
        if mode == "funds":
            return httpx.Response(555, json=load("error_balance"))
        number, message = errors[str(mode)]
        return httpx.Response(555, json={"state": "error", "number": number, "message": message})

    def _objednavky(self, request: httpx.Request) -> httpx.Response:
        return self._outcome(
            "objednavky", request, lambda: httpx.Response(200, json=self.numbered())
        )

    def _stage(self, request: httpx.Request) -> httpx.Response:
        def work() -> httpx.Response:
            body = json.loads(request.read())
            rows = [r for t in self.numbered().values() if isinstance(t, list) for r in t]
            row = next((r for r in rows if str(r["veta"]) == str(body["veta"])), None)
            if row is None:
                return httpx.Response(
                    555,
                    json={"state": "error", "number": 9, "message": "Unknown backend error S5"},
                )
            if body["pocet"] == "1" and row["druh"].startswith("O"):
                for datum, druh in self.table:
                    if datum == row["datum"] and druh.startswith("O"):
                        self.table[(datum, druh)] = 0
            self.table[(row["datum"], row["druh"])] = int(body["pocet"])
            return httpx.Response(200, json={"produkt": [], "konto": "0.00"})

        return self._outcome("pridejJidloS5", request, work)

    def _save(self, request: httpx.Request) -> httpx.Response:
        def work() -> httpx.Response:
            kept = {slot: self.saved[slot] for slot in self.not_recorded}
            self.saved = {**self.table, **kept}
            return httpx.Response(200, json={"produkty": [], "konto": "0.00"})

        return self._outcome("saveOrders", request, work)

    def _reset(self, request: httpx.Request) -> httpx.Response:
        def work() -> httpx.Response:
            self.table = dict(self.saved)
            self.shift += self.RESET_SHIFT
            return httpx.Response(200, json={"tablesReseted": True, "konto": "0.00"})

        return self._outcome("nactiVlastnostiPA", request, work)
