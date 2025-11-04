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
```

> meal_id je unikatni identifikacni cislo jidla v celem jidelnicku. neni ovsem stale vazane na konkretni jidlo a meni se se zmenami jidelnicku


| funkce              | parametry                                                 | return type | popis                                                                                                              |
|---------------------|-----------------------------------------------------------|-------------|--------------------------------------------------------------------------------------------------------------------|
| `__init__()` (=`StravaCZ()`)        | username=None, password=None, canteen_number=None         | None        | Inicializuje objekt StravaCZ a automaticky prihlasi uzivatele, pokud jsou vyplnene parametry username a password   |
| `login()`           | username [str], password [str], canteen_number=None [str] | User        | Prihlasi uzivatele pomoci uzivatelskeho jmena a hesla; pokud neni vyplnene cislo jidelny, automaticky pouzije 3753 |
| `get_menu()` | None                                                      | list        | Vrati jidelnicek jako seznam podle dni; zaroven ho ulozi do promenne menu                        |
| `print_menu()`          | include_soup [bool], include_empty [bool]             | None        | Vypise zformatovane menu         |
| `is_ordered()`      | meal_id [int]                                             | bool        | Zjisti, jestli je dane jidlo objednano        |
| `order_meals()`     | *meal_ids [int]                                           | None        | Objedna vice jidel podle meal_id                                                                                   |
| `logout()`          | None                                                      | bool        | Odhlasi uzivatele                                                                                                  |


## to-do

- [x] Nahrat jako knihovnu na PyPi
- [x] Lepe zorganizovat kod
- [x] Lepsi datum format
- [x] Moznost detailnejsi filtrace jidelnicku
- [x] Kontrola stavu po objednani
- [ ] Lepe zdokumentovat pouziti
- [ ] Rate limiting
- [ ] Balance check pred objednanim
- [ ] Filtrace dnu, ktere nejdou objednat
- [ ] Lepsi testing


## Known bugs



## Co bude dal?

Planuji udelat aplikaci, ktera bude uzivateli automaticky objednavat obedy podle jeho preferenci.

Prosim, nepouzivejte tuto aplikaci k nekalym ucelum. Pouzivejte ji pouze s dobrymi zamery.


## Pomoz mi pls

Nasel jsi chybu nebo mas navrh na zlepseni? Skvele! Vytvor prosim [bug report](https://github.com/jsem-nerad/strava-cz-python/issues/new?labels=bug) nebo [feature request](https://github.com/jsem-nerad/strava-cz-python/issues/new?labels=enhancement), hodne mi tim muzes pomoct.

Udelal jsi sam nejake zlepseni? Jeste lepsi! Kazdy pull request je vitan.




