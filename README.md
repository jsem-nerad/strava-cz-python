# Strava.cz Python API

Python knihovna pro objednávání jídel ve školních jídelnách, které používají systém
**[Strava.cz](https://app.strava.cz)**. Komunikuje přímo s interním JSON API webové
aplikace, takže nepotřebuje prohlížeč ani parsování HTML.

```bash
pip install strava-cz
```

Ve složce [notes](notes/) najdete všechny moje poznatky o vnitřním fungování API
Strava.cz. Kompletní **dokumentace** je na
**[GitHub Wiki](https://github.com/jsem-nerad/strava-cz-python/wiki)**.

## Co knihovna umí

- Přihlášení a odhlášení, včetně správy session
- Načtení a filtrování jídelníčku podle typu jídla, data a objednatelnosti
- Objednávání a rušení jídel v jedné transakci, s ověřením výsledku
- Rozpoznání, proč konkrétní jídlo objednat nelze (uzávěrka, prázdniny, ...)
- Sledování zůstatku na účtu
- Plné typové anotace (`py.typed`), takže vám editor napovídá

## Rychlý start

```python
from strava_cz import StravaCZ

with StravaCZ("vase.jmeno", "VaseHeslo123", "3753") as strava:
    print(strava.user)

    strava.menu.fetch()
    strava.menu.print()

    # Objedná oběd s ID 5 a 9
    strava.menu.order_meals(5, 9)
```

`with` blok se sám postará o odhlášení a uzavření spojení. Pokud ho nepoužijete,
zavolejte na konci `strava.logout()` sami.

> **ID jídla** je unikátní číslo jídla v rámci právě publikovaného jídelníčku
> (v API pole `veta`). **Není trvale vázané na konkrétní jídlo** a mění se s každou
> změnou jídelníčku, takže ho vždy berte z čerstvě načteného jídelníčku.

## Práce s jídelníčkem

```python
from strava_cz import StravaCZ, MealType

strava = StravaCZ("vase.jmeno", "VaseHeslo123", "3753")
strava.menu.fetch()

# Dny a jídla
dny = strava.menu.get_days()          # seznam objektů Day
jidla = strava.menu.get_meals()       # plochý seznam objektů Meal

# Filtrování - všechny parametry jdou kombinovat
obedy = strava.menu.get_meals(meal_types=[MealType.MAIN], orderable=True)
tento_tyden = strava.menu.get_days(date_from="2026-09-07", date_to="2026-09-11")
objednane = strava.menu.get_meals(ordered=True)

# Vyhledávání
den = strava.menu.get_by_date("2026-09-07")
jidlo = strava.menu.get_by_id(9)
print(strava.menu.is_ordered(9))

# Iterace, len() a indexování fungují přímo na menu
for den in strava.menu:
    print(den.date, [j.name for j in den.meals])
```

Ve výchozím nastavení se **nic neskrývá** — vrátí se každé publikované jídlo
a u každého se dozvíte, jestli jde objednat. Jedinou výjimkou jsou dny, kdy se
nevaří; ty se přidají pomocí `include_no_school=True`.

### Objekt `Meal`

| atribut | typ | popis |
|---|---|---|
| `id` | `int` | Identifikátor pro objednávání (API pole `veta`) |
| `date` | `datetime.date` | Den, kdy se jídlo vydává |
| `type` | `MealType` | `SOUP`, `MAIN` nebo `UNKNOWN` |
| `variant` | `str` | Označení, které jídlu dává jídelna, například `"Oběd 1"` |
| `name` | `str` | Název jídla |
| `price` | `float` | Cena |
| `ordered` | `bool` | Jestli je jídlo objednané |
| `can_order` | `bool` | Jestli ho lze právě teď objednat |
| `can_cancel` | `bool` | Jestli lze objednávku zrušit |
| `order_restriction` | `Restriction` | Proč objednat nelze |
| `cancel_restriction` | `Restriction` | Proč zrušit nelze |
| `allergens` | `tuple[Allergen, ...]` | Alergeny, dvojice `(kód, název)` |
| `deadline` | `datetime \| None` | Dokdy lze jídlo objednat |
| `raw` | `dict` | Nezpracovaný záznam z API |

### Objekt `Day`

| atribut | typ | popis |
|---|---|---|
| `date` | `datetime.date` | Datum |
| `meals` | `tuple[Meal, ...]` | Jídla toho dne |
| `ordered` | `bool` | Jestli je aspoň jedno jídlo objednané |
| `orderable` | `tuple[Meal, ...]` | Jídla, která lze objednat |
| `no_school` | `bool` | Jestli se ten den nevaří |
| `auto_ordered` | `bool` | Jestli na ten den jídelna objednává automaticky |
| `status` | `DayStatus` | Stav celého dne |
| `day_code` | `str` | Surový kód dne z API (`omezeniObj.den`) |

### Enumy

**`MealType`** — `SOUP`, `MAIN`, `UNKNOWN`. Odvozuje se z krátkého kódu `druh`
(`"PO"`, `"O1"`, ...), který je stabilnější než zobrazovaný text.

**`Restriction`** — proč jídelna nedovolí jídlo objednat nebo změnit:

| hodnota | význam |
|---|---|
| `NONE` | Bez omezení, jídlo lze objednat |
| `CLOSED` | Uzávěrka objednávek na tento den už proběhla |
| `UNAVAILABLE` | Položku nelze objednat samostatně (typicky polévka) |
| `NO_SCHOOL` | Jídelna ten den nevaří |
| `UNKNOWN` | Jídelna vrátila kód, který knihovna nezná |

**`DayStatus`** — co jídelna říká o celém dni (pole `omezeniObj.den`). Na
objednatelnost nemá vliv, tu určuje vždy jen konkrétní jídlo:

| hodnota | význam |
|---|---|
| `NORMAL` | Běžný den |
| `NOT_AUTO_ORDERED` | Jídelna na tento den neobjednává automaticky |
| `NO_SCHOOL` | Ten den se nevaří |
| `CLOSED` | Uzávěrka dne už proběhla |
| `UNKNOWN` | Jídelna vrátila kód, který knihovna nezná |

### Dny, na které se neobjednává automaticky

Jídelna některé dny označuje kódem `"T"`. **Objednat na ně jde úplně normálně**, jen se
neobjednají samy — typicky pátek, kdy se ve škole neučí. Knihovna to vystavuje jako
`Day.auto_ordered` a jako filtr:

```python
# Co by automat objednal, kdyby na to byl
strava.menu.get_meals(auto_ordered=True, orderable=True)

# Dny, které si musíte objednat sami
[den.date for den in strava.menu.get_days(auto_ordered=False)]
```

Ve výchozím nastavení se tyhle dny **nijak neskrývají** — jsou to obyčejné objednatelné
dny.

## Objednávání

```python
from strava_cz import StravaCZ, InsufficientBalanceError, MealNotOrderableError

strava = StravaCZ("vase.jmeno", "VaseHeslo123", "3753")
strava.menu.fetch()

try:
    vysledek = strava.menu.order_meals(5, 9)
    print(vysledek)          # "2 changed"
    print(vysledek.changed)  # (5, 9)
except MealNotOrderableError as e:
    print(f"Tohle jídlo objednat nejde: {e}")
except InsufficientBalanceError:
    print(f"Nedostatečný zůstatek: {strava.user.balance} Kč")

# Zrušení objednávek
strava.menu.cancel_meals(5, 9)
```

Obě metody proběhnou jako **jedna transakce**: nejdřív se zaškrtnou všechna jídla,
pak se změny uloží najednou a nakonec se výsledek ověří na čerstvě načteném
jídelníčku. Když cokoliv selže, změny se zahodí a nic se neuloží. Pokud není co
měnit, neodešle se žádný požadavek.

**Parametry**

- `continue_on_error=True` — neskončí u první chyby. Objedná, co jde, a zbytek
  vrátí v `OrderResult`, místo aby vyhodila výjimku.
- `strict_duplicates=True` — vyhodí `DuplicateMealError`, když se dvě zvolená jídla
  perou o stejné místo (stejný den, stejný typ). Ve výchozím stavu se objedná
  první z nich a u ostatních se jen vypíše varování.

```python
vysledek = strava.menu.order_meals(5, 85, 999, continue_on_error=True)

print(vysledek.changed)    # (5,)   objednáno
print(vysledek.unchanged)  # ()     už bylo objednané, nic se neposílalo
print(vysledek.skipped)    # ()     vynecháno kvůli duplicitě
print(vysledek.failed)     # ((85, MealNotOrderableError(...)), (999, MealNotFoundError(...)))
print(vysledek.ok)         # False
```

## Výjimky

Všechny výjimky knihovny dědí ze `StravaError`, takže je lze odchytit najednou.

| výjimka | kdy nastane |
|---|---|
| `StravaError` | Základní třída všech výjimek knihovny |
| `StravaAPIError` | API odmítlo požadavek; nese `.code`, `.status_code` a `.payload` |
| `AuthenticationError` | Přihlášení selhalo nebo session vypršela |
| `NotLoggedInError` | Volání, které vyžaduje přihlášení, ale uživatel přihlášený není |
| `InsufficientBalanceError` | Na účtu není dost peněz |
| `MealNotFoundError` | ID jídla není v načteném jídelníčku |
| `MealNotOrderableError` | Jídelna objednávku či zrušení nedovolí; nese `.reason` |
| `DuplicateMealError` | Dvě jídla soupeří o stejné místo a je zapnuté `strict_duplicates` |
| `MenuNotFetchedError` | Přístup k jídelníčku dřív, než se zavolá `fetch()` |

## Nastavení klienta

```python
strava = StravaCZ(
    "vase.jmeno", "VaseHeslo123", "3753",
    timeout=30.0,      # výchozí je 15 s, z toho 10 s na navázání spojení
    retries=2,         # opakuje se jen spojení, které se nenavázalo
    language="CS",     # jazyk odpovědí z API
)
```

Heslo se použije jen pro přihlašovací požadavek a dál se nikde neukládá.
Parametrem `client=` můžete také předat vlastní `httpx.Client`.

## To-do

- [x] Nahrát jako knihovnu na PyPI
- [x] Lépe zorganizovat kód
- [x] Lepší formát data
- [x] Možnost detailnější filtrace jídelníčku
- [x] Kontrola stavu po objednání
- [x] Detekce a prevence duplicitních objednávek
- [x] Rozpoznání důvodu, proč jídlo nelze objednat
- [x] Lépe zdokumentovat použití
- [ ] Login rate limiting
- [ ] Debug/log mód
- [ ] Asynchronní klient

## Co bude dál?

Plánuji udělat aplikaci, která bude uživateli automaticky objednávat obědy podle
jeho preferencí.

Prosím, nepoužívejte tuto knihovnu k nekalým účelům. Používejte ji pouze s dobrými
úmysly.

## Jak mi pomoct

Našel jsi chybu nebo máš návrh na zlepšení? Skvělé! Vytvoř prosím
[bug report](https://github.com/jsem-nerad/strava-cz-python/issues/new?labels=bug)
nebo [feature request](https://github.com/jsem-nerad/strava-cz-python/issues/new?labels=enhancement).

Udělal jsi sám nějaké zlepšení? Ještě lepší! Každý pull request je vítaný — postup
najdeš v [notes/repo_rules.md](notes/repo_rules.md).

## Použití AI

Na tomto projektu byly do jisté míry využity modely LLM, primárně na dokumentaci,
testy a formátování kódu. Každá taková úprava prošla mojí kontrolou.

## Licence

[GPL-3.0-or-later](LICENSE)
