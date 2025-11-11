"""
StravaCZ - High level API pro interakci s webovou aplikaci Strava.cz
"""

from .main import (
    StravaCZ,
    AuthenticationError,
    StravaAPIError,
    InsufficientBalanceError,
    DuplicateMealError,
    InvalidMealTypeError,
    User,
    MealType,
    OrderType,
    Menu,
)

__version__ = "0.2.0"
__author__ = "Vojtěch Nerad"
__email__ = "ja@jsem-nerad.cz"

__all__ = [
    "StravaCZ",
    "AuthenticationError",
    "StravaAPIError",
    "InsufficientBalanceError",
    "DuplicateMealError",
    "InvalidMealTypeError",
    "User",
    "MealType",
    "OrderType",
    "Menu",
]
