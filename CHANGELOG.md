# Changelog

Všechny významné změny v tomto projektu budou dokumentovány v tomto souboru.


## [unreleased]

## [0.3.0] 2026-08-31

Velká oprava a přepis. Verze 0.3.0 obsahuje breaking changes: jídla a dny jsou nově
plnohodnotné objekty místo slovníků a filtrování má jiné výchozí chování.

### Fixed
- **Objednatelnost se určuje ze správných polí.** Knihovna četla jen denní kód
  `omezeniObj.den` a ignorovala `obj` a `zm`, která platí pro konkrétní jídlo.
  Kvůli tomu se dny s kódem `"T"` tvářily jako neobjednatelné a mizely z výpisu
  (na ověřovacím účtu 4 z 20 použitelných dnů), a u jídelníčku, kde měl `den`
  hodnotu na každém jídle, vracelo `get_days()` prázdný seznam.
- Polévky se hlásily jako běžně objednatelné, přestože je API označuje `obj: "I"`.
  Objednání blokovalo jen natvrdo zadané pravidlo „jde objednat pouze hlavní jídlo“,
  které je v jídelnách s objednatelnou polévkou špatně.
- `user.balance` byl po přihlášení `str` a až po objednávce `float`, takže s ním
  nešlo počítat. Nově je to vždy `float`.
- `cancel_meals()` s neznámým ID hlásilo úspěch, a přesto odesílalo `saveOrders`.
  Nyní vyhodí `MealNotFoundError`.
- `order_meals()` a `cancel_meals()` odesílaly `saveOrders`, i když nebylo co měnit.
- S `continue_on_error=True` se chyby posbíraly, ale výjimka stejně vyletěla.
  Nově se vrací `OrderResult` a nevyhazuje se nic.
- Chybějící pole v odpovědi API shodilo celý `fetch()` s `KeyError`.
- Požadavky neměly žádný timeout, takže zaseknuté spojení viselo donekonečna.
- Vytvoření klienta sahalo na síť už v `__init__`.
- Odpověď, která nebyla JSON, skončila výjimkou `json.JSONDecodeError` místo chyby
  knihovny.
- Ručně nastavená hlavička `Accept-Encoding` slibovala kodeky, které klient nemusí
  umět rozbalit.
- `logout()` nahrazoval objekty `user` a `menu`, takže dřív získané reference
  zůstaly viset na starém stavu. Nyní se resetují na místě.
- Jídla jiného typu než polévka a oběd se tiše zahazovala.
- Při každém běhu CI posílaly tři testy skutečné HTTP požadavky na app.strava.cz.

### Added
- Datové třídy `Meal`, `Day`, `Allergen` a `OrderResult` s typovými anotacemi
- Enum `Restriction`, který vysvětluje, proč jídlo nelze objednat
- Enum `DayStatus` a `Day.auto_ordered` pro dny, na které jídelna neobjednává
  automaticky (kód `den: "T"`). Takový den jde objednat ručně jako každý jiný, jen se
  neobjedná sám. Ověřeno na živém účtu: `"T"` se za 32 dnů objevilo jen na pátcích a
  právě ty jako jediné zůstaly v období automatického objednávání prázdné.
- Filtr `auto_ordered` v `get_days()` a `get_meals()`
- `Meal.can_order`, `Meal.can_cancel`, `Meal.deadline`, `Meal.raw`
- `Day.no_school`, `Day.orderable`, `Day.ordered`
- Filtry `orderable`, `date_from`, `date_to` a `include_no_school`
- `StravaCZ` je context manager a má metodu `close()`
- Nastavitelný `timeout`, `retries`, `base_url`, `language` a vlastní `httpx.Client`
- Nové výjimky `StravaError`, `NotLoggedInError`, `MealNotFoundError`,
  `MealNotOrderableError` a `MenuNotFetchedError`
- `StravaAPIError` nese `.code`, `.status_code` a `.payload`; chybové kódy API
  se mapují na konkrétní výjimky
- `Menu.parse_warnings` se záznamy o řádcích, které nešlo zpracovat
- Soubor `py.typed`, takže typy vidí i uživatelé knihovny
- 143 testů nad nahranými odpověďmi z reálného API (95 % pokrytí); testy mají
  zakázaný přístup k síti

### Changed
- **Přechod z `requests` na `httpx`** kvůli výchozím timeoutům a opakování spojení
- Jídla a dny jsou objekty s atributy místo slovníků: `meal.name` místo `meal["name"]`
- `meal.date` je `datetime.date` místo řetězce
- Přejmenováno: `alergens` → `allergens`, `forbiddenAlergens` odstraněno,
  `orderType` → `order_restriction` a `can_order`
- `OrderType` nahrazen enumem `Restriction`
- `get_days()` a `get_meals()` mají nově pojmenované parametry a **nic neskrývají**;
  dřívější výchozí chování vracelo jen `OrderType.NORMAL`
- Práce s jídelníčkem před `fetch()` vyhodí `MenuNotFetchedError` místo prázdného seznamu
- `is_ordered()` vyhodí `MealNotFoundError` místo `False` u neznámého ID
- `order_meals()` a `cancel_meals()` vracejí `OrderResult` místo `None`
- Detekce duplicit rozlišuje den *a* typ jídla, ne jen den
- `InvalidMealTypeError` nahrazen `MealNotOrderableError`
- Heslo se po přihlášení neuchovává
- Minimální verze Pythonu je 3.10
- `black` a `flake8` nahrazeny nástrojem `ruff`

### Removed
- `MIGRATION_GUIDE.md` a migrační poznámky k verzi 0.2.0
- `strava_cz.main` — kód je rozdělený do `client`, `menu`, `models`, `parser`
  a `exceptions`
