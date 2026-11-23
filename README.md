# strava-cz

Objednávání obědů ve školních jídelnách, které používají systém **[Strava.cz](https://app.strava.cz)**,
bez prohlížeče. Podívá se na jídelníček, objedná a zruší jídla, ohlídá zůstatek na účtu
a řekne, proč se konkrétní jídlo objednat nedá.

Je to **knihovna pro Python**, **příkaz `strava-cz`** pro terminál a skripty a **MCP server**,
přes který může váš účet používat AI agent. Všechny tři dělají totéž a sdílejí přihlašovací údaje.

K čemu se to hodí:

- **automatické objednávání**: cron, skript nebo agent, který vám objedná oběd na příští týden,
- rychlý pohled na jídelníček a zůstatek z terminálu,
- vlastní aplikace, upozornění nebo statistiky nad jídelníčkem.

## Instalace a první kroky

Potřebujete **Python 3.10 nebo novější**, přihlašovací jméno do Strava.cz a číslo vaší jídelny
([jak ho najít](https://github.com/jsem-nerad/strava-cz-python/wiki/Installation-Guide#finding-your-canteen-number)).

**1. Nainstalujte**

```bash
pip install "strava-cz[cli]"
```

Extra `cli` přidává bezpečné uložení hesla. Chcete-li i MCP server pro AI agenta, použijte
`pip install "strava-cz[cli,mcp]"`. Samotná knihovna bez extra: `pip install strava-cz`.

**2. Uložte přihlášení** (heslo se vás zeptá a uloží ho do klíčenky, ne do souboru jako text)

```bash
strava-cz profile add skola --username vase.jmeno --canteen 3753 --verify
```

**3. Zkuste to**

```bash
strava-cz menu --week
```

Funguje? Pak pokračujte
**[Rychlým startem](https://github.com/jsem-nerad/strava-cz-python/wiki/Quick-Start)**
nebo podrobným
**[návodem k instalaci](https://github.com/jsem-nerad/strava-cz-python/wiki/Installation-Guide)**.

## Jak to vypadá

### V Pythonu

```python
from strava_cz import MealType, StravaCZ

with StravaCZ.from_profile("skola") as strava:   # přihlášení uložené výše
    strava.menu.fetch()

    # hlavní jídla, která jdou objednat
    for meal in strava.menu.get_meals(meal_types=[MealType.MAIN], orderable=True):
        print(meal.key, meal.name, meal.price)

    strava.menu.order_meals("2026-09-21:O1")      # objedná oběd 1 na pondělí
    print(strava.user.balance)
```

Další: [jídelníček a filtry](https://github.com/jsem-nerad/strava-cz-python/wiki/Menu-System),
[objednávání](https://github.com/jsem-nerad/strava-cz-python/wiki/Ordering-Meals),
[chyby](https://github.com/jsem-nerad/strava-cz-python/wiki/Error-Handling).

### V terminálu

```bash
strava-cz menu --week --orderable --type main   # co jde objednat
strava-cz order 2026-09-21:O1 --dry-run         # jen říct, co by se stalo
strava-cz order 2026-09-21:O1                   # objednat
strava-cz balance                               # 512.50 Kč
strava-cz --json ordered | jq '.total_price'    # JSON pro skripty
```

```
Mon 21.09.2026
  ·  2026-09-21:PO  Polévka    Zeleninová    this item cannot be ordered separa…
  ○  2026-09-21:O1  Oběd 1     Bramborové knedlíky s kuřecím masem a špe…  50 Kč
  ○  2026-09-21:O2  Oběd 2     Bramborové špalíky sypané cibulkou, kysan…  50 Kč
```

Další: [všechny přepínače, JSON a návratové kódy](https://github.com/jsem-nerad/strava-cz-python/wiki/CLI),
[profily a uložení hesla](https://github.com/jsem-nerad/strava-cz-python/wiki/Profiles).

### Pro AI agenta (MCP)

```bash
pip install "strava-cz[cli,mcp]"
```

Do nastavení klienta (například Claude Desktop) přidejte:

```json
{
  "mcpServers": {
    "strava-cz": {
      "command": "strava-cz",
      "args": ["--profile", "skola", "mcp"]
    }
  }
}
```

Agent pak umí číst jídelník, zůstatek i objednávky a **objednávat a rušit jídla**. Heslo se
agentovi nikdy nedostane: server se přihlásí přes uložený profil. Chcete, aby agent jen četl?
Přidejte do `args` `"--read-only"` a nástroje pro objednávání se vůbec nezaregistrují.

Další: [všechny nástroje, nastavení klientů a bezpečnost](https://github.com/jsem-nerad/strava-cz-python/wiki/MCP).

## Dokumentace

Všechno podrobné je na **[GitHub Wiki](https://github.com/jsem-nerad/strava-cz-python/wiki)**:

| | |
|---|---|
| [Instalace](https://github.com/jsem-nerad/strava-cz-python/wiki/Installation-Guide) · [Rychlý start](https://github.com/jsem-nerad/strava-cz-python/wiki/Quick-Start) | začínáme |
| [Příkaz `strava-cz`](https://github.com/jsem-nerad/strava-cz-python/wiki/CLI) · [MCP server](https://github.com/jsem-nerad/strava-cz-python/wiki/MCP) | jak to používat |
| [Profily a hesla](https://github.com/jsem-nerad/strava-cz-python/wiki/Profiles) · [Přihlášení](https://github.com/jsem-nerad/strava-cz-python/wiki/Authentication) | přihlašování |
| [Jídelníček](https://github.com/jsem-nerad/strava-cz-python/wiki/Menu-System) · [Jídla a omezení](https://github.com/jsem-nerad/strava-cz-python/wiki/Meals-and-Restrictions) · [Objednávání](https://github.com/jsem-nerad/strava-cz-python/wiki/Ordering-Meals) · [Výjimky](https://github.com/jsem-nerad/strava-cz-python/wiki/Error-Handling) | knihovna |
| [Vnitřnosti API](https://github.com/jsem-nerad/strava-cz-python/wiki/API-Internals) · [Přispívání](https://github.com/jsem-nerad/strava-cz-python/wiki/Contributing) · [Changelog](https://github.com/jsem-nerad/strava-cz-python/blob/main/CHANGELOG.md) | vývoj |

Moje poznatky o vnitřním fungování API Strava.cz jsou ve složce
[notes](https://github.com/jsem-nerad/strava-cz-python/tree/main/notes).

## Jak mi pomoct

Našel jsi chybu nebo máš návrh na zlepšení? Skvělé! Vytvoř prosím
[bug report](https://github.com/jsem-nerad/strava-cz-python/issues/new?labels=bug)
nebo [feature request](https://github.com/jsem-nerad/strava-cz-python/issues/new?labels=enhancement).

Udělal jsi sám nějaké zlepšení? Ještě lepší! Každý pull request je vítaný — postup
najdeš v [notes/repo_rules.md](https://github.com/jsem-nerad/strava-cz-python/blob/main/notes/repo_rules.md).

Prosím, nepoužívejte tuto knihovnu k nekalým účelům. Používejte ji pouze s dobrými
úmysly.

## Použití AI

Na tomto projektu byly do jisté míry využity modely LLM, primárně na dokumentaci,
testy a formátování kódu. Každá taková úprava prošla mojí kontrolou.

## Licence

[GPL-3.0-or-later](https://github.com/jsem-nerad/strava-cz-python/blob/main/LICENSE)
