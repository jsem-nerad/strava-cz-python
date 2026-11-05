"""Data types describing a canteen account and its menu."""

from __future__ import annotations

import datetime as _dt
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, NamedTuple

__all__ = [
    "Allergen",
    "Day",
    "DayStatus",
    "Meal",
    "MealType",
    "OrderResult",
    "Restriction",
    "User",
]

_DATE_RE = re.compile(r"(\d{1,2})\D(\d{1,2})\D(\d{4})")


def parse_api_date(value: str) -> _dt.date:
    """Parse a date as the Strava.cz API writes it (``"15.09.2026"``).

    The separator has been observed to vary between builds of the web app, so any
    non-digit is accepted between the parts.

    Raises:
        ValueError: If no ``day-month-year`` triple can be found in *value*.
    """
    match = _DATE_RE.search(value or "")
    if not match:
        raise ValueError(f"Unrecognised date from API: {value!r}")
    day, month, year = (int(part) for part in match.groups())
    return _dt.date(year, month, day)


def coerce_date(value: _dt.date | str) -> _dt.date:
    """Accept either a ``date`` or an ISO ``"YYYY-MM-DD"`` string."""
    if isinstance(value, _dt.date):
        return value
    return _dt.date.fromisoformat(value)


class MealType(Enum):
    """What kind of item this is on the menu.

    Derived from the API's short ``druh`` code (``"PO"``, ``"O1"`` ...), which is
    stable, rather than from the localised display text.
    """

    SOUP = "soup"
    MAIN = "main"
    UNKNOWN = "unknown"

    @classmethod
    def from_api(cls, kind_code: str, kind_label: str = "") -> MealType:
        """Classify a meal from its ``druh`` code, falling back to ``druh_popis``."""
        code = (kind_code or "").strip().upper()
        if code == "PO":
            return cls.SOUP
        if re.fullmatch(r"O\d+", code):
            return cls.MAIN
        label = (kind_label or "").casefold()
        if "polévka" in label or "polevka" in label or "soup" in label:
            return cls.SOUP
        if "oběd" in label or "obed" in label or "lunch" in label:
            return cls.MAIN
        return cls.UNKNOWN


class Restriction(Enum):
    """Why the canteen will not let you order or change a meal.

    The API reports this per meal in ``omezeniObj``: ``obj`` for ordering and ``zm``
    for changing an existing order. An empty string means "no restriction"; any other
    value is a single letter naming the reason.
    """

    NONE = ""
    CLOSED = "C"
    UNAVAILABLE = "I"
    NO_SCHOOL = "V"
    UNKNOWN = "?"

    @classmethod
    def from_api(cls, code: str | None) -> Restriction:
        """Map a raw ``omezeniObj`` letter onto a restriction, never raising."""
        try:
            return cls((code or "").strip().upper())
        except ValueError:
            return cls.UNKNOWN

    @property
    def allowed(self) -> bool:
        """True when this restriction does not block the action."""
        return self is Restriction.NONE

    @property
    def description(self) -> str:
        """A short explanation suitable for an error message."""
        return {
            Restriction.NONE: "allowed",
            Restriction.CLOSED: "the ordering deadline for this day has passed",
            Restriction.UNAVAILABLE: "this item cannot be ordered separately",
            Restriction.NO_SCHOOL: "the canteen does not cook on this day",
            Restriction.UNKNOWN: "the canteen reported an unrecognised restriction",
        }[self]


