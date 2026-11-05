"""The ``strava-cz`` command.

    strava-cz menu --week
    strava-cz order 2026-11-09:O2 2026-11-11:O2
    strava-cz --format json menu --orderable | jq '.days[].meals[].id'

Pretty output is the default; ``--format json`` prints one machine-readable object on
stdout, with every diagnostic pushed to stderr so the stream stays parseable. Nothing
outside the standard library is needed.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from .. import __version__
from ..exceptions import StravaError
from ..profiles import SecretSource
from . import commands
from .output import Output, parse_date

__all__ = ["EXIT", "build_parser", "main"]

EXIT = commands.EXIT

_EPILOG = """\
exit codes:
  0  success
  1  the canteen or the network failed
  2  wrong usage
  3  login rejected
  4  a meal could not be ordered, cancelled, or was not found
  5  not enough money on the account
  6  a profile or keyring problem

examples:
  strava-cz profile add skola --username your.name --canteen 3753
  strava-cz menu --week --orderable
  strava-cz order 2026-11-09:O2 2026-11-11:O2 --dry-run
  strava-cz --format json ordered | jq '.total_price'

The password is read from $STRAVA_CZ_PASSWORD_<PROFILE>, then $STRAVA_CZ_PASSWORD, and
only then from wherever the profile keeps it - the OS keyring, an encrypted profile
file, or a prompt. An encrypted profile takes its passphrase from
$STRAVA_CZ_PASSPHRASE_<PROFILE> or $STRAVA_CZ_PASSPHRASE, or asks for it.
"""


def _date(value: str) -> object:
    """argparse type for a date, accepting ISO plus today/tomorrow/yesterday."""
    try:
        return parse_date(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def _positive_float(value: str) -> float:
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number: {value!r}") from None
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return number


def _add_menu_filters(parser: argparse.ArgumentParser) -> None:
    """The flags that map onto ``Menu.get_days()``."""
    dates = parser.add_argument_group("choosing days")
    dates.add_argument(
        "--from",
        dest="date_from",
        type=_date,
        metavar="DATE",
        help="earliest day (YYYY-MM-DD, today, tomorrow)",
    )
    dates.add_argument(
        "--to", dest="date_to", type=_date, metavar="DATE", help="latest day, inclusive"
    )
    span = dates.add_mutually_exclusive_group()
    span.add_argument("--today", action="store_true", help="only today")
    span.add_argument("--tomorrow", action="store_true", help="only tomorrow")
    span.add_argument("--week", action="store_true", help="this week, Monday to Sunday")
    span.add_argument("--next-week", action="store_true", help="next week")

    meals = parser.add_argument_group("choosing meals")
    meals.add_argument(
        "--type",
        action="append",
        choices=["soup", "main", "unknown"],
        help="keep only this kind of meal; repeatable",
    )

    orderable = meals.add_mutually_exclusive_group()
    orderable.add_argument(
        "--orderable",
        action="store_true",
        default=None,
        help="only meals that can be ordered right now",
    )
    orderable.add_argument(
        "--not-orderable", dest="orderable", action="store_false", help="only meals that cannot"
    )

    ordered = meals.add_mutually_exclusive_group()
    ordered.add_argument(
        "--ordered", action="store_true", default=None, help="only meals already ordered"
    )
    ordered.add_argument(
        "--not-ordered", dest="ordered", action="store_false", help="only meals not ordered"
    )

    auto = meals.add_mutually_exclusive_group()
    auto.add_argument(
        "--auto-ordered",
        action="store_true",
        default=None,
        help="only days the canteen orders for you",
    )
    auto.add_argument(
        "--no-auto-ordered",
        dest="auto_ordered",
        action="store_false",
        help="only days it does not (these still need ordering by hand)",
    )

    meals.add_argument(
        "--include-no-school",
        action="store_true",
        help="also show days the canteen does not cook on",
    )
    meals.add_argument(
        "--allergens", action="store_true", help="list each meal's allergens under it"
    )


def _add_write_flags(parser: argparse.ArgumentParser, *, ordering: bool) -> None:
    parser.add_argument(
        "meal_ids",
        nargs="+",
        metavar="ID",
        help="meal ids such as 2026-11-09:O2, as shown by 'strava-cz menu'",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="say what would change without sending anything",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="do what can be done and report the rest, instead of "
        "rolling everything back at the first failure",
    )
    if ordering:
        parser.add_argument(
            "--strict-duplicates",
            action="store_true",
            help="fail when two meals compete for the same slot, "
            "instead of taking the first and warning",
        )


def build_parser() -> argparse.ArgumentParser:
    """The whole command tree."""
    parser = argparse.ArgumentParser(
        prog="strava-cz",
        description="Order school lunches through Strava.cz from the command line.",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-V", "--version", action="version", version=f"strava-cz {__version__}")

    parser.add_argument(
        "-p",
        "--profile",
        metavar="NAME",
        help="stored profile to use (default: the default profile)",
    )
    parser.add_argument(
        "--profile-store",
        metavar="PATH",
        help="use this profile file instead of the one in $XDG_CONFIG_HOME/strava-cz/profiles.json",
    )
    parser.add_argument(
        "--username",
        metavar="NAME",
        help="log in with this username instead of a profile; needs --canteen too",
    )
    parser.add_argument("--canteen", metavar="NUMBER", help="canteen number to go with --username")
    parser.add_argument(
        "--language",
        metavar="LANG",
        help="language the canteen answers in (default: the profile's, else EN)",
    )
    parser.add_argument(
        "--timeout",
        type=_positive_float,
        metavar="SEC",
        help="request timeout in seconds (default: 15)",
    )

    fmt = parser.add_argument_group("output")
    fmt.add_argument(
        "--format",
        choices=["pretty", "json"],
        default="pretty",
        help="pretty for people (default), json for other programs",
    )
    fmt.add_argument(
        "--json",
        dest="format",
        action="store_const",
        const="json",
        help="shorthand for --format json",
    )
    fmt.add_argument(
        "--color",
        choices=["auto", "always", "never"],
        default="auto",
        help="colour the output (default: auto, meaning only a terminal)",
    )

    subs = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)

    menu = subs.add_parser(
        "menu", help="show the menu", description="Show the published menu, day by day."
    )
    _add_menu_filters(menu)

    ordered = subs.add_parser(
        "ordered",
        help="list what is currently ordered",
        description="List the meals that are ordered right now.",
    )
    ordered.add_argument("--from", dest="date_from", type=_date, metavar="DATE")
    ordered.add_argument("--to", dest="date_to", type=_date, metavar="DATE")
    span = ordered.add_mutually_exclusive_group()
    span.add_argument("--today", action="store_true")
    span.add_argument("--tomorrow", action="store_true")
    span.add_argument("--week", action="store_true")
    span.add_argument("--next-week", action="store_true")

    order = subs.add_parser(
        "order",
        help="order one or more meals",
        description="Order meals. All of them are saved in one "
        "transaction, and the result is checked "
        "against a freshly fetched menu.",
    )
    _add_write_flags(order, ordering=True)

    cancel = subs.add_parser(
        "cancel", help="cancel one or more orders", description="Cancel orders, in one transaction."
    )
    _add_write_flags(cancel, ordering=False)

    subs.add_parser(
        "balance",
        help="print the account balance",
        description="Print the balance and nothing else.",
    )
    subs.add_parser(
        "account", help="show the logged-in account", description="Show who is logged in and where."
    )
    subs.add_parser(
        "raw",
        help="dump the raw menu response",
        description="Dump the untouched API response, for a bug report.",
    )

    profile = subs.add_parser(
        "profile",
        help="manage stored logins",
        description="Store canteen logins so you do not have to "
        "type them every time. The password goes to "
        "the OS keyring, never to the profile file, "
        "unless you ask for --secret file.",
    )
    psubs = profile.add_subparsers(dest="profile_command", metavar="ACTION", required=True)

    psubs.add_parser("list", help="list stored profiles")

    add = psubs.add_parser(
        "add",
        help="store a new profile",
        description="Store a profile. The password is asked for on "
        "the terminal unless $STRAVA_CZ_PASSWORD is set "
        "or --password-stdin is given.",
    )
    add.add_argument("name", help="what to call it, e.g. skola")
    add.add_argument("--username", required=True, help="canteen login name")
    add.add_argument("--canteen", required=True, metavar="NUMBER", help="canteen number")
    add.add_argument(
        "--secret",
        choices=["auto", *(s.value for s in SecretSource)],
        default="auto",
        help="where the password lives. auto (default) uses the OS keyring when this "
        "machine has one and an encrypted profile file when it does not, so it "
        "always remembers the password. keyring insists on the OS keyring; "
        "encrypted stores it in the profile file under a passphrase; env reads "
        "$STRAVA_CZ_PASSWORD every run; prompt asks every run; file writes it in "
        "PLAINTEXT",
    )
    add.add_argument(
        "--password-stdin",
        action="store_true",
        help="read the password from stdin instead of asking",
    )
    add.add_argument(
        "--verify",
        action="store_true",
        help="log in once to check the credentials before storing them",
    )
    add.add_argument("--language", metavar="LANG", help="language for this profile")

    remove = psubs.add_parser("remove", help="forget a profile")
    remove.add_argument("name")

    default = psubs.add_parser("default", help="choose the profile used by default")
    default.add_argument("name")

    show = psubs.add_parser("show", help="show one profile (never the password)")
    show.add_argument("name", nargs="?", help="default: the default profile")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the ``strava-cz`` command.

    Args:
        argv: Arguments without the program name. Defaults to ``sys.argv[1:]``.

    Returns:
        One of the exit codes listed in ``--help``.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    out = Output(fmt=args.format, color=args.color)

    try:
        return commands.run(args, out)
    except StravaError as exc:
        out.fail(args.command, exc)
        return commands.exit_code_for(exc)
    except KeyboardInterrupt:  # pragma: no cover - needs a real signal
        out.note("")
        return 130
    except BrokenPipeError:  # pragma: no cover - needs a real closed pipe
        # Someone closed the pipe, e.g. `strava-cz menu | head`. Not our problem.
        sys.stderr.close()
        return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
