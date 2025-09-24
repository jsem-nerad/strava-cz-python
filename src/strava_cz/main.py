"""High level API pro interakci s webovou aplikaci Strava.cz"""

from typing import Dict, List, Optional, Any
import requests


class StravaAPIError(Exception):
    """Custom exception for Strava API errors."""

    pass


class AuthenticationError(StravaAPIError):
    """Exception raised for authentication errors."""

    pass


class User:
    """User data container"""

    def __init__(self):
        self.username: Optional[str] = None
        self.password: Optional[str] = None
        self.canteen_number: Optional[str] = None
        self.sid: Optional[str] = None
        self.s5url: Optional[str] = None
        self.full_name: Optional[str] = None
        self.email: Optional[str] = None
        self.balance: float = 0.0
        self.id: Optional[str] = None
        self.currency: Optional[str] = None
        self.canteen_name: Optional[str] = None
        self.is_logged_in: bool = False

    def __repr__(self):
        """Return string with basic formated user info"""
        return (
            f"User:\nusername={self.username}, \nfull_name={self.full_name}, "
            f"\nemail={self.email}, \nbalance={self.balance}, \ncurrency={self.currency}, "
            f"\ncanteen_name={self.canteen_name}, \nsid={self.sid}, "
            f"\nis_logged_in={self.is_logged_in}\n"
        )


