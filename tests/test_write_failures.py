"""What a write leaves behind when one of its steps fails, and whether the caller is told.

Runs against :class:`~tests.conftest.FakeCanteen`, which copies how the live canteen treats
a session's orders and numbers, because a mock that simply answers can't show any of this.
"""

from __future__ import annotations

import json

import httpx
import pytest

import strava_cz as sc
from strava_cz import MenuNotFetchedError, Profile, ProfileStore, SecretSource, StravaAPIError
from strava_cz.cli import EXIT, main

from .conftest import FakeCanteen

A = "2026-09-07:O2"
B = "2026-09-08:O2"
CLOSED = "2026-09-02:O1"
SOUP = "2026-09-02:PO"


@pytest.fixture
def canteen(api, menu_payload):
    return FakeCanteen(api, menu_payload)


@pytest.fixture
def strava(canteen, login_route):
    client = sc.StravaCZ("test.user", "test-password", "1234")
    client.menu.fetch()
    return client


class TestNumbersMoveOnAReset:
    """A reset renumbers the menu, so nothing read before it may decide what gets ordered."""

    def test_a_retry_after_every_stage_failed_orders_the_meal_it_names(self, strava, canteen):
        canteen.fail("pridejJidloS5", "refuse", "refuse")
        result = strava.menu.order_meals(A, B, continue_on_error=True)
        assert result.changed == ()

        assert strava.menu.order_meals(A).changed == (A,)
        assert canteen.saved_keys() == {A}

    def test_a_failed_reload_leaves_no_numbers_behind_to_order_with(self, strava, canteen):
        canteen.fail("pridejJidloS5", "refuse")
        canteen.fail("objednavky", "timeout")
        with pytest.raises(StravaAPIError):
            strava.menu.order_meals(A)

        with pytest.raises(MenuNotFetchedError):
            strava.menu.order_meals(A)
        assert canteen.saved_keys() == set()

        strava.menu.fetch()
        assert strava.menu.order_meals(A).changed == (A,)
        assert canteen.saved_keys() == {A}

    def test_a_number_read_before_a_reset_is_refused(self, strava, canteen):
        number = strava.menu.get_by_key(A).id
        canteen.fail("pridejJidloS5", "refuse")
        with pytest.raises(StravaAPIError):
            strava.menu.order_meals(number)

        with pytest.raises(MenuNotFetchedError, match="renumber"):
            strava.menu.order_meals(number)
        with pytest.raises(MenuNotFetchedError, match="renumber"):
            strava.menu.get_by_id(number)
        assert number not in strava.menu
        assert canteen.saved_keys() == set()

    def test_a_key_keeps_working_after_a_reset(self, strava, canteen):
        canteen.fail("pridejJidloS5", "refuse")
        with pytest.raises(StravaAPIError):
            strava.menu.order_meals(A)
        assert strava.menu.order_meals(A).changed == (A,)
        assert canteen.saved_keys() == {A}

    def test_fetching_makes_numbers_usable_again(self, strava, canteen):
        canteen.fail("pridejJidloS5", "refuse")
        with pytest.raises(StravaAPIError):
            strava.menu.order_meals(A)

        strava.menu.fetch()
        number = strava.menu.get_by_key(A).id
        assert strava.menu.order_meals(number).changed == (number,)
        assert canteen.saved_keys() == {A}

    def test_a_write_that_worked_leaves_the_numbers_valid(self, strava, canteen):
        first, second = (strava.menu.get_by_key(k).id for k in (A, B))
        strava.menu.order_meals(first)
        strava.menu.order_meals(second)
        assert canteen.saved_keys() == {A, B}

    def test_a_reset_that_failed_is_made_up_for_before_the_next_fetch(self, strava, canteen):
        """Otherwise the staged meal would show as ordered and the next save would commit it."""
        canteen.fail("pridejJidloS5", None, "refuse")
        canteen.fail("nactiVlastnostiPA", "timeout")
        with pytest.raises(StravaAPIError):
            strava.menu.order_meals(A, B)

        strava.menu.fetch()
        assert strava.menu.is_ordered(A) is False
        strava.menu.order_meals(B)
        assert canteen.saved_keys() == {B}


