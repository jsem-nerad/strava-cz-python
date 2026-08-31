"""Parsing recorded menu responses into days and meals."""

from __future__ import annotations

import datetime as dt

import pytest

from strava_cz.models import DayStatus, MealType, Restriction, parse_api_date
from strava_cz.parser import is_placeholder, parse_menu

from .conftest import load


class TestDateParsing:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("15.09.2026", dt.date(2026, 9, 15)),
            ("15-09.2025", dt.date(2025, 9, 15)),  # separator seen in older builds
            ("1.2.2026", dt.date(2026, 2, 1)),
        ],
    )
    def test_accepts_the_separators_the_api_has_used(self, raw, expected):
        assert parse_api_date(raw) == expected

    @pytest.mark.parametrize("raw", ["", "not a date", "2026-09-15T00:00", None])
    def test_rejects_junk(self, raw):
        with pytest.raises(ValueError):
            parse_api_date(raw)


class TestRestrictions:
    """`omezeniObj.obj`/`zm` decide orderability - `den` is a day-level code."""

    @pytest.mark.parametrize(
        "code, restriction, allowed",
        [
            ("", Restriction.NONE, True),
            ("C", Restriction.CLOSED, False),
            ("I", Restriction.UNAVAILABLE, False),
            ("V", Restriction.NO_SCHOOL, False),
            ("?!", Restriction.UNKNOWN, False),
            (None, Restriction.NONE, True),
        ],
    )
    def test_mapping(self, code, restriction, allowed):
        assert Restriction.from_api(code) is restriction
        assert Restriction.from_api(code).allowed is allowed

    def test_unknown_codes_do_not_raise(self):
        assert Restriction.from_api("ZZZ") is Restriction.UNKNOWN


class TestMealType:
    @pytest.mark.parametrize(
        "code, label, expected",
        [
            ("PO", "Polévka", MealType.SOUP),
            ("O1", "Oběd 1", MealType.MAIN),
            ("O4", "Oběd 2 Rad", MealType.MAIN),
            ("O12", "Oběd 12", MealType.MAIN),
            ("", "Polévka", MealType.SOUP),  # falls back to the label
            ("", "Oběd 1", MealType.MAIN),
            ("XX", "Večeře", MealType.UNKNOWN),
        ],
    )
    def test_classification(self, code, label, expected):
        assert MealType.from_api(code, label) is expected


class TestPlaceholders:
    @pytest.mark.parametrize(
        "name, label",
        [("Oběd 2", "Oběd 2"), ("Oběd 3", "Oběd 1 Rad"), ("Oběd 2 Rad 1", "Oběd 2 Rad"), ("", "X")],
    )
    def test_unpublished_slots_are_placeholders(self, name, label):
        assert is_placeholder(name, label) is True

    @pytest.mark.parametrize(
        "name",
        ["Vývar s kuskusem", "Bretaňské fazole, chléb, ovoce, čaj, pv", "Obědvací polívka"],
    )
    def test_real_meals_are_not(self, name):
        assert is_placeholder(name, "Oběd 1") is False


