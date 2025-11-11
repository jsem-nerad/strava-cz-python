# !! NOTICE / UPOZORNENI !! 
# ===========================
# These tests were made mostly by an LLM,
# but they have been reviewed by me.
#  - - - - - - - - - - - - - 
# Tyto testy byly vytvořeny převážně pomociLLM,
# ale byly mnou zkontrolovany.
# ===========================

import pytest
from unittest.mock import patch, MagicMock
from strava_cz import StravaCZ, AuthenticationError, MealType, OrderType

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
    def test_menu_fetch_and_filtering(self, mock_Session):
        """Test menu.fetch() and filtering methods work correctly."""
        # Arrange: fake session and responses
        fake_session = MagicMock()
        mock_Session.return_value = fake_session

        # 1) Login response
        login_response = MagicMock()
        login_response.status_code = 200
        login_response.json.return_value = {
            "sid": "SID123",
            "s5url": "https://fake.s5url",
            "cislo": "1234",
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

        # 2) menu response with different meal types and order types
        menu_response = MagicMock()
        menu_response.status_code = 200
        menu_response.json.return_value = {
            "table0": [
                {
                    "id": 0,
                    "datum": "15-09.2025",
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
                    "datum": "15-09.2025",
                    "druh_popis": "Oběd1",
                    "delsiPopis": "Rajská omáčka s těstovinami",
                    "nazev": "Rajská omáčka s těstovinami",
                    "zakazaneAlergeny": None,
                    "alergeny": [["69", "pavel"]],
                    "omezeniObj": {"den": ""},
                    "pocet": 1,
                    "veta": "1",
                    "cena": "40.00"
                },
                {
                    "id": 2,
                    "datum": "16-09.2025",
                    "druh_popis": "Oběd1",
                    "delsiPopis": "Restricted meal",
                    "nazev": "Restricted meal",
                    "zakazaneAlergeny": None,
                    "alergeny": [],
                    "omezeniObj": {"den": "CO"},
                    "pocet": 0,
                    "veta": "2",
                    "cena": "50.00"
                },
                {
                    "id": 3,
                    "datum": "16-09.2025",
                    "druh_popis": "Oběd2",
                    "delsiPopis": "Optional meal",
                    "nazev": "Optional meal",
                    "zakazaneAlergeny": None,
                    "alergeny": [],
                    "omezeniObj": {"den": "T"},
                    "pocet": 0,
                    "veta": "3",
                    "cena": "45.00"
                }
            ]
        }

        # Configure post side_effect: first call is login, second is menu
        fake_session.post.side_effect = [login_response, menu_response]

        # Act: initialize (logs in) and fetch menu
        s = StravaCZ("user", "pass", "1234")
        s.menu.fetch()

        # Test get_days() - default should return only NORMAL order types
        normal_days = s.menu.get_days()
        assert len(normal_days) == 1
        assert normal_days[0]["date"] == "2025-09-15"
        assert len(normal_days[0]["meals"]) == 2  # Soup and main

        # Test get_days with all order types
        all_days = s.menu.get_days(
            order_types=[OrderType.NORMAL, OrderType.RESTRICTED, OrderType.OPTIONAL]
        )
        assert len(all_days) == 2
        
        # Test get_meals() - flat list
        normal_meals = s.menu.get_meals()
        assert len(normal_meals) == 2
        
        # Test filtering by meal type
        soups = s.menu.get_meals(meal_types=[MealType.SOUP])
        assert len(soups) == 1
        assert soups[0]["type"] == MealType.SOUP
        assert soups[0]["name"] == "Vývar"
        
        mains = s.menu.get_meals(meal_types=[MealType.MAIN])
        assert len(mains) == 1
        assert mains[0]["type"] == MealType.MAIN
        
        # Test filtering by order status
        ordered_meals = s.menu.get_meals(ordered=True)
        assert len(ordered_meals) == 1
        assert ordered_meals[0]["ordered"] is True
        assert ordered_meals[0]["name"] == "Rajská omáčka s těstovinami"
        
        # Test get_by_id
        meal = s.menu.get_by_id(75)
        assert meal is not None
        assert meal["name"] == "Vývar"
        assert meal["type"] == MealType.SOUP
        
        # Test get_by_date
        day = s.menu.get_by_date("2025-09-15")
        assert day is not None
        assert len(day["meals"]) == 2
        
        # Test is_ordered
        assert s.menu.is_ordered(1) is True
        assert s.menu.is_ordered(75) is False
        
        # Verify two POST calls occurred (login + fetch)
        assert fake_session.post.call_count == 2
    
    @patch('strava_cz.main.requests.Session')
    def test_menu_order_types(self, mock_Session):
        """Test that order types are correctly assigned and filtered."""
        fake_session = MagicMock()
        mock_Session.return_value = fake_session

        login_response = MagicMock()
        login_response.status_code = 200
        login_response.json.return_value = {
            "sid": "SID123",
            "s5url": "https://fake.s5url",
            "cislo": "1234",
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

        menu_response = MagicMock()
        menu_response.status_code = 200
        menu_response.json.return_value = {
            "table0": [
                {
                    "id": 0,
                    "datum": "15-09.2025",
                    "druh_popis": "Oběd1",
                    "delsiPopis": "Normal meal",
                    "nazev": "Normal meal",
                    "zakazaneAlergeny": None,
                    "alergeny": [],
                    "omezeniObj": {"den": ""},
                    "pocet": 0,
                    "veta": "1",
                    "cena": "40.00"
                },
                {
                    "id": 1,
                    "datum": "15-09.2025",
                    "druh_popis": "Oběd2",
                    "delsiPopis": "Restricted meal",
                    "nazev": "Restricted meal",
                    "zakazaneAlergeny": None,
                    "alergeny": [],
                    "omezeniObj": {"den": "CO"},
                    "pocet": 0,
                    "veta": "2",
                    "cena": "40.00"
                },
                {
                    "id": 2,
                    "datum": "15-09.2025",
                    "druh_popis": "Oběd3",
                    "delsiPopis": "Optional meal",
                    "nazev": "Optional meal",
                    "zakazaneAlergeny": None,
                    "alergeny": [],
                    "omezeniObj": {"den": "T"},
                    "pocet": 0,
                    "veta": "3",
                    "cena": "40.00"
                }
            ]
        }

        fake_session.post.side_effect = [login_response, menu_response]

        s = StravaCZ("user", "pass", "1234")
        s.menu.fetch()

        # Test that meals have correct orderType
        all_meals = s.menu.get_meals(
            order_types=[OrderType.NORMAL, OrderType.RESTRICTED, OrderType.OPTIONAL]
        )
        assert len(all_meals) == 3
        assert all_meals[0]["orderType"] == OrderType.NORMAL
        assert all_meals[1]["orderType"] == OrderType.RESTRICTED
        assert all_meals[2]["orderType"] == OrderType.OPTIONAL

        # Test filtering by specific order types
        restricted_only = s.menu.get_meals(order_types=[OrderType.RESTRICTED])
        assert len(restricted_only) == 1
        assert restricted_only[0]["name"] == "Restricted meal"

        optional_only = s.menu.get_meals(order_types=[OrderType.OPTIONAL])
        assert len(optional_only) == 1
        assert optional_only[0]["name"] == "Optional meal"

        # Test default behavior (only NORMAL)
        normal_only = s.menu.get_meals()
        assert len(normal_only) == 1
        assert normal_only[0]["name"] == "Normal meal"
    
    @patch('strava_cz.main.requests.Session')
    def test_menu_iteration(self, mock_Session):
        """Test that menu supports iteration and len()."""
        fake_session = MagicMock()
        mock_Session.return_value = fake_session

        login_response = MagicMock()
        login_response.status_code = 200
        login_response.json.return_value = {
            "sid": "SID123",
            "s5url": "https://fake.s5url",
            "cislo": "1234",
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

        menu_response = MagicMock()
        menu_response.status_code = 200
        menu_response.json.return_value = {
            "table0": [
                {
                    "id": 0,
                    "datum": "15-09.2025",
                    "druh_popis": "Oběd1",
                    "delsiPopis": "Meal 1",
                    "nazev": "Meal 1",
                    "zakazaneAlergeny": None,
                    "alergeny": [],
                    "omezeniObj": {"den": ""},
                    "pocet": 0,
                    "veta": "1",
                    "cena": "40.00"
                },
                {
                    "id": 1,
                    "datum": "16-09.2025",
                    "druh_popis": "Oběd1",
                    "delsiPopis": "Meal 2",
                    "nazev": "Meal 2",
                    "zakazaneAlergeny": None,
                    "alergeny": [],
                    "omezeniObj": {"den": ""},
                    "pocet": 0,
                    "veta": "2",
                    "cena": "40.00"
                }
            ]
        }

        fake_session.post.side_effect = [login_response, menu_response]

        s = StravaCZ("user", "pass", "1234")
        s.menu.fetch()

        # Test len()
        assert len(s.menu) == 2

        # Test iteration
        days = list(s.menu)
        assert len(days) == 2
        assert days[0]["date"] == "2025-09-15"
        assert days[1]["date"] == "2025-09-16"

        # Test indexing
        assert s.menu[0]["date"] == "2025-09-15"
        assert s.menu[1]["date"] == "2025-09-16"

        # Test __str__
        str_repr = str(s.menu)
        assert "Menu" in str_repr
        assert "days=" in str_repr
        assert "meals=" in str_repr
    
    def test_canteen_number_required(self):
        """Test that canteen_number is now required."""
        with pytest.raises(ValueError):
            s = StravaCZ("user", "pass")
            s.login("user", "pass", None)
    
    @patch('strava_cz.main.requests.Session')
    def test_invalid_meal_type_order_soup(self, mock_Session):
        """Test that ordering a soup raises InvalidMealTypeError."""
        from strava_cz import InvalidMealTypeError
        
        fake_session = MagicMock()
        mock_Session.return_value = fake_session

        login_response = MagicMock()
        login_response.status_code = 200
        login_response.json.return_value = {
            "sid": "SID123",
            "s5url": "https://fake.s5url",
            "cislo": "1234",
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

        menu_response = MagicMock()
        menu_response.status_code = 200
        menu_response.json.return_value = {
            "table0": [
                {
                    "id": 0,
                    "datum": "15-09.2025",
                    "druh_popis": "Polévka",
                    "delsiPopis": "Soup",
                    "nazev": "Test Soup",
                    "zakazaneAlergeny": None,
                    "alergeny": [],
                    "omezeniObj": {"den": ""},
                    "pocet": 0,
                    "veta": "75",
                    "cena": "20.00"
                }
            ]
        }

        # Add response for cancel_order (nactiVlastnostiPA)
        cancel_response = MagicMock()
        cancel_response.status_code = 200
        cancel_response.json.return_value = {"konto": "10.00"}

        fake_session.post.side_effect = [login_response, menu_response, cancel_response]

        s = StravaCZ("user", "pass", "1234")
        s.menu.fetch()

        # Test ordering a soup raises InvalidMealTypeError
        with pytest.raises(InvalidMealTypeError) as exc_info:
            s.menu.order_meals(75)
        
        assert "Polévka" in str(exc_info.value)
        assert "MAIN" in str(exc_info.value)
    
    @patch('strava_cz.main.requests.Session')
    def test_invalid_meal_type_cancel_soup(self, mock_Session):
        """Test that canceling a soup raises InvalidMealTypeError."""
        from strava_cz import InvalidMealTypeError
        
        fake_session = MagicMock()
        mock_Session.return_value = fake_session

        login_response = MagicMock()
        login_response.status_code = 200
        login_response.json.return_value = {
            "sid": "SID123",
            "s5url": "https://fake.s5url",
            "cislo": "1234",
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

        menu_response = MagicMock()
        menu_response.status_code = 200
        menu_response.json.return_value = {
            "table0": [
                {
                    "id": 0,
                    "datum": "15-09.2025",
                    "druh_popis": "Polévka",
                    "delsiPopis": "Soup",
                    "nazev": "Test Soup",
                    "zakazaneAlergeny": None,
                    "alergeny": [],
                    "omezeniObj": {"den": ""},
                    "pocet": 1,  # Already ordered
                    "veta": "75",
                    "cena": "20.00"
                }
            ]
        }

        # Add response for cancel_order (nactiVlastnostiPA)
        cancel_response = MagicMock()
        cancel_response.status_code = 200
        cancel_response.json.return_value = {"konto": "10.00"}

        fake_session.post.side_effect = [login_response, menu_response, cancel_response]

        s = StravaCZ("user", "pass", "1234")
        s.menu.fetch()

        # Test canceling a soup raises InvalidMealTypeError
        with pytest.raises(InvalidMealTypeError) as exc_info:
            s.menu.cancel_meals(75)
        
        assert "Polévka" in str(exc_info.value)
    
    @patch('strava_cz.main.requests.Session')
    def test_duplicate_meal_error_strict_mode(self, mock_Session):
        """Test that ordering multiple meals from same day raises DuplicateMealError in strict mode."""
        from strava_cz import DuplicateMealError
        
        fake_session = MagicMock()
        mock_Session.return_value = fake_session

        login_response = MagicMock()
        login_response.status_code = 200
        login_response.json.return_value = {
            "sid": "SID123",
            "s5url": "https://fake.s5url",
            "cislo": "1234",
            "jmeno": "user",
            "uzivatel": {
                "id": "user",
                "email": "u@e.cz",
                "konto": "100.00",
                "mena": "Kč",
                "nazevJidelny": "Test Canteen"
            },
            "betatest": False,
            "ignoreCert": False,
            "zustatPrihlasen": False
        }

        menu_response = MagicMock()
        menu_response.status_code = 200
        menu_response.json.return_value = {
            "table0": [
                {
                    "id": 0,
                    "datum": "15-09.2025",
                    "druh_popis": "Oběd1",
                    "delsiPopis": "Meal 1",
                    "nazev": "Meal 1",
                    "zakazaneAlergeny": None,
                    "alergeny": [],
                    "omezeniObj": {"den": ""},
                    "pocet": 0,
                    "veta": "1",
                    "cena": "40.00"
                },
                {
                    "id": 1,
                    "datum": "15-09.2025",
                    "druh_popis": "Oběd2",
                    "delsiPopis": "Meal 2",
                    "nazev": "Meal 2",
                    "zakazaneAlergeny": None,
                    "alergeny": [],
                    "omezeniObj": {"den": ""},
                    "pocet": 0,
                    "veta": "2",
                    "cena": "45.00"
                }
            ]
        }

        fake_session.post.side_effect = [login_response, menu_response]

        s = StravaCZ("user", "pass", "1234")
        s.menu.fetch()

        # Test ordering multiple meals from same day with strict_duplicates=True
        with pytest.raises(DuplicateMealError) as exc_info:
            s.menu.order_meals(1, 2, strict_duplicates=True)
        
        assert "2025-09-15" in str(exc_info.value)
        assert "same day" in str(exc_info.value).lower()
    
    @patch('strava_cz.main.requests.Session')
    def test_duplicate_meal_warning_default_mode(self, mock_Session):
        """Test that ordering multiple meals from same day only orders first one and warns."""
        fake_session = MagicMock()
        mock_Session.return_value = fake_session

        login_response = MagicMock()
        login_response.status_code = 200
        login_response.json.return_value = {
            "sid": "SID123",
            "s5url": "https://fake.s5url",
            "cislo": "1234",
            "jmeno": "user",
            "uzivatel": {
                "id": "user",
                "email": "u@e.cz",
                "konto": "100.00",
                "mena": "Kč",
                "nazevJidelny": "Test Canteen"
            },
            "betatest": False,
            "ignoreCert": False,
            "zustatPrihlasen": False
        }

        menu_response = MagicMock()
        menu_response.status_code = 200
        menu_response.json.return_value = {
            "table0": [
                {
                    "id": 0,
                    "datum": "15-09.2025",
                    "druh_popis": "Oběd1",
                    "delsiPopis": "Meal 1",
                    "nazev": "Meal 1",
                    "zakazaneAlergeny": None,
                    "alergeny": [],
                    "omezeniObj": {"den": ""},
                    "pocet": 0,
                    "veta": "1",
                    "cena": "40.00"
                },
                {
                    "id": 1,
                    "datum": "15-09.2025",
                    "druh_popis": "Oběd2",
                    "delsiPopis": "Meal 2",
                    "nazev": "Meal 2",
                    "zakazaneAlergeny": None,
                    "alergeny": [],
                    "omezeniObj": {"den": ""},
                    "pocet": 0,
                    "veta": "2",
                    "cena": "45.00"
                }
            ]
        }

        order_response = MagicMock()
        order_response.status_code = 200
        order_response.json.return_value = {"konto": "60.00"}

        save_response = MagicMock()
        save_response.status_code = 200
        save_response.json.return_value = {}

        # After save, fetch again to get updated menu
        menu_response_after = MagicMock()
        menu_response_after.status_code = 200
        menu_response_after.json.return_value = {
            "table0": [
                {
                    "id": 0,
                    "datum": "15-09.2025",
                    "druh_popis": "Oběd1",
                    "delsiPopis": "Meal 1",
                    "nazev": "Meal 1",
                    "zakazaneAlergeny": None,
                    "alergeny": [],
                    "omezeniObj": {"den": ""},
                    "pocet": 1,  # Now ordered
                    "veta": "1",
                    "cena": "40.00"
                },
                {
                    "id": 1,
                    "datum": "15-09.2025",
                    "druh_popis": "Oběd2",
                    "delsiPopis": "Meal 2",
                    "nazev": "Meal 2",
                    "zakazaneAlergeny": None,
                    "alergeny": [],
                    "omezeniObj": {"den": ""},
                    "pocet": 0,  # Not ordered
                    "veta": "2",
                    "cena": "45.00"
                }
            ]
        }

        fake_session.post.side_effect = [
            login_response,
            menu_response,
            order_response,  # pridejJidloS5 for meal 1
            save_response,   # saveOrders
            menu_response_after  # fetch after save
        ]

        s = StravaCZ("user", "pass", "1234")
        s.menu.fetch()

        # Test ordering multiple meals from same day without strict_duplicates
        # Should only order first meal and warn about second
        with pytest.warns(UserWarning, match="Skipping meal 2"):
            s.menu.order_meals(1, 2, strict_duplicates=False)
        
        # Verify only meal 1 was ordered
        assert s.menu.is_ordered(1) is True
        assert s.menu.is_ordered(2) is False
    
    @patch('strava_cz.main.requests.Session')
    def test_insufficient_balance_error(self, mock_Session):
        """Test that insufficient balance raises InsufficientBalanceError."""
        from strava_cz import InsufficientBalanceError
        
        fake_session = MagicMock()
        mock_Session.return_value = fake_session

        login_response = MagicMock()
        login_response.status_code = 200
        login_response.json.return_value = {
            "sid": "SID123",
            "s5url": "https://fake.s5url",
            "cislo": "1234",
            "jmeno": "user",
            "uzivatel": {
                "id": "user",
                "email": "u@e.cz",
                "konto": "5.00",  # Low balance
                "mena": "Kč",
                "nazevJidelny": "Test Canteen"
            },
            "betatest": False,
            "ignoreCert": False,
            "zustatPrihlasen": False
        }

        menu_response = MagicMock()
        menu_response.status_code = 200
        menu_response.json.return_value = {
            "table0": [
                {
                    "id": 0,
                    "datum": "15-09.2025",
                    "druh_popis": "Oběd1",
                    "delsiPopis": "Expensive meal",
                    "nazev": "Expensive meal",
                    "zakazaneAlergeny": None,
                    "alergeny": [],
                    "omezeniObj": {"den": ""},
                    "pocet": 0,
                    "veta": "1",
                    "cena": "100.00"
                }
            ]
        }

        # API returns error code 35 for insufficient balance
        order_response = MagicMock()
        order_response.status_code = 400
        order_response.json.return_value = {
            "number": 35,
            "message": "Insufficient balance to order this meal"
        }

        cancel_response = MagicMock()
        cancel_response.status_code = 200
        cancel_response.json.return_value = {"konto": "5.00"}

        fake_session.post.side_effect = [
            login_response,
            menu_response,
            order_response,  # pridejJidloS5 fails
            cancel_response  # nactiVlastnostiPA to cancel
        ]

        s = StravaCZ("user", "pass", "1234")
        s.menu.fetch()

        # Test insufficient balance raises InsufficientBalanceError
        with pytest.raises(InsufficientBalanceError) as exc_info:
            s.menu.order_meals(1)
        
        assert "balance" in str(exc_info.value).lower()
    
    @patch('strava_cz.main.requests.Session')
    def test_continue_on_error_collects_errors(self, mock_Session):
        """Test that continue_on_error=True collects all errors."""
        from strava_cz import StravaAPIError
        
        fake_session = MagicMock()
        mock_Session.return_value = fake_session

        login_response = MagicMock()
        login_response.status_code = 200
        login_response.json.return_value = {
            "sid": "SID123",
            "s5url": "https://fake.s5url",
            "cislo": "1234",
            "jmeno": "user",
            "uzivatel": {
                "id": "user",
                "email": "u@e.cz",
                "konto": "100.00",
                "mena": "Kč",
                "nazevJidelny": "Test Canteen"
            },
            "betatest": False,
            "ignoreCert": False,
            "zustatPrihlasen": False
        }

        menu_response = MagicMock()
        menu_response.status_code = 200
        menu_response.json.return_value = {
            "table0": [
                {
                    "id": 0,
                    "datum": "14-09.2025",
                    "druh_popis": "Polévka",
                    "delsiPopis": "Soup",
                    "nazev": "Soup",
                    "zakazaneAlergeny": None,
                    "alergeny": [],
                    "omezeniObj": {"den": ""},
                    "pocet": 0,
                    "veta": "75",
                    "cena": "20.00"
                },
                {
                    "id": 1,
                    "datum": "15-09.2025",
                    "druh_popis": "Oběd1",
                    "delsiPopis": "Main meal",
                    "nazev": "Main meal",
                    "zakazaneAlergeny": None,
                    "alergeny": [],
                    "omezeniObj": {"den": ""},
                    "pocet": 0,
                    "veta": "1",
                    "cena": "40.00"
                },
                {
                    "id": 2,
                    "datum": "16-09.2025",
                    "druh_popis": "Polévka",
                    "delsiPopis": "Another soup",
                    "nazev": "Another soup",
                    "zakazaneAlergeny": None,
                    "alergeny": [],
                    "omezeniObj": {"den": ""},
                    "pocet": 0,
                    "veta": "76",
                    "cena": "20.00"
                }
            ]
        }

        order_response = MagicMock()
        order_response.status_code = 200
        order_response.json.return_value = {"konto": "60.00"}

        save_response = MagicMock()
        save_response.status_code = 200
        save_response.json.return_value = {}

        menu_response_after = MagicMock()
        menu_response_after.status_code = 200
        menu_response_after.json.return_value = {
            "table0": [
                {
                    "id": 0,
                    "datum": "14-09.2025",
                    "druh_popis": "Polévka",
                    "delsiPopis": "Soup",
                    "nazev": "Soup",
                    "zakazaneAlergeny": None,
                    "alergeny": [],
                    "omezeniObj": {"den": ""},
                    "pocet": 0,
                    "veta": "75",
                    "cena": "20.00"
                },
                {
                    "id": 1,
                    "datum": "15-09.2025",
                    "druh_popis": "Oběd1",
                    "delsiPopis": "Main meal",
                    "nazev": "Main meal",
                    "zakazaneAlergeny": None,
                    "alergeny": [],
                    "omezeniObj": {"den": ""},
                    "pocet": 1,  # Ordered
                    "veta": "1",
                    "cena": "40.00"
                },
                {
                    "id": 2,
                    "datum": "16-09.2025",
                    "druh_popis": "Polévka",
                    "delsiPopis": "Another soup",
                    "nazev": "Another soup",
                    "zakazaneAlergeny": None,
                    "alergeny": [],
                    "omezeniObj": {"den": ""},
                    "pocet": 0,
                    "veta": "76",
                    "cena": "20.00"
                }
            ]
        }

        fake_session.post.side_effect = [
            login_response,
            menu_response,
            order_response,  # pridejJidloS5 for meal 1 (main)
            save_response,
            menu_response_after
        ]

        s = StravaCZ("user", "pass", "1234")
        s.menu.fetch()

        # Test that continue_on_error=True collects errors for soups
        with pytest.raises(StravaAPIError) as exc_info:
            s.menu.order_meals(75, 1, 76, continue_on_error=True)
        
        error_msg = str(exc_info.value)
        assert "75" in error_msg  # First soup
        assert "76" in error_msg  # Second soup
        assert "Polévka" in error_msg
        # Main meal should have been ordered successfully
        assert s.menu.is_ordered(1) is True
    
    @patch('strava_cz.main.requests.Session')
    def test_balance_update_after_order(self, mock_Session):
        """Test that user balance is updated after ordering."""
        fake_session = MagicMock()
        mock_Session.return_value = fake_session

        login_response = MagicMock()
        login_response.status_code = 200
        login_response.json.return_value = {
            "sid": "SID123",
            "s5url": "https://fake.s5url",
            "cislo": "1234",
            "jmeno": "user",
            "uzivatel": {
                "id": "user",
                "email": "u@e.cz",
                "konto": "100.00",
                "mena": "Kč",
                "nazevJidelny": "Test Canteen"
            },
            "betatest": False,
            "ignoreCert": False,
            "zustatPrihlasen": False
        }

        menu_response = MagicMock()
        menu_response.status_code = 200
        menu_response.json.return_value = {
            "table0": [
                {
                    "id": 0,
                    "datum": "15-09.2025",
                    "druh_popis": "Oběd1",
                    "delsiPopis": "Meal",
                    "nazev": "Meal",
                    "zakazaneAlergeny": None,
                    "alergeny": [],
                    "omezeniObj": {"den": ""},
                    "pocet": 0,
                    "veta": "1",
                    "cena": "40.00"
                }
            ]
        }

        order_response = MagicMock()
        order_response.status_code = 200
        order_response.json.return_value = {"konto": "60.00"}  # Balance after ordering

        save_response = MagicMock()
        save_response.status_code = 200
        save_response.json.return_value = {}

        menu_response_after = MagicMock()
        menu_response_after.status_code = 200
        menu_response_after.json.return_value = {
            "table0": [
                {
                    "id": 0,
                    "datum": "15-09.2025",
                    "druh_popis": "Oběd1",
                    "delsiPopis": "Meal",
                    "nazev": "Meal",
                    "zakazaneAlergeny": None,
                    "alergeny": [],
                    "omezeniObj": {"den": ""},
                    "pocet": 1,
                    "veta": "1",
                    "cena": "40.00"
                }
            ]
        }

        fake_session.post.side_effect = [
            login_response,
            menu_response,
            order_response,
            save_response,
            menu_response_after
        ]

        s = StravaCZ("user", "pass", "1234")
        assert s.user.balance == "100.00"
        
        s.menu.fetch()
        s.menu.order_meals(1)
        
        # Balance should be updated to 60.00
        assert s.user.balance == 60.00  # Now it's a float after update
