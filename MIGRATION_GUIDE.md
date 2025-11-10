# Migration Guide: Menu Class Refactoring
### Tento text byl vytvoren pomoci LLM / This text was made by an LLM

## Overview
The menu functionality has been refactored into an independent `Menu` class that maintains a reference to the `StravaCZ` client. Users now interact directly with the `Menu` class instead of calling menu methods on `StravaCZ`.

## Breaking Changes

### Old API (Deprecated)
```python
strava = StravaCZ(username="...", password="...")

# Fetching menu
menu_data = strava.get_menu(include_soup=True)

# Printing menu
strava.print_menu()

# Checking if ordered
is_ordered = strava.is_ordered(meal_id=4)

# Ordering meals
strava.order_meals(3, 6)

# Canceling meals
strava.cancel_meals(3, 6)
```

### New API (Current)
```python
from strava_cz import StravaCZ, MealType

strava = StravaCZ(username="...", password="...")

# Fetching menu
strava.menu.fetch(include_soup=True)

# Printing menu
strava.menu.print()

# Checking if ordered
is_ordered = strava.menu.is_ordered(meal_id=4)

# Ordering meals
strava.menu.order_meals(3, 6)

# Canceling meals
strava.menu.cancel_meals(3, 6)
```

## New Features

### Direct Menu Access
```python
# Get all menu data
all_meals = strava.menu.get_all()

# Get menu for specific date
today_menu = strava.menu.get_by_date("2025-11-04")

# Get all ordered meals
ordered = strava.menu.get_ordered_meals()

# Get specific meal by ID
meal = strava.menu.get_by_id(4)
```

### Filtering Capabilities
```python
from strava_cz import MealType, OrderType

# Filter by meal type (now using enum)
soups = strava.menu.filter_by_type(MealType.SOUP)
main_dishes = strava.menu.filter_by_type(MealType.MAIN)

# Note: meal["type"] is now a MealType enum, not a string
for meal in soups:
    print(meal["type"])  # Output: MealType.SOUP
    print(meal["type"].value)  # Output: "Polévka"

# Each meal also has orderType field
for meal in strava.menu.get_meals():
    print(meal["orderType"])  # Output: OrderType.NORMAL, OrderType.RESTRICTED, or OrderType.OPTIONAL
    if meal["orderType"] == OrderType.RESTRICTED:
        print(f"Meal {meal['id']} can no longer be ordered")
```

### Multiple List Views
```python
# Default list (orderable meals: soups + mains)
default = strava.menu.all

# Only main dishes
mains = strava.menu.main_only

# Only soups
soups = strava.menu.soup_only

# Complete list including optional meals
complete = strava.menu.complete

# Meals that can no longer be ordered ("CO")
restricted = strava.menu.restricted

# Optional meals not usually ordered ("T")
optional = strava.menu.optional

# Flat lists with dates
all_meals = strava.menu.get_meals()
main_meals = strava.menu.get_main_meals()
soup_meals = strava.menu.get_soup_meals()
```

### Controlling Restricted and Optional Inclusion
```python
# By default, list methods exclude restricted and optional
meals = strava.menu.get_meals()  # Only normal meals

# Include restricted meals
meals = strava.menu.get_meals(include_restricted=True)

# Include optional meals
meals = strava.menu.get_meals(include_optional=True)

# Include both
meals = strava.menu.get_meals(include_restricted=True, include_optional=True)

# Search methods include all by default
meal = strava.menu.get_by_id(123)  # Searches all lists
meal = strava.menu.get_by_id(123, include_restricted=False)  # Only searches normal lists

# Get days with no orders
unordered = strava.menu.get_unordered_days()  # Excludes restricted/optional
unordered = strava.menu.get_unordered_days(include_restricted=True, include_optional=True)  # All days
```

### Menu Information
```python
# Get number of days in menu
num_days = len(strava.menu)

# Get string representation
print(strava.menu)  # Output: Menu(days=5, meals=25)

# Access raw API data
raw_data = strava.menu.raw_data

# Access processed data
processed = strava.menu.processed_data
```

## Method Mapping

| Old Method | New Method | Notes |
|------------|------------|-------|
| `strava.get_menu()` | `strava.menu.fetch()` | Returns Menu object for chaining |
| `strava.print_menu()` | `strava.menu.print()` | Renamed for brevity |
| `strava.is_ordered(id)` | `strava.menu.is_ordered(id)` | Moved to Menu class |
| `strava.order_meals(*ids)` | `strava.menu.order_meals(*ids)` | Moved to Menu class |
| `strava.cancel_meals(*ids)` | `strava.menu.cancel_meals(*ids)` | Moved to Menu class |

## Benefits

1. **Separation of Concerns**: Menu logic is isolated in its own class
2. **Self-Contained**: Menu can manage its own data and API calls
3. **Extensible**: Easy to add new filtering and processing methods
4. **Raw Data Access**: Both raw and processed data are preserved
5. **Method Chaining**: `fetch()` returns self for chaining
6. **Better Organization**: Related functionality grouped together

## Complete Example

```python
from strava_cz import StravaCZ, MealType

# Login
strava = StravaCZ(
    username="your.username",
    password="YourPassword123",
    canteen_number="3753"
)

# Fetch and display menu
strava.menu.fetch(include_soup=True, include_empty=False)
strava.menu.print()

# Work with menu data
print(f"Menu contains {len(strava.menu)} days")

# Get ordered meals
ordered = strava.menu.get_ordered_meals()
print(f"You have {len(ordered)} meals ordered")

# Filter by type
soups = strava.menu.filter_by_type(MealType.SOUP)
print(f"Found {len(soups)} soups")

# Order new meals
strava.menu.order_meals(10, 15, 20)

# Check if specific meal is ordered
if strava.menu.is_ordered(10):
    print("Meal 10 is now ordered!")

# Logout
strava.logout()
```

## Architecture

The `Menu` class now holds a reference to its parent `StravaCZ` instance:

```python
class Menu:
    def __init__(self, strava_client: 'StravaCZ'):
        self.strava = strava_client
        self.raw_data = {}
        self.processed_data = []
```

This allows the Menu to:
- Access user credentials for API calls
- Call `_api_request()` method directly
- Refresh its own data after ordering/canceling meals
- Operate independently without external data passing
