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

# Pristup k ruznym seznamum
print(f"Vsechny jidla: {len(strava.menu)} dni")
print(f"Pouze hlavni jidla: {len(strava.menu.main_only)} dni")
print(f"Pouze polevky: {len(strava.menu.soup_only)} dni")
print(f"Kompletni (s volitelymi): {len(strava.menu.complete)} dni")
print(f"Omezene objednavky: {len(strava.menu.restricted)} dni")
print(f"Volitelne objednavky: {len(strava.menu.optional)} dni")

# Iterace pres menu
for day in strava.menu:
    print(f"Datum: {day['date']}, Pocet jidel: {len(day['meals'])}")

# Priklad: Kontrola typu objednavky
for day in strava.menu.complete:
    for meal in day['meals']:
        if meal['orderType'] == OrderType.RESTRICTED:
            print(f"Jidlo {meal['id']} ({meal['name']}) uz nelze objednat")
        elif meal['orderType'] == OrderType.OPTIONAL:
            print(f"Jidlo {meal['id']} ({meal['name']}) je volitelne")
        elif meal['orderType'] == OrderType.NORMAL:
            print(f"Jidlo {meal['id']} ({meal['name']}) lze objednat normalne")

# Zjisti, jestli je jidlo s meal_id 4 objednano (True/False)
print(strava.menu.is_ordered(4))

# Objedna jidla s meal_id 3 a 6
strava.menu.order_meals(3, 6)

# Priklad: Ziskani vsech objednanych jidel
ordered_meals = strava.menu.get_ordered_meals()
print(f"Objednana jidla: {len(ordered_meals)}")

# Priklad: Ziskani neobjednanych dni
unordered_days = strava.menu.get_unordered_days()
print(f"Dny bez objednavky: {unordered_days}")

# Priklad: Ziskani ploschych seznamu jidel
all_meals = strava.menu.get_meals()
main_meals = strava.menu.get_main_meals()
soup_meals = strava.menu.get_soup_meals()
print(f"Celkem jidel: {len(all_meals)} (hlavni: {len(main_meals)}, polevky: {len(soup_meals)})")

# Priklad: Zahrnuti omezenych a volitelnych jidel
all_with_restricted = strava.menu.get_meals(include_restricted=True)
all_complete = strava.menu.get_meals(include_restricted=True, include_optional=True)
print(f"S omezenymi: {len(all_with_restricted)}, kompletni: {len(all_complete)}")

# Odhlasi uzivatele
strava.logout()