class TestASaveWhoseAnswerNeverArrived:
    """A timeout on the save says nothing about the save, so the menu has to be read back."""

    def test_one_that_landed_is_a_success(self, strava, canteen):
        canteen.fail("saveOrders", "lost")
        assert strava.menu.order_meals(A).changed == (A,)
        assert canteen.saved_keys() == {A}

    def test_a_gateway_error_that_landed_is_a_success(self, strava, canteen):
        canteen.fail("saveOrders", "502-lost")
        assert strava.menu.order_meals(A).changed == (A,)
        assert canteen.saved_keys() == {A}

    def test_one_that_did_not_land_says_nothing_was_saved(self, strava, canteen):
        canteen.fail("saveOrders", "timeout")
        with pytest.raises(StravaAPIError, match="Nothing was saved"):
            strava.menu.order_meals(A)
        assert canteen.saved_keys() == set()

    def test_when_it_cannot_be_read_back_either_it_says_it_does_not_know(self, strava, canteen):
        canteen.fail("saveOrders", "lost")
        canteen.fail("nactiVlastnostiPA", "timeout")
        with pytest.raises(sc.OrderNotConfirmedError, match="may or may not") as exc:
            strava.menu.order_meals(A, B)
        assert exc.value.unconfirmed == (A, B)
        assert exc.value.changed == ()

    def test_continuing_on_error_does_not_change_that(self, strava, canteen):
        canteen.fail("saveOrders", "timeout")
        canteen.fail("nactiVlastnostiPA", "timeout")
        with pytest.raises(sc.OrderNotConfirmedError):
            strava.menu.order_meals(A, continue_on_error=True)


class TestASaveTheCanteenRefused:
    def test_it_raises_the_refusal_with_nothing_saved(self, strava, canteen):
        canteen.fail("saveOrders", "refuse")
        with pytest.raises(StravaAPIError, match="Nothing was saved") as exc:
            strava.menu.order_meals(A)
        assert exc.value.code == 7
        assert canteen.saved_keys() == set()

    def test_for_lack_of_money_it_is_still_that_error(self, strava, canteen):
        canteen.fail("saveOrders", "funds")
        with pytest.raises(sc.InsufficientBalanceError):
            strava.menu.order_meals(A)

    def test_a_refusal_stays_a_refusal_when_the_read_back_fails_too(self, strava, canteen):
        """The canteen answered no. Not being able to look again doesn't make that a maybe."""
        canteen.fail("saveOrders", "refuse")
        canteen.fail("nactiVlastnostiPA", "timeout")
        with pytest.raises(StravaAPIError, match="Nope") as exc:
            strava.menu.order_meals(A)
        assert not isinstance(exc.value, sc.OrderNotConfirmedError)


class TestAReadBackThatFails:
    """The canteen took the save. Failing to read it back must not sound like a failed order."""

    def test_it_says_the_canteen_accepted_it(self, strava, canteen):
        canteen.fail("objednavky", "timeout")
        with pytest.raises(sc.OrderNotConfirmedError, match="accepted") as exc:
            strava.menu.order_meals(A)
        assert exc.value.unconfirmed == (A,)
        assert canteen.saved_keys() == {A}

    def test_a_gateway_error_there_is_the_same(self, strava, canteen):
        canteen.fail("objednavky", "502")
        with pytest.raises(sc.OrderNotConfirmedError, match="accepted"):
            strava.menu.order_meals(A)

    def test_continuing_on_error_does_not_hide_it(self, strava, canteen):
        canteen.fail("objednavky", "timeout")
        with pytest.raises(sc.OrderNotConfirmedError, match="accepted"):
            strava.menu.order_meals(A, B, continue_on_error=True)
        assert canteen.saved_keys() == {A, B}

    def test_the_old_menu_is_not_left_looking_current(self, strava, canteen):
        canteen.fail("objednavky", "timeout")
        with pytest.raises(sc.OrderNotConfirmedError):
            strava.menu.order_meals(A)
        with pytest.raises(MenuNotFetchedError):
            strava.menu.is_ordered(A)
        assert strava.menu.fetch().is_ordered(A) is True


