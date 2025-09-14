from strava_cz import StravaCZ

# vytvoreni objektu strava a prihlaseni uzivatele
strava = StravaCZ(
    username="your.username", 
    password="YourPassword123", 
    canteen_number="3753"
    )

# vypsani informaci o uzivateli
print(strava.user)

# ziskani jidelnicku; ulozi list do strava.menu
print(strava.get_menu_list())

# zjisti, jestli je jidlo s meal_id 4 objednano (True/False)
print(strava.is_ordered(4))

# objedna jidlo s meal_id 4
strava.order_meal(4)

# objedna jidla s meal_id 3 a 6
strava.order_meals(3, 6)

# odhlasi uzivatele
strava.logout()