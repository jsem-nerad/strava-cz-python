"""The canteen menu: reading it, filtering it, and changing what is ordered."""

from __future__ import annotations

import datetime as _dt
import warnings
from collections.abc import Iterable, Iterator, Sequence
from typing import TYPE_CHECKING, Any

from .exceptions import (
    DuplicateMealError,
    MealNotFoundError,
    MealNotOrderableError,
    MenuNotFetchedError,
    StravaAPIError,
)
from .models import Day, DayStatus, Meal, MealType, OrderResult, coerce_date
from .parser import ParseWarning, parse_menu

if TYPE_CHECKING:  # pragma: no cover
    from .client import StravaCZ

__all__ = ["Menu"]


class Menu:
    """The published menu for the logged-in account.

    Reached as ``strava.menu``. Call :meth:`fetch` once to load it, then query it::

        strava.menu.fetch()
        for day in strava.menu:
            print(day.date, [meal.name for meal in day.meals])

        strava.menu.order_meals(3, 6)

    Unlike earlier versions, nothing is hidden for being restricted: every published
    meal is returned, and each one says whether it can be ordered
    (:attr:`Meal.can_order`) and why not (:attr:`Meal.order_restriction`). Days the
    canteen does not cook on are the one exception - pass ``include_no_school=True``
    to see those too.

    Days the canteen's standing order skips are *not* an exception: they are ordinary
    orderable days that simply never fill themselves in. :attr:`Day.auto_ordered` says
    which they are, and ``get_days(auto_ordered=True)`` is the filter an automatic
    ordering tool wants.
    """

    def __init__(self, client: StravaCZ) -> None:
        self._client = client
        self._days: tuple[Day, ...] | None = None
        self._by_id: dict[int, Meal] = {}
        self.raw_data: dict[str, Any] = {}
        self.parse_warnings: tuple[ParseWarning, ...] = ()

    # ------------------------------------------------------------------ loading

    def fetch(self) -> Menu:
        """Load the menu from the API and parse it.

        Returns:
            Self, so calls can be chained: ``days = strava.menu.fetch().get_days()``.

        Raises:
            NotLoggedInError: If no one is logged in.
            StravaAPIError: If the API request fails.
        """
        user = self._client.user
        payload = {
            "cislo": user.canteen_number,
            "sid": user.sid,
            "s5url": user.s5url,
            "lang": self._client.language,
            "konto": user.balance,
            "podminka": "",
            "ignoreCert": False,
        }
        self.raw_data = self._client._request("objednavky", payload, authenticated=True)
        self._days, self.parse_warnings = parse_menu(self.raw_data)
        self._by_id = {meal.id: meal for day in self._days for meal in day.meals}
        return self

    @property
    def fetched(self) -> bool:
        """Whether :meth:`fetch` has been called."""
        return self._days is not None

    @property
    def days(self) -> tuple[Day, ...]:
        """Every day in the menu, sorted, exactly as parsed.

        Raises:
            MenuNotFetchedError: If :meth:`fetch` has not been called.
        """
        if self._days is None:
            raise MenuNotFetchedError()
        return self._days

    @property
    def meals(self) -> tuple[Meal, ...]:
        """Every meal in the menu as a flat tuple."""
        return tuple(meal for day in self.days for meal in day.meals)

    def _reset(self) -> None:
        """Forget everything loaded, used when logging out."""
        self._days = None
        self._by_id = {}
        self.raw_data = {}
        self.parse_warnings = ()

    # ---------------------------------------------------------------- filtering

    def get_days(
        self,
        *,
        meal_types: Iterable[MealType] | None = None,
        orderable: bool | None = None,
        ordered: bool | None = None,
        auto_ordered: bool | None = None,
        date_from: _dt.date | str | None = None,
        date_to: _dt.date | str | None = None,
        include_no_school: bool = False,
    ) -> list[Day]:
        """Days matching the given filters, each holding only its matching meals.

        Every filter defaults to "no filtering", so ``get_days()`` returns the whole
        menu apart from days the canteen does not cook on.

        Args:
            meal_types: Keep only these kinds of meal, e.g. ``[MealType.MAIN]``.
            orderable: ``True`` for meals that can be ordered right now, ``False``
                for those that cannot, ``None`` for both.
            ordered: ``True`` for meals already ordered, ``False`` for the rest.
            auto_ordered: ``True`` for days the canteen's standing order covers,
                ``False`` for the days it skips (:attr:`Day.auto_ordered`). This
                filters whole days, not individual meals; the skipped days are still
                orderable by hand, which is why they are included by default.
            date_from: Earliest day to include, as a ``date`` or ``"YYYY-MM-DD"``.
            date_to: Latest day to include, inclusive.
            include_no_school: Also return days the canteen does not cook on. They
                hold no meals, so they only ever appear when this is ``True``.

        Returns:
            Days that still have at least one matching meal, sorted by date.
        """
        wanted_types = set(meal_types) if meal_types is not None else None
        start = coerce_date(date_from) if date_from is not None else None
        end = coerce_date(date_to) if date_to is not None else None

        result: list[Day] = []
        for day in self.days:
            if day.no_school and not include_no_school:
                continue
            if auto_ordered is not None and day.auto_ordered is not auto_ordered:
                continue
            if start is not None and day.date < start:
                continue
            if end is not None and day.date > end:
                continue

            meals = tuple(
                meal
                for meal in day.meals
                if (wanted_types is None or meal.type in wanted_types)
                and (orderable is None or meal.can_order is orderable)
                and (ordered is None or meal.ordered is ordered)
            )
            if not meals and not (day.no_school and include_no_school):
                continue
            result.append(Day(date=day.date, meals=meals, day_code=day.day_code))
        return result

    def get_meals(
        self,
        *,
        meal_types: Iterable[MealType] | None = None,
        orderable: bool | None = None,
        ordered: bool | None = None,
        auto_ordered: bool | None = None,
        date_from: _dt.date | str | None = None,
        date_to: _dt.date | str | None = None,
        include_no_school: bool = False,
    ) -> list[Meal]:
        """The same filtering as :meth:`get_days`, flattened into a list of meals."""
        return [
            meal
            for day in self.get_days(
                meal_types=meal_types,
                orderable=orderable,
                ordered=ordered,
                auto_ordered=auto_ordered,
                date_from=date_from,
                date_to=date_to,
                include_no_school=include_no_school,
            )
            for meal in day.meals
        ]

    def get_by_id(self, meal_id: int) -> Meal | None:
        """The meal with this id, or ``None`` if the menu holds no such meal."""
        if self._days is None:
            raise MenuNotFetchedError()
        return self._by_id.get(int(meal_id))

    def get_by_date(self, date: _dt.date | str) -> Day | None:
        """The day for this date, or ``None`` if the menu does not cover it.

        Args:
            date: A ``datetime.date`` or an ISO string such as ``"2026-09-15"``.
        """
        wanted = coerce_date(date)
        for day in self.days:
            if day.date == wanted:
                return day
        return None

    def is_ordered(self, meal_id: int) -> bool:
        """Whether this meal is currently ordered.

        Raises:
            MealNotFoundError: If the menu holds no meal with this id.
        """
        meal = self.get_by_id(meal_id)
        if meal is None:
            raise MealNotFoundError(meal_id)
        return meal.ordered

    def _require(self, meal_id: int) -> Meal:
        meal = self.get_by_id(meal_id)
        if meal is None:
            raise MealNotFoundError(meal_id)
        return meal

    # ----------------------------------------------------------------- ordering

    def order_meals(
        self,
        *meal_ids: int,
        continue_on_error: bool = False,
        strict_duplicates: bool = False,
    ) -> OrderResult:
        """Order one or more meals and save the changes in a single transaction.

        Meals already ordered are left alone. If nothing needs changing, no request
        is sent at all.

        Args:
            *meal_ids: Ids from the fetched menu, as shown by :meth:`print`.
            continue_on_error: Order everything that can be ordered and report the
                rest in the returned :class:`~strava_cz.models.OrderResult` instead
                of raising. When ``False`` (the default) the first failure rolls back
                every staged change and raises.
            strict_duplicates: Raise :class:`DuplicateMealError` when two of the
                requested meals compete for the same slot (same day, same kind).
                When ``False`` the first one wins and the rest are skipped with a
                warning.

        Returns:
            An :class:`~strava_cz.models.OrderResult` describing what happened.

        Raises:
            MealNotFoundError: If an id is not in the fetched menu.
            MealNotOrderableError: If the canteen does not allow ordering a meal.
            InsufficientBalanceError: If the account cannot cover an order.
            DuplicateMealError: See ``strict_duplicates``.
            StravaAPIError: If the API refuses a request.
        """
        return self._change_orders(
            meal_ids,
            ordered=True,
            continue_on_error=continue_on_error,
            strict_duplicates=strict_duplicates,
        )

    def cancel_meals(
        self,
        *meal_ids: int,
        continue_on_error: bool = False,
    ) -> OrderResult:
        """Cancel one or more orders and save the changes in a single transaction.

        Meals that are not ordered are left alone, and if nothing needs changing no
        request is sent.

        Args:
            *meal_ids: Ids from the fetched menu.
            continue_on_error: Cancel what can be cancelled and report the rest
                instead of raising.

        Returns:
            An :class:`~strava_cz.models.OrderResult` describing what happened.

        Raises:
            MealNotFoundError: If an id is not in the fetched menu.
            MealNotOrderableError: If the canteen does not allow cancelling a meal.
            StravaAPIError: If the API refuses a request.
        """
        return self._change_orders(
            meal_ids,
            ordered=False,
            continue_on_error=continue_on_error,
            strict_duplicates=False,
        )

    def _change_orders(
        self,
        meal_ids: Sequence[int],
        *,
        ordered: bool,
        continue_on_error: bool,
        strict_duplicates: bool,
    ) -> OrderResult:
        """Shared body of :meth:`order_meals` and :meth:`cancel_meals`."""
        action = "order" if ordered else "cancel"
        changed: list[int] = []
        unchanged: list[int] = []
        skipped: list[tuple[int, str]] = []
        failed: list[tuple[int, Exception]] = []

        # 1. Resolve ids and check the canteen allows the change at all.
        planned: list[Meal] = []
        for meal_id in dict.fromkeys(int(i) for i in meal_ids):  # de-duplicate, keep order
            try:
                meal = self._require(meal_id)
                if meal.ordered is ordered:
                    unchanged.append(meal_id)
                    continue
                allowed = meal.can_order if ordered else meal.can_cancel
                if not allowed:
                    reason = meal.order_restriction if ordered else meal.cancel_restriction
                    raise MealNotOrderableError(meal_id, reason, action)
                planned.append(meal)
            except (MealNotFoundError, MealNotOrderableError) as exc:
                if not continue_on_error:
                    raise
                failed.append((meal_id, exc))

        # 2. Two meals of the same kind on the same day compete for one slot.
        if ordered:
            planned, dupes = self._resolve_duplicates(planned, strict_duplicates)
            skipped.extend(dupes)

        # 3. Nothing to do means nothing to send.
        if not planned:
            return OrderResult(tuple(changed), tuple(unchanged), tuple(skipped), tuple(failed))

        # 4. Stage each change, then commit them all at once.
        staged: list[int] = []
        try:
            for meal in planned:
                try:
                    self._stage(meal.id, ordered)
                    staged.append(meal.id)
                except StravaAPIError as exc:
                    if not continue_on_error:
                        raise
                    failed.append((meal.id, exc))

            if not staged:
                self._discard_staged_changes()
                return OrderResult(tuple(changed), tuple(unchanged), tuple(skipped), tuple(failed))

            self._save()
        except StravaAPIError:
            self._rollback()
            raise

        # 5. Confirm against a fresh copy of the menu rather than trusting the write.
        self.fetch()
        for meal_id in staged:
            refreshed = self.get_by_id(meal_id)
            if refreshed is not None and refreshed.ordered is ordered:
                changed.append(meal_id)
                continue
            error = StravaAPIError(
                f"The canteen accepted the request but meal {meal_id} is still "
                f"{'not ordered' if ordered else 'ordered'}"
            )
            if not continue_on_error:
                raise error
            failed.append((meal_id, error))

        return OrderResult(tuple(changed), tuple(unchanged), tuple(skipped), tuple(failed))

    def _resolve_duplicates(
        self, planned: list[Meal], strict: bool
    ) -> tuple[list[Meal], list[tuple[int, str]]]:
        """Keep one meal per (day, kind) slot; skip or reject the rest."""
        kept: list[Meal] = []
        skipped: list[tuple[int, str]] = []
        claimed: dict[tuple[_dt.date, MealType], int] = {}

        for meal in planned:
            slot = (meal.date, meal.type)
            if slot in claimed:
                message = (
                    f"meal {meal.id} competes with meal {claimed[slot]} for the same slot "
                    f"({meal.date.isoformat()}, {meal.type.value})"
                )
                if strict:
                    raise DuplicateMealError(
                        f"Cannot order two meals of the same kind on one day: {message}"
                    )
                warnings.warn(f"Skipping {message}", stacklevel=4)
                skipped.append((meal.id, message))
                continue
            claimed[slot] = meal.id
            kept.append(meal)
        return kept, skipped

    def _rollback(self) -> None:
        """Undo staged changes and reload, without masking the original error."""
        try:
            self._discard_staged_changes()
            self.fetch()
        except StravaAPIError:  # pragma: no cover - best effort only
            pass

    # -------------------------------------------------------------- API actions

    def _stage(self, meal_id: int, ordered: bool) -> Any:
        """Tick or untick one meal. Not saved until :meth:`_save` is called."""
        user = self._client.user
        response = self._client._request(
            "pridejJidloS5",
            {
                "cislo": user.canteen_number,
                "sid": user.sid,
                "url": user.s5url,
                "veta": str(meal_id),
                "pocet": "1" if ordered else "0",
                "lang": self._client.language,
                "ignoreCert": "false",
            },
            authenticated=True,
        )
        self._client._update_balance(response)
        return response

    def _save(self) -> Any:
        """Commit every staged change."""
        user = self._client.user
        response = self._client._request(
            "saveOrders",
            {
                "cislo": user.canteen_number,
                "sid": user.sid,
                "url": user.s5url,
                "xml": None,
                "lang": self._client.language,
                "ignoreCert": "false",
            },
            authenticated=True,
        )
        self._client._update_balance(response)
        return response

    def _discard_staged_changes(self) -> Any:
        """Reload the canteen's state, discarding anything staged but not saved."""
        user = self._client.user
        response = self._client._request(
            "nactiVlastnostiPA",
            {
                "sid": user.sid,
                "url": user.s5url,
                "cislo": user.canteen_number,
                "ignoreCert": "false",
                "lang": self._client.language,
                "getText": True,
                "checkVersion": True,
                "resetTables": True,
                "frontendFunction": "refreshInformations",
            },
            authenticated=True,
        )
        self._client._update_balance(response)
        return response

    # ------------------------------------------------------------------ display

    def print(self, **filters: Any) -> None:
        """Print the menu in a readable form.

        Args:
            **filters: Any keyword accepted by :meth:`get_days`, e.g.
                ``menu.print(orderable=True)``.
        """
        days = self.get_days(**filters)
        if not days:
            print("(no meals match)")
            return

        currency = self._client.user.currency
        for day in days:
            note = "" if day.status is DayStatus.NORMAL else f"  [{day.status.description}]"
            print(f"{day.date:%a %d.%m.%Y}{note}")
            for meal in day.meals:
                if meal.ordered:
                    mark = "[x]"
                elif meal.can_order:
                    mark = "[ ]"
                else:
                    mark = "[-]"
                line = f"  {mark} {meal.id:>4}  {meal.variant:<12} {meal.name}"
                if meal.price:
                    line += f"  ({meal.price:g} {currency})"
                if not meal.can_order and not meal.ordered:
                    line += f"  - {meal.order_restriction.description}"
                print(line)
            print()

    # ----------------------------------------------------------- container API

    def __iter__(self) -> Iterator[Day]:
        return iter(self.get_days())

    def __len__(self) -> int:
        return len(self.get_days())

    def __getitem__(self, key: Any) -> Any:
        return self.get_days()[key]

    def __contains__(self, meal_id: object) -> bool:
        return isinstance(meal_id, int) and meal_id in self._by_id

    def __repr__(self) -> str:
        if self._days is None:
            return "Menu(not fetched)"
        days = self.get_days()
        meals = sum(len(day.meals) for day in days)
        orderable = sum(1 for day in days for meal in day.meals if meal.can_order)
        return f"Menu(days={len(days)}, meals={meals}, orderable={orderable})"
