# Strava.cz Python API

High level API pro interakci s webovou aplikaci Strava.cz udelane v Pythonu ciste pomoci request knihovny.

Ve slozce [notes](https://github.com/jsem-nerad/strava-cz-python/tree/main/notes) muzete najit veskere moje poznatky, ktere jsem zjistil o internim fungovani aplikace Strava.cz.

## Features
- Prihlaseni/odhlaseni
- Vypsani prefiltrovaneho jidelnicku 
- Objednavani jidel podle ID jidla


## Usage

```bash
pip install strava-cz
```



```python
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
```

> meal_id je unikatni identifikacni cislo jidla v celem jidelnicku. jeste jsem poradne nezjistil, jak a jestli se meni v zavislosti na zmene jidelnicku.


| funkce              | parametry                                                 | return type | popis                                                                                                              |
|---------------------|-----------------------------------------------------------|-------------|--------------------------------------------------------------------------------------------------------------------|
| `__init__()`        | username=None, password=None, canteen_number=None         | None        | Inicializuje objekt StravaCZ a automaticky prihlasi uzivatele, pokud jsou vyplnene parametry username a password   |
| `login()`           | username (str), password (str), canteen_number=None (str) | User        | Prihlasi uzivatele pomoci uzivatelskeho jmena a hesla; pokud neni vyplnene cislo jidelny, automaticky pouzije 3753 |
| `get_menu_list()` | None                                                      | list        | Vrati jidelnicek jako seznam podle dni; zaroven ho ulozi do promenne menu                        |
| `is_ordered()`      | meal_id (int)                                             | bool        | Zjisti, jestli je dane jidlo objednano        |
| `order_meal()`      | meal_id (int)                                             | None        | Objedna jidlo podle meal_id                                                                                        |
| `order_meals()`     | *meal_ids (int)                                           | None        | Objedna vice jidel podle meal_id                                                                                   |
| `logout()`          | None                                                      | bool        | Odhlasi uzivatele                                                                                                  |


## to-do

- [x] Nahrat jako knihovnu na PyPi
- [x] Lepe zorganizovat kod
- [ ] Univerzalni datum
- [ ] Moznost detailni filtrace jidelnicku
- [ ] Lepe zdokumentovat pouziti

## Co bude dal?

Planuji udelat aplikaci, ktera bude uzivateli automaticky objednavat obedy podle jeho preferenci.

Prosim, nepouzivejte tuto aplikaci k nekalym ucelum. Pouzivejte ji pouze s dobrymi zamery.


## Pomoz mi pls

Nasel jsi chybu nebo mas navrh na zlepseni? Skvele! Vytvor prosim [bug report](https://github.com/jsem-nerad/strava-cz-python/issues/new?labels=bug) nebo [feature request](https://github.com/jsem-nerad/strava-cz-python/issues/new?labels=enhancement), hodne mi tim muzes pomoct.

Udelal jsi sam nejake zlepseni? Jeste lepsi! Kazdy pull request je vitan.




