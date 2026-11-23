"""The MCP server, called through an in-process MCP client against recorded responses.

Like the rest of the suite nothing here touches the network: the autouse guard in
conftest blocks sockets, respx answers for the canteen, and the profile store lives in
tmp_path. The real SDK client talks to the real server object, so what is checked is
what an agent would see: the tool list, the annotations, the structured results and the
errors.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import anyio
import httpx
import pytest

pytest.importorskip("mcp", reason="the MCP server needs the 'mcp' extra")

from mcp import Client, StdioServerParameters

from strava_cz import Profile, ProfileStore, SecretSource
from strava_cz.cli import EXIT, build_parser, main
from strava_cz.mcp_server import READ_TOOLS, WRITE_TOOLS, build_server

from .conftest import BASE_URL, FakeCanteen, load, with_ordered

A = "2026-09-07:O2"
B = "2026-09-08:O2"
CLOSED = "2026-09-02:O1"
SOUP = "2026-09-02:PO"


@pytest.fixture
def profile(api, login_route, store_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A throwaway profile whose password comes from the environment."""
    ProfileStore(store_path).save(Profile("test", "test.user", "1234", secret=SecretSource.ENV))
    monkeypatch.setenv("STRAVA_CZ_PASSWORD", "test-password")


@pytest.fixture
def canteen(api, profile, menu_payload) -> FakeCanteen:
    return FakeCanteen(api, menu_payload)


def server_for(*, read_only: bool = False) -> Any:
    args = build_parser().parse_args(["--profile", "test", "mcp"])
    return build_server(args, read_only=read_only)


def call(name: str, arguments: dict[str, Any] | None = None, *, read_only: bool = False) -> Any:
    """Call one tool the way an agent's client does and return the SDK's result."""

    async def go() -> Any:
        async with Client(server_for(read_only=read_only)) as client:
            return await client.call_tool(name, arguments or {})

    return anyio.run(go)


def tools(*, read_only: bool = False) -> dict[str, Any]:
    async def go() -> Any:
        async with Client(server_for(read_only=read_only)) as client:
            return await client.list_tools()

    return {tool.name: tool for tool in anyio.run(go).tools}


def data(result: Any) -> dict[str, Any]:
    """The structured result of a call that worked."""
    assert not result.is_error, result.content
    assert result.structured_content is not None
    return dict(result.structured_content)


def error_text(result: Any) -> str:
    assert result.is_error, "expected a tool error"
    return str(result.content[0].text)


class TestToolList:
    def test_everything_is_on_by_default(self):
        assert set(tools()) == set(READ_TOOLS) | set(WRITE_TOOLS)

    def test_read_only_does_not_register_the_write_tools_at_all(self):
        assert set(tools(read_only=True)) == set(READ_TOOLS)

    def test_the_read_tools_say_they_only_read(self):
        for name in READ_TOOLS:
            annotations = tools()[name].annotations
            assert annotations.read_only_hint is True, name

    def test_the_write_tools_say_they_are_destructive(self):
        for name in WRITE_TOOLS:
            annotations = tools()[name].annotations
            assert annotations.read_only_hint is False, name
            assert annotations.destructive_hint is True, name

    def test_a_password_is_never_something_a_tool_takes(self):
        for tool in tools().values():
            assert "password" not in json.dumps(tool.input_schema).lower(), tool.name

    def test_a_write_tool_is_refused_in_read_only_mode(self, canteen):
        result = call("order_meals", {"meal_ids": [A]}, read_only=True)
        assert result.is_error
        assert canteen.routes["saveOrders"].called is False


