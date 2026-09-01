"""Rendering for the command line: a readable table, or JSON for other programs.

Every command hands :class:`Output` both a JSON payload and a function that draws the
same thing for a human, and the chosen format decides which one is used. Keeping the
two next to each other in the command is what stops them drifting apart.

Only the standard library is used, so ``pip install strava-cz`` is enough to get the
command working.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import shutil
import sys
from collections.abc import Callable, Iterable, Sequence
from typing import Any, TextIO

from ..models import Day, Meal, OrderResult, User

__all__ = ["Output", "meal_to_json", "day_to_json", "user_to_json", "result_to_json"]

#: Glyphs for a meal's state. Deliberately ASCII-adjacent so they survive a plain
#: terminal, a pipe and a log file.
MARK_ORDERED = "✓"  # check mark
MARK_ORDERABLE = "○"  # open circle
MARK_BLOCKED = "·"  # middle dot

#: Never squeeze a meal name below this, however narrow the terminal.
NAME_MIN = 12


class Palette:
    """ANSI codes, or empty strings when colour is off.

    Written as attributes rather than a function so a caller cannot forget the reset.
    """

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def _wrap(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.enabled and text else text

    def bold(self, text: str) -> str:
        return self._wrap("1", text)

    def dim(self, text: str) -> str:
        return self._wrap("2", text)

    def green(self, text: str) -> str:
        return self._wrap("32", text)

    def yellow(self, text: str) -> str:
        return self._wrap("33", text)

    def red(self, text: str) -> str:
        return self._wrap("31", text)

    def cyan(self, text: str) -> str:
        return self._wrap("36", text)


def want_color(choice: str, stream: TextIO) -> bool:
    """Decide whether to emit ANSI codes.

    ``auto`` means "only for a terminal": a redirect, a pipe or a cron job gets plain
    text. ``NO_COLOR`` is honoured for ``auto`` and, as the convention says, cannot be
    overridden except by asking for colour explicitly.
    """
    if choice == "always":
        return True
    if choice == "never":
        return False
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError):
        return False


# --------------------------------------------------------------------- JSON shapes


def meal_to_json(meal: Meal, currency: str = "") -> dict[str, Any]:
    """One meal, with the same field names the library uses.

    Enums become their lower-case names rather than the canteen's raw letters, so a
    consumer reads ``"closed"`` instead of having to know that ``"C"`` means that.
    """
    data: dict[str, Any] = {
        "id": meal.id,
        "date": meal.date.isoformat(),
        "type": meal.type.value,
        "variant": meal.variant,
        "name": meal.name,
        "price": meal.price,
        "ordered": meal.ordered,
        "can_order": meal.can_order,
        "can_cancel": meal.can_cancel,
        "order_restriction": meal.order_restriction.name.lower(),
        "cancel_restriction": meal.cancel_restriction.name.lower(),
        "allergens": [{"code": a.code, "name": a.name} for a in meal.allergens],
        "deadline": meal.deadline.isoformat() if meal.deadline else None,
    }
    if currency:
        data["currency"] = currency
    return data


def day_to_json(day: Day, currency: str = "") -> dict[str, Any]:
    """One day and its meals."""
    return {
        "date": day.date.isoformat(),
        "weekday": day.date.strftime("%A").lower(),
        "status": day.status.name.lower(),
        "day_code": day.day_code,
        "no_school": day.no_school,
        "auto_ordered": day.auto_ordered,
        "ordered": day.ordered,
        "meals": [meal_to_json(meal, currency) for meal in day.meals],
    }


def user_to_json(user: User) -> dict[str, Any]:
    """The logged-in account. Never includes the session id or the password."""
    return {
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "canteen_number": user.canteen_number,
        "canteen_name": user.canteen_name,
        "balance": user.balance,
        "currency": user.currency,
    }


def result_to_json(result: OrderResult) -> dict[str, Any]:
    """What an order or cancel run actually did."""
    return {
        "ok": result.ok,
        "changed": list(result.changed),
        "unchanged": list(result.unchanged),
        "skipped": [{"id": mid, "reason": reason} for mid, reason in result.skipped],
        "failed": [
            {"id": mid, "error": type(exc).__name__, "message": str(exc)}
            for mid, exc in result.failed
        ],
    }


def error_to_json(exc: BaseException) -> dict[str, Any]:
    """An error, shaped so a wrapper can branch on it without parsing prose."""
    error: dict[str, Any] = {"type": type(exc).__name__, "message": str(exc)}
    for attr in ("meal_id", "code", "status_code"):
        value = getattr(exc, attr, None)
        if value is not None:
            error[attr] = value
    reason = getattr(exc, "reason", None)
    if reason is not None:
        error["reason"] = getattr(reason, "name", str(reason)).lower()
    return error


# -------------------------------------------------------------------------- Output


class Output:
    """Where a command's result goes, in the format the user asked for.

    Args:
        fmt: ``"pretty"`` or ``"json"``.
        color: ``"auto"``, ``"always"`` or ``"never"``.
        stream: Where results go. Everything else goes to *err*, so ``--format json``
            keeps stdout parseable even when there are warnings.
        err: Where notes, warnings and progress go.
    """

    def __init__(
        self,
        fmt: str = "pretty",
        color: str = "auto",
        stream: TextIO | None = None,
        err: TextIO | None = None,
    ) -> None:
        self.fmt = fmt
        self.stream = stream if stream is not None else sys.stdout
        self.err = err if err is not None else sys.stderr
        self.c = Palette(want_color(color, self.stream))
        self._err_c = Palette(want_color(color, self.err))

    @property
    def json_mode(self) -> bool:
        return self.fmt == "json"

    @property
    def width(self) -> int:
        """Usable terminal width, clamped so a very narrow window still lines up."""
        try:
            return max(48, min(shutil.get_terminal_size((80, 24)).columns, 160))
        except OSError:  # pragma: no cover - only on very odd terminals
            return 80

    # ------------------------------------------------------------------- emitting

    def emit(self, command: str, data: dict[str, Any], render: Callable[[], None]) -> None:
        """Write one command's result: JSON payload, or *render* for a human."""
        if self.json_mode:
            self._dump({"ok": True, "command": command, **data})
        else:
            render()

    def fail(self, command: str, exc: BaseException) -> None:
        """Report a failure in whichever format is in force."""
        if self.json_mode:
            self._dump({"ok": False, "command": command, "error": error_to_json(exc)})
        else:
            print(f"{self._err_c.red('error:')} {exc}", file=self.err)

    def _dump(self, payload: dict[str, Any]) -> None:
        json.dump(payload, self.stream, ensure_ascii=False, indent=2, default=str)
        self.stream.write("\n")

    def dump(self, payload: Any) -> None:
        """Write arbitrary JSON, for commands whose output *is* JSON either way."""
        self._dump(payload)

    def line(self, text: str = "") -> None:
        """A line of human output. Suppressed in JSON mode."""
        if not self.json_mode:
            print(text, file=self.stream)

    def note(self, text: str) -> None:
        """A diagnostic. Always stderr, so it never pollutes JSON on stdout."""
        print(text, file=self.err)

    def warn(self, text: str) -> None:
        print(f"{self._err_c.yellow('warning:')} {text}", file=self.err)

    # -------------------------------------------------------------- menu rendering

    def render_days(
        self,
        days: Sequence[Day],
        *,
        currency: str = "",
        show_allergens: bool = False,
        balance: float | None = None,
    ) -> None:
        """Print days and their meals as an aligned, optionally coloured table."""
        if not days:
            self.line(self.c.dim("(no meals match)"))
            return

        for index, day in enumerate(days):
            if index:
                self.line()
            self.line(self._day_header(day))
            for meal in day.meals:
                self.line(self._meal_line(meal, currency))
                if show_allergens and meal.allergens:
                    allergens = ", ".join(str(a) for a in meal.allergens)
                    self.line(self.c.dim(f"{'':>13}{allergens}"))
            if not day.meals:
                self.line(self.c.dim(f"{'':>4}(nothing published)"))

        self.line()
        self.line(self._summary(days, currency, balance))

    def _day_header(self, day: Day) -> str:
        header = self.c.bold(f"{day.date:%a %d.%m.%Y}")
        if day.no_school:
            return f"{header}  {self.c.dim('no school')}"
        if not day.auto_ordered:
            return f"{header}  {self.c.yellow('not ordered automatically')}"
        return header

    def _meal_line(self, meal: Meal, currency: str) -> str:
        if meal.ordered:
            mark = self.c.green(MARK_ORDERED)
        elif meal.can_order:
            mark = MARK_ORDERABLE
        else:
            mark = self.c.dim(MARK_BLOCKED)

        blocked = not meal.can_order and not meal.ordered
        trailer = (
            meal.order_restriction.description
            if blocked
            else (f"{meal.price:g} {currency}".strip() if meal.price else "")
        )

        # Widths: 2 indent + mark + 2 + id(4) + 2 + variant(10) + 1 + name + trailer.
        # The name keeps at least NAME_MIN characters; a long restriction is clipped
        # rather than pushing the line past the terminal.
        fixed = 2 + 1 + 2 + 4 + 2 + 10 + 1
        trailer = _clip(trailer, max(0, self.width - fixed - NAME_MIN - 2))
        room = max(1, self.width - fixed - len(trailer) - 2)
        name = _clip(meal.name, room)

        left = f"  {mark}  {meal.id:>4}  {_clip(meal.variant, 10):<10} {name}"
        if not trailer:
            return left
        padding = max(1, self.width - _visible_len(left) - len(trailer))
        return f"{left}{' ' * padding}{self.c.dim(trailer) if blocked else trailer}"

    def _summary(self, days: Sequence[Day], currency: str, balance: float | None) -> str:
        """One line of totals, shortened rather than wrapped on a narrow terminal."""
        meals = [meal for day in days for meal in day.meals]
        counts = [
            f"{len(days)} day{'s' if len(days) != 1 else ''}",
            f"{len(meals)} meal{'s' if len(meals) != 1 else ''}",
            f"{sum(1 for m in meals if m.can_order)} orderable",
            f"{sum(1 for m in meals if m.ordered)} ordered",
        ]
        money = f"{balance:.2f} {currency}".strip() if balance is not None else ""

        full = " · ".join(counts + ([f"balance {money}"] if money else []))
        if len(full) <= self.width:
            return self.c.dim(full)
        # Drop the day count and the "balance" label before letting the line wrap.
        short = " · ".join(counts[1:] + ([money] if money else []))
        return self.c.dim(_clip(short, self.width))

    def render_meals(self, meals: Iterable[Meal], *, currency: str = "") -> None:
        """A flat one-line-per-meal listing, for ``ordered`` and dry runs."""
        rows = list(meals)
        if not rows:
            self.line(self.c.dim("(nothing)"))
            return
        for meal in rows:
            price = f"{meal.price:g} {currency}".strip() if meal.price else ""
            left = f"  {meal.id:>4}  {meal.date:%a %d.%m.}  {_clip(meal.variant, 10):<10} "
            room = max(NAME_MIN, self.width - len(left) - len(price) - 2)
            left += _clip(meal.name, room)
            if not price:
                self.line(left)
                continue
            padding = max(1, self.width - len(left) - len(price))
            self.line(f"{left}{' ' * padding}{price}")

    def render_result(self, result: OrderResult, action: str, currency: str = "") -> None:
        """Summarise what an order or cancel run did."""
        verb = "ordered" if action == "order" else "cancelled"
        if result.changed:
            ids = ", ".join(str(i) for i in result.changed)
            self.line(self.c.green(f"{verb} {len(result.changed)}: {ids}"))
        for meal_id in result.unchanged:
            self.line(self.c.dim(f"  {meal_id}: already {verb}, nothing sent"))
        for meal_id, reason in result.skipped:
            self.line(self.c.yellow(f"  {meal_id}: skipped - {reason}"))
        for meal_id, exc in result.failed:
            self.line(self.c.red(f"  {meal_id}: {exc}"))
        if not any((result.changed, result.unchanged, result.skipped, result.failed)):
            self.line(self.c.dim("nothing to do"))

    def render_user(self, user: User) -> None:
        """The account, as a small aligned block."""
        rows = [
            ("Name", user.full_name or "-"),
            ("Username", user.username or "-"),
            ("Email", user.email or "-"),
            ("Canteen", f"{user.canteen_name or '-'} ({user.canteen_number})"),
            ("Balance", f"{user.balance:.2f} {user.currency}"),
        ]
        for label, value in rows:
            self.line(f"{self.c.dim(label + ':'):<20} {value}")


