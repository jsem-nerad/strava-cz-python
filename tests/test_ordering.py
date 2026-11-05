"""Ordering and cancelling meals."""

from __future__ import annotations

import json

import httpx
import pytest

from strava_cz import (
    DuplicateMealError,
    InsufficientBalanceError,
    MealNotFoundError,
    MealNotOrderableError,
    Restriction,
    StravaAPIError,
)

from .conftest import BASE_URL, load, renumbered, veta_of, with_ordered


@pytest.fixture
def canteen(api, menu, menu_payload):
    """A logged-in client plus handles on the endpoints ordering touches."""

    class Canteen:
        def __init__(self):
            self.strava = menu
            self.payload = menu_payload
            self.stage = api.post(f"{BASE_URL}/api/pridejJidloS5").mock(
                return_value=httpx.Response(200, json={"konto": "462.50"})
            )
            self.save = api.post(f"{BASE_URL}/api/saveOrders").mock(
                return_value=httpx.Response(200, json={"konto": "462.50"})
            )
            self.discard = api.post(f"{BASE_URL}/api/nactiVlastnostiPA").mock(
                return_value=httpx.Response(200, json={"konto": "512.50"})
            )
            self.menu_route = api.post(f"{BASE_URL}/api/objednavky")

        def after(self, *ordered_ids):
            """Make the next menu fetch report these ids as ordered."""
            self.menu_route.mock(
                return_value=httpx.Response(200, json=with_ordered(self.payload, *ordered_ids))
            )

        def staged(self):
            """The (meal id, count) pairs actually sent to the canteen."""
            return [
                (int(json.loads(c.request.read())["veta"]), json.loads(c.request.read())["pocet"])
                for c in self.stage.calls
            ]

    return Canteen()


class TestOrdering:
    def test_orders_a_meal_and_confirms_it(self, canteen):
        canteen.after(9)
        result = canteen.strava.menu.order_meals(9)
        assert result.changed == (9,)
        assert result.ok
        assert canteen.staged() == [(9, "1")]
        assert canteen.save.called
        assert canteen.strava.menu.is_ordered(9)

    def test_orders_several_meals_in_one_save(self, canteen):
        canteen.after(9, 13)
        result = canteen.strava.menu.order_meals(9, 13)
        assert set(result.changed) == {9, 13}
        assert len(canteen.stage.calls) == 2
        assert len(canteen.save.calls) == 1  # one transaction, not one per meal

    def test_updates_the_balance_from_the_response(self, canteen):
        canteen.after(9)
        assert canteen.strava.user.balance == 512.50
        canteen.strava.menu.order_meals(9)
        assert canteen.strava.user.balance == 462.50

    def test_repeated_ids_are_collapsed(self, canteen):
        canteen.after(9)
        canteen.strava.menu.order_meals(9, 9, 9)
        assert canteen.staged() == [(9, "1")]

    def test_a_meal_already_ordered_is_left_alone(self, api, strava, menu_payload):
        api.post(f"{BASE_URL}/api/objednavky").mock(
            return_value=httpx.Response(200, json=with_ordered(menu_payload, 9))
        )
        stage = api.post(f"{BASE_URL}/api/pridejJidloS5")
        save = api.post(f"{BASE_URL}/api/saveOrders")
        strava.menu.fetch()

        result = strava.menu.order_meals(9)
        assert result.unchanged == (9,)
        assert result.changed == ()
        assert not stage.called and not save.called