class TestReading:
    def test_the_menu(self, canteen):
        result = data(call("get_menu"))
        assert result["ok"] is True
        assert len(result["days"]) > 5
        assert result["account"]["username"] == "test.user"
        assert {"id", "can_order", "order_restriction", "deadline"} <= set(
            result["days"][0]["meals"][0]
        )

    def test_the_menu_never_carries_a_session_id_or_the_password(self, canteen):
        text = json.dumps(data(call("get_menu")))
        assert "test-password" not in text
        assert "sid" not in data(call("get_menu"))["account"]

    def test_filters_narrow_the_menu(self, canteen):
        everything = data(call("get_menu"))["days"]
        mains = data(call("get_menu", {"meal_types": ["main"]}))["days"]
        assert {m["type"] for day in mains for m in day["meals"]} == {"main"}
        assert len(mains) <= len(everything)

        one = data(call("get_menu", {"date_from": "2026-09-07", "date_to": "2026-09-07"}))
        assert [day["date"] for day in one["days"]] == ["2026-09-07"]

        orderable = data(call("get_menu", {"orderable": True}))["days"]
        assert all(m["can_order"] for day in orderable for m in day["meals"])

    def test_a_period_is_the_clis_shortcut(self, canteen):
        result = data(call("get_menu", {"period": "week"}))
        assert result["ok"] is True  # nothing recorded falls in this week, and that is fine
        assert result["days"] == []

    def test_a_period_and_a_range_together_are_refused(self, canteen):
        text = error_text(call("get_menu", {"period": "week", "date_from": "2026-09-07"}))
        assert "not both" in text

    def test_a_bad_date_is_a_clear_error(self, canteen):
        assert "date_from" in error_text(call("get_menu", {"date_from": "next tuesday"}))

    def test_what_is_ordered(self, api, canteen):
        canteen.payload = with_ordered(load("menu_live"), 5, 7)
        canteen.table = {
            (r["datum"], r["druh"]): int(r["pocet"])
            for t in canteen.payload.values()
            if isinstance(t, list)
            for r in t
        }
        result = data(call("get_ordered"))
        assert sorted(m["id"] for m in result["meals"]) == ["2026-09-03:O1", "2026-09-04:O1"]
        assert result["count"] == 2
        assert result["total_price"] == pytest.approx(100.0)

    def test_the_balance(self, canteen):
        result = data(call("get_balance"))
        assert result["balance"] == pytest.approx(512.5)
        assert result["currency"] == "Kč"

    def test_the_account(self, canteen):
        assert data(call("get_account"))["account"]["canteen_number"]

    def test_every_call_logs_out_again(self, canteen):
        call("get_balance")
        call("get_menu")
        assert canteen.logout.call_count == 2


class TestOrdering:
    def test_ordering_changes_the_account(self, canteen):
        result = data(call("order_meals", {"meal_ids": [A]}))
        assert result["ok"] is True
        assert result["changed"] == [A]
        assert canteen.saved_keys() == {A}

    def test_ids_are_normalised_like_on_the_command_line(self, canteen):
        assert data(call("order_meals", {"meal_ids": ["2026-09-07:o2"]}))["changed"] == [A]

    def test_ordering_twice_changes_nothing_the_second_time(self, canteen):
        call("order_meals", {"meal_ids": [A]})
        again = data(call("order_meals", {"meal_ids": [A]}))
        assert again["changed"] == []
        assert again["unchanged"] == [A]

    def test_cancelling(self, canteen):
        call("order_meals", {"meal_ids": [A]})
        result = data(call("cancel_meals", {"meal_ids": [A]}))
        assert result["changed"] == [A]
        assert canteen.saved_keys() == set()

    def test_a_dry_run_sends_nothing(self, canteen):
        result = data(call("order_meals", {"meal_ids": [A], "dry_run": True}))
        assert result["dry_run"] is True
        assert result["would_change"] == [A]
        assert result["balance_change"] < 0
        assert not canteen.routes["pridejJidloS5"].called
        assert not canteen.routes["saveOrders"].called
        assert canteen.saved_keys() == set()

    def test_a_cancel_dry_run_sends_nothing_either(self, canteen):
        call("order_meals", {"meal_ids": [A]})
        saves = canteen.routes["saveOrders"].call_count
        result = data(call("cancel_meals", {"meal_ids": [A], "dry_run": True}))
        assert result["would_change"] == [A]
        assert canteen.routes["saveOrders"].call_count == saves

    def test_a_meal_past_its_deadline_is_an_error_with_the_reason(self, canteen):
        text = error_text(call("order_meals", {"meal_ids": [CLOSED]}))
        assert "MealNotOrderableError" in text
        assert "reason=closed" in text
        assert CLOSED in text
        assert canteen.saved_keys() == set()

    def test_a_soup_cannot_be_ordered_alone(self, canteen):
        assert "unavailable" in error_text(call("order_meals", {"meal_ids": [SOUP]}))

    def test_too_little_money_is_an_error_that_says_so(self, canteen):
        canteen.fail("pridejJidloS5", "funds")
        assert "InsufficientBalanceError" in error_text(call("order_meals", {"meal_ids": [A]}))

    def test_a_bare_number_is_refused_before_logging_in(self, canteen, login_route):
        text = error_text(call("order_meals", {"meal_ids": ["10"]}))
        assert "changes at every login" in text
        assert not login_route.called

    def test_no_ids_is_an_error(self, canteen, login_route):
        assert "meal_ids" in error_text(call("order_meals", {"meal_ids": []}))
        assert not login_route.called

    def test_continue_on_error_reports_instead_of_failing(self, canteen):
        result = data(call("order_meals", {"meal_ids": [A, CLOSED], "continue_on_error": True}))
        assert result["ok"] is False
        assert result["changed"] == [A]
        assert result["failed"][0]["id"] == CLOSED
        assert result["failed"][0]["error"] == "MealNotOrderableError"

    def test_strict_duplicates(self, canteen):
        text = error_text(
            call("order_meals", {"meal_ids": ["2026-09-07:O1", A], "strict_duplicates": True})
        )
        assert "DuplicateMealError" in text

    def test_a_save_that_cannot_be_confirmed_says_what_to_check(self, canteen):
        canteen.fail("objednavky", None, "timeout")  # the menu loads, the read-back does not
        text = error_text(call("order_meals", {"meal_ids": [A]}))
        assert "OrderNotConfirmedError" in text
        assert f"unconfirmed=['{A}']" in text
        assert canteen.saved_keys() == {A}  # it was saved, and the error does not claim otherwise

    def test_a_wrong_login_is_an_authentication_error(self, api, profile):
        api.post(f"{BASE_URL}/api/login").mock(
            return_value=httpx.Response(200, json=load("login_error"))
        )
        assert "AuthenticationError" in error_text(call("get_balance"))


