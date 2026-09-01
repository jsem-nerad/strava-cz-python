"""What each subcommand actually does.

Every function here takes the parsed arguments and an :class:`~.output.Output`, and
returns an exit code. Connecting to the canteen is deferred to :func:`session`, so the
``profile`` commands never log in and never need a password.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as _dt
import os
import sys
from collections.abc import Iterator
from typing import Any

from ..client import StravaCZ
from ..exceptions import (
    AuthenticationError,
    DuplicateMealError,
    InsufficientBalanceError,
    MealNotFoundError,
    MealNotOrderableError,
    ProfileError,
    StravaError,
)
from ..models import Meal, MealType
from ..profiles import (
    PASSWORD_ENV,
    Profile,
    ProfileStore,
    SecretSource,
    keyring_available,
    prompt_password,
)
from .output import Output, day_to_json, meal_to_json, result_to_json, user_to_json

__all__ = ["EXIT", "exit_code_for", "run", "session"]

#: Exit codes, so a shell script can tell the failures apart. Documented in --help.
EXIT = {
    "ok": 0,
    "error": 1,
    "usage": 2,
    "auth": 3,
    "meal": 4,
    "balance": 5,
    "profile": 6,
}


def exit_code_for(exc: BaseException) -> int:
    """Map an exception onto the exit code documented in ``--help``.

    Checked most specific first: ``InsufficientBalanceError`` and
    ``AuthenticationError`` are both ``StravaAPIError``, so the order matters.
    """
    if isinstance(exc, InsufficientBalanceError):
        return EXIT["balance"]
    if isinstance(exc, AuthenticationError):
        return EXIT["auth"]
    if isinstance(exc, (MealNotFoundError, MealNotOrderableError, DuplicateMealError)):
        return EXIT["meal"]
    if isinstance(exc, ProfileError):
        return EXIT["profile"]
    return EXIT["error"]


# ------------------------------------------------------------------------- session


def _store(args: argparse.Namespace) -> ProfileStore:
    """The profile store this invocation should use."""
    return ProfileStore(getattr(args, "profile_store", None))


@contextlib.contextmanager
def session(args: argparse.Namespace) -> Iterator[StravaCZ]:
    """Log in for the duration of a command, then log out again.

    Credentials come from ``--username``/``--canteen`` when both are given, and from
    the named or default profile otherwise. The password is dropped as soon as the
    login request has been made.
    """
    username = getattr(args, "username", None)
    canteen = getattr(args, "canteen", None)
    kwargs: dict[str, Any] = {}
    if args.timeout:
        kwargs["timeout"] = args.timeout

    if username or canteen:
        if not (username and canteen):
            raise ProfileError("--username and --canteen must be given together")
        password = os.environ.get(PASSWORD_ENV) or prompt_password(
            f"Password for {username} at canteen {canteen}: "
        )
        client = StravaCZ(username, password, canteen, language=args.language or "EN", **kwargs)
    else:
        store = _store(args)
        profile = store.get(args.profile)
        password = store.resolve_password(profile)
        client = StravaCZ(
            profile.username,
            password,
            profile.canteen_number,
            language=args.language or profile.language,
            **kwargs,
        )

    del password
    try:
        yield client
    finally:
        with contextlib.suppress(StravaError):
            client.logout()
        client.close()


# ------------------------------------------------------------------------ filtering


def apply_date_shortcuts(args: argparse.Namespace, today: _dt.date | None = None) -> None:
    """Expand ``--today``/``--week``/... into the ``--from``/``--to`` pair.

    Done when the command runs rather than while parsing, so a long-lived process
    that crosses midnight still means "today" by today.
    """
    today = today or _dt.date.today()
    if getattr(args, "today", False):
        args.date_from = args.date_to = today
    elif getattr(args, "tomorrow", False):
        args.date_from = args.date_to = today + _dt.timedelta(days=1)
    elif getattr(args, "week", False):
        monday = today - _dt.timedelta(days=today.weekday())
        args.date_from, args.date_to = monday, monday + _dt.timedelta(days=6)
    elif getattr(args, "next_week", False):
        monday = today - _dt.timedelta(days=today.weekday()) + _dt.timedelta(days=7)
        args.date_from, args.date_to = monday, monday + _dt.timedelta(days=6)


def _filters(args: argparse.Namespace) -> dict[str, Any]:
    """Turn the menu flags into keyword arguments for :meth:`Menu.get_days`."""
    return {
        "meal_types": [MealType(kind) for kind in args.type] if args.type else None,
        "orderable": args.orderable,
        "ordered": args.ordered,
        "auto_ordered": args.auto_ordered,
        "date_from": args.date_from,
        "date_to": args.date_to,
        "include_no_school": args.include_no_school,
    }


# ------------------------------------------------------------------ menu commands


def cmd_menu(args: argparse.Namespace, out: Output) -> int:
    """Show the menu."""
    apply_date_shortcuts(args)
    with session(args) as strava:
        strava.menu.fetch()
        days = strava.menu.get_days(**_filters(args))
        currency = strava.user.currency
        for warning in strava.menu.parse_warnings:
            out.warn(str(warning))

        def render() -> None:
            out.render_days(
                days,
                currency=currency,
                show_allergens=args.allergens,
                balance=strava.user.balance,
            )

        out.emit(
            "menu",
            {
                "days": [day_to_json(day, currency) for day in days],
                "account": user_to_json(strava.user),
            },
            render,
        )
    return EXIT["ok"]


def cmd_ordered(args: argparse.Namespace, out: Output) -> int:
    """List what is currently ordered."""
    apply_date_shortcuts(args)
    with session(args) as strava:
        strava.menu.fetch()
        meals = strava.menu.get_meals(ordered=True, date_from=args.date_from, date_to=args.date_to)
        currency = strava.user.currency
        total = sum(meal.price for meal in meals)

        def render() -> None:
            out.render_meals(meals, currency=currency)
            out.line()
            out.line(out.c.dim(f"{len(meals)} ordered · {total:g} {currency}"))

        out.emit(
            "ordered",
            {
                "meals": [meal_to_json(meal, currency) for meal in meals],
                "count": len(meals),
                "total_price": total,
                "account": user_to_json(strava.user),
            },
            render,
        )
    return EXIT["ok"]


def cmd_balance(args: argparse.Namespace, out: Output) -> int:
    """Print the account balance and nothing else."""
    with session(args) as strava:
        user = strava.user
        out.emit(
            "balance",
            {"balance": user.balance, "currency": user.currency},
            lambda: out.line(f"{user.balance:.2f} {user.currency}"),
        )
    return EXIT["ok"]


def cmd_account(args: argparse.Namespace, out: Output) -> int:
    """Show who is logged in."""
    with session(args) as strava:
        out.emit(
            "account",
            {"account": user_to_json(strava.user)},
            lambda: out.render_user(strava.user),
        )
    return EXIT["ok"]


def cmd_raw(args: argparse.Namespace, out: Output) -> int:
    """Dump the untouched menu response, for debugging or a bug report."""
    with session(args) as strava:
        strava.menu.fetch()
        raw = strava.menu.raw_data
        out.emit("raw", {"raw": raw}, lambda: out.dump(raw))
    return EXIT["ok"]


# -------------------------------------------------------------- ordering commands


def cmd_order(args: argparse.Namespace, out: Output) -> int:
    """Order meals, or with ``--dry-run`` say what ordering them would do."""
    return _change(args, out, ordered=True)


def cmd_cancel(args: argparse.Namespace, out: Output) -> int:
    """Cancel orders, or with ``--dry-run`` say what cancelling them would do."""
    return _change(args, out, ordered=False)


def _change(args: argparse.Namespace, out: Output, *, ordered: bool) -> int:
    action = "order" if ordered else "cancel"
    with session(args) as strava:
        strava.menu.fetch()
        currency = strava.user.currency

        if args.dry_run:
            plan = _plan(strava, args.meal_ids, ordered=ordered)
            out.emit(
                action,
                {"dry_run": True, **plan.payload},
                lambda: _render_plan(out, plan, action, currency),
            )
            return EXIT["meal"] if plan.refused else EXIT["ok"]

        kwargs: dict[str, Any] = {"continue_on_error": args.continue_on_error}
        if ordered:
            kwargs["strict_duplicates"] = args.strict_duplicates
        method = strava.menu.order_meals if ordered else strava.menu.cancel_meals
        result = method(*args.meal_ids, **kwargs)

        def render() -> None:
            out.render_result(result, action, currency)
            out.line(out.c.dim(f"balance {strava.user.balance:.2f} {currency}"))

        out.emit(
            action,
            {**result_to_json(result), "account": user_to_json(strava.user)},
            render,
        )
        return EXIT["ok"] if result.ok else EXIT["meal"]


class Plan:
    """What a dry run worked out, before anything is sent.

    Mirrors the checks :meth:`Menu._change_orders` makes - unknown id, already in the
    wanted state, refused by the canteen, two meals competing for one slot - so a dry
    run answers the same question the real call would.
    """

    def __init__(self) -> None:
        self.would: list[Meal] = []
        self.already: list[int] = []
        self.refused: list[dict[str, Any]] = []
        self.duplicate: list[dict[str, Any]] = []
        self.balance_change: float = 0.0

    @property
    def empty(self) -> bool:
        return not (self.would or self.already or self.refused or self.duplicate)

    @property
    def payload(self) -> dict[str, Any]:
        return {
            "would_change": [meal.id for meal in self.would],
            "already": self.already,
            "refused": self.refused,
            "duplicate": self.duplicate,
            "balance_change": self.balance_change,
        }


def _plan(strava: StravaCZ, meal_ids: list[int], *, ordered: bool) -> Plan:
    """Resolve *meal_ids* against the fetched menu without sending anything."""
    plan = Plan()
    claimed: dict[tuple[_dt.date, MealType], int] = {}

    for meal_id in dict.fromkeys(int(i) for i in meal_ids):
        meal = strava.menu.get_by_id(meal_id)
        if meal is None:
            plan.refused.append({"id": meal_id, "reason": "not in the fetched menu"})
            continue
        if meal.ordered is ordered:
            plan.already.append(meal_id)
            continue
        allowed = meal.can_order if ordered else meal.can_cancel
        if not allowed:
            reason = meal.order_restriction if ordered else meal.cancel_restriction
            plan.refused.append({"id": meal_id, "reason": reason.description})
            continue
        slot = (meal.date, meal.type)
        if ordered and slot in claimed:
            plan.duplicate.append({"id": meal_id, "competes_with": claimed[slot]})
            continue
        claimed[slot] = meal_id
        plan.would.append(meal)

    total = sum(meal.price for meal in plan.would)
    plan.balance_change = -total if ordered else total
    return plan


def _render_plan(out: Output, plan: Plan, action: str, currency: str) -> None:
    out.line(out.c.dim("dry run - nothing was sent to the canteen"))
    out.line()
    if plan.would:
        out.line(out.c.bold(f"would {action}:"))
        out.render_meals(plan.would, currency=currency)
        out.line(out.c.dim(f"  balance change: {plan.balance_change:+g} {currency}"))
    for meal_id in plan.already:
        verb = "ordered" if action == "order" else "not ordered"
        out.line(out.c.dim(f"  {meal_id}: already {verb}, nothing would be sent"))
    for item in plan.duplicate:
        out.line(
            out.c.yellow(f"  {item['id']}: same slot as {item['competes_with']}, would be skipped")
        )
    for item in plan.refused:
        out.line(out.c.red(f"  {item['id']}: {item['reason']}"))
    if plan.empty:
        out.line(out.c.dim("nothing to do"))


# ---------------------------------------------------------------- profile commands


def cmd_profile_list(args: argparse.Namespace, out: Output) -> int:
    """List stored profiles, marking the default one."""
    store = _store(args)
    profiles = store.list()
    default = store.default_name

    def render() -> None:
        if not profiles:
            out.line(out.c.dim("no profiles yet - run 'strava-cz profile add NAME'"))
            out.line(out.c.dim(f"store: {store.path}"))
            return
        for profile in profiles:
            mark = out.c.green("*") if profile.name == default else " "
            out.line(
                f" {mark} {profile.name:<14} {profile.username:<20} "
                f"canteen {profile.canteen_number:<7} "
                f"{out.c.dim(profile.secret.description)}"
            )
        out.line()
        out.line(out.c.dim(f"* default · store: {store.path}"))

    out.emit(
        "profile list",
        {
            "default": default,
            "store": str(store.path),
            "profiles": [
                {
                    "name": p.name,
                    "username": p.username,
                    "canteen_number": p.canteen_number,
                    "language": p.language,
                    "secret": p.secret.value,
                    "default": p.name == default,
                }
                for p in profiles
            ],
        },
        render,
    )
    return EXIT["ok"]


def cmd_profile_add(args: argparse.Namespace, out: Output) -> int:
    """Store a profile, putting the password wherever ``--secret`` says."""
    store = _store(args)
    secret = SecretSource(args.secret)

    if secret is SecretSource.KEYRING and not keyring_available():
        raise ProfileError(
            "No usable OS keyring on this machine, so --secret keyring cannot store "
            'the password. Install one with: pip install "strava-cz[cli]" - or use '
            "--secret env (reads $STRAVA_CZ_PASSWORD), --secret prompt (asks every "
            "time), or --secret file to accept a plaintext file."
        )

    password: str | None = None
    if secret.stores_password:
        if args.password_stdin:
            password = _read_stdin_password()
        else:
            password = os.environ.get(PASSWORD_ENV) or prompt_password(
                f"Password for {args.username} at canteen {args.canteen}: "
            )

    if secret is SecretSource.FILE:
        out.warn(
            f"--secret file writes the password in PLAINTEXT to {store.path}. The file "
            f"is chmod 0600, which stops other users but not anyone who can read your "
            f"home directory or a backup of it."
        )

    profile = Profile(
        name=args.name,
        username=args.username,
        canteen_number=args.canteen,
        language=args.language or "EN",
        secret=secret,
    )
    if args.verify:
        _verify_login(profile, password, store, out)

    stored = store.save(profile, password)
    out.emit(
        "profile add",
        {
            "name": stored.name,
            "username": stored.username,
            "canteen_number": stored.canteen_number,
            "secret": stored.secret.value,
            "store": str(store.path),
        },
        lambda: out.line(
            f"saved profile {out.c.bold(stored.name)} "
            f"({stored.username} @ canteen {stored.canteen_number}), "
            f"password in {stored.secret.description}"
        ),
    )
    return EXIT["ok"]


def _read_stdin_password() -> str:
    """Read one line from stdin, for ``cat secret | strava-cz profile add ...``."""
    password = sys.stdin.readline().rstrip("\n")
    if not password:
        raise ProfileError("--password-stdin was given but nothing was read")
    return password


def _verify_login(profile: Profile, password: str | None, store: ProfileStore, out: Output) -> None:
    """Try the credentials before storing them, so a typo is caught now, not later."""
    if password is None:
        password = store.resolve_password(profile)
    out.note("checking the credentials...")
    with StravaCZ(
        profile.username, password, profile.canteen_number, language=profile.language
    ) as strava:
        out.note(f"ok - {strava.user.full_name} at {strava.user.canteen_name}")


def cmd_profile_remove(args: argparse.Namespace, out: Output) -> int:
    """Forget a profile and its keyring entry."""
    store = _store(args)
    store.delete(args.name)
    out.emit(
        "profile remove",
        {"name": args.name},
        lambda: out.line(f"removed profile {out.c.bold(args.name)}"),
    )
    return EXIT["ok"]


def cmd_profile_default(args: argparse.Namespace, out: Output) -> int:
    """Choose the profile used when ``--profile`` is not given."""
    store = _store(args)
    store.set_default(args.name)
    out.emit(
        "profile default",
        {"default": args.name},
        lambda: out.line(f"default profile is now {out.c.bold(args.name)}"),
    )
    return EXIT["ok"]


def cmd_profile_show(args: argparse.Namespace, out: Output) -> int:
    """Show one profile. Never prints the password, wherever it is kept."""
    store = _store(args)
    profile = store.get(args.name)
    data = {
        "name": profile.name,
        "username": profile.username,
        "canteen_number": profile.canteen_number,
        "language": profile.language,
        "secret": profile.secret.value,
        "password_env": profile.env_var,
        "default": profile.name == store.default_name,
        "store": str(store.path),
    }

    def render() -> None:
        rows = (
            ("Name", profile.name),
            ("Username", profile.username),
            ("Canteen", profile.canteen_number),
            ("Language", profile.language),
            ("Password", profile.secret.description),
            ("Env override", f"${profile.env_var}"),
            ("Default", "yes" if data["default"] else "no"),
            ("Store", str(store.path)),
        )
        for label, value in rows:
            out.line(f"{out.c.dim(label + ':'):<22} {value}")

    out.emit("profile show", data, render)
    return EXIT["ok"]


# --------------------------------------------------------------------- dispatching

#: Subcommand name (``"profile add"`` for the nested ones) to handler.
COMMANDS = {
    "menu": cmd_menu,
    "ordered": cmd_ordered,
    "order": cmd_order,
    "cancel": cmd_cancel,
    "balance": cmd_balance,
    "account": cmd_account,
    "raw": cmd_raw,
    "profile list": cmd_profile_list,
    "profile add": cmd_profile_add,
    "profile remove": cmd_profile_remove,
    "profile default": cmd_profile_default,
    "profile show": cmd_profile_show,
}


def run(args: argparse.Namespace, out: Output) -> int:
    """Dispatch to the chosen command."""
    key = args.command
    if key == "profile":
        key = f"profile {args.profile_command}"
    return COMMANDS[key](args, out)