class TestLiveCapture:
    """The recorded 31-day menu from a real canteen."""

    @pytest.fixture
    def days(self, menu_payload):
        days, warnings = parse_menu(menu_payload)
        assert warnings == ()
        return days

    def test_every_day_is_parsed(self, days):
        assert len(days) == 31
        assert [d.date for d in days] == sorted(d.date for d in days)

    def test_no_school_days_are_flagged_and_hold_no_meals(self, days):
        closed = [d for d in days if d.no_school]
        assert [d.date.isoformat() for d in closed] == ["2026-09-01", "2026-09-28"]
        assert all(d.meals == () for d in closed)
        assert all(d.day_code == "VP" for d in closed)

    def test_days_the_standing_order_skips_are_flagged_but_still_orderable(self, days):
        skipped = [d for d in days if not d.auto_ordered]
        assert [d.date.isoformat() for d in skipped] == [
            "2026-09-04",
            "2026-09-11",
            "2026-09-18",
            "2026-09-25",
            "2026-10-02",
            "2026-10-09",
        ]
        assert all(d.date.weekday() == 4 for d in skipped), "all of them are Fridays"
        assert all(d.status is DayStatus.NOT_AUTO_ORDERED for d in skipped)
        assert all(not d.no_school for d in skipped), "skipped is not the same as closed"
        # The last two Fridays are not published yet and so hold no meals at all; the
        # rest are ordinary orderable days that simply never fill themselves in.
        published = [d for d in skipped if d.meals]
        assert len(published) == 4
        assert all(d.orderable for d in published), "a skipped day is still orderable by hand"

    def test_soups_are_never_orderable_in_this_canteen(self, days):
        soups = [m for d in days for m in d.meals if m.type is MealType.SOUP]
        assert len(soups) == 20
        assert all(not m.can_order for m in soups)
        assert all(m.order_restriction is Restriction.UNAVAILABLE for m in soups)

    def test_a_day_past_its_deadline_is_closed_not_orderable(self, days):
        day = next(d for d in days if d.date == dt.date(2026, 9, 2))
        mains = [m for m in day.meals if m.type is MealType.MAIN]
        assert mains and all(m.order_restriction is Restriction.CLOSED for m in mains)
        assert not day.orderable

    def test_meal_fields_are_typed(self, days):
        meal = next(m for d in days for m in d.meals if m.type is MealType.MAIN and m.can_order)
        assert isinstance(meal.id, int)
        assert isinstance(meal.date, dt.date)
        assert isinstance(meal.price, float) and meal.price > 0
        assert isinstance(meal.ordered, bool)
        assert meal.deadline is not None and isinstance(meal.deadline, dt.datetime)
        assert meal.raw["veta"] == str(meal.id)

    def test_allergens_are_parsed(self, days):
        meal = next(m for d in days for m in d.meals if m.allergens)
        code, name = meal.allergens[0]
        assert code and name
        assert str(meal.allergens[0]) == f"{code} {name}"


class TestHistoricCapture:
    """The 2025 capture in notes/README.md, on which v0.2.0 returned an empty menu."""

    def test_the_day_is_parsed_with_all_three_meals(self):
        days, warnings = parse_menu(load("menu_2025"))
        assert warnings == ()
        assert len(days) == 1
        day = days[0]
        assert day.date == dt.date(2025, 9, 15)
        assert len(day.meals) == 3
        assert day.day_code == "CO"  # kept, but no longer used to decide orderability
        assert day.status is DayStatus.CLOSED
        assert day.auto_ordered

    def test_restrictions_come_from_the_per_meal_fields(self):
        days, _ = parse_menu(load("menu_2025"))
        by_id = {m.id: m for m in days[0].meals}
        assert by_id[75].order_restriction is Restriction.UNAVAILABLE  # soup, obj="I"
        assert by_id[1].order_restriction is Restriction.CLOSED  # obj="C"
        assert by_id[2].order_restriction is Restriction.CLOSED
        assert by_id[1].ordered is True  # pocet == 1


class TestMalformedInput:
    """A surprising payload must never take the whole fetch down."""

    def test_non_mapping_payload(self):
        days, warnings = parse_menu(["not", "a", "menu"])
        assert days == ()
        assert len(warnings) == 1

    def test_row_missing_fields_is_reported_not_raised(self):
        days, warnings = parse_menu({"table0": [{"datum": "15.09.2026", "nazev": "Guláš"}]})
        assert len(days) == 1
        meal = days[0].meals[0]
        assert meal.name == "Guláš"
        assert meal.price == 0.0 and meal.allergens == () and meal.type is MealType.UNKNOWN
        assert warnings == ()

    def test_row_with_an_unparsable_date_is_skipped_with_a_warning(self):
        days, warnings = parse_menu({"table0": [{"datum": "???", "nazev": "Guláš"}]})
        assert days == ()
        assert len(warnings) == 1

    @pytest.mark.parametrize(
        "price, expected", [("", 0.0), ("40,50", 40.5), (12, 12.0), (None, 0.0)]
    )
    def test_prices_are_coerced(self, price, expected):
        days, _ = parse_menu(
            {"table0": [{"datum": "15.09.2026", "nazev": "X", "druh": "O1", "cena": price}]}
        )
        assert days[0].meals[0].price == expected

    def test_unknown_meal_types_are_kept_not_dropped(self):
        days, _ = parse_menu(
            {
                "table0": [
                    {
                        "datum": "15.09.2026",
                        "nazev": "Svíčková",
                        "druh": "VE",
                        "druh_popis": "Večeře",
                    }
                ]
            }
        )
        assert len(days[0].meals) == 1
        assert days[0].meals[0].type is MealType.UNKNOWN

    def test_non_table_keys_and_junk_rows_are_ignored(self):
        days, warnings = parse_menu({"konto": "0.00", "table0": ["junk"], "table1": None})
        assert days == ()
        assert len(warnings) == 1