class TestAStageWhoseAnswerNeverArrived:
    def test_one_that_landed_and_got_saved_is_reported_as_changed(self, strava, canteen):
        canteen.fail("pridejJidloS5", "lost", None)
        result = strava.menu.order_meals(A, B, continue_on_error=True)
        assert canteen.saved_keys() == {A, B}
        assert set(result.changed) == {A, B}
        assert result.ok

    def test_one_that_did_not_land_stays_failed(self, strava, canteen):
        canteen.fail("pridejJidloS5", "timeout", None)
        result = strava.menu.order_meals(A, B, continue_on_error=True)
        assert canteen.saved_keys() == {B}
        assert result.changed == (B,)
        assert [ref for ref, _ in result.failed] == [A]

    def test_without_continuing_nothing_is_saved_and_it_says_so(self, strava, canteen):
        canteen.fail("pridejJidloS5", None, "lost")
        with pytest.raises(StravaAPIError, match="timed out"):
            strava.menu.order_meals(A, B)
        assert canteen.saved_keys() == set()


class TestAWriteThatPartlyLanded:
    def test_it_names_what_changed_and_what_did_not(self, strava, canteen):
        canteen.not_recorded.add(("07.09.2026", "O2"))
        with pytest.raises(sc.OrderNotConfirmedError, match="still not ordered") as exc:
            strava.menu.order_meals(A, B, verify_saved=True)
        assert exc.value.unconfirmed == (A,)
        assert exc.value.changed == (B,)
        assert B in str(exc.value)

    def test_continuing_on_error_reports_it_per_meal(self, strava, canteen):
        canteen.not_recorded.add(("07.09.2026", "O2"))
        result = strava.menu.order_meals(A, B, continue_on_error=True, verify_saved=True)
        assert result.changed == (B,)
        assert [ref for ref, _ in result.failed] == [A]


class TestVerifySaved:
    """A fetch in the same session reads the session's own copy, staged changes included."""

    def test_a_same_session_read_cannot_see_a_save_that_did_nothing(self, strava, canteen):
        """The default, and why the option exists."""
        canteen.fail("saveOrders", "ignored")
        assert strava.menu.order_meals(A).changed == (A,)
        assert canteen.saved_keys() == set()

    def test_reading_the_canteens_records_can(self, strava, canteen):
        canteen.fail("saveOrders", "ignored")
        with pytest.raises(StravaAPIError, match="still not ordered"):
            strava.menu.order_meals(A, verify_saved=True)

    def test_cancelling_takes_it_too(self, strava, canteen):
        strava.menu.order_meals(A)
        canteen.fail("saveOrders", "ignored")
        with pytest.raises(StravaAPIError, match="still ordered"):
            strava.menu.cancel_meals(A, verify_saved=True)

    def test_a_write_that_landed_passes(self, strava, canteen):
        assert strava.menu.order_meals(A, verify_saved=True).changed == (A,)
        assert canteen.saved_keys() == {A}
        assert strava.menu.is_ordered(A) is True

    def test_it_renumbers_so_old_numbers_are_refused(self, strava, canteen):
        number = strava.menu.get_by_key(A).id
        strava.menu.order_meals(number, verify_saved=True)
        with pytest.raises(MenuNotFetchedError, match="renumber"):
            strava.menu.order_meals(number)


@pytest.fixture
def cli_canteen(canteen, login_route, store_path, monkeypatch):
    ProfileStore(store_path).save(Profile("test", "test.user", "1234", secret=SecretSource.ENV))
    monkeypatch.setenv("STRAVA_CZ_PASSWORD", "test-password")
    return canteen


