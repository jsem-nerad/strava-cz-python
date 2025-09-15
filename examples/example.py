from strava_cz import StravaCZ

# Vytvoreni objektu strava a prihlaseni uzivatele
strava = StravaCZ(
    username="your.username", 
    password="YourPassword123", 
    canteen_number="your canteen number"
    )

# Vypsani informaci o uzivateli
print(strava.user)

# Ziskani jidelnicku; ulozi list do strava.menu
print(strava.get_menu())

# Zjisti, jestli je jidlo s meal_id 4 objednano (True/False)
print(strava.is_ordered(4))

# Objedna jidla s meal_id 3 a 6
strava.order_meals(3, 6)

# Odhlasi uzivatele
strava.logout()