- `OrderType`, `InvalidMealTypeError`, `User.password`

## [0.2.0] 2025-11-11
### Added
- `Menu` class jako samostatna trida pro praci s jidelnickem
- `MealType` enum pro typy jidel (SOUP, MAIN, UNKNOWN)
- `OrderType` enum pro typy objednavek (NORMAL, RESTRICTED, OPTIONAL)
- `InvalidMealTypeError` exception pro pokusy o objednani/zruseni jidel, ktera nelze modifikovat (polevky)
- `DuplicateMealError` exception pro pokusy o objednani vice jidel ze stejneho dne ve strict modu
- `InsufficientBalanceError` exception pro nedostatecny zustatek na uctu
- Kazde jidlo nyni obsahuje `orderType` pole s informaci o typu objednavky
- `Menu.fetch()` pro ziskani jidelnicku z API (bez parametru)
- Dve hlavni metody pro ziskani dat:
  - `Menu.get_days(meal_types, order_types, ordered)` - jidla seskupena podle dni
  - `Menu.get_meals(meal_types, order_types, ordered)` - vsechna jidla jako flat seznam
- Filtrovani pomoci parametru:
  - `meal_types` - seznam typu jidel k ziskani (napr. `[MealType.SOUP, MealType.MAIN]`)
  - `order_types` - seznam typu objednavek (napr. `[OrderType.NORMAL, OrderType.RESTRICTED]`)
  - `ordered` - filtrovani podle stavu objednavky (True = objednano / False = neobjednano / None = oboji)
- Magic metody pro Menu: `__repr__`, `__str__`, `__iter__`, `__len__`, `__getitem__`
- Automaticke filtrovani podle omezeniObj hodnot na typ moznosti objednani:
  - "VP" jidla se preskakuji (zadna skola tento den)
  - "CO" jidla maji OrderType.RESTRICTED (jiz nejde zmenit)
  - "T" jidla maji OrderType.OPTIONAL (normalne neobjednavano)
  - Prazdny string = OrderType.NORMAL (objednavatelne)
- Pomocne metody: `get_by_id()`, `get_by_date()`, `is_ordered()` (prohledavaji vsechny typy automaticky)
- `Menu.order_meals()` a `Menu.cancel_meals()` primo v Menu objektu
- Export `MealType`, `OrderType` a `Menu` z hlavniho modulu
- MIGRATION_GUIDE.md s detailnim navodem pro prechod na novou verzi
- Automaticka detekce duplicitnich jidel ze stejneho dne pri objednavani
- Parametr `strict_duplicates` v `order_meals()` - kontroluje duplikaty (defaultne: False = pouze varuje)
- Parametr `continue_on_error` v `order_meals()` a `cancel_meals()` - pokracuje, i kdyz se naskytne chyba (default: False = zastavi po chybe a zrusi objednavani)
- Automaticka kontrola typu jidla - pouze hlavni jidla (MAIN) lze objednavat/rusit
- Automaticke sledovani zustatku na uctu po kazde operaci
- Automaticke ruseni zmen pri chybe pri objednavani (rollback pomoci `nactiVlastnostiPA` endpointu)
- Prevence duplicitnich chybovych hlaseni - kazde jidlo je ohlaseno pouze jednou
- Kompletni testovaci pokryti pro vsechny nove funkce (16 testu, 75% coverage)

### Changed
- Menu je nyni samostatny objekt pristupny pres `strava.menu`
- Uzivatel nyni interaguje primo s Menu objektem misto volani metod na StravaCZ
- `fetch()` uz nema parametry include_soup a include_empty - vse se zpracovava automaticky
- `meal["type"]` je nyni primo `MealType` enum misto stringu
- `meal["orderType"]` je enum typ objednavky (NORMAL/RESTRICTED/OPTIONAL)
- `find_meal_by_id()` prejmenovano na `get_by_id()`
- `is_meal_ordered()` prejmenovano na `is_ordered()`
- Vyhledavaci metody nyni prohledavaji vsechny typy objednavek automaticky
- Filtrovani pomoci parametru misto specializovanych metod nebo vlastnosti
- Defaultni chovani: `order_types=None` vraci pouze `OrderType.NORMAL` (objednavatelne jidla)
- Magic metoda `__str__` vraci format `Menu(days=X, meals=Y)`
- **`canteen_number` je nyni povinny parametr** - odstranena default hodnota "3753" 
- `order_meals()` nyni automaticky detekuje a hlasi duplicitni jidla ze stejneho dne
- Default chovani pri duplicitach: objedna prvni jidlo, varuje o dalsich
- Zpracovani chyb: defaultne zastavi pri prvni chybe a zrusi vsechny zmeny
- Balance tracking: `user.balance` se aktualizuje po kazdé operaci z API odpovedi

### Removed
- `StravaCZ.get_menu()` - nahrazeno `strava.menu.fetch()`
- `StravaCZ.print_menu()` - nahrazeno `strava.menu.print()`
- `StravaCZ.is_ordered()` - nahrazeno `strava.menu.is_ordered()`
- `StravaCZ.order_meals()` - nahrazeno `strava.menu.order_meals()`
- `StravaCZ.cancel_meals()` - nahrazeno `strava.menu.cancel_meals()`
- `StravaCZ.filter_by_price_range()` - odstraneno filtrovani podle ceny
- Pole `local_id` z jidel - nepouzivane
- `StravaCZ.cancel_meals()` - nahrazeno `strava.menu.cancel_meals()`
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
- Automaticke preskoceni "VP" jidel
- Duplicitni chybove zpravy pri neuspesnem objednani
- Chybejici validace typu jidla (zabraneno objednavani polevek)
- Chybejici kontrola zustatku pred objednanim
- Chybejici rollback mechanismus pri chybach

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