def _visible_len(text: str) -> int:
    """Length of *text* as the terminal sees it, ignoring ANSI escapes."""
    length = 0
    in_escape = False
    for char in text:
        if in_escape:
            in_escape = char != "m"
            continue
        if char == "\033":
            in_escape = True
            continue
        length += 1
    return length


def _clip(text: str, width: int) -> str:
    """Shorten *text* to *width*, marking that something was cut."""
    text = text or ""
    if len(text) <= width:
        return text
    return text[: max(1, width - 1)].rstrip() + "…"


def parse_date(value: str, today: _dt.date | None = None) -> _dt.date:
    """Parse a date from the command line.

    Accepts ISO ``YYYY-MM-DD`` plus the words ``today``, ``tomorrow`` and
    ``yesterday``, because typing today's date to see today's lunch is silly.

    Raises:
        ValueError: If *value* is neither.
    """
    today = today or _dt.date.today()
    word = value.strip().lower()
    if word in ("today", "dnes"):
        return today
    if word in ("tomorrow", "zitra"):
        return today + _dt.timedelta(days=1)
    if word in ("yesterday", "vcera"):
        return today - _dt.timedelta(days=1)
    try:
        return _dt.date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"not a date: {value!r} (use YYYY-MM-DD, today or tomorrow)") from None
