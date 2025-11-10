"""High level API pro interakci s webovou aplikaci Strava.cz"""

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
    NORMAL = "Objednavatelne"  # Empty string - normal orderable
    RESTRICTED = "Nelze objednat"  # "CO" - too late to order
    OPTIONAL = "Volitelne"  # "T" - not usually ordered but can be


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
            f"User information:\n  - {self.full_name} ({self.username})"
            f"\n  - Email: {self.email} \n  - Balance: {self.balance} {self.currency}"
            f"\n  - Canteen: {self.canteen_name}\n\n"
        )


class Menu:
    """Menu data container and processor"""

    def __init__(self, strava_client: 'StravaCZ'):
        """Initialize Menu with reference to StravaCZ client.
        
        Args:
            strava_client: Reference to the parent StravaCZ instance
        """
        self.strava = strava_client
        self.raw_data: Dict[str, Any] = {}
        
        # Day-grouped lists (primary storage)
        self.all: List[Dict[str, Any]] = []  # Default: soups + mains, orderable
        self.main_only: List[Dict[str, Any]] = []  # Only main meals
        self.soup_only: List[Dict[str, Any]] = []  # Only soups
        self.restricted: List[Dict[str, Any]] = []  # "CO" - too late to order
        self.optional: List[Dict[str, Any]] = []  # "T" - not usually ordered
        self.complete: List[Dict[str, Any]] = []  # all + optional, sorted

    def fetch(self) -> 'Menu':
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
        """Parse raw menu response into structured lists."""
        # Temporary storage categorized by restriction status
        all_meals: Dict[str, List[Dict]] = {}  # Orderable (empty string)
        restricted_meals: Dict[str, List[Dict]] = {}  # "CO" - too late
        optional_meals: Dict[str, List[Dict]] = {}  # "T" - not usually ordered
        
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
                }

                # Categorize by restriction status
                if order_type == OrderType.RESTRICTED:
                    if date not in restricted_meals:
                        restricted_meals[date] = []
                    restricted_meals[date].append(meal_filtered)
                elif order_type == OrderType.OPTIONAL:
                    if date not in optional_meals:
                        optional_meals[date] = []
                    optional_meals[date].append(meal_filtered)
                else:  # NORMAL - orderable
                    if date not in all_meals:
                        all_meals[date] = []
                    all_meals[date].append(meal_filtered)

        # Convert to day-grouped format and sort by date
        self.all = sorted([
            {"date": date, "ordered": any(m["ordered"] for m in meals), "meals": meals}
            for date, meals in all_meals.items()
        ], key=lambda x: x["date"])
        
        self.restricted = sorted([
            {"date": date, "ordered": any(m["ordered"] for m in meals), "meals": meals}
            for date, meals in restricted_meals.items()
        ], key=lambda x: x["date"])
        
        self.optional = sorted([
            {"date": date, "ordered": any(m["ordered"] for m in meals), "meals": meals}
            for date, meals in optional_meals.items()
        ], key=lambda x: x["date"])
        
        # Create filtered views by meal type
        self.main_only = self._filter_by_type_internal(self.all, MealType.MAIN)
        self.soup_only = self._filter_by_type_internal(self.all, MealType.SOUP)
        
        # Create complete list (all + optional, sorted)
        self.complete = self._merge_sorted_lists(self.all, self.optional)

    def _filter_by_type_internal(self, days: List[Dict[str, Any]], meal_type: MealType) -> List[Dict[str, Any]]:
        """Filter days to only include specific meal type."""
        filtered_days = []
        for day in days:
            filtered_meals = [m for m in day["meals"] if m["type"] == meal_type]
            if filtered_meals:
                filtered_days.append({
                    "date": day["date"],
                    "ordered": any(m["ordered"] for m in filtered_meals),
                    "meals": filtered_meals
                })
        return filtered_days

    def _merge_sorted_lists(self, list1: List[Dict[str, Any]], list2: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Merge two sorted day lists, combining meals for same dates."""
        merged = {}
        
        for day in list1 + list2:
            date = day["date"]
            if date not in merged:
                merged[date] = {"date": date, "meals": [], "ordered": False}
            merged[date]["meals"].extend(day["meals"])
            merged[date]["ordered"] = merged[date]["ordered"] or day["ordered"]
        
        return sorted(merged.values(), key=lambda x: x["date"])

    def get_by_date(
        self, date: str, include_restricted: bool = True, include_optional: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Get menu items for a specific date.

        Args:
            date: Date in YYYY-MM-DD format
            include_restricted: Include restricted ("CO") meals in search
            include_optional: Include optional ("T") meals in search

        Returns:
            Dictionary with date and meals, or None if not found
        """
        # Build list of lists to search
        lists_to_search = [self.all]
        if include_restricted:
            lists_to_search.append(self.restricted)
        if include_optional:
            lists_to_search.append(self.optional)
        
        for day_list in lists_to_search:
            for day in day_list:
                if day["date"] == date:
                    return day
        return None

    def get_unordered_days(
        self, include_restricted: bool = False, include_optional: bool = False
    ) -> List[Dict[str, Any]]:
        """Get all days where no meals are ordered.

        Args:
            include_restricted: Include restricted ("CO") days
            include_optional: Include optional ("T") days

        Returns:
            List of days with no ordered meals
        """
        lists_to_search = [self.all]
        if include_restricted:
            lists_to_search.append(self.restricted)
        if include_optional:
            lists_to_search.append(self.optional)
        
        unordered_days = []
        for day_list in lists_to_search:
            for day in day_list:
                if not day["ordered"]:
                    unordered_days.append(day)
        
        return sorted(unordered_days, key=lambda x: x["date"])

    def get_ordered_meals(
        self, include_restricted: bool = True, include_optional: bool = True
    ) -> List[Dict[str, Any]]:
        """Get all ordered meals across all dates.

        Args:
            include_restricted: Include restricted ("CO") meals in results
            include_optional: Include optional ("T") meals in results

        Returns:
            List of ordered meals with their date information
        """
        lists_to_search = [self.all]
        if include_restricted:
            lists_to_search.append(self.restricted)
        if include_optional:
            lists_to_search.append(self.optional)
        
        ordered_meals = []
        for day_list in lists_to_search:
            for day in day_list:
                for meal in day["meals"]:
                    if meal["ordered"]:
                        ordered_meals.append({**meal, "date": day["date"]})
        
        return sorted(ordered_meals, key=lambda x: x["date"])

    def filter_by_type(
        self, meal_type: MealType, include_restricted: bool = False, include_optional: bool = False
    ) -> List[Dict[str, Any]]:
        """Filter meals by type.

        Args:
            meal_type: Type of meal to filter by (MealType.SOUP or MealType.MAIN)
            include_restricted: Include restricted ("CO") meals
            include_optional: Include optional ("T") meals

        Returns:
            List of meals matching the type with their date information
        """
        lists_to_search = [self.all]
        if include_restricted:
            lists_to_search.append(self.restricted)
        if include_optional:
            lists_to_search.append(self.optional)
        
        filtered_meals = []
        for day_list in lists_to_search:
            for day in day_list:
                for meal in day["meals"]:
                    if meal["type"] == meal_type:
                        filtered_meals.append({**meal, "date": day["date"]})
        return sorted(filtered_meals, key=lambda x: x["date"])

    def get_meals(
        self, include_restricted: bool = False, include_optional: bool = False
    ) -> List[Dict[str, Any]]:
        """Get all meals as flat list with date.

        Args:
            include_restricted: Include restricted ("CO") meals
            include_optional: Include optional ("T") meals

        Returns:
            List of all meals (flattened) with date included in each meal
        """
        lists_to_search = [self.all]
        if include_restricted:
            lists_to_search.append(self.restricted)
        if include_optional:
            lists_to_search.append(self.optional)
        
        meals = []
        for day_list in lists_to_search:
            for day in day_list:
                for meal in day["meals"]:
                    meals.append({**meal, "date": day["date"]})
        return meals

    def get_main_meals(
        self, include_restricted: bool = False, include_optional: bool = False
    ) -> List[Dict[str, Any]]:
        """Get only main meals as flat list with date.

        Args:
            include_restricted: Include restricted ("CO") meals
            include_optional: Include optional ("T") meals

        Returns:
            List of main meals (flattened) with date included in each meal
        """
        lists_to_search = [self.all]
        if include_restricted:
            lists_to_search.append(self.restricted)
        if include_optional:
            lists_to_search.append(self.optional)
        
        meals = []
        for day_list in lists_to_search:
            for day in day_list:
                for meal in day["meals"]:
                    if meal["type"] == MealType.MAIN:
                        meals.append({**meal, "date": day["date"]})
        return meals

    def get_soup_meals(
        self, include_restricted: bool = False, include_optional: bool = False
    ) -> List[Dict[str, Any]]:
        """Get only soup meals as flat list with date.

        Args:
            include_restricted: Include restricted ("CO") meals
            include_optional: Include optional ("T") meals

        Returns:
            List of soup meals (flattened) with date included in each meal
        """
        lists_to_search = [self.all]
        if include_restricted:
            lists_to_search.append(self.restricted)
        if include_optional:
            lists_to_search.append(self.optional)
        
        meals = []
        for day_list in lists_to_search:
            for day in day_list:
                for meal in day["meals"]:
                    if meal["type"] == MealType.SOUP:
                        meals.append({**meal, "date": day["date"]})
        return meals

    def get_by_id(
        self, meal_id: int, include_restricted: bool = True, include_optional: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Get a specific meal by its ID.

        Args:
            meal_id: Meal identification number
            include_restricted: Include restricted ("CO") meals in search
            include_optional: Include optional ("T") meals in search

        Returns:
            Meal dictionary with date information, or None if not found
        """
        lists_to_search = [self.all]
        if include_restricted:
            lists_to_search.append(self.restricted)
        if include_optional:
            lists_to_search.append(self.optional)
        
        for day_list in lists_to_search:
            for day in day_list:
                for meal in day["meals"]:
                    if meal["id"] == meal_id:
                        return {**meal, "date": day["date"]}
        return None

    def is_ordered(
        self, meal_id: int, include_restricted: bool = True, include_optional: bool = True
    ) -> bool:
        """Check whether a meal is ordered or not.

        Args:
            meal_id: Meal identification number
            include_restricted: Include restricted ("CO") meals in search
            include_optional: Include optional ("T") meals in search

        Returns:
            True if meal is ordered, False otherwise
        """
        meal = self.get_by_id(meal_id, include_restricted, include_optional)
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
            StravaAPIError: If changing meal order status fails
        """
        if not self.strava.user.is_logged_in:
            raise AuthenticationError("User not logged in")

        if self.is_ordered(meal_id) == ordered:
            return True

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
            raise StravaAPIError("Failed to change meal order status")
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

    def order_meals(self, *meal_ids: int) -> None:
        """Order multiple meals in a single transaction.

        Args:
            *meal_ids: Variable number of meal identification numbers

        Raises:
            StravaAPIError: If ordering any meal fails
        """
        for meal_id in meal_ids:
            self._change_meal_order(meal_id, True)
        self._save_order()
        self.fetch()  # Refresh menu data

        for meal_id in meal_ids:
            if not self.is_ordered(meal_id):
                raise StravaAPIError(f"Failed to order meal with ID {meal_id}")

    def cancel_meals(self, *meal_ids: int) -> None:
        """Cancel multiple meal orders in a single transaction.

        Args:
            *meal_ids: Variable number of meal identification numbers

        Raises:
            StravaAPIError: If canceling any meal fails
        """
        for meal_id in meal_ids:
            self._change_meal_order(meal_id, False)
        self._save_order()
        self.fetch()  # Refresh menu data

        for meal_id in meal_ids:
            if self.is_ordered(meal_id):
                raise StravaAPIError(f"Failed to cancel meal with ID {meal_id}")

    def print(self) -> None:
        """Print the current menu in a readable format."""
        if not self.all:
            print("No menu data available")
            return

        for day in self.all:
            print(f"Date: {day['date']} - {'Ordered' if day['ordered'] else 'Not ordered'}")
            for meal in day["meals"]:
                status = "Ordered" if meal["ordered"] else "Not ordered"
                meal_type_str = meal['type'].value  # Get string value from enum
                print(f"  - {meal['id']} {meal['name']} ({meal_type_str}) - [{status}]")
            print()

    def __repr__(self) -> str:
        """Return the default processed list representation."""
        return repr(self.all)

    def __str__(self) -> str:
        """Return string representation of the default list."""
        return str(self.all)

    def __iter__(self):
        """Iterate over the default processed list."""
        return iter(self.all)

    def __len__(self) -> int:
        """Return the number of days in default menu."""
        return len(self.all)

    def __getitem__(self, key):
        """Access days by index from default list."""
        return self.all[key]


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
    print(strava.user)

    # Fetch and display menu
    strava.menu.fetch()
    #strava.menu.print()

    #print(strava.menu.optional)
    #print(strava.menu.restricted)
    #print(strava.menu.all)
    #print(strava.menu.complete)
    #ordered = strava.menu.get_ordered_meals()
    #print(f"\nOrdered meals: {len(ordered)}")

    print(strava.menu)

    strava.logout()
    print("Logged out")
