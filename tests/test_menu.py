"""Reading, filtering and printing the menu."""

from __future__ import annotations

import datetime as dt

import httpx
import pytest

from strava_cz import MealNotFoundError, MealType, MenuNotFetchedError, Restriction

from .conftest import BASE_URL


class TestFetch:
    def test_before_fetching_the_menu_says_so(self, strava):
        assert strava.menu.fetched is False
        assert repr(strava.menu) == "Menu(not fetched)"
        for access in (
            lambda: strava.menu.days,
            lambda: strava.menu.meals,
            lambda: len(strava.menu),
        ):
            with pytest.raises(MenuNotFetchedError):
                access()

    def test_fetch_returns_self_for_chaining(self, api, strava, menu_payload):
        api.post(f"{BASE_URL}/api/objednavky").mock(
            return_value=httpx.Response(200, json=menu_payload)
        )
        assert strava.menu.fetch() is strava.menu

    def test_sends_the_balance_as_a_number(self, api, strava, menu_payload):
        route = api.post(f"{BASE_URL}/api/objednavky").mock(
            return_value=httpx.Response(200, json=menu_payload)
        )
        strava.menu.fetch()
        import json

        payload = json.loads(route.calls.last.request.read())
        assert payload["konto"] == 512.50
        assert payload["sid"] == strava.user.sid
        assert payload["cislo"] == "1234"

    def test_raw_data_is_kept(self, menu, menu_payload):
        assert menu.menu.raw_data == menu_payload


class TestFiltering:
    def test_the_default_hides_nothing_but_no_school_days(self, menu):
        days = menu.menu.get_days()
        assert len(days) == 20
        assert all(not day.no_school for day in days)

    def test_no_school_days_can_be_asked_for(self, menu):
        days = menu.menu.get_days(include_no_school=True)
        closed = [d for d in days if d.no_school]
        assert [d.date.isoformat() for d in closed] == ["2026-09-01", "2026-09-28"]

    def test_days_hidden_by_v0_2_0_are_visible(self, menu):
        # These four days carry the day-level code "T", which v0.2.0 treated as
        # "not normally ordered" and excluded from its default listing.
        visible = {d.date.isoformat() for d in menu.menu.get_days()}
        for iso in ("2026-09-04", "2026-09-11", "2026-09-18", "2026-09-25"):
            assert iso in visible
            day = menu.menu.get_by_date(iso)
            assert day.day_code == "T"
            assert day.orderable, f"{iso} should have orderable meals"

    def test_filter_by_auto_ordered(self, menu):
        covered = menu.menu.get_days(auto_ordered=True)
        skipped = menu.menu.get_days(auto_ordered=False)
        assert [d.date.isoformat() for d in skipped] == [
            "2026-09-04",
            "2026-09-11",
            "2026-09-18",
            "2026-09-25",
        ]
        assert all(d.auto_ordered for d in covered)
        assert len(covered) + len(skipped) == len(menu.menu.get_days())

        # The filter picks days, but get_meals() still flattens to the day's meals.
        meals = menu.menu.get_meals(auto_ordered=False, orderable=True)
        assert meals and all(m.can_order for m in meals)
        assert {m.date.isoformat() for m in meals} == {d.date.isoformat() for d in skipped}

    def test_filter_by_meal_type(self, menu):
        soups = menu.menu.get_meals(meal_types=[MealType.SOUP])
        assert soups and all(m.type is MealType.SOUP for m in soups)
        mains = menu.menu.get_meals(meal_types=[MealType.MAIN])
        assert mains and all(m.type is MealType.MAIN for m in mains)
        assert len(soups) + len(mains) == len(menu.menu.get_meals())

    def test_filter_by_orderability(self, menu):
        assert all(m.can_order for m in menu.menu.get_meals(orderable=True))
        assert all(not m.can_order for m in menu.menu.get_meals(orderable=False))

    def test_filter_by_ordered_state(self, menu):
        assert menu.menu.get_meals(ordered=True) == []
        assert len(menu.menu.get_meals(ordered=False)) == len(menu.menu.get_meals())

    def test_filter_by_date_range(self, menu):
        days = menu.menu.get_days(date_from="2026-09-07", date_to="2026-09-09")
        assert [d.date.isoformat() for d in days] == ["2026-09-07", "2026-09-08", "2026-09-09"]
        days = menu.menu.get_days(date_from=dt.date(2026, 10, 1))
        assert all(d.date >= dt.date(2026, 10, 1) for d in days)

    def test_filters_combine(self, menu):
        meals = menu.menu.get_meals(
            meal_types=[MealType.MAIN], orderable=True, date_from="2026-09-07", date_to="2026-09-07"
        )
        assert {m.id for m in meals} == {9, 10}

    def test_days_without_matching_meals_drop_out(self, menu):
        # No soup is orderable in this canteen, so filtering for both yields nothing.
        assert menu.menu.get_days(meal_types=[MealType.SOUP], orderable=True) == []

    def test_filtering_does_not_mutate_the_menu(self, menu):
        before = len(menu.menu.get_meals())
        menu.menu.get_days(meal_types=[MealType.SOUP])
        assert len(menu.menu.get_meals()) == before


