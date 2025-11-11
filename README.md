# Strava.cz Python API

High level API pro interakci s webovou aplikaci Strava.cz udelane v Pythonu ciste pomoci request knihovny.

Ve slozce [notes](https://github.com/jsem-nerad/strava-cz-python/tree/main/notes) muzete najit veskere moje poznatky, ktere jsem zjistil o internim fungovani aplikace Strava.cz.

## Features
- Prihlaseni/odhlaseni systemu
- Vypsani a filtrace jidelnicku
- Objednavani a odhlasovani jidel podle ID jidla
- Automaticke filtrovani jidel podle typu a objednatelnosti
- Vyhledavani jidel podle ID nebo data
- Ulozeni raw i zpracovanych dat z API
- Sledovani zustatku na uctu


## Usage

```bash
pip install strava-cz
```

```python
from strava_cz import StravaCZ, MealType, OrderType

# Vytvoreni objektu strava a prihlaseni uzivatele
strava = StravaCZ(
    username="your.username", 
    password="YourPassword123", 
    canteen_number="your canteen number"  # POVINNY parametr
    )

# Vypsani informaci o uzivateli
print(strava.user)
print(f"Zustatok: {strava.user.balance} Kč")

# Ziskani jidelnicku
strava.menu.fetch()
strava.menu.print()

# Pristup k jidelnicku podle dni
days = strava.menu.get_days()  # Default - vsechna objednavatelna jidla
print(f"Vsechny jidla: {len(days)} dni")

# Pristup k jidlum jako ploschy seznam
meals = strava.menu.get_meals()  # Vsechna jidla jako ploschy seznam
main_meals = strava.menu.get_meals(meal_types=[MealType.MAIN])  # Pouze hlavni jidla
soup_meals = strava.menu.get_meals(meal_types=[MealType.SOUP])  # Pouze polevky

# Vcetne volitelnych jidel
complete = strava.menu.get_days(
    order_types=[OrderType.NORMAL, OrderType.OPTIONAL]
)

# Iterace pres menu (default seznam)
for day in strava.menu:
    print(f"Datum: {day['date']}, Pocet jidel: {len(day['meals'])}")

# Zjisti, jestli je jidlo s meal_id 4 objednano (True/False)
print(strava.menu.is_ordered(4))

# Objedna jidla s meal_id 3 a 6
# Automaticky detekuje duplicity a kontroluje typ jidla
strava.menu.order_meals(3, 6)

# Objednani s pokrocilymi parametry
strava.menu.order_meals(
    3, 6, 
    continue_on_error=True,      # Pokracuj i pri chybach
    strict_duplicates=False       # Pouze varuj pri duplikatech
)

# Ziskani vsech objednanych jidel
ordered = strava.menu.get_meals(ordered=True)

# Ziskani jidelnicku podle konkretniho data (prohledava vsechny seznamy)
today_menu = strava.menu.get_by_date("2025-11-04")

# Zrus objednavky
strava.menu.cancel_meals(3, 6)

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
| `raw_data`     | dict                 | Surova odpoved z API bez zpracovani                                            |

#### Hlavni Metody
| funkce              | parametry                                                 | return type | popis                                                                                                              |
|---------------------|-----------------------------------------------------------|-------------|--------------------------------------------------------------------------------------------------------------------|
| `fetch()`           | None                                                      | Menu        | Ziska jidelnicek z API a zpracuje ho; vraci sam sebe                                                              |
| `print()`           | None                                                      | None        | Vypise zformatovane menu (default: pouze objednavatelna jidla)                                                    |
| `get_days()`        | meal_types=None, order_types=None, ordered=None           | list        | Vrati jidla seskupena podle dni: `[{date, ordered, meals: [...]}]`                                                |
| `get_meals()`       | meal_types=None, order_types=None, ordered=None           | list        | Vrati vsechna jidla jako ploschy seznam: `[{...meal}]`                                                            |
| `order_meals()`     | *meal_ids, continue_on_error=False, strict_duplicates=False | None      | Objedna vice jidel; detekuje duplicity a kontroluje typy                                                          |
| `cancel_meals()`    | *meal_ids, continue_on_error=False                        | None        | Zrusi objednavky vice jidel                                                                                        |

**Parametry filtrovani:**
- `meal_types` - Seznam typu jidel k ziskani (napr. `[MealType.SOUP, MealType.MAIN]`). None = vsechny typy
- `order_types` - Seznam typu objednavek k ziskani (napr. `[OrderType.NORMAL, OrderType.OPTIONAL]`). None = pouze `[OrderType.NORMAL]`
- `ordered` - Filtrovani podle stavu objednavky: `True` = pouze objednane, `False` = pouze neobjednane, `None` = vse

**Priklady:**
```python
# Vsechna objednavatelna jidla podle dni (default)
menu.get_days()

# Vsechna jidla jako flat seznam
menu.get_meals()

# Pouze polevky
menu.get_meals(meal_types=[MealType.SOUP])

# Pouze objednana jidla
menu.get_meals(ordered=True)

# Vcetne omezenych a volitelnych jidel
menu.get_days(order_types=[OrderType.NORMAL, OrderType.RESTRICTED, OrderType.OPTIONAL])
```

#### Pomocne Metody
| funkce              | parametry                                                 | return type | popis                                                                                                              |
|---------------------|-----------------------------------------------------------|-------------|--------------------------------------------------------------------------------------------------------------------|
| `get_by_date()`     | date [str]                                                | dict/None   | Vrati jidla pro konkretni datum (prohledava vsechny typy objednavek)                                              |
| `get_by_id()`       | meal_id [int]                                             | dict/None   | Vrati konkretni jidlo podle ID (prohledava vsechny typy objednavek)                                               |
| `is_ordered()`      | meal_id [int]                                             | bool        | Zjisti, jestli je dane jidlo objednano (prohledava vsechny typy objednavek)                                       |

#### Parametry objednavani
- `continue_on_error` - Pokud True, pokracuje pri chybach a sbirá je; pokud False (default), zastavi pri prvni chybe
- `strict_duplicates` - Pokud True, vyhodit chybu pri vice jidlech ze stejneho dne; pokud False (default), pouze varuje a objedna prvni

**Poznamka:** Menu objekt podporuje iteraci, indexovani a len() - vse pracuje s defaultnim seznamem objednatelnych jidel.

### Exceptions

Knihovna nabizi specialni vyjimky pro ruzne chybove stavy:

| Exception                    | Popis                                                          |
|------------------------------|----------------------------------------------------------------|
| `StravaAPIError`             | Zakladni vyjimka pro vsechny API chyby                         |
| `AuthenticationError`        | Chyba pri prihlaseni nebo pokud uzivatel neni prihlasen       |
| `InsufficientBalanceError`   | Nedostatecny zustatek na uctu pro objednani jidla              |
| `InvalidMealTypeError`       | Pokus o objednani/zruseni jidla, ktere nelze modifikovat (polevka) |
| `DuplicateMealError`         | Pokus o objednani vice jidel ze stejneho dne (strict mode)    |

**Priklad pouziti:**
```python
from strava_cz import StravaCZ, InvalidMealTypeError, InsufficientBalanceError, DuplicateMealError

strava = StravaCZ("user", "pass", "1234")
strava.menu.fetch()

try:
    # Pokus o objednani polevky (vyhodit InvalidMealTypeError)
    strava.menu.order_meals(75)  # ID polevky
except InvalidMealTypeError as e:
    print(f"Chyba: {e}")

try:
    # Pokus o objednani vice jidel ze stejneho dne
    strava.menu.order_meals(1, 2, strict_duplicates=True)
except DuplicateMealError as e:
    print(f"Duplicita: {e}")

try:
    # Pokus o objednani draheho jidla
    strava.menu.order_meals(100)
except InsufficientBalanceError as e:
    print(f"Nedostatecny zustatek: {e}")
    print(f"Aktualni zustatek: {strava.user.balance} Kč")
```


### StravaCZ class

| funkce              | parametry                                                 | return type | popis                                                                                                              |
|---------------------|-----------------------------------------------------------|-------------|--------------------------------------------------------------------------------------------------------------------|
| `__init__()` (=`StravaCZ()`)        | username=None, password=None, canteen_number=None         | None        | Inicializuje objekt StravaCZ a automaticky prihlasi uzivatele, pokud jsou vyplnene vsechny tri parametry           |
| `login()`           | username [str], password [str], canteen_number [str]      | User        | Prihlasi uzivatele pomoci uzivatelskeho jmena, hesla a cisla jidelny (vsechny parametry jsou povinne)              |
| `logout()`          | None                                                      | bool        | Odhlasi uzivatele                                                                                                  |


## to-do

- [x] Nahrat jako knihovnu na PyPi
- [x] Lepe zorganizovat kod
- [x] Lepsi datum format
- [x] Moznost detailnejsi filtrace jidelnicku
- [x] Kontrola stavu po objednani
- [x] Filtrace dnu, ktere nejdou objednat
- [x] Lepsi testing
- [x] Balance check pred objednanim
- [x] Detekce a prevence duplicitnich objednavek
- [x] Kontrola typu jidla pri objednavani
- [ ] Lepe zdokumentovat pouziti
- [ ] Rate limiting
- [ ] Zrychleni interakce
- [ ] Debug/Log mode


## Known bugs



## Co bude dal?

Planuji udelat aplikaci, ktera bude uzivateli automaticky objednavat obedy podle jeho preferenci.

Prosim, nepouzivejte tuto aplikaci k nekalym ucelum. Pouzivejte ji pouze s dobrymi zamery.


## Pomoz mi pls

Nasel jsi chybu nebo mas navrh na zlepseni? Skvele! Vytvor prosim [bug report](https://github.com/jsem-nerad/strava-cz-python/issues/new?labels=bug) nebo [feature request](https://github.com/jsem-nerad/strava-cz-python/issues/new?labels=enhancement), hodne mi tim muzes pomoct.

Udelal jsi sam nejake zlepseni? Jeste lepsi! Kazdy pull request je vitan.


### Pouziti AI

Na tento projekt byly do jiste miry vyuzity modely LLM, primarne na formatovani a dokumentaci kodu. V projektu nebyl ani nebude tolerovan cisty vibecoding.

Zaznamy konkretniho pouziti:

- Kontrola syntaxe kodu a repetetivni upravy detailu
- Vytvoreni testu
- Vytvoreni example.py
- Uprava a ladeni README
- Obcasny zapis do CHANGELOGu
- Vytvoreni MIGRATION GUIDE

