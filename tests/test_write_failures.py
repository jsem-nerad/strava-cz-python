"""What a write leaves behind when one of its steps fails, and whether the caller is told.

Runs against :class:`~tests.conftest.FakeCanteen`, which copies how the live canteen treats
a session's orders and numbers, because a mock that simply answers can't show any of this.
"""

from __future__ import annotations

import pytest

import strava_cz as sc
from strava_cz import MenuNotFetchedError, StravaAPIError

from .conftest import FakeCanteen

A = "2026-09-07:O2"
B = "2026-09-08:O2"


@pytest.fixture
def canteen(api, menu_payload):
    return FakeCanteen(api, menu_payload)


@pytest.fixture
def strava(canteen, login_route):
    client = sc.StravaCZ("test.user", "test-password", "1234")
    client.menu.fetch()
    return client


class TestNumbersMoveOnAReset:
    """A reset renumbers the menu, so nothing read before it may decide what gets ordered."""

    def test_a_retry_after_every_stage_failed_orders_the_meal_it_names(self, strava, canteen):
        canteen.fail("pridejJidloS5", "refuse", "refuse")
        result = strava.menu.order_meals(A, B, continue_on_error=True)
        assert result.changed == ()

        assert strava.menu.order_meals(A).changed == (A,)
        assert canteen.saved_keys() == {A}

    def test_a_failed_reload_leaves_no_numbers_behind_to_order_with(self, strava, canteen):
        canteen.fail("pridejJidloS5", "refuse")
        canteen.fail("objednavky", "timeout")
        with pytest.raises(StravaAPIError):
            strava.menu.order_meals(A)

        with pytest.raises(MenuNotFetchedError):
            strava.menu.order_meals(A)
        assert canteen.saved_keys() == set()

        strava.menu.fetch()
        assert strava.menu.order_meals(A).changed == (A,)
        assert canteen.saved_keys() == {A}

    def test_a_number_read_before_a_reset_is_refused(self, strava, canteen):
        number = strava.menu.get_by_key(A).id
        canteen.fail("pridejJidloS5", "refuse")
        with pytest.raises(StravaAPIError):
            strava.menu.order_meals(number)

        with pytest.raises(MenuNotFetchedError, match="renumber"):
            strava.menu.order_meals(number)
        with pytest.raises(MenuNotFetchedError, match="renumber"):
            strava.menu.get_by_id(number)
        assert number not in strava.menu
        assert canteen.saved_keys() == set()

    def test_a_key_keeps_working_after_a_reset(self, strava, canteen):
        canteen.fail("pridejJidloS5", "refuse")
        with pytest.raises(StravaAPIError):
            strava.menu.order_meals(A)
        assert strava.menu.order_meals(A).changed == (A,)
        assert canteen.saved_keys() == {A}

    def test_fetching_makes_numbers_usable_again(self, strava, canteen):
        canteen.fail("pridejJidloS5", "refuse")
        with pytest.raises(StravaAPIError):
            strava.menu.order_meals(A)

        strava.menu.fetch()
        number = strava.menu.get_by_key(A).id
        assert strava.menu.order_meals(number).changed == (number,)
        assert canteen.saved_keys() == {A}

    def test_a_write_that_worked_leaves_the_numbers_valid(self, strava, canteen):
        first, second = (strava.menu.get_by_key(k).id for k in (A, B))
        strava.menu.order_meals(first)
        strava.menu.order_meals(second)
        assert canteen.saved_keys() == {A, B}

    def test_a_reset_that_failed_is_made_up_for_before_the_next_fetch(self, strava, canteen):
        """Otherwise the staged meal would show as ordered and the next save would commit it."""
        canteen.fail("pridejJidloS5", None, "refuse")
        canteen.fail("nactiVlastnostiPA", "timeout")
        with pytest.raises(StravaAPIError):
            strava.menu.order_meals(A, B)

        strava.menu.fetch()
        assert strava.menu.is_ordered(A) is False
        strava.menu.order_meals(B)
        assert canteen.saved_keys() == {B}
