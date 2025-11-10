# Changelog

Vsechny vyznamne zmeny v tomto projektu budou dokumentovany v tomto souboru.


## [unreleased]

## [0.2.0] 2025-11-06
### Added
- `Menu` class jako samostatna trida pro praci s jidelnickem
- `MealType` enum pro typy jidel (SOUP, MAIN, UNKNOWN)
- `OrderType` enum pro typy objednavek (NORMAL, RESTRICTED, OPTIONAL)
- Kazde jidlo nyni obsahuje `orderType` pole s informaci o typu objednavky
- `Menu.fetch()` pro ziskani jidelnicku z API (bez parametru)
- Vice pohledu na menu jako vlastnosti:
  - `Menu.all` - default seznam (polevky + hlavni, objednavatelne)
  - `Menu.main_only` - pouze hlavni jidla
  - `Menu.soup_only` - pouze polevky
  - `Menu.complete` - kompletni seznam vcetne volitelnych jidel
  - `Menu.restricted` - jidla "CO" (uz nelze objednat)
  - `Menu.optional` - jidla "T" (obvykle neobjednavana)
- Ploschy seznamy jidel s datem:
  - `Menu.get_meals()` - vsechna jidla jako ploschy seznam
  - `Menu.get_main_meals()` - pouze hlavni jidla
  - `Menu.get_soup_meals()` - pouze polevky
- `Menu.get_unordered_days()` - vrati seznam dnu bez objednavek
- Parametry `include_restricted` a `include_optional` pro vsechny metody vracejici jidla nebo dny:
  - Default False pro seznamove metody (get_meals, get_main_meals, get_soup_meals, filter_by_type, get_unordered_days)
  - Default True pro vyhledavaci metody (get_by_id, get_by_date, get_ordered_meals, is_ordered)
- Magic methods pro Menu: `__repr__`, `__str__`, `__iter__`, `__len__`, `__getitem__`
- Automaticke filtrovani podle omezeniObj hodnot:
  - "VP" jidla se preskakuji (zadna skola)
  - "CO" jidla jdou do `restricted` seznamu (OrderType.RESTRICTED)
  - "T" jidla jdou do `optional` seznamu (OrderType.OPTIONAL)
  - Prazdny string = objednavatelne jidla (OrderType.NORMAL)
- Inteligentni vyhledavani pres vybrane seznamy podle parametru include_restricted a include_optional
- `Menu.order_meals()` a `Menu.cancel_meals()` primo v Menu objektu
- Export `MealType`, `OrderType` a `Menu` z hlavniho modulu
- MIGRATION_GUIDE.md s detailnim navodem pro prechod na novou verzi

### Changed
- Menu je nyni samostatny objekt pristupny pres `strava.menu`
- Uzivatel nyni interaguje primo s Menu objektem misto volani metod na StravaCZ
- `fetch()` uz nema parametry include_soup a include_empty - vse se zpracovava automaticky
- `filter_by_type()` nyni pouziva `MealType` enum misto stringu
- `meal["type"]` je nyni primo `MealType` enum misto stringu
- `find_meal_by_id()` prejmenovano na `get_by_id()`
- `is_meal_ordered()` prejmenovano na `is_ordered()`
- Vyhledavaci metody nyni prohledavaji vsechny seznamy (all, restricted, optional)
- Zmena verze z 0.1.3 na 0.2.0

### Removed
- `StravaCZ.get_menu()` - pouzij `strava.menu.fetch()`
- `StravaCZ.print_menu()` - pouzij `strava.menu.print()`
- `StravaCZ.is_ordered()` - pouzij `strava.menu.is_ordered()`
- `StravaCZ.order_meals()` - pouzij `strava.menu.order_meals()`
- `StravaCZ.cancel_meals()` - pouzij `strava.menu.cancel_meals()`
- `StravaCZ._change_meal_order()` - presunuto do Menu class
- `StravaCZ._add_meal_to_order()` - presunuto do Menu class
- `StravaCZ._cancel_meal_order()` - presunuto do Menu class
- `StravaCZ._save_order()` - presunuto do Menu class
- `StravaCZ._parse_menu_response()` - presunuto do Menu class jako `_parse_menu_data()`
- `Menu.filter_by_price_range()` - odstranena funkce pro filtrovani podle ceny
- `Menu.get_all()` - nahrazeno vlastnosti `Menu.all`
- `Menu.processed_data` - nahrazeno vlastnostmi `all`, `main_only`, atd.
- `local_id` polozka z meal dat - odstranena nepotrebna hodnota
- Parametry `include_soup` a `include_empty` z `fetch()` - nyni se vse zpracovava automaticky

### Fixed
- Hodnota `ordered` u kazdeho dne
- Hodnota `price` u kazdeho jidla
- Overovani uspesnosti objednani/odhlaseni
- Filtrace prazdnych jidel, vcetne svatku a prazdnin
- Opravene filtrovani prazdnych jidel
- Automaticke preskoceni "VP" jidel (zadna skola)

## [0.1.3] 2025-09-24
### Added
- Funkce `print_menu`, ktera vypise prehledne menu
- Moznost filtrace prazdnych obedu a polevek ve funkci `get_menu`

### Changed
- Zmena formatu hodnoty `date` ve funkci `_parse_menu_response`
- Mensi zmeny filtrovani ve funkci `_parse_menu_response`

## [0.1.2] 2025-09-18
### Added
- Popisy funkci v kodu knihovny
- Vlastni error exceptions
- Jasne deklarovane datove typy

### Changed
- Lepe zorganizovany kod
- Funkce `get_menu_list` prejmenovana na `get_menu`
- `User` class presunut mimo `StravaCZ`

### Removed
- Funkce `order_meal`


## [0.1.1] - 2025-09-14
### Added
- repo_rules.md soubor, kam budu postupne zapisovat spravne zachazeni s repozitarem

### Fixed
- Opraveny print user objektu

### Changed
- Upravene README
- Zmena promenne `orders` na `menu`
- Zmena nazvu funkce `get_orders_list` na `get_menu_list`
- Zmena `menu` a `get_menu_list` v testech

## [0.1.0] - 2025-09-14
### Added
- Prvni verejna verze
- Zakladni funkcionalita pro praci se Strava.cz
- Prihlaseni uzivatele
- Objednavani jidel
- Kontrola stavu objednavek
- Hromadné objednavani
- Podpora Python 3.9+
- Automaticke testy s pytest
- GitHub Actions
- Publikovani na PyPI
