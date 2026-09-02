"""The HTTP client: login, logout, error mapping and lifetime."""

from __future__ import annotations

import httpx
import pytest

from strava_cz import (
    AuthenticationError,
    InsufficientBalanceError,
    MenuNotFetchedError,
    NotLoggedInError,
    StravaAPIError,
    StravaCZ,
)

from .conftest import BASE_URL, load


class TestConstruction:
    def test_no_credentials_does_no_io_and_does_not_log_in(self, api):
        strava = StravaCZ()
        assert strava.user.is_logged_in is False
        assert not api.calls  # constructing a client must not touch the network

    @pytest.mark.parametrize(
        "args",
        [("user", None, None), ("user", "pass", None), (None, "pass", "1234"), ("", "", "")],
    )
    def test_partial_credentials_are_rejected(self, api, args):
        username, password, canteen = args
        if not any([username, password, canteen]):
            StravaCZ(username, password, canteen)  # all empty is "log in later"
            return
        with pytest.raises(TypeError, match="together"):
            StravaCZ(username, password, canteen)

    def test_full_credentials_log_in(self, api, login_route):
        strava = StravaCZ("test.user", "test-password", "1234")
        assert strava.user.is_logged_in
        assert login_route.called

    def test_password_is_not_retained(self, strava):
        assert "test-password" not in repr(vars(strava.user))
        assert not hasattr(strava.user, "password")


class TestLogin:
    def test_populates_the_account(self, strava):
        user = strava.user
        assert user.username == "test.user"
        assert user.canteen_number == "1234"
        assert user.full_name == "Testovací Uživatel"
        assert user.email == "test@example.com"
        assert user.canteen_name == "Testovací školní jídelna"
        assert user.currency == "Kč"
        assert user.sid == "01C6FCF02A7146159BC5F245A57AF29F"

    def test_balance_is_a_float(self, strava):
        # The API sends "512.50" as a string; arithmetic on it must work.
        assert isinstance(strava.user.balance, float)
        assert strava.user.balance == 512.50
        assert strava.user.balance - 50 == 462.50

    def test_sends_the_documented_payload(self, api, login_route):
        StravaCZ("test.user", "test-password", "1234")
        body = login_route.calls.last.request.read()
        import json

        payload = json.loads(body)
        assert payload == {
            "cislo": "1234",
            "jmeno": "test.user",
            "heslo": "test-password",
            "zustatPrihlasen": True,
            "environment": "W",
            "lang": "EN",
        }

    def test_keeps_the_web_apps_content_type(self, api, login_route):
        StravaCZ("test.user", "test-password", "1234")
        request = login_route.calls.last.request
        assert request.headers["content-type"] == "text/plain;charset=UTF-8"
        assert request.read().startswith(b"{")  # still JSON encoded

    def test_wrong_password_raises_authentication_error(self, api):
        # The real API answers a bad login with HTTP 555 and an error envelope.
        api.post(f"{BASE_URL}/api/login").mock(
            return_value=httpx.Response(555, json=load("login_error"))
        )
        strava = StravaCZ()
        with pytest.raises(AuthenticationError) as exc:
            strava.login("test.user", "wrong", "1234")
        assert exc.value.code == 20
        assert "wrong nickname or password" in exc.value.message
        assert strava.user.is_logged_in is False

    def test_success_without_a_session_id_is_still_a_failure(self, api):
        api.post(f"{BASE_URL}/api/login").mock(
            return_value=httpx.Response(200, json={"uzivatel": {}})
        )
        with pytest.raises(AuthenticationError, match="no session id"):
            StravaCZ().login("test.user", "pass", "1234")

    @pytest.mark.parametrize(
        "args, missing",
        [(("", "p", "1"), "username"), (("u", "", "1"), "password"), (("u", "p", ""), "canteen")],
    )
    def test_empty_arguments_are_rejected(self, api, args, missing):
        with pytest.raises(ValueError, match=missing):
            StravaCZ().login(*args)

    def test_logging_in_twice_is_refused(self, strava):
        with pytest.raises(AuthenticationError, match="Already logged in"):
            strava.login("test.user", "test-password", "1234")


