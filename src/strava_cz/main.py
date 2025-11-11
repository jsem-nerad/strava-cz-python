"""High level API pro interakci s webovou aplikaci Strava.cz"""

# Komentare v tomto kodu byly doplnene pomoci LLM

from typing import Dict, List, Optional, Any
from enum import Enum
import requests


class MealType(Enum):
    """Enum for meal types."""

    SOUP = "Polévka"
    MAIN = "Hlavní jídlo"
    UNKNOWN = "Neznámý typ"


class OrderType(Enum):
    """Enum for order restriction types."""

    NORMAL = "Objednatelne"  # Empty string - normal orderable
    RESTRICTED = "Nelze objednat"  # "CO" - too late to order
    OPTIONAL = "Volitelne"  # "T" - not usually ordered but can be


class StravaAPIError(Exception):
    """Custom exception for Strava API errors."""

    pass


class AuthenticationError(StravaAPIError):
    """Exception raised for authentication errors."""

    pass


class InsufficientBalanceError(StravaAPIError):
    """Raised when user has insufficient balance to order a meal."""

    pass


class DuplicateMealError(StravaAPIError):
    """Raised when trying to order multiple meals from the same day."""

    pass


class InvalidMealTypeError(StravaAPIError):
    """Raised when trying to order or cancel a meal type that cannot be modified (e.g., soup)."""

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
            f"User information:\n  - {self.full_name} ({self.username})"
            f"\n  - Email: {self.email} \n  - Balance: {self.balance} {self.currency}"
            f"\n  - Canteen: {self.canteen_name}\n\n"
        )