class TestKeys:
    """A meal named by its day and slot, the name that survives logging in again."""

    def test_a_key_is_the_day_and_the_slot(self, menu):
        assert menu.menu.get_by_id(10).key == "2026-09-07:O2"
        assert menu.menu.get_by_key("2026-09-07:O2").id == 10

    def test_a_key_is_forgiving_about_case_and_whitespace(self, menu):
        assert menu.menu.get_by_key(" 2026-09-07:o2 ").id == 10

    def test_an_unknown_key_finds_nothing(self, menu):
        assert menu.menu.get_by_key("2030-01-01:O1") is None

    def test_a_key_two_meals_share_finds_neither(self, api, strava, menu_payload):
        """A canteen could repeat a slot on one day; guessing could order the wrong one."""
        import copy

        payload = copy.deepcopy(menu_payload)
        rows = [r for t in payload.values() if isinstance(t, list) for r in t]
        other = next(r for r in rows if r["datum"] == "07.09.2026" and r["druh"] == "O2")
        other["druh"] = "O1"
        api.post(f"{BASE_URL}/api/objednavky").mock(return_value=httpx.Response(200, json=payload))
        strava.menu.fetch()
        assert strava.menu.get_by_key("2026-09-07:O1") is None

    def test_ordering_by_key_stages_this_logins_number(self, canteen):
        canteen.after(10)
        result = canteen.strava.menu.order_meals("2026-09-07:O2")
        assert result.changed == ("2026-09-07:O2",)
        assert canteen.staged() == [(10, "1")]

    def test_an_id_and_a_key_can_be_mixed(self, canteen):
        canteen.after(9, 14)
        result = canteen.strava.menu.order_meals(9, "2026-09-08:O2")
        assert set(result.changed) == {9, "2026-09-08:O2"}

    def test_an_unknown_key_is_reported(self, canteen):
        with pytest.raises(MealNotFoundError, match="2030-01-01:O1"):
            canteen.strava.menu.order_meals("2030-01-01:O1")
        assert not canteen.stage.called

    def test_a_refusal_names_the_meal_the_way_the_caller_did(self, canteen):
        with pytest.raises(MealNotOrderableError, match="2026-09-02:PO"):
            canteen.strava.menu.order_meals("2026-09-02:PO")

    def test_is_ordered_takes_a_key_too(self, canteen):
        assert canteen.strava.menu.is_ordered("2026-09-07:O2") is False

    def test_a_number_in_a_string_is_still_an_id(self, canteen):
        canteen.after(10)
        assert canteen.strava.menu.order_meals("10").changed == (10,)
        assert canteen.staged() == [(10, "1")]

    def test_one_meal_named_two_ways_is_one_meal(self, canteen):
        canteen.after(10)
        result = canteen.strava.menu.order_meals(10, "2026-09-07:O2", "2026-09-07:o2", "10")
        assert result.changed == (10,) and result.skipped == ()
        assert canteen.staged() == [(10, "1")]

    def test_naming_a_meal_two_ways_is_not_a_duplicate_in_strict_mode(self, canteen):
        canteen.after(10)
        result = canteen.strava.menu.order_meals(10, "2026-09-07:O2", strict_duplicates=True)
        assert result.changed == (10,)

    def test_cancelling_one_meal_named_two_ways_sends_one_request(self, api, strava, menu_payload):
        route = api.post(f"{BASE_URL}/api/objednavky").mock(
            return_value=httpx.Response(200, json=with_ordered(menu_payload, 10))
        )
        stage = api.post(f"{BASE_URL}/api/pridejJidloS5").mock(
            return_value=httpx.Response(200, json={})
        )
        api.post(f"{BASE_URL}/api/saveOrders").mock(return_value=httpx.Response(200, json={}))
        strava.menu.fetch()
        route.mock(return_value=httpx.Response(200, json=menu_payload))
        assert strava.menu.cancel_meals(10, "2026-09-07:O2").changed == (10,)
        assert len(stage.calls) == 1

    def test_in_agrees_with_ordering_on_every_way_of_naming_a_meal(self, menu):
        for ref in (10, "10", " 10 ", "2026-09-07:O2", "2026-09-07:o2"):
            assert ref in menu.menu
        for ref in (999999, "999999", "2030-01-01:O1", "nonsense", 1.5, None):
            assert ref not in menu.menu

    def test_a_shared_key_is_reported_when_the_menu_loads(self, api, strava, menu_payload):
        import copy

        payload = copy.deepcopy(menu_payload)
        rows = [r for t in payload.values() if isinstance(t, list) for r in t]
        other = next(r for r in rows if r["datum"] == "07.09.2026" and r["druh"] == "O2")
        other["druh"] = "O1"
        api.post(f"{BASE_URL}/api/objednavky").mock(return_value=httpx.Response(200, json=payload))
        strava.menu.fetch()
        assert any("2026-09-07:O1" in str(warning) for warning in strava.menu.parse_warnings)

    def test_a_meal_with_no_slot_code_is_reported_and_has_no_key_to_order_by(
        self, api, strava, menu_payload
    ):
        import copy

        payload = copy.deepcopy(menu_payload)
        rows = [r for t in payload.values() if isinstance(t, list) for r in t]
        row = next(r for r in rows if r["datum"] == "07.09.2026" and r["druh"] == "O2")
        row["druh"] = ""
        api.post(f"{BASE_URL}/api/objednavky").mock(return_value=httpx.Response(200, json=payload))
        strava.menu.fetch()
        assert strava.menu.get_by_key("2026-09-07:") is None
        assert any("2026-09-07:" in str(warning) for warning in strava.menu.parse_warnings)


