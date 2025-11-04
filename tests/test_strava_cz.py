import pytest
from unittest.mock import patch, MagicMock
from strava_cz import StravaCZ, AuthenticationError

class TestStravaCZ:
    """Test StravaCZ without real credentials using mocks."""
    
    def test_import(self):
        """Test that the package imports correctly."""
        assert StravaCZ is not None
    
    @patch('strava_cz.main.requests.Session')
    def test_initialization_valid_params(self, mock_Session):
        # Create a fake session whose .post() returns our fake_response
        fake_session = MagicMock()
        mock_Session.return_value = fake_session

        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            "sid": "FAKE_SID",
            "s5url": "https://fake.s5url",
            "cislo": "1234",
            "jmeno": "fake_user",
            "uzivatel": {
                "id": "fake_user",
                "email": "x@y.cz",
                "konto": "0.00",
                "mena": "Kč",
                "nazevJidelny": "Test Canteen"
            },
            "betatest": False,
            "ignoreCert": False,
            "zustatPrihlasen": False
        }
        fake_session.post.return_value = fake_response

        # Exercise
        strava = StravaCZ("fake_user", "fake_pass", "1234")

        # Verify fields set
        assert strava.user.username == "fake_user"
        assert strava.user.canteen_number == "1234"
        assert strava.user.sid == "FAKE_SID"
        # And ensure we never made real HTTP calls:
        mock_Session.assert_called_once()
        fake_session.post.assert_called()
    
    def test_initialization_invalid_params(self):
        """Test initialization with invalid parameters."""
        with pytest.raises(AuthenticationError):
            StravaCZ("", "", "")
    
    @patch('strava_cz.main.requests.Session')
    def test_login_success(self, mock_Session):
        """Test successful login without real credentials."""
        # Arrange: create a fake session and response
        fake_session = MagicMock()
        mock_Session.return_value = fake_session

        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            "sid": "FAKE_SID",
            "s5url": "https://fake.s5url",
            "cislo": "1234",
            "jmeno": "fake_user",
            "uzivatel": {
                "id": "fake_user",
                "email": "x@y.cz",
                "konto": "0.00",
                "mena": "Kč",
                "nazevJidelny": "Test Canteen"
            },
            "betatest": False,
            "ignoreCert": False,
            "zustatPrihlasen": False
        }
        fake_response.cookies = {'session_id': 'fake_session_123'}
        fake_session.post.return_value = fake_response

        # Act
        strava = StravaCZ("fake_user", "fake_pass", "1234")

        # Assert
        mock_Session.assert_called_once()
        fake_session.post.assert_called_once()
        assert strava.user.username == "fake_user"
        assert strava.user.sid == "FAKE_SID"
        assert strava.user.canteen_number == "1234"
    
    @patch('strava_cz.main.requests.post')
    def test_login_failure(self, mock_post):
        """Test failed login handling."""
        # Mock failed login response
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json = '{"message": "Invalid credentials"}'
        mock_post.return_value = mock_response
        
        with pytest.raises(Exception):  # Adjust based on your error handling
            StravaCZ("bad_user", "bad_pass", "1234")
    
    @patch('strava_cz.main.requests.Session')
    def test_get_menu(self, mock_Session):
        """Test get_menu returns correctly formatted data without real HTTP calls."""
        # Arrange: fake session and responses
        fake_session = MagicMock()
        mock_Session.return_value = fake_session

        # 1) Login response
        login_response = MagicMock()
        login_response.status_code = 200
        login_response.json.return_value = {
            "sid": "SID123",
            "s5url": "https://fake.s5url",
            "cislo": "3753",
            "jmeno": "user",
            "uzivatel": {
                "id": "user",
                "email": "u@e.cz",
                "konto": "10.00",
                "mena": "Kč",
                "nazevJidelny": "Test Canteen"
            },
            "betatest": False,
            "ignoreCert": False,
            "zustatPrihlasen": False
        }

        # 2) menu response
        menu_response = MagicMock()
        menu_response.status_code = 200
        menu_response.json.return_value = {
            "table0": [
                {
                    "id": 0,
                    "datum": "15.09.2025",
                    "druh_popis": "Polévka",
                    "delsiPopis": "zelnacka",
                    "nazev": "Vývar",
                    "zakazaneAlergeny": None,
                    "alergeny": [["01", "brambory"]],
                    "omezeniObj": {"den": ""},
                    "pocet": 0,
                    "veta": "75",
                    "cena": "40.00"
                },
                {
                    "id": 1,
                    "datum": "15.09.2025",
                    "druh_popis": "Oběd1",
                    "delsiPopis": "Rajská omáčka s těstovinami",
                    "nazev": "Rajská omáčka s těstovinami",
                    "zakazaneAlergeny": None,
                    "alergeny": [["69", "pavel"]],
                    "omezeniObj": {"den": ""},
                    "pocet": 1,
                    "veta": "1",
                    "cena": "40.00"
                }
            ]
        }

        # Configure post side_effect: first call is login, second is menu list
        fake_session.post.side_effect = [login_response, menu_response]

        # Act: initialize (logs in) and fetch menu
        s = StravaCZ("user", "pass", "3753")
        menu = s.get_menu(include_soup=True)

        # Assert structure
        assert isinstance(menu, list)
        assert len(menu) == 1
        day = menu[0]
        assert day["date"] == "2025-09-15"
        meals = day["meals"]
        assert len(meals) == 2

        # First meal: not ordered
        first = meals[0]
        assert first["local_id"] == 0
        assert first["type"] == "Polévka"
        assert first["name"] == "Vývar"
        assert first["ordered"] is False
        assert first["id"] == 75

        # Second meal: ordered
        second = meals[1]
        assert second["local_id"] == 1
        assert second["type"] == "Oběd1"
        assert second["name"] == "Rajská omáčka s těstovinami"
        assert second["ordered"] is True
        assert second["id"] == 1

        # Verify two POST calls occurred
        assert fake_session.post.call_count == 2