class Menu:
    """Menu data container and processor"""

    def __init__(self, strava_client: "StravaCZ"):
        """Initialize Menu with reference to StravaCZ client.

        Args:
            strava_client: Reference to the parent StravaCZ instance
        """
        self.strava = strava_client
        self.raw_data: Dict[str, Any] = {}
        self._all_meals: List[Dict[str, Any]] = []  # Internal storage for all meals

    def fetch(self) -> "Menu":
        """Fetch menu data from API and process it into various lists.

        Returns:
            Self for method chaining

        Raises:
            AuthenticationError: If user is not logged in
            StravaAPIError: If menu retrieval fails
        """
        if not self.strava.user.is_logged_in:
            raise AuthenticationError("User not logged in")

        payload = {
            "cislo": self.strava.user.canteen_number,
            "sid": self.strava.user.sid,
            "s5url": self.strava.user.s5url,
            "lang": "EN",
            "konto": self.strava.user.balance,
            "podminka": "",
            "ignoreCert": False,
        }

        response = self.strava._api_request("objednavky", payload)

        if response["status_code"] != 200:
            raise StravaAPIError("Failed to fetch menu")

        self.raw_data = response["response"]
        self._parse_menu_data()
        return self

    def _parse_menu_data(self) -> None:
        """Parse raw menu response into internal storage."""
        # Single storage for all meals grouped by date
        meals_by_date: Dict[str, List[Dict]] = {}

        # Process all table entries (table0, table1, etc.)
        for table_key, meals_list in self.raw_data.items():
            if not table_key.startswith("table"):
                continue

            for meal in meals_list:
                # Skip empty meals
                has_no_description = not meal["delsiPopis"] and not meal["alergeny"]
                is_unnamed_meal = meal["nazev"] == meal["druh_popis"]
                if has_no_description or is_unnamed_meal:
                    continue

                # Get restriction status
                restriction = meal["omezeniObj"]["den"]

                # Skip "VP" (no school) completely
                if "VP" in restriction:
                    continue

                # Parse date
                unformated_date = meal["datum"]  # Format: "dd-mm.yyyy"
                date = f"{unformated_date[6:10]}-{unformated_date[3:5]}-{unformated_date[0:2]}"

                # Convert string type to MealType enum
                meal_type_str = meal["druh_popis"]
                if meal_type_str == "Polévka":
                    meal_type = MealType.SOUP
                elif "Oběd" in meal_type_str:
                    meal_type = MealType.MAIN
                else:
                    meal_type = MealType.UNKNOWN

                # Skip unknown types
                if meal_type == MealType.UNKNOWN:
                    continue

                # Determine order type
                if "CO" in restriction:
                    order_type = OrderType.RESTRICTED
                elif "T" in restriction:
                    order_type = OrderType.OPTIONAL
                else:  # Empty string - orderable
                    order_type = OrderType.NORMAL

                meal_filtered = {
                    "type": meal_type,
                    "orderType": order_type,
                    "name": meal["nazev"],
                    "forbiddenAlergens": meal["zakazaneAlergeny"],
                    "alergens": meal["alergeny"],
                    "ordered": meal["pocet"] == 1,
                    "id": int(meal["veta"]),
                    "price": float(meal["cena"]),
                    "date": date,
                }

                # Store all meals together
                if date not in meals_by_date:
                    meals_by_date[date] = []
                meals_by_date[date].append(meal_filtered)

        # Convert to day-grouped format and sort by date
        self._all_meals = sorted(
            [
                {"date": date, "ordered": any(m["ordered"] for m in meals), "meals": meals}
                for date, meals in meals_by_date.items()
            ],
            key=lambda x: x["date"],
        )

    def get_days(
        self,
        meal_types: Optional[List[MealType]] = None,
        order_types: Optional[List[OrderType]] = None,
        ordered: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """Get menu grouped by days with optional filtering.

        Args:
            meal_types: List of meal types to include (None = all types)
            order_types: List of order types to include
                (None = [OrderType.NORMAL] only)
            ordered: Filter by order status
                (True = ordered only, False = unordered only, None = all)

        Returns:
            List of days with meals:
                [{"date": "YYYY-MM-DD", "ordered": bool, "meals": [...]}]
        """
        # Default to NORMAL order type only
        if order_types is None:
            order_types = [OrderType.NORMAL]

        filtered_days = []
        for day in self._all_meals:
            # Filter meals by type and order type
            filtered_meals = [
                meal
                for meal in day["meals"]
                if (meal_types is None or meal["type"] in meal_types)
                and (meal["orderType"] in order_types)
            ]

            if not filtered_meals:
                continue

            # Check if day has ordered meals
            day_has_orders = any(m["ordered"] for m in filtered_meals)

            # Apply ordered filter
            if ordered is not None:
                if ordered and not day_has_orders:
                    continue
                if not ordered and day_has_orders:
                    continue

            filtered_days.append(
                {"date": day["date"], "ordered": day_has_orders, "meals": filtered_meals}
            )

        return filtered_days

    def get_meals(
        self,
        meal_types: Optional[List[MealType]] = None,
        order_types: Optional[List[OrderType]] = None,
        ordered: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """Get all meals as flat list with optional filtering.

        Args:
            meal_types: List of meal types to include (None = all types)
            order_types: List of order types to include
                (None = [OrderType.NORMAL] only)
            ordered: Filter by order status
                (True = ordered only, False = unordered only, None = all)

        Returns:
            Flat list of meals with date: [{...meal, "date": "YYYY-MM-DD"}]
        """
        # Default to NORMAL order type only
        if order_types is None:
            order_types = [OrderType.NORMAL]

        meals = []
        for day in self._all_meals:
            for meal in day["meals"]:
                # Apply filters
                if meal_types is not None and meal["type"] not in meal_types:
                    continue
                if meal["orderType"] not in order_types:
                    continue
                if ordered is not None and meal["ordered"] != ordered:
                    continue

                meals.append(meal)

        return meals

    def get_by_date(self, date: str) -> Optional[Dict[str, Any]]:
        """Get menu items for a specific date (searches all order types).

        Args:
            date: Date in YYYY-MM-DD format

        Returns:
            Dictionary with date and meals, or None if not found
        """
        for day in self._all_meals:
            if day["date"] == date:
                return day
        return None

    def get_by_id(self, meal_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific meal by its ID (searches all order types).

        Args:
            meal_id: Meal identification number

        Returns:
            Meal dictionary, or None if not found
        """
        for day in self._all_meals:
            for meal in day["meals"]:
                if meal["id"] == meal_id:
                    return meal
        return None

    def is_ordered(self, meal_id: int) -> bool:
        """Check whether a meal is ordered or not (searches all order types).

        Args:
            meal_id: Meal identification number

        Returns:
            True if meal is ordered, False otherwise
        """
        meal = self.get_by_id(meal_id)
        return meal["ordered"] if meal else False

    def _change_meal_order(self, meal_id: int, ordered: bool) -> bool:
        """Change the order status of a meal (without saving).

        Args:
            meal_id: Meal identification number
            ordered: New order status

        Returns:
            True if meal order status was changed successfully

        Raises:
            AuthenticationError: If user is not logged in
            InsufficientBalanceError: If insufficient balance to order meal
            InvalidMealTypeError: If trying to order/cancel non-MAIN meal type
            StravaAPIError: If changing meal order status fails
        """
        if not self.strava.user.is_logged_in:
            raise AuthenticationError("User not logged in")

        if self.is_ordered(meal_id) == ordered:
            return True

        # Check meal type - only MAIN meals can be ordered/canceled
        meal = self.get_by_id(meal_id)
        if meal and meal["type"] != MealType.MAIN:
            raise InvalidMealTypeError(
                f"Cannot order or cancel {meal['type'].value} meals. "
                f"Only main dishes (MAIN) can be ordered or canceled."
            )

        payload = {
            "cislo": self.strava.user.canteen_number,
            "sid": self.strava.user.sid,
            "url": self.strava.user.s5url,
            "veta": str(meal_id),
            "pocet": "1" if ordered else "0",
            "lang": "EN",
            "ignoreCert": "false",
        }

        response = self.strava._api_request("pridejJidloS5", payload)

        if response["status_code"] != 200:
            # Check for specific error codes
            response_data = response.get("response", {})

            # Error code 35 = insufficient balance
            if response_data.get("number") == 35:
                error_msg = response_data.get("message", "Insufficient balance")
                raise InsufficientBalanceError(error_msg)

            raise StravaAPIError(
                f"Failed to change meal order status: "
                f"{response_data.get('message', 'Unknown error')}"
            )

        # Update balance from response
        response_data = response.get("response", {})
        if "konto" in response_data:
            try:
                self.strava.user.balance = float(response_data["konto"])
            except (ValueError, TypeError):
                pass  # Keep old balance if parsing fails

        return True

    def _save_order(self) -> bool:
        """Save current order changes.

        Returns:
            True if order was saved successfully

        Raises:
            AuthenticationError: If user is not logged in
            StravaAPIError: If saving order fails
        """
        if not self.strava.user.is_logged_in:
            raise AuthenticationError("User not logged in")

        payload = {
            "cislo": self.strava.user.canteen_number,
            "sid": self.strava.user.sid,
            "url": self.strava.user.s5url,
            "xml": None,
            "lang": "EN",
            "ignoreCert": "false",
        }

        response = self.strava._api_request("saveOrders", payload)

        if response["status_code"] != 200:
            raise StravaAPIError("Failed to save order")
        return True

    def _cancel_order(self) -> bool:
        """Cancel current order changes (revert to previous state).

        Returns:
            True if order was canceled successfully

        Raises:
            AuthenticationError: If user is not logged in
            StravaAPIError: If canceling order fails
        """
        if not self.strava.user.is_logged_in:
            raise AuthenticationError("User not logged in")

        payload = {
            "sid": self.strava.user.sid,
            "url": self.strava.user.s5url,
            "cislo": self.strava.user.canteen_number,
            "ignoreCert": "false",
            "lang": "EN",
            "getText": True,
            "checkVersion": True,
            "resetTables": True,
            "frontendFunction": "refreshInformations",
        }

        response = self.strava._api_request("nactiVlastnostiPA", payload)

        if response["status_code"] != 200:
            raise StravaAPIError("Failed to cancel order changes")

        # Update balance from response
        response_data = response.get("response", {})
        if "konto" in response_data:
            try:
                self.strava.user.balance = float(response_data["konto"])
            except (ValueError, TypeError):
                pass

        return True

    def order_meals(
        self,
        *meal_ids: int,
        continue_on_error: bool = False,
        strict_duplicates: bool = False,
    ) -> None:
        """Order multiple meals in a single transaction.

        Args:
            *meal_ids: Variable number of meal identification numbers
            continue_on_error: If True, continue ordering other meals if one fails
                and collect errors. If False (default), stop on first error
                and cancel all changes.
            strict_duplicates: If True, raise DuplicateMealError when multiple
                meals from the same day are being ordered. If False (default),
                only order the first meal from each day and warn about skipped duplicates.

        Raises:
            InsufficientBalanceError: If insufficient balance (only if continue_on_error=False)
            InvalidMealTypeError: If trying to order non-MAIN meal type
                (only if continue_on_error=False)
            DuplicateMealError: If ordering multiple meals from same day
                (only if strict_duplicates=True)
            StravaAPIError: If ordering any meal fails (only if continue_on_error=False)
        """
        import warnings

        # Detect duplicate days
        seen_dates: Dict[str, int] = {}
        filtered_meal_ids: List[int] = []
        skipped_meals: List[tuple] = []

        for meal_id in meal_ids:
            meal = self.get_by_id(meal_id)
            if not meal:
                if continue_on_error:
                    warnings.warn(f"Meal with ID {meal_id} not found, skipping")
                    continue
                else:
                    raise StravaAPIError(f"Meal with ID {meal_id} not found")

            meal_date = meal["date"]

            if meal_date in seen_dates:
                # Duplicate day detected
                if strict_duplicates:
                    raise DuplicateMealError(
                        f"Cannot order multiple meals from the same day ({meal_date}). "
                        f"Meal IDs {seen_dates[meal_date]} and {meal_id} are from the same day."
                    )
                else:
                    skipped_meals.append((meal_id, meal_date, seen_dates[meal_date]))
                    continue

            seen_dates[meal_date] = meal_id
            filtered_meal_ids.append(meal_id)

        # Warn about skipped duplicates
        if skipped_meals and not strict_duplicates:
            for meal_id, meal_date, first_meal_id in skipped_meals:
                warnings.warn(
                    f"Skipping meal {meal_id} from {meal_date} because meal {first_meal_id} "
                    f"from the same day is already being ordered"
                )

        errors = []
        failed_meal_ids = set()  # Track meals that already failed

        for meal_id in filtered_meal_ids:
            try:
                self._change_meal_order(meal_id, True)
            except (InsufficientBalanceError, InvalidMealTypeError, StravaAPIError) as e:
                if continue_on_error:
                    errors.append((meal_id, str(e)))
                    failed_meal_ids.add(meal_id)  # Mark as failed
                else:
                    # Cancel all changes and re-raise
                    self._cancel_order()
                    raise

        self._save_order()
        self.fetch()  # Refresh menu data

        # Verify orders (skip meals that already failed)
        for meal_id in filtered_meal_ids:
            if meal_id in failed_meal_ids:
                continue  # Skip verification for meals that already had errors
            if not self.is_ordered(meal_id):
                error_msg = f"Failed to order meal with ID {meal_id}"
                if continue_on_error:
                    errors.append((meal_id, error_msg))
                else:
                    raise StravaAPIError(error_msg)

        # If there were errors and continue_on_error is True, report them
        if errors and continue_on_error:
            error_details = "; ".join([f"Meal {mid}: {err}" for mid, err in errors])
            raise StravaAPIError(f"Some meals failed to order: {error_details}")

    def cancel_meals(self, *meal_ids: int, continue_on_error: bool = False) -> None:
        """Cancel multiple meal orders in a single transaction.

        Args:
            *meal_ids: Variable number of meal identification numbers
            continue_on_error: If True, continue canceling other meals if one fails
                and collect errors. If False (default), stop on first error
                and cancel all changes.

        Raises:
            InvalidMealTypeError: If trying to cancel non-MAIN meal type
                (only if continue_on_error=False)
            StravaAPIError: If canceling any meal fails (only if continue_on_error=False)
        """
        errors = []
        failed_meal_ids = set()  # Track meals that already failed

        for meal_id in meal_ids:
            try:
                self._change_meal_order(meal_id, False)
            except (InvalidMealTypeError, StravaAPIError) as e:
                if continue_on_error:
                    errors.append((meal_id, str(e)))
                    failed_meal_ids.add(meal_id)  # Mark as failed
                else:
                    # Cancel all changes and re-raise
                    self._cancel_order()
                    raise

        self._save_order()
        self.fetch()  # Refresh menu data

        # Verify cancellations (skip meals that already failed)
        for meal_id in meal_ids:
            if meal_id in failed_meal_ids:
                continue  # Skip verification for meals that already had errors
            if self.is_ordered(meal_id):
                error_msg = f"Failed to cancel meal with ID {meal_id}"
                if continue_on_error:
                    errors.append((meal_id, error_msg))
                else:
                    raise StravaAPIError(error_msg)

        # If there were errors and continue_on_error is True, report them
        if errors and continue_on_error:
            error_details = "; ".join([f"Meal {mid}: {err}" for mid, err in errors])
            raise StravaAPIError(f"Some meals failed to cancel: {error_details}")

    def print(self) -> None:
        """Print formatted menu (default: orderable meals only)."""
        days = self.get_days()
        for day in days:
            print(f"{day['date']}:")
            for meal in day["meals"]:
                meal_type_str = meal["type"].value
                status = "Ordered" if meal["ordered"] else "Not ordered"
                order_type_info = ""
                if meal["orderType"] != OrderType.NORMAL:
                    order_type_info = f" [{meal['orderType'].name}]"
                meal_info = (
                    f"  - {meal['id']} {meal['name']} "
                    f"({meal_type_str}){order_type_info} - [{status}]"
                )
                print(meal_info)
            print()

    def __repr__(self) -> str:
        """Return representation of menu."""
        days = self.get_days()
        total_meals = sum(len(day["meals"]) for day in days)
        return f"Menu(days={len(days)}, meals={total_meals})"

    def __str__(self) -> str:
        """Return string representation of menu."""
        return self.__repr__()

    def __iter__(self):
        """Iterate over orderable days."""
        return iter(self.get_days())

    def __len__(self) -> int:
        """Return the number of orderable days."""
        return len(self.get_days())

    def __getitem__(self, key):
        """Access days by index from orderable days."""
        return self.get_days()[key]


class StravaCZ:
    """Strava.cz API client"""

    BASE_URL = "https://app.strava.cz"

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
            canteen_number: Canteen number (required for login)
        """

        self.session = requests.Session()
        self.api_url = f"{self.BASE_URL}/api"

        self.user = User()  # Initialize the user object
        self.menu = Menu(self)  # Initialize the menu object with reference to self

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

    def login(self, username, password, canteen_number):
        """Log in to Strava.cz account.

        Args:
            username: User's login username
            password: User's login password
            canteen_number: Canteen number (required)

        Returns:
            User object with populated account information

        Raises:
            AuthenticationError: If user is already logged in or login fails
            ValueError: If username, password, or canteen_number is missing
        """
        if self.user.is_logged_in:
            raise AuthenticationError("User already logged in")
        if not username or not password:
            raise ValueError("Username and password are required for login")
        if not canteen_number:
            raise ValueError("Canteen number is required for login")

        self.user.username = username
        self.user.password = password
        self.user.canteen_number = canteen_number

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
            self.menu = Menu(self)  # Clear menu
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

    # Ziskani jidelnicku a vypsani
    strava.menu.fetch()

    # Vsechna objednavatelna jidla
    days = strava.menu.get_days(
        order_types=[OrderType.NORMAL], ordered=False, meal_types=[MealType.SOUP]
    )
    print("".join(f"{day['date']}\n" for day in days))

    meal_ids = []
    for day in days:
        meal_ids.append(day["meals"][0]["id"])

    strava.menu.order_meals(64, *meal_ids[:5], continue_on_error=True, strict_duplicates=False)

    strava.logout()
