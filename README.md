# Strava.cz Python API

High level API pro interakci s webovou aplikaci Strava.cz udelane v Pythonu ciste pomoci request knihovny.

Ve slozce [notes](https://github.com/jsem-nerad/strava-cz-python/tree/main/notes) muzete najit veskere moje poznatky, ktere jsem zjistil o internim fungovani aplikace Strava.cz.

## Features
- Prihlaseni/odhlaseni
- Vypsani prefiltrovaneho jidelnicku
- Objednavani a odhlasovani jidel podle ID jidla
- Automaticke filtrovani jidel podle typu a objednatelnosti
- Vice pohledu na jidelnicek (vsechny, pouze hlavni, pouze polevky, kompletni, omezene)
- Vyhledavani jidel podle ID nebo data
- Ulozeni raw i zpracovanych dat z API
- Menu objekt se chova jako list pro snadnou iteraci


## Usage

```bash
pip install strava-cz
```

```python
from strava_cz import StravaCZ, MealType

# Vytvoreni objektu strava a prihlaseni uzivatele
strava = StravaCZ(
    username="your.username", 
    password="YourPassword123", 
    canteen_number="your canteen number"
    )

# Vypsani informaci o uzivateli
print(strava.user)

# Ziskani jidelnicku
strava.menu.fetch()
strava.menu.print()

# Pristup k ruznym pohledum na menu
print(f"Vsechny jidla: {len(strava.menu)} dni")  # Default - vsechna objednavatelna jidla
print(f"Pouze hlavni: {len(strava.menu.main_only)} dni")
print(f"Pouze polevky: {len(strava.menu.soup_only)} dni")
print(f"Kompletni: {len(strava.menu.complete)} dni")  # Vcetne volitelnych jidel

# Iterace pres menu (default seznam)
for day in strava.menu:
    print(f"Datum: {day['date']}, Pocet jidel: {len(day['meals'])}")

# Zjisti, jestli je jidlo s meal_id 4 objednano (True/False)
print(strava.menu.is_ordered(4))

# Objedna jidla s meal_id 3 a 6
strava.menu.order_meals(3, 6)

# Ziskani vsech objednanych jidel (prohledava vsechny seznamy)
ordered = strava.menu.get_ordered_meals()

# Ziskani ploschych seznamu jidel s datem
all_meals = strava.menu.get_meals()  # Vsechna jidla jako ploschy seznam
main_meals = strava.menu.get_main_meals()  # Pouze hlavni jidla
soup_meals = strava.menu.get_soup_meals()  # Pouze polevky

# Ziskani jidelnicku podle konkretniho data (prohledava vsechny seznamy)
today_menu = strava.menu.get_by_date("2025-11-04")

# Odhlasi uzivatele
strava.logout()
```

> meal_id je unikatni identifikacni cislo jidla v celem jidelnicku. neni ovsem stale vazane na konkretni jidlo a meni se se zmenami jidelnicku kazdy den

> **Pozor!** Verze 0.2.0 obsahuje breaking changes. Prosim precti si [migration guide](MIGRATION_GUIDE.md) pro vice informaci o pruchodu na novou verzi.

### Struktura dat jidla

Kazde jidlo v menu obsahuje nasledujici polozky:
- `id` [int] - Unikatni identifikacni cislo jidla
- `type` [MealType] - Typ jidla (MealType.SOUP nebo MealType.MAIN)
- `orderType` [OrderType] - Typ objednavky (OrderType.NORMAL, OrderType.RESTRICTED, OrderType.OPTIONAL)
- `name` [str] - Nazev jidla
- `price` [float] - Cena jidla
- `ordered` [bool] - Zda je jidlo objednano
- `alergens` [str] - Alergeny
- `forbiddenAlergens` [str] - Zakazane alergeny

### Enumy

**MealType** - Typy jidel:
- `SOUP` - Polevka
- `MAIN` - Hlavni jidlo

**OrderType** - Typy objednavek:
- `NORMAL` - Normalni objednavatelne jidlo
- `RESTRICTED` - Jidlo, ktere uz nelze objednat (prilis pozde - "CO")
- `OPTIONAL` - Jidlo, ktere obvykle neni objednavano, ale muze byt ("T")


### Menu class

#### Vlastnosti (Properties)
| vlastnost      | typ                  | popis                                                                          |
|----------------|----------------------|--------------------------------------------------------------------------------|
| `all`          | list                 | Default seznam - vsechna objednavatelna jidla (polevky + hlavni) podle dni    |
| `main_only`    | list                 | Pouze hlavni jidla podle dni                                                   |
| `soup_only`    | list                 | Pouze polevky podle dni                                                        |
| `complete`     | list                 | Kompletni seznam vcetne volitelnych jidel ("T") podle dni                      |
| `restricted`   | list                 | Jidla, ktera uz nelze objednat ("CO") podle dni                                |
| `optional`     | list                 | Jidla, ktera obvykle nejsou objednavana ("T") podle dni                        |

#### Metody
| funkce              | parametry                                                 | return type | popis                                                                                                              |
|---------------------|-----------------------------------------------------------|-------------|--------------------------------------------------------------------------------------------------------------------|
| `fetch()`           | None                                                      | Menu        | Ziska jidelnicek z API a zpracuje ho do vsech seznamu; vraci sam sebe                                             |
| `print()`           | None                                                      | None        | Vypise zformatovane default menu                                                                                   |
| `get_meals()`       | include_restricted=False, include_optional=False          | list        | Vrati vsechna jidla z prislusnych seznamu jako ploschy seznam s datem                                             |
| `get_main_meals()`  | include_restricted=False, include_optional=False          | list        | Vrati pouze hlavni jidla z prislusnych seznamu jako ploschy seznam s datem                                        |
| `get_soup_meals()`  | include_restricted=False, include_optional=False          | list        | Vrati pouze polevky z prislusnych seznamu jako ploschy seznam s datem                                             |
| `get_by_date()`     | date [str], include_restricted=True, include_optional=True | dict/None   | Vrati jidla pro konkretni datum (prohledava vybrane seznamy)                                                      |
| `get_by_id()`       | meal_id [int], include_restricted=True, include_optional=True | dict/None   | Vrati konkretni jidlo podle ID (prohledava vybrane seznamy)                                                       |
| `get_ordered_meals()` | include_restricted=True, include_optional=True          | list        | Vrati vsechna objednana jidla z vybranych seznamu                                                                 |
| `get_unordered_days()` | include_restricted=False, include_optional=False       | list        | Vrati seznam dnu (datumy), ve kterych neni objednano zadne jidlo                                                  |
| `filter_by_type()`  | meal_type [MealType], include_restricted=False, include_optional=False | list | Filtruje jidla z vybranych seznamu podle typu                                                                      |
| `is_ordered()`      | meal_id [int], include_restricted=True, include_optional=True | bool        | Zjisti, jestli je dane jidlo objednano (prohledava vybrane seznamy)                                               |
| `order_meals()`     | *meal_ids [int]                                           | None        | Objedna vice jidel podle meal_id                                                                                   |
| `cancel_meals()`    | *meal_ids [int]                                           | None        | Zrusi objednavky vice jidel podle meal_id                                                                          |

Menu objekt podporuje iteraci, indexovani a len() - vse pracuje s default seznamem `all`.


### StravaCZ class

| funkce              | parametry                                                 | return type | popis                                                                                                              |
|---------------------|-----------------------------------------------------------|-------------|--------------------------------------------------------------------------------------------------------------------|
| `__init__()` (=`StravaCZ()`)        | username=None, password=None, canteen_number=None         | None        | Inicializuje objekt StravaCZ a automaticky prihlasi uzivatele, pokud jsou vyplnene parametry username a password   |
| `login()`           | username [str], password [str], canteen_number=None [str] | User        | Prihlasi uzivatele pomoci uzivatelskeho jmena a hesla; pokud neni vyplnene cislo jidelny, automaticky pouzije 3753 |
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


### Pouziti AI

Na tento projekt byly do jiste miry vyuzity modely LLM, primarne na formatovani a dokumentaci kodu. V projektu nebyl ani nebude tolerovan cisty vibecoding.

