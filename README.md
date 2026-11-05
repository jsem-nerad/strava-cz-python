# Strava.cz Python API

Python knihovna pro objednávání jídel ve školních jídelnách, které používají systém
**[Strava.cz](https://app.strava.cz)**. Komunikuje přímo s interním JSON API webové
aplikace, takže nepotřebuje prohlížeč ani parsování HTML.

```bash
pip install strava-cz          # knihovna
pip install "strava-cz[cli]"   # + bezpečné uložení hesla pro příkaz strava-cz
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
- Rozlišení dnů, na které jídelna neobjednává automaticky
- Příkaz `strava-cz` pro práci z terminálu, s výpisem pro lidi i s JSON pro skripty
- Profily, takže se přihlašovací údaje nezadávají znovu a heslo leží v klíčence
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

> **ID jídla** (`meal.id`, v API pole `veta`) **platí jen do dalšího přečíslování**:
> jídelna čísluje jídelníček znovu při každém přihlášení a při každém resetu session, který
> proběhne i při vracení neúspěšné objednávky. Stejné číslo pak může znamenat jiné jídlo v
> jiný den. Co má přežít jedno načtení, ukládejte jako `meal.key`, tedy den a místo v
> jídelníčku (`"2026-11-09:O2"`). `order_meals()` i `cancel_meals()` berou obojí.

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
jidlo = strava.menu.get_by_key("2026-09-07:O2")
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
| `id` | `int` | Identifikátor pro objednávání (API pole `veta`), platí jen do dalšího přihlášení nebo resetu session |
| `key` | `str` | Den a místo v jídelníčku, například `"2026-09-07:O2"`; platí i po novém přihlášení |
| `kind_code` | `str` | Kód místa v jídelníčku (API pole `druh`), například `"O2"` |
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
pak se změny uloží najednou a nakonec se výsledek ověří na znovu načteném jídelníčku.
Když selže zaškrtnutí, změny se zahodí a nic se neuloží. Pokud není co měnit, neodešle se
žádný požadavek.

Když selže samotné uložení, knihovna se podívá, co se stalo: když se změna uložila, je to
úspěch, když ne, chyba říká „Nothing was saved“. **Když to zjistit nejde, přijde
`OrderNotConfirmedError`, která neznamená, že se nic nestalo.** Nese `.changed` a
`.unconfirmed`, a před dalším pokusem je potřeba se podívat do jídelníčku.

**Parametry**

- `continue_on_error=True` — neskončí u první chyby. Objedná, co jde, a zbytek
  vrátí v `OrderResult`, místo aby vyhodila výjimku.
- `strict_duplicates=True` — vyhodí `DuplicateMealError`, když se dvě zvolená jídla
  perou o stejné místo (stejný den, stejný typ). Ve výchozím stavu se objedná
  první z nich a u ostatních se jen vypíše varování.
- `verify_saved=True` — ověří výsledek proti záznamům jídelny. Bez něj se čte kopie
  objednávek v tomhle přihlášení, ve které je zaškrtnuté jídlo vidět už před uložením, takže
  se nepozná uložení, které nic neudělalo. Stojí jeden požadavek a přečísluje jídelníček,
  takže čísla přečtená předtím přestanou platit do dalšího `fetch()`; klíče platí dál.

```python
vysledek = strava.menu.order_meals(5, 85, 999, continue_on_error=True)

print(vysledek.changed)    # (5,)   objednáno
print(vysledek.unchanged)  # ()     už bylo objednané, nic se neposílalo
print(vysledek.skipped)    # ()     vynecháno kvůli duplicitě
print(vysledek.failed)     # ((85, MealNotOrderableError(...)), (999, MealNotFoundError(...)))
print(vysledek.ok)         # False
```

## Příkazová řádka

Balíček instaluje příkaz `strava-cz`. Umí všechno, co knihovna, a ve výchozím stavu
vypisuje čitelnou tabulku; pro skripty je tu `--format json`.

```bash
# jednou uložit přihlášení (heslo jde do klíčenky operačního systému)
strava-cz profile add skola --username vase.jmeno --canteen 3753

strava-cz menu --week                  # jídelníček na tento týden
strava-cz menu --orderable --type main # jen hlavní jídla, která jdou objednat
strava-cz order 2026-09-21:O1 2026-09-25:O1   # objednat
strava-cz order 2026-09-21:O1 --dry-run # jen říct, co by se stalo
strava-cz cancel 2026-09-21:O1         # zrušit
strava-cz ordered                      # co mám objednáno
strava-cz balance                      # 512.50 Kč
```

```
Mon 21.09.2026
  ·  2026-09-21:PO  Polévka    Zeleninová    this item cannot be ordered separa…
  ○  2026-09-21:O1  Oběd 1     Bramborové knedlíky s kuřecím masem a špe…  50 Kč
  ○  2026-09-21:O2  Oběd 2     Bramborové špalíky sypané cibulkou, kysan…  50 Kč

Fri 25.09.2026  not ordered automatically
  ○  2026-09-25:O1  Oběd 1     Kuřecí asijská pánev, kari rýže, tvaroháč…  50 Kč

2 days · 4 meals · 3 orderable · 0 ordered · balance 0.00 Kč
```

Id jídla je den a místo v jídelníčku a platí i v dalších spuštěních. Holé číslo příkaz
odmítne, protože jídelna čísluje jídelníček při každém přihlášení znovu.

Barvy se zapínají jen na terminálu — v rouře, v souboru nebo v cronu se nevypisují,
stejně jako když je nastavená proměnná `NO_COLOR`. Vynutit je jde přes `--color always`.

### Pro skripty

S `--format json` (nebo zkratkou `--json`) vypadne na standardní výstup **jeden JSON
objekt** a všechna hlášení jdou na chybový výstup, takže výstup zůstane zpracovatelný.
Chyba se hlásí taky JSONem, ne textem:

```bash
strava-cz --json menu --orderable | jq '.days[].meals[] | select(.type=="main") | .id'
strava-cz --json ordered | jq '.total_price'
```

```json
{ "ok": false,
  "command": "order",
  "error": { "type": "MealNotOrderableError", "meal_id": "2026-09-21:PO", "reason": "unavailable",
             "message": "Cannot order meal 2026-09-21:PO: this item cannot be ordered separately" } }
```

**Návratové kódy** — aby se šlo v shellu rozhodnout, co se pokazilo:

| kód | význam |
|---|---|
| 0 | Hotovo |
| 1 | Selhala jídelna nebo síť |
| 2 | Špatně zadaný příkaz |
| 3 | Přihlášení odmítnuto |
| 4 | Jídlo nelze objednat, zrušit, nebo neexistuje |
| 5 | Nedostatečný zůstatek |
| 6 | Problém s profilem nebo klíčenkou |

S `--continue-on-error` kód říká to nejhorší, co se stalo: 5, když na nějaké jídlo nebyly
peníze, jinak 1, když u některého selhala jídelna nebo síť, jinak 4.

Kód 1 u `order` a `cancel` neznamená vždycky, že se nic nestalo. Když jídelna uložení
přijala, ale nejde ho potvrdit, hlášení to řekne a s `--json` jsou jídla v `error.unconfirmed`
a `error.changed`. **Před dalším pokusem se podívejte přes `strava-cz ordered`.**

`--dry-run` u `order` a `cancel` **neodešle vůbec nic** — jen spočítá, co by se změnilo,
včetně jídel, která už jsou objednaná, a dvou jídel, která by soupeřila o stejné místo.
Počítá se zadanými přepínači, takže bez `--continue-on-error` jedno odmítnuté jídlo zastaví
celou dávku a `would_change` je prázdné. Nezná jen limit účtu: když by zůstatek klesl pod
nulu, přijde varování a pole `balance_after`, protože jídelna může objednávku odmítnout, a
to i na účtu placeném fakturou, ale kód zůstává 0.

Úplný seznam přepínačů vypíše `strava-cz --help` a `strava-cz menu --help`.

## Profily

Profil si pamatuje uživatelské jméno a číslo jídelny; **heslo se do souboru nezapisuje**.
Ve výchozím stavu putuje do klíčenky operačního systému (GNOME Keyring, KWallet, macOS
Keychain, Windows Credential Locker) přes balíček `keyring`.

```bash
strava-cz profile add skola --username vase.jmeno --canteen 3753 --verify
strava-cz profile list
strava-cz profile show skola
strava-cz profile default doma
strava-cz profile remove doma

strava-cz --profile doma menu   # jednorázově jiný profil
```

Přepínač `--secret` říká, odkud se heslo bere:

| hodnota | kam se heslo uloží |
|---|---|
| `auto` | **Výchozí.** Klíčenka, když na stroji nějaká je; jinak `encrypted`. |
| `keyring` | Klíčenka systému. Do souboru se nedostane nic. |
| `encrypted` | **Zašifrované** do souboru s profily, pod heslovou frází. |
| `env` | Nikam. Čte se z `$STRAVA_CZ_PASSWORD` při každém spuštění. |
| `prompt` | Nikam. Zeptá se pokaždé na terminálu. |
| `file` | **Otevřeným textem** do souboru s profily. Jen když si o to řeknete. |

`auto` vždycky vypíše, kterou z obou cest zvolilo, a do profilu zapíše konkrétní
výsledek — `profile show` tedy nikdy neuhýbá.

Profily leží v `$XDG_CONFIG_HOME/strava-cz/profiles.json` (soubor `0600`, složka `0700`).
Prostředí má vždycky přednost před uloženým heslem, takže cron může použít existující
profil, aniž by se do něj sahalo: `$STRAVA_CZ_PASSWORD_<JMENO_PROFILU>` přebije
`$STRAVA_CZ_PASSWORD` a obojí přebije klíčenku.

### Server bez klíčenky

Na serveru bez grafického prostředí klíčenka většinou nefunguje. `strava-cz profile add`
to pozná dopředu a přepne na `encrypted`: heslo se zašifruje algoritmem **AES-256-GCM**
klíčem, který z vaší heslové fráze odvodí **scrypt** (n=2^15, r=8, p=1). Parametry se
ukládají do záznamu, takže i po jejich pozdější změně půjdou starší profily otevřít.

```json
"encrypted": {
  "cipher": "aes-256-gcm",
  "kdf": { "name": "scrypt", "n": 32768, "r": 8, "p": 1, "salt": "…" },
  "nonce": "…",
  "ciphertext": "…"
}
```

Heslová fráze se hledá stejně jako heslo: `$STRAVA_CZ_PASSPHRASE_<JMENO_PROFILU>`, pak
`$STRAVA_CZ_PASSPHRASE`, pak se na ni program zeptá na terminálu. Pro cron tedy stačí
nastavit proměnnou.

> **Co to řeší a co ne.** Šifrování chrání **soubor v klidu** — zálohu, kopii domovského
> adresáře, složku, která se omylem odsynchronizuje jinam. Kdo umí přečíst jen
> `profiles.json`, s ním nic nesvede. **Nechrání** vás před někým, kdo už čte vaše
> prostředí nebo paměť běžícího procesu. V cronu je heslová fráze v proměnné podobně,
> jako by tam bylo heslo — rozdíl je v tom, že samotný soubor s profily je pak bezpečné
> zálohovat a synchronizovat.

Zašifrovaný záznam je navíc **ověřený** (GCM), takže poškozený nebo pozměněný soubor
skončí srozumitelnou chybou, ne tichým nesmyslem.

Profily jdou použít i z Pythonu:

```python
from strava_cz import StravaCZ

with StravaCZ.from_profile("skola") as strava:   # bez profilu se vezme výchozí
    strava.menu.fetch()
    strava.menu.print()
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
| `OrderNotConfirmedError` | Změna možná proběhla, ale nejde ji potvrdit; nese `.changed` a `.unconfirmed` |
| `MealNotFoundError` | ID jídla není v načteném jídelníčku |
| `MealNotOrderableError` | Jídelna objednávku či zrušení nedovolí; nese `.reason` |
| `DuplicateMealError` | Dvě jídla soupeří o stejné místo a je zapnuté `strict_duplicates` |
| `MenuNotFetchedError` | Přístup k jídelníčku dřív, než se zavolá `fetch()` |
| `ProfileError` | Něco je špatně s profilem nebo se souborem profilů |
| `ProfileNotFoundError` | Profil daného jména není uložený |
| `KeyringUnavailableError` | Na tomhle stroji není použitelná klíčenka |
| `EncryptionUnavailableError` | Chybí balíček `cryptography`, nelze šifrovat |

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
- [x] Nástroj pro příkazovou řádku
- [x] Profily s bezpečně uloženým heslem
- [x] Uložení hesla i na stroji bez klíčenky
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