class DayStatus(Enum):
    """What the canteen says about a whole day, from ``omezeniObj.den``.

    Unlike :class:`Restriction`, this is a property of the *day*, not of a meal, and
    it never decides whether a meal can be ordered - that comes from ``obj``/``zm``.
    Reading orderability out of this code is exactly the bug 0.3.0 fixed.
    """

    NORMAL = ""
    NOT_AUTO_ORDERED = "T"
    NO_SCHOOL = "VP"
    CLOSED = "CO"
    UNKNOWN = "?"

    @classmethod
    def from_api(cls, code: str | None) -> DayStatus:
        """Map a raw ``omezeniObj.den`` value onto a status, never raising."""
        try:
            return cls((code or "").strip().upper())
        except ValueError:
            return cls.UNKNOWN

    @property
    def description(self) -> str:
        """A short explanation suitable for a display line."""
        return {
            DayStatus.NORMAL: "ordinary day",
            DayStatus.NOT_AUTO_ORDERED: "not ordered automatically",
            DayStatus.NO_SCHOOL: "the canteen does not cook on this day",
            DayStatus.CLOSED: "the ordering deadline for this day has passed",
            DayStatus.UNKNOWN: "the canteen reported an unrecognised day code",
        }[self]


class Allergen(NamedTuple):
    """One allergen listed for a meal."""

    code: str
    name: str

    def __str__(self) -> str:
        return f"{self.code} {self.name}".strip()


@dataclass(frozen=True, slots=True)
class Meal:
    """A single item on the menu.

    Attributes:
        id: Identifier used when ordering (the API's ``veta``). **Only valid for the
            login that fetched it**: the canteen numbers its whole menu afresh per
            session, so after logging in again the same number can be a different
            meal on a different day. Use :attr:`key` for anything that outlives a login.
        date: The day this meal is served on.
        type: Soup, main dish, or unknown.
        variant: The canteen's own label, e.g. ``"Oběd 1"``.
        name: What is actually being served.
        price: Price in the account's currency.
        ordered: Whether it is currently ordered.
        can_order: Whether it may be ordered right now.
        can_cancel: Whether an existing order may be cancelled right now.
        order_restriction: Why it cannot be ordered, when ``can_order`` is False.
        cancel_restriction: Why it cannot be cancelled, when ``can_cancel`` is False.
        allergens: Allergens declared for the meal.
        deadline: When ordering closes, if the API reported it.
        raw: The untouched API record, so nothing is ever lost.
        kind_code: The canteen's code for the meal's slot that day (the API's
            ``druh``), e.g. ``"O2"``. Part of :attr:`key`.
    """

    id: int
    date: _dt.date
    type: MealType
    variant: str
    name: str
    price: float
    ordered: bool
    can_order: bool
    can_cancel: bool
    order_restriction: Restriction
    cancel_restriction: Restriction
    allergens: tuple[Allergen, ...] = ()
    deadline: _dt.datetime | None = None
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)
    kind_code: str = ""

    @property
    def key(self) -> str:
        """A name for this meal that survives logging in again, e.g. ``"2026-11-09:O2"``.

        It is the day and the slot, so it keeps meaning the same place on the menu when
        :attr:`id` has moved. If the canteen republishes that slot with another dish, the
        key follows the slot: check :attr:`name` when the dish itself matters.
        """
        return f"{self.date.isoformat()}:{self.kind_code}"

    def __str__(self) -> str:
        status = "ordered" if self.ordered else "not ordered"
        if not self.can_order and not self.ordered:
            status = self.order_restriction.description
        return f"[{self.id}] {self.name} ({self.price:g}) - {status}"

    def __repr__(self) -> str:
        return (
            f"Meal(id={self.id}, date={self.date.isoformat()}, "
            f"type={self.type.name}, name={self.name!r}, ordered={self.ordered})"
        )


