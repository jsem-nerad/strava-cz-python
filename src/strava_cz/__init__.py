"""strava_cz - a Python client for the Strava.cz school canteen system.

from strava_cz import StravaCZ

with StravaCZ("your.username", "YourPassword", "3753") as strava:
    strava.menu.fetch()
    strava.menu.print()
    strava.menu.order_meals(3, 6)
"""

from .client import DEFAULT_BASE_URL, StravaCZ
from .exceptions import (
    AuthenticationError,
    DuplicateMealError,
    InsufficientBalanceError,
    MealNotFoundError,
    MealNotOrderableError,
    MenuNotFetchedError,
    NotLoggedInError,
    StravaAPIError,
    StravaError,
)
from .menu import Menu
from .models import (
    Allergen,
    Day,
    DayStatus,
    Meal,
    MealType,
    OrderResult,
    Restriction,
    User,
)

__version__ = "0.3.0"
__author__ = "Vojtěch Nerad"
__email__ = "ja@jsem-nerad.cz"

__all__ = [
    # client
    "StravaCZ",
    "Menu",
    "DEFAULT_BASE_URL",
    # data
    "User",
    "Day",
    "Meal",
    "Allergen",
    "MealType",
    "DayStatus",
    "Restriction",
    "OrderResult",
    # exceptions
    "StravaError",
    "StravaAPIError",
    "AuthenticationError",
    "NotLoggedInError",
    "InsufficientBalanceError",
    "MealNotFoundError",
    "MealNotOrderableError",
    "DuplicateMealError",
    "MenuNotFetchedError",
    "__version__",
]
