# Migration Guide: Menu Class Refactoring & Advanced Error Handling
### Tento text byl vytvoren pomoci LLM / This text was made by an LLM

## Overview

### Version 0.2.0 (Current)
The menu functionality has been refactored into an independent `Menu` class that maintains a reference to the `StravaCZ` client. Users now interact directly with the `Menu` class instead of calling menu methods on `StravaCZ`.

The new API provides two main methods with flexible filtering parameters instead of multiple specialized methods.

**New in 0.2.0:**
- Advanced error handling with `continue_on_error` parameter
- Automatic duplicate meal detection with `strict_duplicates` parameter
- Meal type validation (only MAIN meals can be ordered)
- Balance tracking and insufficient balance detection
- New exceptions: `InvalidMealTypeError`, `DuplicateMealError`, `InsufficientBalanceError`

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

### New API (v0.2.0 - Current)
```python
from strava_cz import (
    StravaCZ, 
    MealType, 
    OrderType,
    InvalidMealTypeError,
    DuplicateMealError,
    InsufficientBalanceError
)

strava = StravaCZ(username="...", password="...", canteen_number="...")

# Fetching menu (no parameters needed)
strava.menu.fetch()

# Printing menu
strava.menu.print()

# Checking if ordered
is_ordered = strava.menu.is_ordered(meal_id=4)

# Ordering meals with advanced error handling
try:
    strava.menu.order_meals(
        3, 6,
        continue_on_error=False,    # Stop on first error (default)
        strict_duplicates=False      # Warn about duplicates (default)
    )
except InvalidMealTypeError as e:
    print(f"Invalid meal type: {e}")
except DuplicateMealError as e:
    print(f"Duplicate meals: {e}")
except InsufficientBalanceError as e:
    print(f"Insufficient balance: {e}")

# Canceling meals
strava.menu.cancel_meals(3, 6, continue_on_error=False)

# Check balance
print(f"Balance: {strava.user.balance} Kč")
```

## New Features in v0.2.0

### 1. Duplicate Meal Detection

The system now automatically detects when you try to order multiple meals from the same day:

```python
# Default behavior: warn and order only the first meal
strava.menu.order_meals(meal_1, meal_2_same_day)
# Warning: Skipping meal X from 2025-11-11 because meal Y from the same day is already being ordered

# Strict mode: throw error
try:
    strava.menu.order_meals(meal_1, meal_2_same_day, strict_duplicates=True)
except DuplicateMealError as e:
    print(f"Error: {e}")
```

### 2. Meal Type Validation

Only MAIN meals can be ordered or canceled. Soups are automatically served with main dishes:

```python
try:
    strava.menu.order_meals(soup_id)  # Will raise InvalidMealTypeError
except InvalidMealTypeError as e:
    print(f"Cannot order soups: {e}")
```

### 3. Balance Tracking

User balance is automatically updated after each operation:

```python
print(f"Before: {strava.user.balance} Kč")
strava.menu.order_meals(meal_id)
print(f"After: {strava.user.balance} Kč")  # Updated automatically

try:
    strava.menu.order_meals(expensive_meal)
except InsufficientBalanceError as e:
    print(f"Not enough money: {e}")
    print(f"Current balance: {strava.user.balance} Kč")
```

### 4. Advanced Error Handling

Control how errors are handled with `continue_on_error`:

```python
# Default: stop on first error and rollback all changes
try:
    strava.menu.order_meals(soup, main, another_main)
except InvalidMealTypeError:
    pass  # Nothing was ordered, all changes rolled back

# Continue on error: collect all errors and report at the end
from strava_cz import StravaAPIError

try:
    strava.menu.order_meals(
        soup, main, another_main,
        continue_on_error=True
    )
except StravaAPIError as e:
    # e contains all errors that occurred
    # main and another_main were still ordered successfully
    print(f"Some errors occurred: {e}")
```

### 5. Automatic Rollback

When an error occurs (and `continue_on_error=False`), all changes are automatically rolled back:

```python
try:
    strava.menu.order_meals(meal_1, meal_2, invalid_meal)
except InvalidMealTypeError:
    # meal_1 and meal_2 were NOT ordered
    # all changes were automatically rolled back
    pass
```

## Menu Class Features (v0.2.0)

### Flexible Filtering System

The new API uses two main methods with flexible parameters:

**1. `get_days(meal_types=None, order_types=None, ordered=None)`** - Returns meals grouped by days
**2. `get_meals(meal_types=None, order_types=None, ordered=None)`** - Returns flat list of meals

**Parameters:**
- `meal_types`: List of `MealType` values (e.g., `[MealType.SOUP, MealType.MAIN]`)
  - `None` = all types
- `order_types`: List of `OrderType` values (e.g., `[OrderType.NORMAL, OrderType.RESTRICTED]`)
  - `None` = defaults to `[OrderType.NORMAL]` (orderable meals only)
- `ordered`: Boolean filter for order status
  - `True` = only ordered meals
  - `False` = only unordered meals
  - `None` = all meals

**Examples:**

```python
from strava_cz import StravaCZ, MealType, OrderType

strava = StravaCZ(username="...", password="...", canteen_number="...")
strava.menu.fetch()

# Get all orderable meals (default - grouped by days)
days = strava.menu.get_days()

# Get all orderable meals as flat list
meals = strava.menu.get_meals()

# Get only soups
soups = strava.menu.get_meals(meal_types=[MealType.SOUP])

# Get only main dishes
mains = strava.menu.get_days(meal_types=[MealType.MAIN])

# Get all meals including restricted and optional
all_meals = strava.menu.get_meals(
    order_types=[OrderType.NORMAL, OrderType.RESTRICTED, OrderType.OPTIONAL]
)

# Get only ordered meals
ordered = strava.menu.get_meals(ordered=True)

# Get days with no orders
unordered_days = strava.menu.get_days(ordered=False)

# Get restricted meals only
restricted = strava.menu.get_days(order_types=[OrderType.RESTRICTED])

# Complex filtering: ordered main dishes including optional ones
ordered_mains = strava.menu.get_meals(
    meal_types=[MealType.MAIN],
    order_types=[OrderType.NORMAL, OrderType.OPTIONAL],
    ordered=True
)
```

### Direct Menu Access
```python
# Get menu for specific date (searches all order types)
today_menu = strava.menu.get_by_date("2025-11-10")

# Get specific meal by ID (searches all order types)
meal = strava.menu.get_by_id(4)

# Check order status (searches all order types)
is_ordered = strava.menu.is_ordered(4)
```

### Type Safety with Enums
```python
# meal["type"] is a MealType enum
for meal in strava.menu.get_meals():
    print(meal["type"])  # Output: MealType.SOUP or MealType.MAIN
    print(meal["type"].value)  # Output: "Polévka" or "Oběd"

# meal["orderType"] indicates order restriction
for meal in strava.menu.get_meals(order_types=[OrderType.NORMAL, OrderType.RESTRICTED, OrderType.OPTIONAL]):
    if meal["orderType"] == OrderType.RESTRICTED:
        print(f"Meal {meal['id']} can no longer be ordered")
    elif meal["orderType"] == OrderType.OPTIONAL:
        print(f"Meal {meal['id']} is optional")
```

### Menu Information
```python
# Get number of orderable days in menu
num_days = len(strava.menu)

# Get string representation
print(strava.menu)  # Output: Menu(days=5, meals=25)

# Iterate over orderable days
for day in strava.menu:
    print(f"{day['date']}: {len(day['meals'])} meals")

# Access raw API data
raw_data = strava.menu.raw_data
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