#: A step that goes wrong, and what the command must then say about the account.
FAILURES = [
    pytest.param("saveOrders", ["timeout"], 1, "Nothing was saved", set(), id="save-timeout"),
    pytest.param("saveOrders", ["refuse"], 1, "Nothing was saved", set(), id="save-refused"),
    pytest.param("saveOrders", ["502"], 1, "Nothing was saved", set(), id="save-502"),
    pytest.param("saveOrders", ["lost"], 0, "ordered 1", {A}, id="save-landed-answer-lost"),
    pytest.param("saveOrders", ["ignored"], 1, "still not ordered", set(), id="save-ignored"),
    pytest.param("pridejJidloS5", ["timeout"], 1, "timed out", set(), id="stage-timeout"),
    pytest.param("pridejJidloS5", ["lost"], 1, "timed out", set(), id="stage-landed-answer-lost"),
    pytest.param("nactiVlastnostiPA", ["timeout"], 1, "accepted", {A}, id="reset-timeout"),
    pytest.param("nactiVlastnostiPA", ["502"], 1, "accepted", {A}, id="reset-502"),
    pytest.param("objednavky", [None, "timeout"], 1, "accepted", {A}, id="read-back-timeout"),
    pytest.param("objednavky", [None, "502"], 1, "accepted", {A}, id="read-back-502"),
    pytest.param("objednavky", ["timeout"], 1, "timed out", set(), id="first-fetch-timeout"),
]


class TestTheCommandTellsTheTruth:
    @pytest.mark.parametrize(("endpoint", "modes", "code", "said", "saved"), FAILURES)
    def test_pretty(self, cli_canteen, capsys, endpoint, modes, code, said, saved):
        cli_canteen.fail(endpoint, *modes)
        assert main(["order", A]) == code
        captured = capsys.readouterr()
        assert said in captured.out + captured.err
        assert cli_canteen.saved_keys() == saved

    @pytest.mark.parametrize(("endpoint", "modes", "code", "said", "saved"), FAILURES)
    def test_json(self, cli_canteen, capsys, endpoint, modes, code, said, saved):
        cli_canteen.fail(endpoint, *modes)
        assert main(["--json", "order", A]) == code
        body = json.loads(capsys.readouterr().out)
        assert body["ok"] is (code == 0)
        assert cli_canteen.saved_keys() == saved

    def test_json_names_what_is_unconfirmed(self, cli_canteen, capsys):
        cli_canteen.fail("nactiVlastnostiPA", "timeout")
        assert main(["--json", "order", A, B]) == EXIT["error"]
        error = json.loads(capsys.readouterr().out)["error"]
        assert error["type"] == "OrderNotConfirmedError"
        assert error["unconfirmed"] == [A, B]
        assert error["changed"] == []

    @pytest.mark.parametrize(("endpoint", "modes", "code", "said", "saved"), FAILURES)
    def test_it_logs_out_whatever_happened(
        self, cli_canteen, capsys, endpoint, modes, code, said, saved
    ):
        cli_canteen.fail(endpoint, *modes)
        main(["order", A])
        assert cli_canteen.logout.call_count == 1

    @pytest.mark.parametrize("flag", [[], ["--json"]])
    @pytest.mark.parametrize(("endpoint", "modes", "code", "said", "saved"), FAILURES)
    def test_no_secret_reaches_the_output(
        self, cli_canteen, capsys, flag, endpoint, modes, code, said, saved
    ):
        from .conftest import load

        cli_canteen.fail(endpoint, *modes)
        main([*flag, "order", A])
        captured = capsys.readouterr()
        session = load("login")
        for secret in ("test-password", session["sid"], session["s5url"]):
            assert secret not in captured.out + captured.err