class TestCommand:
    def test_the_profile_flag_works_before_and_after_the_command(self):
        parser = build_parser()
        assert parser.parse_args(["--profile", "a", "mcp"]).profile == "a"
        assert parser.parse_args(["mcp", "--profile", "a"]).profile == "a"
        assert parser.parse_args(["mcp"]).profile is None
        assert parser.parse_args(["mcp"]).read_only is False
        assert parser.parse_args(["mcp", "--read-only"]).read_only is True

    def test_the_command_serves_on_stdio_with_the_flag_it_was_given(self, profile, monkeypatch):
        from strava_cz import mcp_server

        seen: list[Any] = []

        class Stub:
            def run(self, transport: str) -> None:
                seen.append(transport)

        def fake_build(args: Any, *, read_only: bool = False) -> Stub:
            seen.append((args.profile, read_only))
            return Stub()

        monkeypatch.setattr(mcp_server, "build_server", fake_build)
        assert main(["mcp", "--profile", "test", "--read-only"]) == EXIT["ok"]
        assert seen == [("test", True), "stdio"]

        seen.clear()
        assert main(["--profile", "test", "mcp"]) == EXIT["ok"]
        assert seen == [("test", False), "stdio"]

    def test_stdout_is_left_to_the_protocol(self, profile, monkeypatch, capsys):
        from strava_cz import mcp_server

        class Stub:
            def run(self, transport: str) -> None:
                pass

        monkeypatch.setattr(mcp_server, "build_server", lambda *a, **k: Stub())
        main(["--profile", "test", "mcp"])
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "read" in captured.err

    def test_an_unknown_profile_stops_before_serving(self, profile, capsys):
        assert main(["--profile", "nope", "mcp"]) == EXIT["profile"]
        assert "nope" in capsys.readouterr().err

    def test_a_username_without_a_password_in_the_environment_cannot_prompt(
        self, store_path, capsys
    ):
        code = main(["--username", "x", "--canteen", "1234", "mcp"])
        assert code == EXIT["profile"]
        assert "STRAVA_CZ_PASSWORD" in capsys.readouterr().err

    def test_without_the_extra_the_command_says_how_to_install_it(
        self, profile, monkeypatch, capsys
    ):
        import strava_cz

        monkeypatch.delitem(sys.modules, "strava_cz.mcp_server", raising=False)
        monkeypatch.delattr(strava_cz, "mcp_server", raising=False)
        for name in [m for m in sys.modules if m == "mcp" or m.startswith("mcp.")]:
            monkeypatch.setitem(sys.modules, name, None)  # as if it were not installed
        monkeypatch.setitem(sys.modules, "mcp", None)
        assert main(["--profile", "test", "mcp"]) == EXIT["error"]
        assert "strava-cz[mcp]" in capsys.readouterr().err


class TestOverStdio:
    """The installed command, started as an agent's client would start it."""

    @pytest.mark.parametrize(("flags", "expected"), [([], 6), (["--read-only"], 4)])
    def test_tools_list(self, profile, store_path, flags, expected):
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "strava_cz", "--profile", "test", "mcp", *flags],
            env={"XDG_CONFIG_HOME": str(store_path.parent.parent), "PATH": ""},
        )

        async def go() -> list[str]:
            async with Client(params) as client:
                return [tool.name for tool in (await client.list_tools()).tools]

        names = anyio.run(go)
        assert len(names) == expected
        assert set(READ_TOOLS) <= set(names)
