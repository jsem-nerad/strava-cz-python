"""The ``strava-cz mcp`` command: an MCP server that talks to the canteen over stdio.

    pip install "strava-cz[mcp]"
    strava-cz mcp                  # reading, ordering and cancelling
    strava-cz mcp --read-only      # reading only; the write tools are not even offered

It signs in the way the command line does: the named or default profile, with the
password from ``$STRAVA_CZ_PASSWORD``, the OS keyring or an encrypted profile file. A
password is never an argument of a tool, so it never passes through the model.

Every tool call is one login and one logout, exactly like one run of the command line.
That keeps the server stateless (an expired session cannot linger) and means meals are
named by their key, ``2026-11-09:O2``, because the canteen's own numbers change at every
login.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import functools
import os
import sys
import threading
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from . import __version__
from .cli import commands
from .cli.output import (
    day_to_json,
    error_to_json,
    meal_to_json,
    parse_date,
    result_to_json,
    user_to_json,
)
from .exceptions import ProfileError, StravaError
from .models import MealType
from .profiles import PASSWORD_ENV, ProfileStore

__all__ = ["READ_TOOLS", "WRITE_TOOLS", "build_server", "serve"]

#: What each tool is called, so the docs and the tests agree with the code.
READ_TOOLS = ("get_menu", "get_ordered", "get_balance", "get_account")
WRITE_TOOLS = ("order_meals", "cancel_meals")

Period = Literal["today", "tomorrow", "week", "next_week"]
Kind = Literal["soup", "main", "unknown"]

_INSTRUCTIONS = """\
Orders school lunches at a canteen that uses Strava.cz.

Meals are named by an id made of the day and the slot, such as 2026-11-09:O2. Take ids
from get_menu or get_ordered and pass them back unchanged; never invent one and never use
a bare number, because the canteen renumbers its menu at every login.

get_menu shows every published meal and says for each whether it can be ordered right now
(can_order, order_restriction, deadline). Days with "auto_ordered": false are ones the
canteen does not order for the user; they can still be ordered by hand. Soups cannot be
ordered on their own. Ordering a main replaces any other main already ordered that day.