class StravaCZ:
    """Strava.cz API client"""

    BASE_URL = "https://app.strava.cz"
    DEFAULT_CANTEEN_NUMBER = "3753"  # Default SSPS canteen number

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        canteen_number: Optional[str] = None,
    ):
        """Initialize Strava.cz API client.

        Args:
            username: User's login username
            password: User's login password
            canteen_number: Canteen number
        """

        self.session = requests.Session()
        self.api_url = f"{self.BASE_URL}/api"

        self.user = User()  # Initialize the user object
        self.menu: List[Dict[str, Any]] = []

        self._setup_headers()
        self._initialize_session()

        # Auto-login if credentials are provided
        if username and password:
            self.login(username=username, password=password, canteen_number=canteen_number)
        elif username == "" or password == "":
            raise AuthenticationError("Both username and password are required for login")

    def _setup_headers(self) -> None:
        """Set up default headers for API requests."""
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9,de-DE;q=0.8,de;q=0.7,cs;q=0.6",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Content-Type": "text/plain;charset=UTF-8",
            "Origin": self.BASE_URL,
            "Referer": f"{self.BASE_URL}/en/prihlasit-se?jidelna",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        }

    def _initialize_session(self) -> None:
        """Initialize session with initial GET request."""
        self.session.get(f"{self.BASE_URL}/en/prihlasit-se?jidelna")

    def _api_request(
        self, endpoint: str, payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make API request to Strava.cz endpoint.

        Args:
            endpoint: API endpoint path
            payload: Request payload data

        Returns:
            Dictionary containing status code and response data

        Raises:
            StravaAPIError: If API request fails
        """
        url = f"{self.api_url}/{endpoint}"
        try:
            response = self.session.post(url, json=payload, headers=self.headers)
            return {"status_code": response.status_code, "response": response.json()}
        except requests.RequestException as e:
            raise StravaAPIError(f"API request failed: {e}")

    def login(self, username, password, canteen_number=None):
        """Log in to Strava.cz account.

        Args:
            username: User's login username
            password: User's login password
            canteen_number: Canteen number

        Returns:
            User object with populated account information

        Raises:
            AuthenticationError: If user is already logged in or login fails
            ValueError: If username or password is empty
        """
        if self.user.is_logged_in:
            raise AuthenticationError("User already logged in")
        if not username or not password:
            raise ValueError("Username and password are required for login")

        self.user.username = username
        self.user.password = password
        self.user.canteen_number = canteen_number or self.DEFAULT_CANTEEN_NUMBER

        payload = {
            "cislo": self.user.canteen_number,
            "jmeno": self.user.username,
            "heslo": self.user.password,
            "zustatPrihlasen": True,
            "environment": "W",
            "lang": "EN",
        }

        response = self._api_request("login", payload)

        if response["status_code"] == 200:
            self._populate_user_data(response["response"])
            self.user.is_logged_in = True
            return self.user
        else:
            error_message = response["response"].get("message", "Unknown error")
            raise AuthenticationError(f"Login failed: {error_message}")

    def _populate_user_data(self, data: Dict[str, Any]) -> None:
        """Populate user object with login response data."""
        user_data = data.get("uzivatel", {})

        self.user.sid = data.get("sid", "")
        self.user.s5url = data.get("s5url", "")
        self.user.full_name = user_data.get("jmeno", "")
        self.user.email = user_data.get("email", "")
        self.user.balance = user_data.get("konto", 0.0)
        self.user.id = user_data.get("id", 0)
        self.user.currency = user_data.get("mena", "Kč")
        self.user.canteen_name = user_data.get("nazevJidelny", "")

    def get_menu(self, include_soup: bool = False, include_empty: bool = False) -> List[Dict[str, Any]]:
        """Retrieve and parse user's menu list from API.

        Args:
            include_soup: Whether to include soups in the menu
            include_empty: Whether to include empty meals or meals not named yet

        Returns:
            List of menu items grouped by date

        Raises:
            AuthenticationError: If user is not logged in
            StravaAPIError: If menu retrieval fails
        """
        if not self.user.is_logged_in:
            raise AuthenticationError("User not logged in")

        payload = {
            "cislo": self.user.canteen_number,
            "sid": self.user.sid,
            "s5url": self.user.s5url,
            "lang": "EN",
            "konto": self.user.balance,
            "podminka": "",
            "ignoreCert": False,
        }

        response = self._api_request("objednavky", payload)

        if response["status_code"] != 200:
            raise StravaAPIError("Failed to fetch menu")

        self.menu = self._parse_menu_response(response["response"], include_soup, include_empty)
        return self.menu

    def _parse_menu_response(self, menu_data: Dict[str, Any], include_soup: bool = False, include_empty: bool = False) -> List[Dict[str, Any]]:
        """Parse raw menu response into structured format."""
        meals_by_date: Dict[str, Any] = {}

        # Process all table entries (table0, table1, etc.)
        for table_key, meals_list in menu_data.items():
            if not table_key.startswith("table"):
                continue

            for meal in meals_list:
                if not include_empty and not meal["delsiPopis"]:
                    continue
                if not include_soup and meal["druh_popis"] == "Polévka":
                    continue

                unformated_date = meal["datum"]  # Format: "dd-mm.yyyy"
                date = f"{unformated_date[6:10]}-{unformated_date[3:5]}-{unformated_date[0:2]}"


                meal_filtered = {
                    "local_id": meal["id"],
                    "type": meal["druh_popis"],
                    "name": meal["nazev"],
                    "forbiddenAlergens": meal["zakazaneAlergeny"],
                    "alergens": meal["alergeny"],
                    "ordered": meal["pocet"] == 1,
                    "meal_id": int(meal["veta"]),
                }

                if date not in meals_by_date:
                    meals_by_date[date] = []
                meals_by_date[date].append(meal_filtered)

        # Convert to final format
        return [{"date": date, "meals": meals} for date, meals in meals_by_date.items()]
    
    def print_menu(self) -> None:
        """Print the current menu in a readable format."""
        if not self.menu:
            self.get_menu()

        for day in self.menu:
            print(f"Date: {day['date']}")
            for meal in day["meals"]:
                status = "Ordered" if meal["ordered"] else "Not ordered"
                print(f"  - {meal['name']} ({meal['type']}) [{status}]")
            print()

    def is_ordered(self, meal_id: int) -> bool:
        """Check wheather a meal is ordered or not.

        Args:
            meal_id: Meal identification number

        Returns:
            True if meal is ordered, False otherwise

        Raises:
            AuthenticationError: If user is not logged in
        """
        if not self.user.is_logged_in:
            raise AuthenticationError("User not logged in")

        for day in self.menu:
            for meal in day["meals"]:
                if meal["meal_id"] == meal_id:
                    return meal["ordered"]
        return False

    def _add_meal_to_order(self, meal_id: int) -> bool:
        """Add a meal to the order (without saving).

        Args:
            meal_id: Meal identification number

        Returns:
            True if meal was added successfully

        Raises:
            AuthenticationError: If user is not logged in
            StravaAPIError: If adding meal fails
        """
        if not self.user.is_logged_in:
            raise AuthenticationError("User not logged in")

        if self.is_ordered(meal_id):
            return True  # Already ordered

        payload = {
            "cislo": self.user.canteen_number,
            "sid": self.user.sid,
            "url": self.user.s5url,
            "veta": str(meal_id),
            "pocet": 1,
            "lang": "EN",
            "ignoreCert": "false",
        }

        response = self._api_request("pridejJidloS5", payload)
        if response["status_code"] != 200:
            raise StravaAPIError("Failed to add meal to order")
        return True

    def _save_order(self) -> bool:
        """Save current order changes.

        Returns:
            True if order was saved successfully

        Raises:
            AuthenticationError: If user is not logged in
            StravaAPIError: If saving order fails
        """
        if not self.user.is_logged_in:
            raise AuthenticationError("User not logged in")

        payload = {
            "cislo": self.user.canteen_number,
            "sid": self.user.sid,
            "url": self.user.s5url,
            "xml": None,
            "lang": "EN",
            "ignoreCert": "false",
        }

        response = self._api_request("saveOrders", payload)

        if response["status_code"] != 200:
            raise StravaAPIError("Failed to save order")
        return True

    def order_meals(self, *meal_ids: int) -> None:
        """Order multiple meals in a single transaction.

        Args:
            *meal_ids: Variable number of meal identification numbers
        """
        for meal_id in meal_ids:
            self._add_meal_to_order(meal_id)
        self._save_order()
        self.get_menu()

    def logout(self) -> bool:
        """Log out from Strava.cz account.

        Returns:
            True if logout was successful

        Raises:
            StravaAPIError: If logout fails
        """
        if not self.user.is_logged_in:
            return True  # Already logged out

        payload = {
            "sid": self.user.sid,
            "cislo": self.user.canteen_number,
            "url": self.user.s5url,
            "lang": "EN",
            "ignoreCert": "false",
        }

        response = self._api_request("logOut", payload)

        if response["status_code"] == 200:
            self.user = User()  # Reset user
            self.menu = []  # Clear menu
            return True
        else:
            raise StravaAPIError("Failed to logout")


if __name__ == "__main__":
    import os
    import dotenv
    dotenv.load_dotenv()

    STRAVA_USERNAME = os.getenv("STRAVA_USERNAME", "")
    STRAVA_PASSWORD = os.getenv("STRAVA_PASSWORD", "")
    STRAVA_CANTEEN_NUMBER = os.getenv("STRAVA_CANTEEN_NUMBER", "")

    strava = StravaCZ(
        username=STRAVA_USERNAME,
        password=STRAVA_PASSWORD,
        canteen_number=STRAVA_CANTEEN_NUMBER,
    )
    print(strava.user)

    strava.print_menu()

    strava.logout()
    print("Logged out")