class TestLogout:
    def test_clears_the_session(self, strava):
        assert strava.logout() is True
        assert strava.user.is_logged_in is False
        assert strava.user.sid is None

    def test_the_user_object_is_reset_in_place(self, strava):
        user = strava.user  # a reference someone might be holding
        strava.logout()
        assert user is strava.user
        assert user.is_logged_in is False

    def test_the_menu_is_cleared(self, menu):
        assert menu.menu.fetched
        menu.logout()
        assert menu.menu.fetched is False
        with pytest.raises(MenuNotFetchedError):
            _ = menu.menu.days

    def test_when_not_logged_in_it_is_a_no_op(self, api):
        assert StravaCZ().logout() is True

    def test_handles_the_bare_true_the_api_returns(self, api, strava):
        # /api/logOut answers with the JSON literal `true`, not an object.
        assert strava.logout() is True


class TestErrorHandling:
    def test_authenticated_calls_require_a_session(self, api):
        with pytest.raises(NotLoggedInError):
            StravaCZ().menu.fetch()

    def test_non_json_body_becomes_a_strava_error(self, api, strava):
        api.post(f"{BASE_URL}/api/objednavky").mock(
            return_value=httpx.Response(502, text="<html>Bad Gateway</html>")
        )
        with pytest.raises(StravaAPIError) as exc:
            strava.menu.fetch()
        assert exc.value.status_code == 502
        assert "non-JSON" in str(exc.value)

    def test_error_envelope_maps_to_a_specific_exception(self, api, strava):
        api.post(f"{BASE_URL}/api/objednavky").mock(
            return_value=httpx.Response(200, json=load("error_balance"))
        )
        with pytest.raises(InsufficientBalanceError) as exc:
            strava.menu.fetch()
        assert exc.value.code == 35

    def test_unmapped_error_codes_still_carry_their_number(self, api, strava):
        api.post(f"{BASE_URL}/api/objednavky").mock(
            return_value=httpx.Response(
                555, json={"state": "error", "number": 99, "message": "Nope"}
            )
        )
        with pytest.raises(StravaAPIError) as exc:
            strava.menu.fetch()
        assert exc.value.code == 99
        assert "API code 99" in str(exc.value)

    def test_http_error_without_an_envelope(self, api, strava):
        api.post(f"{BASE_URL}/api/objednavky").mock(return_value=httpx.Response(500, json={}))
        with pytest.raises(StravaAPIError, match="HTTP 500"):
            strava.menu.fetch()

    def test_timeouts_become_strava_errors(self, api, strava):
        api.post(f"{BASE_URL}/api/objednavky").mock(side_effect=httpx.ConnectTimeout("slow"))
        with pytest.raises(StravaAPIError, match="timed out"):
            strava.menu.fetch()

    def test_transport_errors_become_strava_errors(self, api, strava):
        api.post(f"{BASE_URL}/api/objednavky").mock(side_effect=httpx.ConnectError("refused"))
        with pytest.raises(StravaAPIError, match="failed"):
            strava.menu.fetch()


class TestTransport:
    def test_a_timeout_is_always_configured(self, api):
        strava = StravaCZ()
        assert strava._client.timeout.connect is not None
        assert strava._client.timeout.read is not None

    def test_timeout_is_configurable(self, api):
        strava = StravaCZ(timeout=1.5)
        assert strava._client.timeout.read == 1.5

    def test_accept_encoding_is_left_to_httpx(self, api):
        # Advertising br/zstd by hand risks a body the client cannot decode.
        assert "accept-encoding" not in {k.lower() for k in StravaCZ()._default_headers()}

    def test_base_url_can_be_overridden(self, api):
        assert StravaCZ(base_url="https://example.test/").base_url == "https://example.test"


class TestLifetime:
    def test_context_manager_logs_out_and_closes(self, api, login_route):
        with StravaCZ("test.user", "test-password", "1234") as strava:
            assert strava.user.is_logged_in
        assert strava.user.is_logged_in is False
        assert strava._client.is_closed

    def test_close_leaves_a_caller_supplied_client_alone(self, api):
        client = httpx.Client(base_url=BASE_URL)
        strava = StravaCZ(client=client)
        strava.close()
        assert client.is_closed is False
        client.close()

    def test_repr_never_leaks_the_session(self, strava):
        assert "test.user" in repr(strava)
        assert strava.user.sid not in repr(strava)
        assert strava.user.sid not in repr(strava.user)
