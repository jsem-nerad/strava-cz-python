"""The canteen menu: reading it, filtering it, and changing what is ordered."""

from __future__ import annotations

import contextlib
import datetime as _dt
import warnings
from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from typing import TYPE_CHECKING, Any

from .exceptions import (
    AuthenticationError,
    DuplicateMealError,
    MealNotFoundError,
    MealNotOrderableError,
    MenuNotFetchedError,
    OrderNotConfirmedError,
    StravaAPIError,
)
from .models import Day, DayStatus, Meal, MealType, OrderResult, coerce_date
from .parser import ParseWarning, parse_menu

if TYPE_CHECKING:  # pragma: no cover
    from .client import StravaCZ

__all__ = ["Menu"]


def _normal_ref(ref: int | str) -> int | str:
    """One spelling per meal: a number as an int, a key stripped and upper-case."""
    if isinstance(ref, str):
        text = ref.strip().upper()
        return int(text) if text.isdigit() else text
    return int(ref)


def _index_by_key(days: Iterable[Day]) -> tuple[dict[str, Meal], tuple[ParseWarning, ...]]:
    """Map each :attr:`Meal.key` to its meal, leaving out any key that can't name just one.

    A meal with no slot code, or sharing its key with another, stays out of the index, so
    asking for it finds nothing rather than a guess that could order the wrong one. Each
    one gets a warning, because "not found" alone would hide the reason.
    """
    meals = [meal for day in days for meal in day.meals]
    counts = Counter(meal.key for meal in meals)
    index: dict[str, Meal] = {}
    problems: list[ParseWarning] = []
    for meal in meals:
        if meal.kind_code and counts[meal.key] == 1:
            index[meal.key] = meal
        else:
            problems.append(
                ParseWarning(
                    f"{meal.name!r} cannot be named by {meal.key!r}: the canteen gave it no "
                    "slot code, or gave the same one to another meal that day"
                )
            )
    return index, tuple(problems)


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

    Meals can be named two ways. :attr:`Meal.id` is the canteen's own number. It is only
    good until the canteen next renumbers the menu, which it does at every login and at
    every reset of the session, including the one that rolls back a failed order.
    :attr:`Meal.key` is the day and slot (``"2026-11-09:O2"``), which means the same thing
    in every session. Anything that outlives one fetch should use the key.
    """

    def __init__(self, client: StravaCZ) -> None:
        self._client = client
        self._days: tuple[Day, ...] | None = None
        self._by_id: dict[int, Meal] = {}
        self._by_key: dict[str, Meal] = {}
        self.raw_data: dict[str, Any] = {}
        self.parse_warnings: tuple[ParseWarning, ...] = ()
        #: The canteen renumbered the menu and the caller hasn't fetched since.
        self._numbers_moved = False
        #: A reset failed, so the session may still hold staged changes.
        self._reset_owed = False

    # ------------------------------------------------------------------ loading

    def fetch(self) -> Menu:
        """Load this login's copy of the menu and parse it.

        The canteen gives each login its own copy of the orders, taken when it logged in,
        so this doesn't show what another session has changed since: an order placed in
        the app meanwhile, say. Log in again to see that.

        Returns:
            Self, so calls can be chained: ``days = strava.menu.fetch().get_days()``.

        Raises:
            NotLoggedInError: If no one is logged in.
            StravaAPIError: If the API request fails.
        """
        if self._reset_owed:
            self._discard_staged_changes()
            self._reset_owed = False
        self._load()
        self._numbers_moved = False
        return self

    def _load(self) -> None:
        """Read the menu without telling the caller its numbers are good again."""
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
        self._days, parse_warnings = parse_menu(self.raw_data)
        self._by_id = {meal.id: meal for day in self._days for meal in day.meals}
        self._by_key, key_warnings = _index_by_key(self._days)
        self.parse_warnings = parse_warnings + key_warnings

    def _resync(self) -> None:
        """Drop the session's copy of the orders and read the canteen's records.

        The reset this needs also renumbers the menu, so whatever was loaded before it
        goes first: if a step here fails there are no old numbers left that could order
        another meal. Numbers the caller got earlier stay refused until they fetch.

        Raises:
            StravaAPIError: If either request fails. The menu is then not fetched.
        """
        self._forget()
        self._numbers_moved = True
        self._reset_owed = True
        self._discard_staged_changes()
        self._reset_owed = False
        self._load()

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
        """Forget everything about this login, used when logging out."""
        self._forget()
        self._numbers_moved = False
        self._reset_owed = False

    def _forget(self) -> None:
        """Forget the loaded menu, when it may no longer be true."""
        self._days = None
        self._by_id = {}
        self._by_key = {}
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
        """The meal with this id, or ``None`` if the menu holds no such meal.

        Raises:
            MenuNotFetchedError: If the menu isn't fetched, or the canteen has renumbered
                it since the last :meth:`fetch`, when a number could mean another meal.
        """
        if self._days is None:
            raise MenuNotFetchedError()
        if self._numbers_moved:
            raise MenuNotFetchedError(
                "The canteen renumbered the menu when the session was reset, so this number "
                "may be another meal now. Call menu.fetch() again, or use Meal.key"
            )
        return self._by_id.get(int(meal_id))

    def get_by_key(self, key: str) -> Meal | None:
        """The meal with this :attr:`Meal.key`, or ``None`` if no single meal has it.

        A key two meals share is treated as not found rather than guessed at, so it can
        never put an order on the wrong one. :attr:`parse_warnings` says which those are.
        """
        if self._days is None:
            raise MenuNotFetchedError()
        return self._by_key.get(key.strip().upper())

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

    def is_ordered(self, meal_id: int | str) -> bool:
        """Whether this meal, given by id or key, is currently ordered.

        Raises:
            MealNotFoundError: If the menu holds no such meal.
        """
        return self._require(meal_id).ordered

    def _find(self, ref: int | str) -> Meal | None:
        """Look a meal up by key, or by id when given a number."""
        normal = _normal_ref(ref)
        return self.get_by_key(normal) if isinstance(normal, str) else self.get_by_id(normal)

    def _require(self, ref: int | str) -> Meal:
        meal = self._find(ref)
        if meal is None:
            raise MealNotFoundError(_normal_ref(ref))
        return meal

    # ----------------------------------------------------------------- ordering

    def order_meals(
        self,
        *meals: int | str,
        continue_on_error: bool = False,
        strict_duplicates: bool = False,
        verify_saved: bool = False,
    ) -> OrderResult:
        """Order one or more meals and save the changes in a single transaction.

        Meals already ordered are left alone. If nothing needs changing, no request
        is sent at all.

        Args:
            *meals: Each one a :attr:`Meal.key`, or a :attr:`Meal.id` from this login's
                fetched menu, as shown by :meth:`print`.
            continue_on_error: Order everything that can be ordered and report the
                rest in the returned :class:`~strava_cz.models.OrderResult` instead
                of raising. When ``False`` (the default) the first failure rolls back
                every staged change and raises.
            strict_duplicates: Raise :class:`DuplicateMealError` when two of the
                requested meals compete for the same slot (same day, same kind).
                When ``False`` the first one wins and the rest are skipped with a
                warning.
            verify_saved: Check the result against the canteen's records. By default it
                is checked against this login's own copy, which already shows staged
                changes, so it can't tell a save that did nothing. This costs one more
                request and renumbers the menu, so :attr:`Meal.id` values read earlier
                stop working until the next :meth:`fetch`. :attr:`Meal.key` values don't.

        Returns:
            An :class:`~strava_cz.models.OrderResult` describing what happened.

        Raises:
            MealNotFoundError: If a meal is not in the fetched menu.
            MealNotOrderableError: If the canteen does not allow ordering a meal.
            InsufficientBalanceError: If the account cannot cover an order.
            DuplicateMealError: See ``strict_duplicates``.
            MenuNotFetchedError: If the menu isn't fetched, or a failed read-back forgot it.
            OrderNotConfirmedError: If a change may have been saved but can't be confirmed,
                or was accepted and didn't happen. Raised even with ``continue_on_error``
                when the whole batch is in doubt. Check the menu before trying again.
            StravaAPIError: If the API refuses a request. Nothing was saved.
        """
        return self._change_orders(
            meals,
            ordered=True,
            continue_on_error=continue_on_error,
            strict_duplicates=strict_duplicates,
            verify_saved=verify_saved,
        )

    def cancel_meals(
        self,
        *meals: int | str,
        continue_on_error: bool = False,
        verify_saved: bool = False,
    ) -> OrderResult:
        """Cancel one or more orders and save the changes in a single transaction.

        Meals that are not ordered are left alone, and if nothing needs changing no
        request is sent.

        Args:
            *meals: Each one a :attr:`Meal.key`, or a :attr:`Meal.id` from this login's
                fetched menu.
            continue_on_error: Cancel what can be cancelled and report the rest
                instead of raising.
            verify_saved: Check the result against the canteen's records rather than
                this login's copy. See :meth:`order_meals`.

        Returns:
            An :class:`~strava_cz.models.OrderResult` describing what happened.

        Raises:
            MealNotFoundError: If a meal is not in the fetched menu.
            MealNotOrderableError: If the canteen does not allow cancelling a meal.
            MenuNotFetchedError: If the menu isn't fetched, or a failed read-back forgot it.
            OrderNotConfirmedError: If a change may have been saved but can't be confirmed,
                or was accepted and didn't happen. Raised even with ``continue_on_error``
                when the whole batch is in doubt. Check the menu before trying again.
            StravaAPIError: If the API refuses a request. Nothing was saved.
        """
        return self._change_orders(
            meals,
            ordered=False,
            continue_on_error=continue_on_error,
            strict_duplicates=False,
            verify_saved=verify_saved,
        )

    def _change_orders(
        self,
        refs: Sequence[int | str],
        *,
        ordered: bool,
        continue_on_error: bool,
        strict_duplicates: bool,
        verify_saved: bool,
    ) -> OrderResult:
        """Shared body of :meth:`order_meals` and :meth:`cancel_meals`.

        Results name each meal the way the caller did, whether that was an id or a key.
        """
        action = "order" if ordered else "cancel"
        changed: list[int | str] = []
        unchanged: list[int | str] = []
        skipped: list[tuple[int | str, str]] = []
        failed: list[tuple[int | str, Exception]] = []

        # 1. Resolve each meal and check the canteen allows the change at all.
        planned: list[tuple[int | str, Meal]] = []
        already: list[tuple[int | str, Meal]] = []
        seen: set[int] = set()
        for ref in dict.fromkeys(_normal_ref(r) for r in refs):  # de-duplicate, keep order
            try:
                meal = self._require(ref)
                if meal.id in seen:  # the same meal again, by its other name
                    continue
                seen.add(meal.id)
                if meal.ordered is ordered:
                    unchanged.append(ref)
                    already.append((ref, meal))
                    continue
                allowed = meal.can_order if ordered else meal.can_cancel
                if not allowed:
                    reason = meal.order_restriction if ordered else meal.cancel_restriction
                    raise MealNotOrderableError(ref, reason, action)
                planned.append((ref, meal))
            except (MealNotFoundError, MealNotOrderableError) as exc:
                if not continue_on_error:
                    raise
                failed.append((ref, exc))

        # 2. Two meals of the same kind on the same day compete for one slot.
        if ordered:
            planned, dupes = self._resolve_duplicates(planned, already, strict_duplicates)
            skipped.extend(dupes)

        # 3. Nothing to do means nothing to send.
        if not planned:
            return OrderResult(tuple(changed), tuple(unchanged), tuple(skipped), tuple(failed))

        # 4. Stage each change. Only the save reaches the canteen's records, so a failure
        #    in here leaves nothing behind once the session's copy is thrown away.
        staged: list[tuple[int | str, Meal]] = []
        unanswered: list[tuple[int | str, Meal, StravaAPIError]] = []
        try:
            for ref, meal in planned:
                try:
                    self._stage(meal.id, ordered)
                    staged.append((ref, meal))
                except AuthenticationError:
                    raise  # the session is gone, so the other meals can't go through either
                except StravaAPIError as exc:
                    if not continue_on_error:
                        raise
                    unanswered.append((ref, meal, exc))
        except StravaAPIError:
            self._rollback()
            raise

        if not staged:
            self._rollback()
            failed.extend((ref, exc) for ref, _, exc in unanswered)
            return OrderResult(tuple(changed), tuple(unchanged), tuple(skipped), tuple(failed))

        # 5. Commit them all at once. A failure here doesn't say the save didn't happen.
        save_error: StravaAPIError | None = None
        try:
            self._save()
        except StravaAPIError as exc:
            save_error = exc

        # 6. Read the result back, which after a failed save is the only way to learn it.
        try:
            if save_error is not None or verify_saved:
                self._resync()
            else:
                self._load()
        except StravaAPIError as exc:
            self._forget()
            if save_error is not None and save_error.code is not None:
                raise save_error from exc  # the canteen answered no, whatever came after
            # A stage with no answer from the canteen may have landed, and the save takes it.
            doubtful = [ref for ref, _ in staged]
            doubtful += [ref for ref, _, stage_error in unanswered if stage_error.code is None]
            names = ", ".join(str(ref) for ref in doubtful)
            if save_error is not None:
                message = (
                    f"{save_error}, and reading the menu back failed too, so {names} may or "
                    "may not have been saved. Check the menu before trying again"
                )
            else:
                message = (
                    f"The canteen accepted the change for {names}, but reading the menu back "
                    f"failed, so it isn't confirmed: {exc}. Check the menu before trying again"
                )
            raise OrderNotConfirmedError(message, unconfirmed=tuple(doubtful)) from exc

        # 7. Compare meal by meal.
        unconfirmed = [
            ref for ref, meal in staged if not self._has_state(meal, ordered, changed, ref)
        ]
        for ref, meal, stage_error in unanswered:
            # Its answer was lost, not necessarily its effect, and the save takes it along.
            if not self._has_state(meal, ordered, changed, ref):
                failed.append((ref, stage_error))

        if save_error is not None and not changed:
            save_error.message += ". Nothing was saved: the menu was read back and is unchanged"
            raise save_error

        if unconfirmed:
            state = "not ordered" if ordered else "ordered"
            still = [f"meal {ref} is still {state}" for ref in unconfirmed]
            if not continue_on_error:
                done = f". These did change: {', '.join(map(str, changed))}" if changed else ""
                raise OrderNotConfirmedError(
                    f"The canteen accepted the request but {', '.join(still)}{done}",
                    changed=tuple(changed),
                    unconfirmed=tuple(unconfirmed),
                )
            failed.extend(
                (ref, StravaAPIError(f"The canteen accepted the request but {text}"))
                for ref, text in zip(unconfirmed, still, strict=True)
            )

        return OrderResult(tuple(changed), tuple(unchanged), tuple(skipped), tuple(failed))

    def _has_state(
        self, meal: Meal, ordered: bool, changed: list[int | str], ref: int | str
    ) -> bool:
        """Whether the menu now shows *meal* as wanted, noting it in *changed* if so."""
        fresh = self._same_meal(meal)
        if fresh is None or fresh.ordered is not ordered:
            return False
        changed.append(ref)
        return True

    def _same_meal(self, meal: Meal) -> Meal | None:
        """Find *meal* in a fresh menu, never answering with another meal's row.

        By key where the key names one meal. Otherwise its number is all there is, and
        that counts only while the row with that number is still the same day and slot.
        """
        found = self.get_by_key(meal.key)
        if found is not None:
            return found
        by_id = self._by_id.get(meal.id)
        return by_id if by_id is not None and by_id.key == meal.key else None

    def _resolve_duplicates(
        self,
        planned: list[tuple[int | str, Meal]],
        already: list[tuple[int | str, Meal]],
        strict: bool,
    ) -> tuple[list[tuple[int | str, Meal]], list[tuple[int | str, str]]]:
        """Keep one meal per (day, kind) slot; skip or reject the rest.

        A requested meal that is already ordered holds its slot, wherever it comes in the
        request: ordering the other one would replace it, and it was reported unchanged.
        """
        kept: list[tuple[int | str, Meal]] = []
        skipped: list[tuple[int | str, str]] = []
        claimed: dict[tuple[_dt.date, MealType], int | str] = {
            (meal.date, meal.type): ref for ref, meal in already
        }

        for ref, meal in planned:
            slot = (meal.date, meal.type)
            if slot in claimed:
                message = (
                    f"meal {ref} competes with meal {claimed[slot]} for the same slot "
                    f"({meal.date.isoformat()}, {meal.type.value})"
                )
                if strict:
                    raise DuplicateMealError(
                        f"Cannot order two meals of the same kind on one day: {message}"
                    )
                warnings.warn(f"Skipping {message}", stacklevel=4)
                skipped.append((ref, message))
                continue
            claimed[slot] = ref
            kept.append((ref, meal))
        return kept, skipped

    def _rollback(self) -> None:
        """Undo staged changes and reload, without masking the original error."""
        with contextlib.suppress(StravaAPIError):
            self._resync()

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
        if self._days is None or not isinstance(meal_id, (int, str)):
            return False
        try:
            return self._find(meal_id) is not None
        except MenuNotFetchedError:
            return False

    def __repr__(self) -> str:
        if self._days is None:
            return "Menu(not fetched)"
        days = self.get_days()
        meals = sum(len(day.meals) for day in days)
        orderable = sum(1 for day in days for meal in day.meals if meal.can_order)
        return f"Menu(days={len(days)}, meals={meals}, orderable={orderable})"