@dataclass(frozen=True, slots=True)
class Day:
    """All meals served on one day.

    Attributes:
        date: The day itself.
        meals: Every meal published for it, in the order the API returned them.
        day_code: The raw day-level ``omezeniObj.den`` value. :attr:`status` is the
            parsed form and is what you normally want.
    """

    date: _dt.date
    meals: tuple[Meal, ...]
    day_code: str = ""

    @property
    def status(self) -> DayStatus:
        """What the canteen says about this day as a whole."""
        return DayStatus.from_api(self.day_code)

    @property
    def no_school(self) -> bool:
        """True when the canteen does not cook on this day."""
        return self.status is DayStatus.NO_SCHOOL

    @property
    def auto_ordered(self) -> bool:
        """Whether the canteen's standing order covers this day.

        False on days the canteen marks ``"T"``. Their meals can still be ordered by
        hand - and :attr:`Meal.can_order` says so - they just never appear on their
        own, which is what an automatic ordering tool needs to know.
        """
        return self.status is not DayStatus.NOT_AUTO_ORDERED

    @property
    def ordered(self) -> bool:
        """True when at least one meal on this day is ordered."""
        return any(meal.ordered for meal in self.meals)

    @property
    def orderable(self) -> tuple[Meal, ...]:
        """The meals that can be ordered right now."""
        return tuple(meal for meal in self.meals if meal.can_order)

    def __iter__(self) -> Iterator[Meal]:
        return iter(self.meals)

    def __len__(self) -> int:
        return len(self.meals)

    def __str__(self) -> str:
        note = "" if self.status is DayStatus.NORMAL else f", {self.status.description}"
        return f"{self.date.isoformat()} ({len(self.meals)} meals{note})"


@dataclass(frozen=True, slots=True)
class OrderResult:
    """What actually happened during an ordering or cancelling run.

    Returned by :meth:`~strava_cz.Menu.order_meals` and
    :meth:`~strava_cz.Menu.cancel_meals` when ``continue_on_error=True``.

    Meals are reported the way the caller named them, by id or by key.

    Attributes:
        changed: Meals whose state was successfully changed.
        unchanged: Meals that already had the requested state, so nothing was sent.
        skipped: ``(meal, reason)`` for meals deliberately left out, e.g. duplicates.
        failed: ``(meal, error)`` for meals the canteen refused.
    """

    changed: tuple[int | str, ...] = ()
    unchanged: tuple[int | str, ...] = ()
    skipped: tuple[tuple[int | str, str], ...] = ()
    failed: tuple[tuple[int | str, Exception], ...] = ()

    @property
    def ok(self) -> bool:
        """True when nothing failed."""
        return not self.failed

    def __bool__(self) -> bool:
        return self.ok

    def __str__(self) -> str:
        bits = [f"{len(self.changed)} changed"]
        if self.unchanged:
            bits.append(f"{len(self.unchanged)} already set")
        if self.skipped:
            bits.append(f"{len(self.skipped)} skipped")
        if self.failed:
            bits.append(f"{len(self.failed)} failed")
        return ", ".join(bits)


@dataclass
class User:
    """The logged-in account.

    The password is deliberately not kept: it is used for the login request and then
    discarded.
    """

    username: str | None = None
    canteen_number: str | None = None
    full_name: str | None = None
    email: str | None = None
    balance: float = 0.0
    currency: str = "Kč"
    canteen_name: str | None = None
    id: str | None = None
    is_logged_in: bool = False
    sid: str | None = field(default=None, repr=False)
    s5url: str | None = field(default=None, repr=False)

    def reset(self) -> None:
        """Clear every field in place, so held references do not go stale."""
        for name, default in (
            ("username", None),
            ("canteen_number", None),
            ("full_name", None),
            ("email", None),
            ("balance", 0.0),
            ("currency", "Kč"),
            ("canteen_name", None),
            ("id", None),
            ("is_logged_in", False),
            ("sid", None),
            ("s5url", None),
        ):
            setattr(self, name, default)

    def __str__(self) -> str:
        if not self.is_logged_in:
            return "User(not logged in)"
        return (
            f"{self.full_name} ({self.username})\n"
            f"  Email:   {self.email}\n"
            f"  Balance: {self.balance:.2f} {self.currency}\n"
            f"  Canteen: {self.canteen_name}"
        )


def _as_sequence(value: Any) -> Sequence[Any]:
    """Return *value* as a sequence, tolerating the API's ``null`` for empty lists."""
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        return value
    return (value,)
