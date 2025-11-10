from strava_cz import StravaCZ, MealType, OrderType

# Vytvoreni objektu strava a prihlaseni uzivatele
strava = StravaCZ(
    username="your.username", 
    password="YourPassword123", 
    canteen_number="your canteen number"
    )

# Vypsani informaci o uzivateli
print(strava.user)

# Ziskani jidelnicku a vypsani
strava.menu.fetch()
strava.menu.print()

# Informace o menu
print(f"\nMenu: {strava.menu}")
print(f"Pocet objednatelnych dni: {len(strava.menu)}")

# Iterace pres objednavatelna jidla (default)
for day in strava.menu:
    print(f"Datum: {day['date']}, Pocet jidel: {len(day['meals'])}")

# ===== Ziskani jidel podle dni =====

# Pouze objednavatelna jidla (default)
normal_days = strava.menu.get_days()
print(f"\nObjednavatelne dny: {len(normal_days)}")

# Pouze polevky
soup_days = strava.menu.get_days(meal_types=[MealType.SOUP])
print(f"Dny s polevkami: {len(soup_days)}")

# Pouze hlavni jidla
main_days = strava.menu.get_days(meal_types=[MealType.MAIN])
print(f"Dny s hlavnimi jidly: {len(main_days)}")

# Vsechna jidla (vcetne omezenych a volitelnych)
all_days = strava.menu.get_days(
    order_types=[OrderType.NORMAL, OrderType.RESTRICTED, OrderType.OPTIONAL]
)
print(f"Vsechny dny: {len(all_days)}")

# Pouze dny s objednavkami
ordered_days = strava.menu.get_days(ordered=True)
print(f"Dny s objednavkami: {len(ordered_days)}")

# Pouze dny bez objednavek
unordered_days = strava.menu.get_days(ordered=False)
print(f"Dny bez objednavek: {len(unordered_days)}")

# ===== Ziskani jidel jako ploschy seznam =====

# Vsechna objednavatelna jidla
meals = strava.menu.get_meals()
print(f"\nCelkem objednatelnych jidel: {len(meals)}")

# Pouze polevky
soups = strava.menu.get_meals(meal_types=[MealType.SOUP])
print(f"Polevky: {len(soups)}")

# Pouze hlavni jidla
mains = strava.menu.get_meals(meal_types=[MealType.MAIN])
print(f"Hlavni jidla: {len(mains)}")

# Pouze objednana jidla
ordered = strava.menu.get_meals(ordered=True)
print(f"Objednana jidla: {len(ordered)}")

# Vcetne omezenych jidel
with_restricted = strava.menu.get_meals(
    order_types=[OrderType.NORMAL, OrderType.RESTRICTED]
)
print(f"S omezenymi: {len(with_restricted)}")

# Vsechna jidla (vcetne omezenych a volitelnych)
all_meals = strava.menu.get_meals(
    order_types=[OrderType.NORMAL, OrderType.RESTRICTED, OrderType.OPTIONAL]
)
print(f"Vsechna jidla: {len(all_meals)}")

# ===== Priklady kontroly typu objednavky =====

for meal in all_meals[:5]:  # Prvnich 5 jidel
    if meal['orderType'] == OrderType.RESTRICTED:
        print(f"  {meal['name']} - NELZE OBJEDNAT")
    elif meal['orderType'] == OrderType.OPTIONAL:
        print(f"  {meal['name']} - VOLITELNE")
    else:
        print(f"  {meal['name']} - NORMALNI")

# ===== Vyhledavani =====

# Zjisti, jestli je jidlo s meal_id 4 objednano (True/False)
print(f"\nJidlo 4 je objednano: {strava.menu.is_ordered(4)}")

# Ziskej jidlo podle ID
meal = strava.menu.get_by_id(4)
if meal:
    print(f"Jidlo 4: {meal['name']} ({meal['type'].value})")

# Ziskej jidla pro konkretni datum
today_meals = strava.menu.get_by_date("2025-11-11")
if today_meals:
    print(f"Jidla na 11.11: {len(today_meals['meals'])} jidel")

# ===== Objednavani =====

# Objedna jidla s meal_id 3 a 6
strava.menu.order_meals(3, 6)

# Zrus objednavky
strava.menu.cancel_meals(3, 6)

# Odhlasi uzivatele
strava.logout()