class TestConfirmingAgainstARenumberedMenu:
    """The check after a write must not read the answer off whichever row has that number."""

    #: Moves every id, and hands Monday's Oběd 2's old number to Tuesday's Oběd 1.
    SHIFT = -3

    @staticmethod
    def rows(payload):
        return [r for t in payload.values() if isinstance(t, list) for r in t]

    def impostor(self, payload, number):
        """The row now holding *number*, checked to be a real meal on another day."""
        row = next(r for r in self.rows(payload) if int(r["veta"]) == number)
        assert (row["datum"], row["druh"]) == ("08.09.2026", "O1")
        assert row["nazev"] and row["nazev"] != row["druh_popis"]
        return row

    def test_an_order_that_landed_is_not_reported_as_failed(self, canteen):
        wanted = veta_of(canteen.payload, "07.09.2026", "O2")
        shifted = renumbered(with_ordered(canteen.payload, wanted), self.SHIFT)
        self.impostor(shifted, wanted)
        canteen.menu_route.mock(return_value=httpx.Response(200, json=shifted))
        assert canteen.strava.menu.order_meals(wanted).changed == (wanted,)

    def test_an_order_that_did_not_land_is_not_reported_as_done(self, canteen):
        """The meal's old number now means another meal, already ordered. It proves nothing."""
        wanted = veta_of(canteen.payload, "07.09.2026", "O2")
        shifted = renumbered(canteen.payload, self.SHIFT)
        self.impostor(shifted, wanted)["pocet"] = 1
        canteen.menu_route.mock(return_value=httpx.Response(200, json=shifted))
        with pytest.raises(StravaAPIError, match="still not ordered"):
            canteen.strava.menu.order_meals(wanted)

    def test_a_slot_that_vanished_is_not_vouched_for_by_whatever_has_its_number(self, canteen):
        """The slot is gone from the fresh menu and its old number is another, ordered meal."""
        wanted = veta_of(canteen.payload, "07.09.2026", "O2")
        shifted = renumbered(canteen.payload, self.SHIFT)
        slot = next(
            r for r in self.rows(shifted) if r["datum"] == "07.09.2026" and r["druh"] == "O2"
        )
        slot["nazev"] = ""  # the canteen unpublished it
        self.impostor(shifted, wanted)["pocet"] = 1
        canteen.menu_route.mock(return_value=httpx.Response(200, json=shifted))
        with pytest.raises(StravaAPIError, match="still not ordered"):
            canteen.strava.menu.order_meals(wanted)

    def test_a_meal_whose_key_is_shared_is_still_confirmed_by_its_number(
        self, api, strava, menu_payload
    ):
        """With no usable key the number is all there is, while it's still the same slot."""
        import copy

        payload = copy.deepcopy(menu_payload)
        row = next(
            r for r in self.rows(payload) if r["datum"] == "07.09.2026" and r["druh"] == "O2"
        )
        wanted = int(row["veta"])
        row["druh"] = "O1"
        route = api.post(f"{BASE_URL}/api/objednavky").mock(
            return_value=httpx.Response(200, json=payload)
        )
        api.post(f"{BASE_URL}/api/pridejJidloS5").mock(return_value=httpx.Response(200, json={}))
        api.post(f"{BASE_URL}/api/saveOrders").mock(return_value=httpx.Response(200, json={}))
        strava.menu.fetch()
        route.mock(return_value=httpx.Response(200, json=with_ordered(payload, wanted)))
        assert strava.menu.order_meals(wanted).changed == (wanted,)


class TestNothingToDo:
    """No API call may be made when there is nothing to change."""

    def test_ordering_nothing_sends_nothing(self, canteen):
        result = canteen.strava.menu.order_meals()
        assert result.changed == () and result.ok
        assert not canteen.stage.called
        assert not canteen.save.called

    def test_cancelling_nothing_sends_nothing(self, canteen):
        result = canteen.strava.menu.cancel_meals()
        assert result.ok
        assert not canteen.stage.called and not canteen.save.called

    def test_cancelling_an_unordered_meal_sends_nothing(self, canteen):
        result = canteen.strava.menu.cancel_meals(9)
        assert result.unchanged == (9,)
        assert not canteen.stage.called and not canteen.save.called


class TestRefusedMeals:
    def test_ordering_a_soup_is_refused_by_restriction_not_by_type(self, canteen):
        with pytest.raises(MealNotOrderableError) as exc:
            canteen.strava.menu.order_meals(85)
        assert exc.value.meal_id == 85
        assert exc.value.reason is Restriction.UNAVAILABLE
        assert not canteen.stage.called

    def test_ordering_past_the_deadline_is_refused(self, canteen):
        with pytest.raises(MealNotOrderableError) as exc:
            canteen.strava.menu.order_meals(3)
        assert exc.value.reason is Restriction.CLOSED
        assert "deadline" in str(exc.value)

    def test_cancelling_an_ordered_but_locked_meal_is_refused(self, api, strava, menu_payload):
        api.post(f"{BASE_URL}/api/objednavky").mock(
            return_value=httpx.Response(200, json=with_ordered(menu_payload, 3))
        )
        stage = api.post(f"{BASE_URL}/api/pridejJidloS5")
        strava.menu.fetch()
        with pytest.raises(MealNotOrderableError, match="cancel"):
            strava.menu.cancel_meals(3)
        assert not stage.called

    def test_unknown_ids_are_reported(self, canteen):
        with pytest.raises(MealNotFoundError, match="999999"):
            canteen.strava.menu.order_meals(999999)
        with pytest.raises(MealNotFoundError, match="999999"):
            canteen.strava.menu.cancel_meals(999999)
        assert not canteen.stage.called
        assert not canteen.save.called


