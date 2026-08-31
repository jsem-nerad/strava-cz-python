"""Regressions for bugs found in v0.2.0.

Each test names the behaviour that used to be wrong, so a future change that
reintroduces it fails here with an explanation rather than a bare assertion.
"""

from __future__ import annotations

import socket

import httpx
import pytest

from strava_cz import (
    DayStatus,
    MealNotFoundError,
    MealType,
    Restriction,
    StravaAPIError,
    StravaCZ,
)
from strava_cz.parser import parse_menu

from .conftest import BASE_URL, load, with_ordered


def test_menu_is_not_empty_for_a_day_carrying_a_day_level_code():
    """v0.2.0 read `omezeniObj.den`, so this recorded day produced an empty menu."""
    days, _ = parse_menu(load("menu_2025"))
    assert days, "the whole menu disappeared"
    assert len(days[0].meals) == 3


def test_orderable_days_are_not_hidden_by_the_day_code(menu):
    """`den == "T"` used to be read as OPTIONAL and hidden from the default listing."""
    days = menu.menu.get_days()
    t_days = [d for d in days if d.day_code == "T"]
    assert len(t_days) == 4
    assert all(d.orderable for d in t_days)


def test_a_skipped_day_is_orderable_but_not_automatic(menu):
    """0.3.0 fixed the hiding but dropped the meaning: "T" is not "unorderable".

    The canteen's standing order does not cover these days, which is why they never
    fill themselves in - but every meal on them can still be ordered by hand.
    """
    for iso in ("2026-09-04", "2026-09-11", "2026-09-18", "2026-09-25"):
        day = menu.menu.get_by_date(iso)
        assert day.status is DayStatus.NOT_AUTO_ORDERED
        assert not day.auto_ordered
        assert day.orderable
        assert all(m.order_restriction is Restriction.NONE for m in day.orderable)


def test_orderability_comes_from_the_canteen_not_from_the_meal_type():
    """v0.2.0 hard-coded "only main dishes can be ordered".

    Where a canteen does allow ordering soup separately it says so with
    ``omezeniObj.obj == ""``, and the library must believe the canteen.
    """
    payload = {
        "table0": [
            {
                "datum": "15.09.2026",
                "druh": "PO",
                "druh_popis": "Polévka",
                "nazev": "Česnečka",
                "cena": "15.00",
                "pocet": 0,
                "veta": "42",
                "omezeniObj": {"den": "", "obj": "", "zm": "", "bur": "C"},
            }
        ]
    }
    days, _ = parse_menu(payload)
    soup = days[0].meals[0]
    assert soup.type is MealType.SOUP
    assert soup.can_order is True
    assert soup.order_restriction is Restriction.NONE


def test_cancelling_an_unknown_meal_does_not_report_success(canteen_for_regressions):
    """v0.2.0 returned success and still POSTed saveOrders for ids it had never seen."""
    canteen = canteen_for_regressions
    with pytest.raises(MealNotFoundError):
        canteen["strava"].menu.cancel_meals(123456)
    assert not canteen["save"].called


def test_no_write_is_sent_when_there_is_nothing_to_change(canteen_for_regressions):
    """v0.2.0 POSTed saveOrders even for `order_meals()` with no arguments."""
    canteen = canteen_for_regressions
    canteen["strava"].menu.order_meals()
    canteen["strava"].menu.cancel_meals()
    assert not canteen["save"].called
    assert not canteen["stage"].called


def test_continue_on_error_returns_a_result_instead_of_raising(canteen_for_regressions):
    """v0.2.0 collected the errors and then raised them as one joined string anyway."""
    canteen = canteen_for_regressions
    canteen["menu_route"].mock(
        return_value=httpx.Response(200, json=with_ordered(canteen["payload"], 9))
    )
    result = canteen["strava"].menu.order_meals(9, 85, continue_on_error=True)
    assert result.changed == (9,)
    assert len(result.failed) == 1


def test_balance_is_a_number_from_the_moment_of_login(strava):
    """v0.2.0 left it as the API's string until the first order turned it into a float."""
    assert isinstance(strava.user.balance, float)
    assert strava.user.balance * 2 == 1025.0


def test_a_menu_row_missing_fields_does_not_kill_the_fetch():
    """v0.2.0 indexed rows directly and raised KeyError on the whole response."""
    days, warnings = parse_menu({"table0": [{"datum": "15.09.2026", "nazev": "Guláš"}]})
    assert len(days) == 1 and warnings == ()


def test_constructing_a_client_performs_no_io(api):
    """v0.2.0 fetched the login page from __init__, so even tests hit strava.cz."""
    StravaCZ()
    assert not api.calls


def test_requests_always_carry_a_timeout(api):
    """v0.2.0 passed no timeout, so a stalled connection hung the caller forever."""
    strava = StravaCZ()
    assert strava._client.timeout.connect and strava._client.timeout.read


def test_a_non_json_response_is_a_library_error(api, strava):
    """v0.2.0 let json.JSONDecodeError escape to the caller."""
    api.post(f"{BASE_URL}/api/objednavky").mock(
        return_value=httpx.Response(200, text="<html>maintenance</html>")
    )
    with pytest.raises(StravaAPIError):
        strava.menu.fetch()


def test_logout_keeps_held_references_valid(strava):
    """v0.2.0 rebound self.user, so anything holding it kept a stale logged-in copy."""
    user = strava.user
    menu = strava.menu
    strava.logout()
    assert user is strava.user and menu is strava.menu
    assert user.is_logged_in is False


def test_the_network_guard_actually_blocks_connections():
    """The autouse fixture is what keeps this suite from calling a real canteen."""
    with pytest.raises(AssertionError, match="real network connection"):
        socket.create_connection(("example.com", 80))


@pytest.fixture
def canteen_for_regressions(api, menu, menu_payload):
    return {
        "strava": menu,
        "payload": menu_payload,
        "menu_route": api.post(f"{BASE_URL}/api/objednavky"),
        "stage": api.post(f"{BASE_URL}/api/pridejJidloS5").mock(
            return_value=httpx.Response(200, json={"konto": "462.50"})
        ),
        "save": api.post(f"{BASE_URL}/api/saveOrders").mock(
            return_value=httpx.Response(200, json={})
        ),
    }
