# Changelog

Všechny významné změny v tomto projektu budou dokumentovány v tomto souboru.


## [unreleased]

Čísla jídel neplatí napříč přihlášeními, a příkaz `strava-cz` je proto přestal brát:
jídlo teď určuje den a místo v jídelníčku. **Mění se tím rozhraní příkazu i jeho JSON.**
Knihovna zůstává zpětně kompatibilní.

### Fixed
- **`strava-cz order` a `cancel` mohly zasáhnout jiné jídlo, než jste vybrali.** Jídelna
  čísluje celý jídelníček (`veta`) při každém přihlášení znovu a každé spuštění příkazu
  je nové přihlášení. Číslo přečtené z `strava-cz menu` tak v dalším běhu mohlo být
  polévka, takže přišlo odmítnutí s důvodem, který k vybranému jídlu nepatřil, nebo
  objednatelné jídlo v jiný den, které se objednalo s návratovým kódem 0. Na živém účtu
  to bylo vidět 5. 11. 2026: stejný jídelníček chodí v několika číslováních a uvnitř
  jednoho přihlášení se číslování nemění. Starší poznámka, že se čísla mění jen se změnou
  jídelníčku, neplatila.
- Kontrola po zápisu hledá jídlo podle dne a místa v jídelníčku, takže odpověď nemůže
  přijít z řádku jiného jídla. Pokud místo z jídelníčku zmizelo, zápis se hlásí jako
  nepotvrzený.
- **Opakovaný pokus po neúspěšné objednávce mohl v knihovně objednat jiné jídlo v jiný
  den.** Jídelna čísluje jídelníček znovu nejen při přihlášení, ale i při resetu session
  (`nactiVlastnostiPA`), a ten knihovna volá při vracení změn zpátky. Když selhalo
  zaškrtnutí všech jídel a nebo následné načtení, zůstala v paměti stará čísla a další
  `order_meals()` v tomtéž přihlášení je poslalo dál. Reset teď vždycky znovu načte
  jídelníček, a když se to nepovede, jídelníček se zahodí. Číslo přečtené před resetem se
  odmítne s `MenuNotFetchedError`, dokud nezavoláte `fetch()`; klíč funguje dál.
- **Selhání při zápisu už nelže o tom, co je na účtu.** Vypršený čas u `saveOrders` nic
  neříká o tom, jestli se uložení povedlo, a knihovna přesto hlásila jen „timed out“, i když
  objednávka na účtu byla. Timeout při kontrole po úspěšném uložení vypadal jako neúspěšná
  objednávka. Teď se po neúspěšném uložení přečte stav znovu: když se změna uložila, je to
  úspěch, když ne, chyba říká „Nothing was saved“. Když to zjistit nejde, přijde nová
  výjimka `OrderNotConfirmedError` s atributy `changed` a `unconfirmed`, a příkaz skončí
  kódem 1 a napíše, co je nepotvrzené, s `--json` i v polích `error.unconfirmed` a
  `error.changed`. S `--continue-on-error` se jídlo, u kterého se ztratila odpověď na
  zaškrtnutí a které se přesto uložilo, hlásí jako změněné, ne jako selhané.
- **Kontrola po zápisu nic nedokazovala.** Každé přihlášení pracuje s vlastní kopií
  objednávek a zaškrtnuté jídlo je v ní vidět ještě před uložením, takže ji uložení, které
  nic neudělalo, projde (na živém účtu 5. 11. 2026). `strava-cz order` a `cancel` teď
  ověřují výsledek proti záznamům jídelny, stejně jako knihovna s `verify_saved=True`.
- **S `--continue-on-error` byl návratový kód vždycky 4**, ať se stalo cokoliv. Nedostatek
  peněz teď končí kódem 5 a selhání sítě nebo jídelny kódem 1, obojí i vedle odmítnutého
  dne. Odmítnuté jídlo zůstává 4. Skončená session přeruší celou dávku, nic neuloží a
  skončí kódem 3, i s `continue_on_error=True` v knihovně.
- **`--dry-run` tvrdil něco jiného, než co pak skutečné volání udělalo.** Bez
  `--continue-on-error` jedno odmítnuté jídlo zastaví celou dávku, ale `--dry-run` dál
  vypisoval, co by se objednalo. Stejně tak u `--strict-duplicates`. Teď je `would_change`
  v takovém případě prázdné, zadržená jídla jsou v novém poli `blocked` a návratový kód
  sedí. V JSONu bylo `ok: true` i u odmítnutého jídla s kódem 4. `balance_change` u výměny
  jídla počítá rozdíl cen, ne celou cenu nového jídla. Nové pole `balance_after` říká, kolik
  by na účtu zůstalo, a když by to bylo pod nulou, přijde varování: jídelna v takovém případě
  může objednávku odmítnout (na živém účtu s nulovým zůstatkem kódem 35), ale limit účtu
  `--dry-run` nezná, takže návratový kód zůstává 0.
- `order` s objednaným jídlem a jeho alternativou na stejný den jídlo vyměnil a přitom
  o tom objednaném hlásil „already ordered“, což už po běhu neplatilo. Objednané jídlo teď
  své místo drží, alternativa se přeskočí s varováním a s `--strict-duplicates` je to chyba.
- **Vypršená session teď opravdu je `AuthenticationError`**, jak slibuje dokumentace.
  Jídelna na ni odpovídá číslem chyby 15, které knihovna neznala, takže šla jen obecná
  `StravaAPIError` a příkaz končil kódem 1 místo 3 (na živém účtu 5. 11. 2026).
- `logout()` u skončené session nezvládl odhlášení a klient pak `login()` odmítal, protože
  se pořád tvářil přihlášeně. Po `logout()` je teď klient odhlášený vždycky, a odhlášení ze
  session, která už skončila, není chyba.