order_meals and cancel_meals change a real account and spend real money, so use dry_run
first when unsure and tell the user what was ordered. If an order fails with
OrderNotConfirmedError the change may have been saved: call get_ordered before retrying.
"""

_READ = ToolAnnotations(read_only_hint=True, open_world_hint=True)
_WRITE = ToolAnnotations(
    read_only_hint=False, destructive_hint=True, idempotent_hint=True, open_world_hint=True
)


def _describe(exc: BaseException) -> str:
    """An error as one clear line a model can act on: its type, its message, its details."""
    data = error_to_json(exc)
    details = ", ".join(
        f"{key}={value}" for key, value in data.items() if key not in ("type", "message")
    )
    return f"{data['type']}: {data['message']}" + (f" ({details})" if details else "")


def _date(value: str | None, name: str) -> _dt.date | None:
    if value is None or value == "":
        return None
    try:
        return parse_date(value)
    except ValueError as exc:
        raise ToolError(f"{name}: {exc}") from None


def _range(
    date_from: str | None, date_to: str | None, period: str | None
) -> tuple[_dt.date | None, _dt.date | None]:
    """The day range a tool was asked for; *period* is the same shortcut the CLI has."""
    if period and (date_from or date_to):
        raise ToolError("give either period or date_from/date_to, not both")
    # The shortcut is expanded by the command line's own code, so "week" means the same.
    shortcuts = argparse.Namespace(
        date_from=None,
        date_to=None,
        today=period == "today",
        tomorrow=period == "tomorrow",
        week=period == "week",
        next_week=period == "next_week",
    )
    commands.apply_date_shortcuts(shortcuts)
    if period:
        return shortcuts.date_from, shortcuts.date_to
    return _date(date_from, "date_from"), _date(date_to, "date_to")


def _meal_ids(values: list[str]) -> list[str]:
    if not values:
        raise ToolError("meal_ids is empty: give at least one id such as 2026-11-09:O2")
    try:
        return [commands.parse_meal_id(value) for value in values]
    except StravaError as exc:
        raise ToolError(_describe(exc)) from None


def build_server(args: argparse.Namespace, *, read_only: bool = False) -> MCPServer:
    """The server, with its tools registered.

    Args:
        args: Parsed command line, as :func:`strava_cz.cli.commands.session` reads it:
            which profile (or username and canteen), the language and the timeout.
        read_only: Leave the tools that change the account out altogether, instead of
            registering them and refusing, so a client never sees them.
    """
    server = MCPServer("strava-cz", instructions=_INSTRUCTIONS, version=__version__)
    # One login at a time. Tools run in worker threads, and two parallel logins would
    # renumber each other's menus and race on the same account.
    lock = threading.Lock()

    def guarded(fn: Any) -> Any:
        """Turn the library's errors into tool errors that keep their message.

        Anything else the SDK would report as a bare "Error executing tool", hiding what
        went wrong, such as a closed ordering window or too little money.
        """

        @functools.wraps(fn)
        def wrapper(*a: Any, **kw: Any) -> Any:
            try:
                with lock:
                    return fn(*a, **kw)
            except ToolError:
                raise
            except StravaError as exc:
                raise ToolError(_describe(exc)) from exc

        return wrapper

    @server.tool(title="Show the menu", annotations=_READ)
    @guarded
    def get_menu(
        period: Period | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        meal_types: list[Kind] | None = None,
        orderable: bool | None = None,
        ordered: bool | None = None,
        auto_ordered: bool | None = None,
        include_no_school: bool = False,
    ) -> dict[str, Any]:
        """The published menu, day by day, with what can be ordered and what already is.

        Every filter is optional and they combine. Days with no meals left after
        filtering are left out.

        Args:
            period: A shortcut for a range of days: today, tomorrow, week (this week,
                Monday to Sunday) or next_week. Not together with date_from/date_to.
            date_from: Earliest day, as YYYY-MM-DD, "today" or "tomorrow".
            date_to: Latest day, inclusive, in the same forms.
            meal_types: Keep only these kinds of meal: soup, main, unknown.
            orderable: True for only meals that can be ordered right now, False for
                only those that cannot.
            ordered: True for only meals already ordered, False for only those not.
            auto_ordered: True for only days the canteen orders for the user, False for
                only days it does not (those still need ordering by hand).
            include_no_school: Also show days the canteen does not cook on.
        """
        first, last = _range(date_from, date_to, period)
        with commands.session(args) as strava:
            strava.menu.fetch()
            days = strava.menu.get_days(
                meal_types=[MealType(kind) for kind in meal_types] if meal_types else None,
                orderable=orderable,
                ordered=ordered,
                auto_ordered=auto_ordered,
                date_from=first,
                date_to=last,
                include_no_school=include_no_school,
            )
            currency = strava.user.currency
            data: dict[str, Any] = {
                "ok": True,
                "command": "menu",
                "days": [day_to_json(day, currency) for day in days],
                "account": user_to_json(strava.user),
            }
            warnings = [str(warning) for warning in strava.menu.parse_warnings]
            if warnings:
                data["warnings"] = warnings
            return data

    @server.tool(title="Show what is ordered", annotations=_READ)
    @guarded
    def get_ordered(
        period: Period | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict[str, Any]:
        """The meals that are ordered right now, with their total price.

        Args:
            period: today, tomorrow, week (Monday to Sunday) or next_week. Not together
                with date_from/date_to.
            date_from: Earliest day, as YYYY-MM-DD, "today" or "tomorrow".
            date_to: Latest day, inclusive, in the same forms.
        """
        first, last = _range(date_from, date_to, period)
        with commands.session(args) as strava:
            strava.menu.fetch()
            meals = strava.menu.get_meals(ordered=True, date_from=first, date_to=last)
            currency = strava.user.currency
            return {
                "ok": True,
                "command": "ordered",
                "meals": [meal_to_json(meal, currency) for meal in meals],
                "count": len(meals),
                "total_price": sum(meal.price for meal in meals),
                "account": user_to_json(strava.user),
            }

    @server.tool(title="Show the balance", annotations=_READ)
    @guarded
    def get_balance() -> dict[str, Any]:
        """The account balance, and nothing else."""
        with commands.session(args) as strava:
            user = strava.user
            return {
                "ok": True,
                "command": "balance",
                "balance": user.balance,
                "currency": user.currency,
            }

    @server.tool(title="Show the account", annotations=_READ)
    @guarded
    def get_account() -> dict[str, Any]:
        """Who is logged in, at which canteen, and the balance."""
        with commands.session(args) as strava:
            return {"ok": True, "command": "account", "account": user_to_json(strava.user)}

    if read_only:
        return server

    def change(
        meal_ids: list[str],
        *,
        ordered: bool,
        dry_run: bool,
        continue_on_error: bool,
        strict_duplicates: bool,
    ) -> dict[str, Any]:
        action = "order" if ordered else "cancel"
        ids = _meal_ids(meal_ids)  # before logging in
        with commands.session(args) as strava:
            strava.menu.fetch()
            currency = strava.user.currency

            if dry_run:
                strict = ordered and strict_duplicates
                plan = commands._plan(  # the very check the CLI's --dry-run makes
                    strava,
                    ids,
                    ordered=ordered,
                    continue_on_error=continue_on_error,
                    strict_duplicates=strict,
                )
                after = strava.user.balance + plan.balance_change
                data: dict[str, Any] = {
                    "ok": not (plan.refused or (strict and plan.duplicate)),
                    "command": action,
                    "dry_run": True,
                    **plan.payload,
                    "balance_after": after,
                    "meals": [meal_to_json(meal, currency) for meal in plan.would],
                }
                if after < 0 and plan.balance_change < 0:
                    data["warning"] = (
                        f"this would leave the balance at {after:g} {currency}, so the "
                        "canteen may refuse it, which a dry run can't tell"
                    )
                return data

            # Each call is one login and names meals by key, so renumbering costs nothing.
            kwargs: dict[str, Any] = {"continue_on_error": continue_on_error, "verify_saved": True}
            if ordered:
                kwargs["strict_duplicates"] = strict_duplicates
            method = strava.menu.order_meals if ordered else strava.menu.cancel_meals
            result = method(*ids, **kwargs)
            return {
                "command": action,
                **result_to_json(result),
                "account": user_to_json(strava.user),
            }

    @server.tool(title="Order meals", annotations=_WRITE)
    @guarded
    def order_meals(
        meal_ids: list[str],
        dry_run: bool = False,
        continue_on_error: bool = False,
        strict_duplicates: bool = False,
    ) -> dict[str, Any]:
        """Order meals. This changes the real account and spends money.

        All the meals are saved in one transaction and the result is checked against a
        freshly fetched menu. By default one meal that cannot be ordered, such as one
        past its deadline, stops the whole batch and nothing is ordered.

        Args:
            meal_ids: Ids such as 2026-11-09:O2, exactly as get_menu shows them.
            dry_run: Only say what would change, without sending anything.
            continue_on_error: Order what can be ordered and report the rest in
                "failed", instead of ordering nothing at the first failure.
            strict_duplicates: Fail when two of the meals compete for the same slot
                (same day, same kind), instead of taking the first and skipping the rest.
        """
        return change(
            meal_ids,
            ordered=True,
            dry_run=dry_run,
            continue_on_error=continue_on_error,
            strict_duplicates=strict_duplicates,
        )

    @server.tool(title="Cancel orders", annotations=_WRITE)
    @guarded
    def cancel_meals(
        meal_ids: list[str],
        dry_run: bool = False,
        continue_on_error: bool = False,
    ) -> dict[str, Any]:
        """Cancel orders. This changes the real account.

        Args:
            meal_ids: Ids such as 2026-11-09:O2, exactly as get_ordered shows them.
            dry_run: Only say what would change, without sending anything.
            continue_on_error: Cancel what can be cancelled and report the rest in
                "failed", instead of cancelling nothing at the first failure.
        """
        return change(
            meal_ids,
            ordered=False,
            dry_run=dry_run,
            continue_on_error=continue_on_error,
            strict_duplicates=False,
        )

    return server


def serve(args: argparse.Namespace, *, read_only: bool = False) -> int:
    """Check the login can be found, then serve MCP on stdin and stdout until it closes.

    stdout belongs to the protocol, so everything said to the person goes to stderr.
    A prompt is never possible there: the password has to come from a profile, the
    keyring or ``$STRAVA_CZ_PASSWORD``.
    """
    if args.username or args.canteen:
        if not (args.username and args.canteen):
            raise ProfileError("--username and --canteen must be given together")
        if not os.environ.get(PASSWORD_ENV):
            raise ProfileError(
                f"the MCP server cannot ask for a password: set ${PASSWORD_ENV}, or store "
                "a profile with 'strava-cz profile add' and use --profile"
            )
        who = f"{args.username} @ canteen {args.canteen}"
    else:
        profile = ProfileStore(getattr(args, "profile_store", None)).get(args.profile)
        who = f"profile {profile.name} ({profile.username} @ canteen {profile.canteen_number})"

    server = build_server(args, read_only=read_only)
    mode = "read-only" if read_only else "reading, ordering and cancelling"
    print(f"strava-cz MCP server {__version__} on stdio: {who}, {mode}", file=sys.stderr)
    server.run("stdio")
    return commands.EXIT["ok"]