class TestExitCodesWhileContinuing:
    """--continue-on-error is how every weekly run calls this, so its exit code has to mean it."""

    def test_no_money_exits_five(self, cli_canteen, capsys):
        cli_canteen.fail("pridejJidloS5", "funds")
        assert main(["order", A, "--continue-on-error"]) == EXIT["balance"]

    def test_no_money_outranks_a_closed_day(self, cli_canteen, capsys):
        cli_canteen.fail("pridejJidloS5", "funds")
        assert main(["order", A, CLOSED, "--continue-on-error"]) == EXIT["balance"]

    def test_a_network_failure_exits_one(self, cli_canteen, capsys):
        cli_canteen.fail("pridejJidloS5", "timeout")
        assert main(["order", A, "--continue-on-error"]) == EXIT["error"]

    def test_a_network_failure_outranks_a_closed_day(self, cli_canteen, capsys):
        cli_canteen.fail("pridejJidloS5", "timeout", None)
        assert main(["order", A, B, CLOSED, "--continue-on-error"]) == EXIT["error"]
        assert cli_canteen.saved_keys() == {B}

    def test_a_meal_the_canteen_refused_exits_four(self, cli_canteen, capsys):
        cli_canteen.fail("pridejJidloS5", "refuse", None)
        assert main(["order", A, B, "--continue-on-error"]) == EXIT["meal"]
        assert cli_canteen.saved_keys() == {B}

    def test_a_closed_day_and_a_soup_exit_four(self, cli_canteen, capsys):
        assert main(["order", A, CLOSED, SOUP, "--continue-on-error"]) == EXIT["meal"]
        assert cli_canteen.saved_keys() == {A}

    def test_a_save_that_did_not_take_exits_one(self, cli_canteen, capsys):
        cli_canteen.not_recorded.add(("07.09.2026", "O2"))
        assert main(["order", A, B, "--continue-on-error"]) == EXIT["error"]
        assert cli_canteen.saved_keys() == {B}

    @pytest.mark.parametrize("flag", [[], ["--continue-on-error"]])
    def test_a_session_that_died_exits_three_with_nothing_saved(self, cli_canteen, capsys, flag):
        cli_canteen.fail("pridejJidloS5", None, "expired")
        assert main(["order", A, B, *flag]) == EXIT["auth"]
        assert cli_canteen.saved_keys() == set()
        assert cli_canteen.logout.call_count == 1


BATCHES = [
    pytest.param([A, B], [], id="plain"),
    pytest.param([A, B], ["--continue-on-error"], id="plain-continuing"),
    pytest.param([A, CLOSED, B], [], id="closed-stops-it"),
    pytest.param([A, CLOSED, SOUP, B], ["--continue-on-error"], id="closed-continuing"),
    pytest.param([A, "2030-01-01:O1"], [], id="unknown-stops-it"),
    pytest.param([A, "2026-09-07:O1"], [], id="duplicate"),
    pytest.param([A, "2026-09-07:O1", B], ["--strict-duplicates"], id="duplicate-strict"),
    pytest.param([SOUP], [], id="only-a-soup"),
]


class TestADryRunPredictsTheRealCall:
    """Whatever a dry run says would change is exactly what the real call then changes."""

    @pytest.mark.parametrize(("meals", "flags"), BATCHES)
    def test_it_agrees(self, cli_canteen, capsys, meals, flags, recwarn):
        dry_code = main(["--json", "order", *meals, *flags, "--dry-run"])
        dry = json.loads(capsys.readouterr().out)
        assert cli_canteen.saved_keys() == set()

        real_code = main(["--json", "order", *meals, *flags])
        assert dry_code == real_code
        assert set(dry["would_change"]) == cli_canteen.saved_keys()
        assert [meal["id"] for meal in dry["meals"]] == dry["would_change"]
        assert dry["ok"] is (real_code == 0)

    def test_it_says_why_a_refusal_stops_the_batch(self, cli_canteen, capsys):
        assert main(["order", A, CLOSED, "--dry-run"]) == EXIT["meal"]
        out = capsys.readouterr().out
        assert "--continue-on-error" in out
        assert "would order:" not in out

    def test_json_names_what_the_refusal_held_back(self, cli_canteen, capsys):
        main(["--json", "order", A, CLOSED, "--dry-run"])
        body = json.loads(capsys.readouterr().out)
        assert body["would_change"] == []
        assert body["blocked"] == [A]

    def test_a_swap_costs_the_difference_not_the_whole_price(self, cli_canteen, capsys):
        cli_canteen.table[("07.09.2026", "O1")] = 1
        main(["--json", "order", A, "--dry-run"])
        assert json.loads(capsys.readouterr().out)["balance_change"] == 0

    def test_an_order_on_an_empty_day_costs_the_price(self, cli_canteen, capsys):
        main(["--json", "order", A, "--dry-run"])
        assert json.loads(capsys.readouterr().out)["balance_change"] == -50


