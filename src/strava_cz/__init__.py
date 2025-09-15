"""
StravaCZ - High level API pro interakci s webovou aplikaci Strava.cz
"""

from .main import StravaCZ, AuthenticationError, StravaAPIError, User

__version__ = "0.1.1"
__author__ = "Vojtěch Nerad"
__email__ = "ja@jsem-nerad.cz"

__all__ = ["StravaCZ", "AuthenticationError", "StravaAPIError", "User"]
