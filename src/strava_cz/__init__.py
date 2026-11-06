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
    EncryptionUnavailableError,
    InsufficientBalanceError,
    KeyringUnavailableError,
    MealNotFoundError,
    MealNotOrderableError,
    MenuNotFetchedError,
    NotLoggedInError,
    OrderNotConfirmedError,
    ProfileError,
    ProfileNotFoundError,
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
from .profiles import Profile, ProfileStore, SecretSource

__version__ = "0.5.0"
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
    # profiles
    "Profile",
    "ProfileStore",
    "SecretSource",
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
    "OrderNotConfirmedError",
    "ProfileError",
    "ProfileNotFoundError",
    "KeyringUnavailableError",
    "EncryptionUnavailableError",
    "__version__",
]
