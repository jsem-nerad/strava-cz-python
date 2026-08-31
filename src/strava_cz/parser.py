"""Turning the raw ``objednavky`` response into :class:`~strava_cz.models.Day` objects.

The API groups meals into ``table0``, ``table1``, ... - one table per day - and
describes what you may do with each meal in ``omezeniObj``:

===========  ======================================================================
``obj``      may this meal be ordered
``zm``       may an existing order be changed or cancelled
``bur``      is the meal offered on the canteen's exchange (burza)
``den``      a code for the whole day - see :class:`~strava_cz.models.DayStatus`
===========  ======================================================================

For ``obj`` and ``zm`` an empty string means "allowed" and any other value is a
single letter naming the reason - see :class:`~strava_cz.models.Restriction`.

``den`` describes the day, never a meal, so it must not be used to decide whether
something can be ordered. ``"VP"`` marks a day the canteen does not cook, whose rows
are placeholders rather than meals; ``"T"`` marks a day the canteen's standing order
skips, whose meals are perfectly orderable by hand.

Versions of this library before 0.3.0 classified meals from ``den`` alone, which
silently hid orderable days and, for menus where ``den`` was set on every meal,
produced an empty menu.
"""

from __future__ import annotations

import datetime as _dt
import re
from collections.abc import Mapping
from typing import Any

from .models import Allergen, Day, DayStatus, Meal, MealType, Restriction, parse_api_date

__all__ = ["ParseWarning", "parse_menu"]

#: Names the canteen uses for a slot whose meal has not been published yet, e.g.
#: ``"Oběd 2"`` or ``"Oběd 2 Rad 1"``. Such rows carry no real meal.
_GENERIC_NAME_RE = re.compile(
    r"""^\s*(
        ob[eě]d | pol[ée]vka | sva[čc]ina | ve[čc]e[řr]e |
        sn[íi]dan[ěe] | p[řr]esn[íi]d[áa]vka | lunch | soup | dinner
    )\b [\s\d]* (rad [\s\d]*)? $""",
    re.IGNORECASE | re.VERBOSE,
)


class ParseWarning(str):
    """A note about a menu row that could not be used, attached to the Menu."""


def _get(row: Mapping[str, Any], key: str, default: Any = "") -> Any:
    """Read *key* from an API row, treating ``null`` as absent."""
    value = row.get(key, default)
    return default if value is None else value


def _to_float(value: Any) -> float:
    """Parse a price, which the API sends as a string like ``"50.00"`` or ``"0"``."""
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", ".").strip() or 0)
    except ValueError:
        return 0.0


def _parse_allergens(value: Any) -> tuple[Allergen, ...]:
    """Parse ``alergeny``: a list of ``[code, name]`` pairs, or ``null``."""
    if not isinstance(value, (list, tuple)):
        return ()
    allergens = []
    for item in value:
        if isinstance(item, (list, tuple)) and item:
            code = str(item[0])
            name = str(item[1]) if len(item) > 1 else ""
            allergens.append(Allergen(code, name))
        elif isinstance(item, str):
            allergens.append(Allergen(item, ""))
    return tuple(allergens)


def _parse_deadline(value: Any) -> _dt.datetime | None:
    """Parse ``casKonec`` (``"2026-09-14T15:00:00"``), tolerating anything odd."""
    if not value:
        return None
    try:
        return _dt.datetime.fromisoformat(str(value))
    except ValueError:
        return None


def is_placeholder(name: str, kind_label: str) -> bool:
    """True when a row is an unpublished slot rather than an actual meal.

    A slot is unpublished when it has no name, when its name is just the canteen's
    label for it (``nazev == druh_popis``, as documented in ``notes/README.md``), or
    when the name is a generic label such as ``"Oběd 3"``.
    """
    name = (name or "").strip()
    if not name:
        return True
    if name.casefold() == (kind_label or "").strip().casefold():
        return True
    return bool(_GENERIC_NAME_RE.match(name))


def _parse_meal(row: Mapping[str, Any], date: _dt.date) -> Meal:
    """Build a :class:`Meal` from one API row."""
    restrictions = _get(row, "omezeniObj", {}) or {}
    if not isinstance(restrictions, Mapping):
        restrictions = {}

    order_restriction = Restriction.from_api(_get(restrictions, "obj"))
    cancel_restriction = Restriction.from_api(_get(restrictions, "zm"))

    kind_code = str(_get(row, "druh"))
    kind_label = str(_get(row, "druh_popis"))

    return Meal(
        id=int(str(_get(row, "veta", "0")).strip() or 0),
        date=date,
        type=MealType.from_api(kind_code, kind_label),
        variant=kind_label,
        name=str(_get(row, "nazev")).strip(),
        price=_to_float(_get(row, "cena", 0)),
        ordered=_to_float(_get(row, "pocet", 0)) >= 1,
        can_order=order_restriction.allowed,
        can_cancel=cancel_restriction.allowed,
        order_restriction=order_restriction,
        cancel_restriction=cancel_restriction,
        allergens=_parse_allergens(row.get("alergeny")),
        deadline=_parse_deadline(_get(row, "casKonec", None)),
        raw=dict(row),
    )


def parse_menu(raw: Any) -> tuple[tuple[Day, ...], tuple[ParseWarning, ...]]:
    """Turn a raw ``objednavky`` response into days sorted by date.

    Nothing is dropped for being restricted or unorderable - restrictions are
    recorded on each meal instead, so filtering stays the caller's decision.
    Unpublished slots and rows without a usable id or date are left out, and each
    such row produces a :class:`ParseWarning`.

    Args:
        raw: The decoded ``objednavky`` response.

    Returns:
        A ``(days, warnings)`` pair.
    """
    warnings: list[ParseWarning] = []
    if not isinstance(raw, Mapping):
        return (), (ParseWarning(f"Menu response was {type(raw).__name__}, not an object"),)

    by_date: dict[_dt.date, list[Meal]] = {}
    day_codes: dict[_dt.date, str] = {}

    for table_key, rows in raw.items():
        if not str(table_key).startswith("table") or not isinstance(rows, list):
            continue

        for row in rows:
            if not isinstance(row, Mapping):
                warnings.append(ParseWarning(f"{table_key}: skipped a non-object row"))
                continue

            try:
                date = parse_api_date(str(_get(row, "datum")))
            except ValueError as exc:
                warnings.append(ParseWarning(f"{table_key}: {exc}"))
                continue

            day_code = str(_get(_get(row, "omezeniObj", {}) or {}, "den")).strip().upper()
            if day_code:
                day_codes[date] = day_code

            # A day the canteen does not cook on carries placeholder rows such as
            # "Nevaří se" or "Státní svátek"; keep the day, drop the fake meals.
            if DayStatus.from_api(day_code) is DayStatus.NO_SCHOOL:
                by_date.setdefault(date, [])
                continue

            if is_placeholder(str(_get(row, "nazev")), str(_get(row, "druh_popis"))):
                by_date.setdefault(date, [])
                continue

            try:
                meal = _parse_meal(row, date)
            except (TypeError, ValueError) as exc:
                warnings.append(
                    ParseWarning(f"{table_key}: skipped {_get(row, 'nazev')!r} - {exc}")
                )
                continue

            by_date.setdefault(date, []).append(meal)

    days = tuple(
        Day(date=date, meals=tuple(meals), day_code=day_codes.get(date, ""))
        for date, meals in sorted(by_date.items())
    )
    return days, tuple(warnings)