- Když reset selže, udělá se dodatečně před dalším `fetch()`. Jinak by se zaškrtnuté a
  neuložené jídlo tvářilo jako objednané a další uložení by ho opravdu objednalo.

### Changed
- `examples/example.py` ve výchozím stavu jen čte. Dřív po spuštění objednal první tři dny
  a pak zrušil všechny objednávky na účtu, včetně těch cizích, aniž by na to cokoliv
  upozornilo. Zapisuje až s `STRAVA_OPRAVDU_ZAPISOVAT=1`.
- **Id v příkazu `strava-cz` je den a místo v jídelníčku**, např. `2026-11-09:O2`.
  Vypisují ho `menu`, `ordered` a `--dry-run`, je v poli `id` v JSONu (teď řetězec,
  stejně jako v `changed`, `unchanged`, `failed` a `meal_id`) a berou ho `order` a
  `cancel`. Holé číslo se odmítne s návratovým kódem 2 ještě před přihlášením, s `--json`
  i jako JSON.
- `--dry-run` s `--json` vypisuje v poli `meals` i jídla, která by se objednala, takže
  jde zkontrolovat název.
- Nejužší tabulka má 57 sloupců místo 48, aby se delší id vešlo vedle celé ceny. Na užším
  terminálu se řádky zalomí.

### Added
- `order_meals()` a `cancel_meals()` berou `verify_saved=True`, které výsledek ověří proti
  záznamům jídelny. Stojí jeden požadavek navíc a přečísluje jídelníček, takže `Meal.id`
  přečtená předtím přestanou platit do dalšího `fetch()`, klíče platí dál. Výchozí chování
  se proto nemění.
- `Meal.key`, `Meal.kind_code` a `Menu.get_by_key()`. `order_meals()`, `cancel_meals()`
  a `is_ordered()` berou vedle `Meal.id` i klíč a `OrderResult` hlásí jídla tak, jak je
  zadal volající. `in` na jídelníčku bere obojí a jedno jídlo zadané dvakrát různě se
  bere jako jedno. Klíč, který by sdílela dvě jídla, nebo jídlo bez kódu místa se berou
  jako nenalezené a ohlásí je `Menu.parse_warnings`.

## [0.4.0] 2026-09-01

Přibyl nástroj pro příkazovou řádku a profily. Knihovna sama je zpětně kompatibilní
s 0.3.0.

### Added
- **Příkaz `strava-cz`** (a `python -m strava_cz`), který zpřístupňuje všechno, co umí
  knihovna: `menu`, `ordered`, `order`, `cancel`, `balance`, `account`, `raw` a `profile`.
  Výchozí výpis je pro lidi, `--format json` (zkratka `--json`) vypíše na standardní
  výstup jeden objekt pro další zpracování. Nepotřebuje nic mimo standardní knihovnu.
- `--dry-run` u `order` a `cancel` spočítá, co by se změnilo, a **neodešle nic**.
  Pozná i jídla, která už jsou objednaná, a dvě jídla soupeřící o stejné místo.
- Návratové kódy 0–6, aby shell rozeznal odmítnuté přihlášení od neobjednatelného
  jídla nebo od prázdného konta.
- Filtry jídelníčku jako přepínače: `--from`, `--to`, `--today`, `--tomorrow`,
  `--week`, `--next-week`, `--type`, `--orderable`, `--ordered`, `--auto-ordered`,
  `--include-no-school` a `--allergens`.
- **Profily**: `strava-cz profile add|list|show|default|remove`. Uživatelské jméno
  a číslo jídelny se ukládají do `$XDG_CONFIG_HOME/strava-cz/profiles.json` (soubor
  `0600`, složka `0700`, zápis atomický). **Heslo se do souboru nezapisuje otevřeným
  textem** — jde do klíčenky systému, nebo se zašifruje, nebo se čte z prostředí či se
  na něj program ptá. Otevřeným textem se uloží jen po výslovném `--secret file`, a i
  tak s varováním.
- **`--secret encrypted`** pro stroje bez klíčenky, typicky servery. Heslo se zašifruje
  algoritmem AES-256-GCM klíčem, který z heslové fráze odvodí scrypt (n=2^15, r=8, p=1);
  sůl, nonce i parametry se ukládají do záznamu, takže pozdější zvýšení náročnosti
  starší profily nezneplatní. GCM záznam ověřuje, takže poškozený soubor skončí
  srozumitelnou chybou. Heslová fráze se bere z `$STRAVA_CZ_PASSPHRASE_<JMENO>`,
  `$STRAVA_CZ_PASSPHRASE`, nebo se na ni program zeptá.
- **`--secret auto` jako výchozí**: klíčenka, když nějaká funguje, jinak `encrypted`.
  Heslo si tedy zapamatuje i server bez grafického prostředí, aniž by se kamkoliv
  ukládalo otevřeným textem. Zvolená cesta se vypíše a zapíše do profilu.
- Nepovinná závislost `cryptography` v extra `[cli]`. Na Linuxu ji stejně už instaluje
  `keyring` přes `SecretStorage`.
- `StravaCZ.from_profile()`, `Profile`, `ProfileStore` a `SecretSource` pro použití
  profilů přímo z Pythonu.
- Výjimky `ProfileError`, `ProfileNotFoundError`, `KeyringUnavailableError`
  a `EncryptionUnavailableError`.
- Nepovinný extra `[cli]` s balíčky `keyring` a `cryptography`.

### Changed
- Barvy se vypisují jen na terminál. V rouře, v souboru, v cronu a při nastavené
  proměnné `NO_COLOR` se vypnou samy; `--color always` je vynutí.

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