class TestDuplicates:
    def test_two_mains_on_one_day_keep_the_first_and_warn(self, canteen):
        canteen.after(9)
        with pytest.warns(UserWarning, match="competes with meal 9"):
            result = canteen.strava.menu.order_meals(9, 10)
        assert result.changed == (9,)
        assert [meal_id for meal_id, _ in result.skipped] == [10]
        assert canteen.staged() == [(9, "1")]

    def test_strict_mode_raises_instead(self, canteen):
        with pytest.raises(DuplicateMealError, match="same kind on one day"):
            canteen.strava.menu.order_meals(9, 10, strict_duplicates=True)
        assert not canteen.stage.called

    def test_meals_on_different_days_are_not_duplicates(self, canteen):
        canteen.after(9, 13)
        result = canteen.strava.menu.order_meals(9, 13)
        assert set(result.changed) == {9, 13}
        assert result.skipped == ()


class TestCancelling:
    def test_cancels_an_ordered_meal(self, api, strava, menu_payload):
        menu_route = api.post(f"{BASE_URL}/api/objednavky").mock(
            return_value=httpx.Response(200, json=with_ordered(menu_payload, 9))
        )
        stage = api.post(f"{BASE_URL}/api/pridejJidloS5").mock(
            return_value=httpx.Response(200, json={"konto": "562.50"})
        )
        save = api.post(f"{BASE_URL}/api/saveOrders").mock(
            return_value=httpx.Response(200, json={})
        )
        strava.menu.fetch()
        assert strava.menu.is_ordered(9)

        menu_route.mock(return_value=httpx.Response(200, json=menu_payload))
        result = strava.menu.cancel_meals(9)

        assert result.changed == (9,)
        assert json.loads(stage.calls.last.request.read())["pocet"] == "0"
        assert save.called
        assert strava.menu.is_ordered(9) is False


class TestFailures:
    def test_insufficient_balance_rolls_back_and_raises(self, canteen):
        canteen.stage.mock(return_value=httpx.Response(555, json=load("error_balance")))
        with pytest.raises(InsufficientBalanceError):
            canteen.strava.menu.order_meals(9)
        assert canteen.discard.called, "staged changes must be discarded"
        assert not canteen.save.called, "nothing may be saved after a failure"

    def test_a_save_that_fails_rolls_back(self, canteen):
        canteen.save.mock(
            return_value=httpx.Response(
                555, json={"state": "error", "number": 7, "message": "Nope"}
            )
        )
        with pytest.raises(StravaAPIError):
            canteen.strava.menu.order_meals(9)
        assert canteen.discard.called

    def test_an_order_the_canteen_silently_ignored_is_reported(self, canteen):
        canteen.after()  # the refreshed menu still shows the meal as not ordered
        with pytest.raises(StravaAPIError, match="still not ordered"):
            canteen.strava.menu.order_meals(9)

    def test_continue_on_error_reports_instead_of_raising(self, canteen):
        canteen.after(9)
        result = canteen.strava.menu.order_meals(85, 9, 999999, continue_on_error=True)

        assert result.changed == (9,)
        assert result.ok is False
        assert bool(result) is False
        failed = dict(result.failed)
        assert isinstance(failed[85], MealNotOrderableError)
        assert isinstance(failed[999999], MealNotFoundError)
        assert canteen.staged() == [(9, "1")]  # the good meal still went through

    def test_continue_on_error_with_nothing_orderable_sends_nothing(self, canteen):
        result = canteen.strava.menu.order_meals(85, 999999, continue_on_error=True)
        assert result.changed == ()
        assert len(result.failed) == 2
        assert not canteen.stage.called
        assert not canteen.save.called

    def test_continue_on_error_never_raises_for_refused_meals(self, canteen):
        result = canteen.strava.menu.cancel_meals(999999, continue_on_error=True)
        assert len(result.failed) == 1


class TestOrderResult:
    def test_summarises_itself(self, canteen):
        canteen.after(9)
        with pytest.warns(UserWarning):
            result = canteen.strava.menu.order_meals(9, 10)
        assert "1 changed" in str(result)
        assert "1 skipped" in str(result)
        assert result.ok and bool(result)
