# Repo rules

Jednoduchý seznam na udržování funkčního repozitáře.

## Lokální development

### 1. Klonování repozitáře

```bash
git clone https://github.com/jsem-nerad/strava-cz-python.git
cd strava-cz-python
```

### 2. Virtuální prostředí

Knihovna vyžaduje Python 3.10 nebo novější.

#### Linux / macOS

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
```

#### Windows

```bash
python --version
python -m venv .venv
.venv\Scripts\activate
```

### 3. Instalace v development módu

```bash
pip install -e ".[dev,cli]"
```

Extra `cli` přidá balíčky `keyring` a `cryptography`. Testy si klíčenku podstrkují
vlastní, ale bez extra by se neověřilo, že se skutečné importy chovají, jak mají,
a šifrované profily by nešlo otestovat vůbec.

> Ujistěte se, že je aktivní venv.

### 4. Wiki

Dokumentace žije ve wiki, což je samostatný git repozitář. Naklonujte si ji vedle
kódu — složka `wiki/` je v `.gitignore`, takže se do hlavního repozitáře nedostane:

```bash
git clone git@github.com:jsem-nerad/strava-cz-python.wiki.git wiki
```

Změny ve wiki se commitují a pushují zvlášť, z adresáře `wiki/`.

## Tvorba nových funkcí

### 1. Nová feature branch

```bash
git checkout main
git pull origin main
git checkout -b feature/nazev-planovanych-funkci
```

### 2. Práce na nových funkcích

- Dělat commity, jak uznáte za vhodné:

```bash
git add .
git commit -m "něco jsem přidal"
```

- Zapsat změny do `CHANGELOG.md`.
- Spustit testy a opravit případné chyby:

```bash
pytest
```

- Zkontrolovat a naformátovat kód a ověřit typy:

```bash
ruff check src tests examples
ruff format src tests examples
mypy
```

### 3. Vytvoření pull requestu

```bash
git push origin feature/nazev-planovanych-funkci
```

### 4. Správce repozitáře zkontroluje a schválí pull request, merge s main branch

### 5. Přepnutí zpět na main branch

```bash
git checkout main
git pull origin main
git branch -d feature/nazev-planovanych-funkci
```

## Testování

Testy běží proti nahraným odpovědím z API ve složce `tests/fixtures/`, takže
**nesahají na síť**. Zajišťuje to autouse fixture v `tests/conftest.py`, která
jakýkoliv pokus o otevření socketu shodí s chybou. Nikdy tuhle pojistku neobcházejte —
dřív testy při každém běhu CI posílaly skutečné požadavky na app.strava.cz.

Když potřebujete otestovat něco, co ve fixtures ještě není, nahrajte si vlastní
odpověď pomocí `examples/capture_api.py` a uložte ji jako nový soubor v
`tests/fixtures/`. Skript odstraní osobní údaje, ale stejně si výsledek před
commitem projděte.

## Tag nové verze a nahrání na PyPI

1. Aktualizace verze v `src/strava_cz/__init__.py` a `pyproject.toml`.
2. Kontrola verze v `CHANGELOG.md`.
3. Vytvoření git tagu: `git tag v0.3.0`
4. Push na GitHub s tagem: `git push origin v0.3.0`

GitHub Actions pak samy spustí testy, sestaví balíček a publikují ho na PyPI.