class TestLookup:
    def test_get_by_id(self, menu):
        meal = menu.menu.get_by_id(9)
        assert meal.id == 9 and meal.date == dt.date(2026, 9, 7)
        assert menu.menu.get_by_id(999999) is None

    def test_get_by_date_accepts_strings_and_dates(self, menu):
        by_string = menu.menu.get_by_date("2026-09-07")
        by_date = menu.menu.get_by_date(dt.date(2026, 9, 7))
        assert by_string == by_date
        assert menu.menu.get_by_date("2020-01-01") is None

    def test_is_ordered_raises_for_unknown_ids(self, menu):
        assert menu.menu.is_ordered(9) is False
        with pytest.raises(MealNotFoundError, match="999999"):
            menu.menu.is_ordered(999999)

    def test_membership(self, menu):
        assert 9 in menu.menu
        assert 999999 not in menu.menu
        assert "2026-09-07:O2" in menu.menu
        assert "2030-01-01:O1" not in menu.menu


class TestContainerProtocol:
    def test_len_iter_and_index(self, menu):
        assert len(menu.menu) == 20
        days = list(menu.menu)
        assert len(days) == 20
        assert menu.menu[0].date == days[0].date
        assert menu.menu[0:2] == days[0:2]

    def test_days_iterate_over_their_meals(self, menu):
        day = menu.menu.get_by_date("2026-09-07")
        assert len(day) == len(day.meals)
        assert [m.id for m in day] == [m.id for m in day.meals]

    def test_repr_summarises(self, menu):
        assert repr(menu.menu).startswith("Menu(days=20, meals=")
        assert "orderable=" in repr(menu.menu)


class TestPrint:
    def test_prints_every_day_and_marks_restrictions(self, menu, capsys):
        menu.menu.print()
        out = capsys.readouterr().out
        assert "Kuřecí kostky na paprice" in out
        assert "[ ]" in out  # orderable
        assert "[-]" in out  # blocked
        assert "cannot be ordered separately" in out  # a soup's reason
        assert "Kč" in out

    def test_accepts_the_same_filters(self, menu, capsys):
        menu.menu.print(orderable=True)
        out = capsys.readouterr().out
        assert "[-]" not in out

    def test_says_so_when_nothing_matches(self, menu, capsys):
        menu.menu.print(meal_types=[MealType.SOUP], orderable=True)
        assert "no meals match" in capsys.readouterr().out


class TestMealPresentation:
    def test_str_and_repr(self, menu):
        meal = menu.menu.get_by_id(9)
        assert str(meal).startswith("[9]")
        assert "Meal(id=9" in repr(meal)

    def test_a_blocked_meal_explains_itself(self, menu):
        soup = menu.menu.get_by_id(85)
        assert soup.can_order is False
        assert soup.order_restriction is Restriction.UNAVAILABLE
        assert "cannot be ordered separately" in str(soup)


def test_asking_for_a_key_before_fetching_is_false_rather_than_an_error(strava):
    """`in` never raises, whichever way the meal is named."""
    assert "2026-09-07:O2" not in strava.menu
    assert 9 not in strava.menu
