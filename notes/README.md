# Poznámky ke Strava.cz

Všechno, co jsem zjistil o interním API webové aplikace
[app.strava.cz](https://app.strava.cz). Aplikace mluví se svým backendem přes
JSON POST požadavky na `https://app.strava.cz/api/<endpoint>`.

Kompletní nahrané odpovědi z reálného účtu jsou v `tests/fixtures/`, takže se sem
už nemusí opisovat celé. Novou odpověď si nahrajete pomocí `examples/capture_api.py`.

## Obecné chování

- Všechny endpointy jsou **POST** s JSON tělem.
- Webová aplikace posílá hlavičku `Content-Type: text/plain;charset=UTF-8`, přestože
  tělo je JSON. Server to přijímá a knihovna to napodobuje.
- `sid` získané při přihlášení musí být v každém dalším autorizovaném požadavku.
- `ignoreCert` se posílá jako řetězec `"false"`, ne jako boolean. Server je v tom
  ale tolerantní.

### Chybové odpovědi

Chyba se ohlašuje **nestandardním HTTP statusem 555** a tělem v tomto tvaru:

```json
{
    "state": "error",
    "number": 20,
    "message": "The client was not found in the client register or the wrong nickname or password was entered...",
    "backend": { "...": "..." }
}
```

Samotný HTTP status tedy nestačí — je potřeba se dívat i na pole `state`.

| `number` | význam |
|---|---|
| 20 | Neexistující uživatel, špatné heslo nebo zablokovaný účet |
| 35 | Nedostatečný zůstatek na kontě pro objednání jídla |
| 43 | Server je přetížený, zkuste to za chvíli |

Kód 43 přišel při rychlém opakovaném přihlašování ze skriptu ("The service is currently
overloaded, please try again in a few minutes"). Vypadá to tedy spíš na omezení počtu
požadavků než na skutečné přetížení. Knihovna ho zatím nemapuje na vlastní výjimku —
vyletí jako obecná `StravaAPIError` s `.code == 43`.

## Přihlášení uživatele

`POST /api/login`

```json
{
    "cislo": "3753",
    "jmeno": "vojtech.nerad",
    "heslo": "XXXXXXXXX",
    "zustatPrihlasen": false,
    "environment": "W",
    "lang": "EN"
}
```

| key | popis | příklad | typ |
|---|---|---|---|
| cislo | číslo jídelny | 3753 | string |
| jmeno | uživatelské jméno | vojtech.nerad | string |
| heslo | plaintext heslo uživatele | Heslo123 | string |
| zustatPrihlasen | zůstat přihlášen | false | boolean |
| environment | prostředí, web posílá `W` | W | string |
| lang | jazyk aplikace | EN | string |

### Odpověď

Plná odpověď je v `tests/fixtures/login.json`. Důležité hodnoty:

| key | popis | příklad | typ |
|---|---|---|---|
| sid | identifikátor session, patří do každého dalšího autorizovaného požadavku | 01C6FCF02A7146159BC5F245A57AF29F | string |
| s5url | endpoint webové služby Stravné 5 | https://wss5.strava.cz/WSStravne5_15/WSStravne5.svc | string |
| uzivatel/konto | peníze na účtu, **posílá se jako řetězec** | "0.00" | string |
| uzivatel/jmeno | jméno a příjmení uživatele | Vojtěch Nerad | string |
| uzivatel/email | e-mail uživatele | muj.email@gmail.com | string |
| uzivatel/mena | měna | Kč | string |
| uzivatel/nazevJidelny | název jídelny | Školní jídelna, Praha 5 - Smíchov | string |

Pozor: `konto` je řetězec, ne číslo. Před počítáním je potřeba ho převést.

## Seznam objednávek (jídelníček)

`POST /api/objednavky`

```json
{
    "cislo": "3753",
    "sid": "01C6FCF02A7146159BC5F245A57AF29F",
    "s5url": "https://wss5.strava.cz/WSStravne5_15/WSStravne5.svc",
    "lang": "EN",
    "konto": 0,
    "podminka": "",
    "ignoreCert": "false"
}
```

### Odpověď

Odpověď je slovník, kde **každý klíč `table<N>` odpovídá jednomu dni** a obsahuje
seznam jídel toho dne. Plná nahraná odpověď (31 dnů) je v
`tests/fixtures/menu_live.json`.

Důležitá pole jednoho jídla:

| key | popis | příklad | typ |
|---|---|---|---|
| datum | datum, formát `dd.mm.yyyy` | 15.09.2026 | string |
| druh | **krátký kód typu jídla**, stabilní napříč jazyky | PO, O1, O2 | string |
| druh_popis | zobrazovaný popis typu jídla | Polévka, Oběd 1 | string |
| nazev | název jídla | Vývar s kuskusem | string |
| cena | cena, **jako řetězec** | "50.00" | string |
| alergeny | alergeny jako dvojice `[kód, název]` | [["04","Ryby"]] | list |
| zakazaneAlergeny | alergeny označené uživatelem jako nevhodné | null | list/null |
| pocet | stav objednání: 0 = neobjednáno, 1 = objednáno | 0 | integer |
| veta | **identifikátor jídla použitý při objednávání**; platí jen do dalšího přihlášení nebo resetu session (`nactiVlastnostiPA`), jídelna čísluje jídelníček při každém přihlášení znovu | "7" | string |
| casKonec | dokdy lze jídlo objednat | 2026-09-14T15:00:00 | string |
| omezeniObj | omezení objednávky, viz níže | {"den":"","obj":"","zm":"","bur":"C"} | object |

Datum se v některých verzích aplikace objevilo i s jiným oddělovačem
(`15-09.2025`), takže se vyplatí parsovat tolerantně.

### omezeniObj — kdy jde jídlo objednat

Tohle je nejdůležitější část celého API a zároveň ta, kterou je nejsnazší pochopit
špatně. Objekt má čtyři pole:

| pole | platí pro | význam |
|---|---|---|
| `obj` | konkrétní jídlo | jde jídlo objednat |
| `zm` | konkrétní jídlo | jde už uloženou objednávku změnit nebo zrušit |
| `bur` | konkrétní jídlo | je jídlo dostupné na burze |
| `den` | celý den | kód dne |

**Pravidlo: prázdný řetězec u `obj` a `zm` znamená „smí se“.** Jakákoliv jiná hodnota
je jedno písmeno, které říká proč ne:

| hodnota | význam |
|---|---|
| `""` | bez omezení |
| `"C"` | uzávěrka objednávek už proběhla (`casKonec` je v minulosti) |
| `"I"` | položku nelze objednat samostatně — typicky polévka, která patří k obědu |
| `"V"` | volno, jídelna ten den nevaří |

Ověřeno na živém účtu (31 dnů, 113 jídel); přesně to odpovídá poli `casKonec`:

| stav dne | `obj` | `zm` | `bur` | `den` |
|---|---|---|---|---|
| uzávěrka ještě neproběhla | `""` | `""` | `"C"` | `""` |
| uzávěrka proběhla | `"C"` | `"C"` | `"!"` | `""` nebo `"CO"` |
| neobjednává se automaticky | `""` | `""` | `"C"` | `"T"` |
| nevaří se / státní svátek | `"V"` | `""` | `"V"` | `"VP"` |
| polévka (vždy) | `"I"` | `"I"` | `"I"` | — |

Pole `den` je **kód celého dne, ne konkrétního jídla**, a nehodí se k rozhodování
o objednatelnosti:

| hodnota | význam |
|---|---|
| `""` | běžný den |
| `"T"` | den, na který jídelna neobjednává automaticky |
| `"VP"` | volno nebo prázdniny |
| `"CO"` | den po uzávěrce |

- `"VP"` — volno nebo prázdniny. Jídla toho dne se jmenují `"Nevaří se"` nebo
  `"Státní svátek"` a nejsou to skutečná jídla.
- `"T"` — **den, který nepokrývá automatické objednávání jídelny.** Jídla na něm mají
  `obj: ""`, takže je lze normálně objednat ručně; samy se ale nikdy neobjednají.
  Typicky pátek, kdy se ve škole neučí.
- `"CO"` — den, jehož uzávěrka už proběhla. Jídla mají `obj: "C"`. Verze aplikace se
  v tom liší: 5.13 i některé jídelny na 5.15 posílají `den: "CO"`, jinde je den prázdný
  a stav nese jen `obj`. Proto se den po uzávěrce pozná spolehlivě jen z `obj`.

Ověření `"T"` na živém účtu (32 dnů, 118 jídel, září–říjen 2026):

- `"T"` se vyskytlo na 6 dnech a **všech 6 byly pátky**; na žádný jiný den týdne nikdy.
- Všechny tyhle dny měly u hlavních jídel `obj: ""`, tedy byly objednatelné.
- V období, kde automat objednával (2.–18. 9.), měl **každý den pondělí až čtvrtek
  právě jedno objednané jídlo, zatímco všechny pátky s `"T"` měly nula.**
- Jinak se řádek dne s `"T"` neliší od běžného dne ani jedním polem — rozdíl je jen
  v `omezeniObj.den`.

Knihovna to od 0.3.0 vystavuje jako `Day.auto_ordered` a `DayStatus.NOT_AUTO_ORDERED`.
Objednatelnost tím zůstává netknutá; jde o informaci navíc pro nástroje, které
objednávají automaticky.

Verze knihovny do 0.2.0 včetně četla jen `den` a podle něj určovala objednatelnost.
Kvůli tomu mizely objednatelné dny s kódem `"T"` a u jídelníčku z verze 5.13
vracela knihovna prázdný seznam. Od 0.3.0 se rozhoduje podle `obj` a `zm`.

### Nepublikovaná jídla

Jídelna zveřejňuje jídelníček po částech. Dokud jídlo není vypsané, má místo názvu
obecný popisek. Poznáte je dvěma způsoby:

- `nazev` je shodný s `druh_popis` (například obojí `"Oběd 2"`), nebo
- `nazev` je sám o sobě obecný popisek — `"Oběd 3"`, `"Oběd 2 Rad 1"`.

Kombinace `delsiPopis == "" && alergeny == []`, kterou jsem používal dřív, je
nespolehlivá: existují reálná jídla bez dlouhého popisu i bez alergenů.

## Objednávání

Objednávka se skládá ze dvou kroků:

1. **Zaškrtnutí políčka konkrétního jídla** — `pridejJidloS5`
2. **Potvrzení změn** — `saveOrders`

Mezi těmito dvěma kroky je změna jen rozpracovaná. Zahodit ji lze požadavkem na
`nactiVlastnostiPA`, který znovu načte stav ze serveru.

### pridejJidloS5

`POST /api/pridejJidloS5`

```json
{
    "cislo": "3753",
    "sid": "01C6FCF02A7146159BC5F245A57AF29F",
    "url": "https://wss5.strava.cz/WSStravne5_15/WSStravne5.svc",
    "veta": "7",
    "pocet": "1",
    "lang": "EN",
    "ignoreCert": "false"
}
```

Pozor na nekonzistenci v pojmenování: tenhle endpoint chce `url`, zatímco
`objednavky` chce `s5url`.

Odpověď vrátí stav všech jídel daného dne a nový zůstatek v poli `konto`:

```json
{
    "produkt": [
        { "$": { "Veta": "7", "Pocet": "1", "Druh": "O2", "NelzeObj": "", "...": "..." } }
    ],
    "konto": "0.00"
}
```

### saveOrders

`POST /api/saveOrders`

```json
{
    "cislo": "3753",
    "sid": "01C6FCF02A7146159BC5F245A57AF29F",
    "url": "https://wss5.strava.cz/WSStravne5_15/WSStravne5.svc",
    "xml": null,
    "lang": "EN",
    "ignoreCert": "false"
}
```

Odpověď obsahuje aktuální stav objednávek a nový zůstatek:

```json
{
    "produkty": [
        { "veta": "75", "pocet": 0, "burza": { "...": "..." } },
        { "veta": "1", "pocet": 1, "burza": { "...": "..." } }
    ],
    "konto": "0.00"
}
```

Odpověď se ale nedá brát jako potvrzení, že se objednávka opravdu propsala.
Knihovna proto po uložení znovu načte jídelníček a zkontroluje `pocet`.

### nactiVlastnostiPA

`POST /api/nactiVlastnostiPA`

```json
{
    "sid": "01C6FCF02A7146159BC5F245A57AF29F",
    "url": "https://wss5.strava.cz/WSStravne5_15/WSStravne5.svc",
    "cislo": "3753",
    "ignoreCert": "false",
    "lang": "EN",
    "getText": true,
    "checkVersion": true,
    "resetTables": true,
    "frontendFunction": "refreshInformations"
}
```

Znovu načte stav ze serveru. Používá se jako rollback, když objednávání selže
uprostřed — rozpracované změny se tím zahodí.

## Odhlášení uživatele

`POST /api/logOut`

```json
{
    "sid": "E9D5B96FE3D14DED8E543B33A4D910F2",
    "cislo": "3753",
    "url": "https://wss5.strava.cz/WSStravne5_15/WSStravne5.svc",
    "lang": "EN",
    "ignoreCert": "false"
}
```

Odpověď je holý JSON literál `true`, ne objekt. Kód, který naslepo volá
`.json()["neco"]`, na tom spadne.

## Co jsem ještě nerozluštil

- Pole `burza` a celá funkce burzy (nabídka a poptávka jídel mezi strávníky).
- Pole `environment`, `podminka`, `ignoreCert` a `xml` — server je přijímá, ale
  co s nimi dělá, nevím.
- Objednávání více porcí najednou (`pocet` větší než 1).