class TestAMealAlreadyOrderedAndItsAlternative:
    """Asked for both, the canteen could only keep one, so what's there already stays."""

    BOTH = (("2026-09-07:O1", A), (A, "2026-09-07:O1"))

    @pytest.fixture(autouse=True)
    def monday_has_lunch_1(self, canteen):
        canteen.saved[("07.09.2026", "O1")] = 1
        canteen.table[("07.09.2026", "O1")] = 1

    @pytest.mark.parametrize("meals", BOTH)
    def test_nothing_is_swapped(self, strava, canteen, meals, recwarn):
        result = strava.menu.order_meals(*meals)
        assert result.changed == ()
        assert result.unchanged == ("2026-09-07:O1",)
        assert [ref for ref, _ in result.skipped] == [A]
        assert not canteen.routes["pridejJidloS5"].called
        assert canteen.saved_keys() == {"2026-09-07:O1"}

    @pytest.mark.parametrize("meals", BOTH)
    def test_strict_mode_refuses_it(self, strava, canteen, meals):
        with pytest.raises(sc.DuplicateMealError):
            strava.menu.order_meals(*meals, strict_duplicates=True)

    @pytest.mark.parametrize("meals", BOTH)
    def test_a_dry_run_says_the_same(self, cli_canteen, capsys, meals, recwarn):
        assert main(["--json", "order", *meals, "--dry-run"]) == EXIT["ok"]
        body = json.loads(capsys.readouterr().out)
        assert body["would_change"] == []
        assert body["already"] == ["2026-09-07:O1"]
        assert [item["id"] for item in body["duplicate"]] == [A]

    def test_cancelling_both_is_not_a_duplicate(self, strava, canteen):
        result = strava.menu.cancel_meals(*self.BOTH[0])
        assert result.changed == ("2026-09-07:O1",)
        assert result.unchanged == (A,)


class TestADryRunAndTheMoney:
    """The live canteen refused a Friday at zero balance (code 35), so it isn't only prepaid."""

    def test_it_warns_when_the_order_would_go_below_zero(self, cli_canteen, capsys, api):
        from .conftest import BASE_URL, load

        login = load("login")
        login["uzivatel"]["konto"] = "0.00"
        api.post(f"{BASE_URL}/api/login").mock(return_value=httpx.Response(200, json=login))
        assert main(["order", A, "--dry-run"]) == EXIT["ok"]
        assert "canteen may refuse" in capsys.readouterr().err

    def test_json_says_what_the_balance_would_be(self, cli_canteen, capsys, api):
        from .conftest import BASE_URL, load

        login = load("login")
        login["uzivatel"]["konto"] = "0.00"
        api.post(f"{BASE_URL}/api/login").mock(return_value=httpx.Response(200, json=login))
        main(["--json", "order", A, "--dry-run"])
        captured = capsys.readouterr()
        assert json.loads(captured.out)["balance_after"] == -50
        assert "canteen may refuse" in captured.err

    def test_a_swap_at_zero_is_no_cause_for_alarm(self, cli_canteen, capsys, api):
        from .conftest import BASE_URL, load

        login = load("login")
        login["uzivatel"]["konto"] = "0.00"
        api.post(f"{BASE_URL}/api/login").mock(return_value=httpx.Response(200, json=login))
        cli_canteen.table[("07.09.2026", "O1")] = 1
        main(["order", A, "--dry-run"])
        assert "canteen may refuse" not in capsys.readouterr().err
