# Toto je jednoduchy seznam na udrzovani funkcniho repozitare

## Lokalni development

### 1. Klonovani repozitare

```bash
git clone https://github.com/jsem-nerad/strava-cz-python.git
cd strava-cz-python
```

### 2. Setup Python Virtual Enviroment

Zkontrolujte verzi Pythonu a vytvorte virtualni prostredi.
Tento krok se muze lisit v zavislosti na operacnim systemu.

#### Linux

```bash
python3 --version
python3 -m venv venv
source venv/bin/activate
```

#### Windows
```bash
python --version
python -m venv .venv
.venv\Scripts\activate
```

### 3. Package instalace v develpement modu

```bash
pip install -e .[dev]
```

> Ujistete se ze je aktivni venv


## Tvorba novych funkci

### 1. Nova feature branch

```bash
git checkout main
git pull origin main
git checkout -b feature/nazev-planovanych-funkci
```

### 2. Prace na novych funkcich

- Delat commity jak uznate za vhodne
```bash
git add .
git commit -m "neco jsem pridal"
```

- Zapsat zmeny do CHANGELOG.md
- Spusteni testu pomoci pytest a opravit pripadne chyby:
```bash
pytest
```
- Vycistit kod pomoci black, zkontrolovat pomoci flake8 a provest mypy type check, popripade opravit vsechny chyby:
```bash
black src/strava_cz/
flake8 src/strava_cz --max-line-length=100
mypy src/strava_cz/
```

### 3. Vytvoreni pull requestu

```bash
git push origin feature/nazev-planovanych-funkci
```

### 4. Spravce repozitare zkontroluje a schvali pull request, merge s main branch

### 5. Prepnuti zpet na main branch

```bash
git checkout main
git pull origin main
git branch -d feature/nazev-planovanych-funkci
```




## Tag nove verze a nahrani na PyPi

1. Aktualizace tagu verze v souborech `src/strava_cz/__init__.py`, `pyproject.toml`.
2. Kontrola verze v `CHANGELOG.md`

3. Vytvoreni git tagu: `git tag v0.1.0`

4. Push na GitHub s tagem: `git push origin v0.1.0`