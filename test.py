from src import strava_cz 

strava = strava_cz.StravaCZ()
strava.login(username="", password="", canteen_number="3753")
print(strava.user)
print(strava.get_orders_list())
print(strava.is_ordered(4))
strava.order_meal(4)
strava.order_meals(3, 6)
strava.logout()