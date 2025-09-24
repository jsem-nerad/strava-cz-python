# Changelog

Vsechny vyznamne zmeny v tomto projektu budou dokumentovany v tomto souboru.

## [unreleased]
### Added
- Funkce `print_menu`, ktera vypise prehledne menu
- Moznost filtrace prazdnych obedu a polevek ve funkci `get_menu`

### Changed
- Zmena formatu hodnoty `date` ve funkci `_parse_menu_response`
- Mensi zmeny filtrovani ve funkci `_parse_menu_response`

## [0.1.2] 2025-9-18
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


## [0.1.1] - 2025-9-14
### Added
- repo_rules.md soubor, kam budu postupne zapisovat spravne zachazeni s repozitarem

### Fixed
- Opraveny print user objektu

### Changed
- Upravene README
- Zmena promenne `orders` na `menu`
- Zmena nazvu funkce `get_orders_list` na `get_menu_list`
- Zmena `menu` a `get_menu_list` v testech

## [0.1.0] - 2025-9-14
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
