# Poznamky Strava.cz

## Prihlaseni uzivatele

#### Request payload 

Login request: https://app.strava.cz/api/login

Request type: POST

Payload type: JSON

Payload value: 
```json
{"cislo":"3753","jmeno":"vojtech.nerad","heslo":"XXXXXXXXX","zustatPrihlasen":false,"environment":"W","lang":"EN"}
```


| key             | description               | example       | type    |
|-----------------|---------------------------|---------------|---------|
| cislo           | cislo jidelny             | 3753          | string  |
| jmeno           | uzivatelske jmeno         | vojtech.nerad | string  |
| heslo           | plaintext heslo uzivatele | Heslo123      | string  |
| zustatPrihlasen | zustat prihlasen          | false         | boolean |
| environment     | ...                       | W             | string  |
| lang            | jazyk aplikace            | EN            | string  |


#### Response

Response type: JSON

Response value:

```json
{
    "sid": "01C6FCF02A7146159BC5F245A57AF29F",
    "s5url": "https://wss5.strava.cz/WSStravne5_15/WSStravne5.svc",
    "cislo": "3753",
    "jmeno": "vojtech.nerad",
    "uzivatel": {
        "konto": "0.00",
        "kontoAll": "[{\"nazev\":\"Stravné\",\"hodnota\":\"0.00\"}]",
        "vydej": "1",
        "pocetJidel": "0",
        "podrobnosti": "0",
        "hodnoceni": "0",
        "dochazka": "",
        "editaceJidelnicku": 0,
        "vs": "12173",
        "jmeno": "Vojtěch Nerad",
        "email": "muj.email@gmail.com",
        "zprava": "",
        "slabeHeslo": false,
        "id": "vojtech.nerad",
        "vicenasobny": false,
        "mena": "Kč",
        "blokace": false,
        "cislo": "3753",
        "bakalarId": "202507140700010003",
        "prihlaska": "0",
        "prodej": "0",
        "zapsan": "1",
        "trida": "1.",
        "zakazPrihlaskou": "0",
        "evCislo": "12173",
        "burza": "0",
        "patron": "[]",
        "text": "Vítejte na stránkách pro objednávání stravy naší jídelny.<br>",
        "nazevJidelny": "Školní jídelna, Praha 5 - Smíchov, Štefánikova 11/235",
        "pasivni": false,
        "verze": "5.13"
    },
    "betatest": false,
    "ignoreCert": false,
    "zustatPrihlasen": false
}
```

Dulezite hodnoty:

| key            | description                                                                                             | example                                             | type   |
|----------------|---------------------------------------------------------------------------------------------------------|-----------------------------------------------------|--------|
| sid            | session identifier, slouzi k identifikaci uzivatele, musi byt u kazdeho dalsiho autorizovaneho requestu | 01C6FCF02A7146159BC5F245A57AF29F                    | string |
| s5url          | SOAP Web Service Endpoint URL                                                                           | https://wss5.strava.cz/WSStravne5_15/WSStravne5.svc | string |
| jmeno          | uzivatelske jmeno uzivatele                                                                             | vojtech.nerad                                       | string |
| uzivatel/konto | penize na uctu uzivatele                                                                                | 0.00                                                | string |
| uzivatel/jmeno | jmeno a prijmeni uzivatele                                                                              | Vojtěch Nerad                                       | string |
| uzivatel/email | email uzivatele                                                                                         | muj.email@gmail.com                                 | string |
| uzivatel/id    | id uzivatele                                                                                            | vojtech.nerad                                       | string |



## Objednavky

#### Request payload

Request URL: https://app.strava.cz/api/objednavky

Request type: POST

Payload type: JSON

Payload value:
```json
{"cislo":"3753","sid":"01C6FCF02A7146159BC5F245A57AF29F","s5url":"https://wss5.strava.cz/WSStravne5_15/WSStravne5.svc","lang":"EN","konto":0,"podminka":"","ignoreCert":"false"}
```

| key        | description                                         | example                                             | type          |
|------------|-----------------------------------------------------|-----------------------------------------------------|---------------|
| cislo      | cislo jidelny                                       | 3753                                                | string        |
| sid        | session identifier, slouzi k identifikaci uzivatele | 01C6FCF02A7146159BC5F245A57AF29F                    | string        |
| s5url      | SOAP Web Service Endpoint URL                       | https://wss5.strava.cz/WSStravne5_15/WSStravne5.svc | string        |
| lang       | jazyk                                               | EN                                                  | string        |
| konto      | penize na uctu uzivatele                            | 0                                                   | integer/float |
| podminka   | ...                                                 |                                                     | string        |
| ignoreCert | ...                                                 | false                                               | boolean       |




#### Response

Response type: JSON

Response value:

```json
{
    "table0": [
        {
            "id": 0,
            "datum": "15.09.2025",
            "druh_popis": "Polévka",
            "druh_chod": "Oběd",
            "nazev": "Vývar s kuskusem",
            "popis": "",
            "delsiPopis": "Vývar s kuskusem",
            "zakazaneAlergeny": null,
            "alergeny_text": "01 -Obiloviny obsahující lepek|06 -Sójové boby (sója)|07 -Mléko|09 -Celer|",
            "alergeny": [
                [
                    "01",
                    "Obiloviny obsahující lepek"
                ],
                [
                    "06",
                    "Sójové boby"
                ],
                [
                    "07",
                    "Mléko"
                ],
                [
                    "09",
                    "Celer"
                ]
            ],
            "chod": "C",
            "druh": "PO",
            "cena": "0",
            "polevka": "A",
            "pocet": 0,
            "veta": "75",
            "vetaDieta": "1",
            "omezeniObj": {
                "den": "CO",
                "obj": "I",
                "zm": "I",
                "bur": "I"
            },
            "burza": {
                "zmena": "0",
                "ostatni": "0",
                "nabidka": "0",
                "poptavka": "0"
            },
            "vydejniMisto": {
                "misto": "",
                "mista": ""
            },
            "diety": {
                "dieta": "",
                "diety": ""
            },
            "zkratkaProduktu": "",
            "cisloJidelnicku": "1",
            "multipleNazev": "AVývar s kuskusemCPO",
            "version": 5,
            "casKonec": "2025-09-12T15:00:00",
            "casOdhlaseni": "2025-09-12T15:00:00",
            "obrazky": []
        },
        {
            "id": 1,
            "datum": "15.09.2025",
            "druh_popis": "Oběd 1",
            "druh_chod": "Oběd",
            "nazev": "Čočka s uzeným masem, kysané zelí, čaj, pv",
            "popis": "Oběd 1",
            "delsiPopis": "Čočka s uzeným masem, kysané zelí, čaj, pv",
            "zakazaneAlergeny": null,
            "alergeny_text": "01 -Obiloviny obsahující lepek|",
            "alergeny": [
                [
                    "01",
                    "Obiloviny obsahující lepek"
                ]
            ],
            "chod": "C",
            "druh": "O1",
            "cena": "40.00",
            "polevka": "N",
            "pocet": 1,
            "veta": "1",
            "vetaDieta": "2",
            "omezeniObj": {
                "den": "CO",
                "obj": "C",
                "zm": "C",
                "bur": "!"
            },
            "burza": {
                "zmena": "0",
                "ostatni": "0",
                "nabidka": "0",
                "poptavka": "0"
            },
            "vydejniMisto": {
                "misto": "",
                "mista": ""
            },
            "diety": {
                "dieta": "",
                "diety": ""
            },
            "zkratkaProduktu": "O1",
            "cisloJidelnicku": "1",
            "multipleNazev": "NČočka s uzeným masem, kysané zelí, čaj, pvCO1",
            "version": 5,
            "casKonec": "2025-09-12T15:00:00",
            "casOdhlaseni": "2025-09-12T15:00:00",
            "obrazky": []
        },
        {
            "id": 2,
            "datum": "15.09.2025",
            "druh_popis": "Oběd 2",
            "druh_chod": "Oběd",
            "nazev": "Čočka s vejcem, cibulka, okurka, čaj, pv - V",
            "popis": "Oběd 2",
            "delsiPopis": "Čočka s vejce, cibulka, okurka, čaj, pv",
            "zakazaneAlergeny": null,
            "alergeny_text": "01 -Obiloviny obsahující lepek|03 -Vejce|",
            "alergeny": [
                [
                    "01",
                    "Obiloviny obsahující lepek"
                ],
                [
                    "03",
                    "Vejce"
                ]
            ],
            "chod": "C",
            "druh": "O2",
            "cena": "40.00",
            "polevka": "N",
            "pocet": 0,
            "veta": "2",
            "vetaDieta": "3",
            "omezeniObj": {
                "den": "CO",
                "obj": "C",
                "zm": "C",
                "bur": "!"
            },
            "burza": {
                "zmena": "0",
                "ostatni": "0",
                "nabidka": "0",
                "poptavka": "0"
            },
            "vydejniMisto": {
                "misto": "",
                "mista": ""
            },
            "diety": {
                "dieta": "",
                "diety": ""
            },
            "zkratkaProduktu": "O2",
            "cisloJidelnicku": "1",
            "multipleNazev": "NČočka s vejcem, cibulka, okurka, čaj, pv - VCO2",
            "version": 5,
            "casKonec": "2025-09-12T15:00:00",
            "casOdhlaseni": "2025-09-12T15:00:00",
            "obrazky": []
        }
    ],

    "dalsi obedy nebudu vypisovat, je to moc dlouhe":[]
}
```

Dulezite informace:

JSON struktura seznamu objednavek:
```json
{
    "table0":[
        {prvek polevka},
        {prvek jidlo1},
        {prvek jidlo2}
    ],
    "table1":[
        {prvek jidlo1},
        {prvek jidlo2},
        {prvek jidlo3}
    ]
    ...
}
```

Kazdy prvek s nazvem tableX odpovida urcitemu dni. V kazdem z techto prvku se nachazi nekolik prvku jidel.

JSON struktura prvku jednotlivych jidel (dulezite info):
```json
{
    "id": 0 / 1 / 2 ...,
    "datum": "15.09.2025",
    "druh_popis": "Polévka" / "Obed1" / "Obed2"...,
    ...
    "nazev": "Vývar s kuskusem" / "Čočka s uzeným masem, kysané zelí, čaj, pv",
    ...
    "zakazaneAlergeny": null,
    "alergeny": [
        ["04","Ryby"],
        ["06","Sójové boby"],
    ],
    ...
    "pocet": 0 / 1 (neobjednano / objednano),

}
```

Sepsane dulezite hodnoty jednotlivych jidel:

| key              | description                                                   | example 1                            | example 2                                  | type    |
|------------------|---------------------------------------------------------------|--------------------------------------|--------------------------------------------|---------|
| id               | id jidla z daneho dne                                         | 0                                    | 1                                          | integer |
| datum            | datum dne                                                     | 15.09.2025                           | 02.10.2025                                 | string  |
| druh_popis       | popis typu jidla                                              | Polévka                              | Obed1                                      | pocet   |
| nazev            | nazev jidla                                                   | Vývar s kuskusem                     | Čočka s uzeným masem, kysané zelí, čaj, pv | pocet   |
| zakazaneAlergeny | nejspis vypsane alergeny, ktere uzivatel nastavil jako spatne | null                                 | ...                                        | ...     |
| alergeny         | alergeny obsazene v jidle                                     | [["04","Ryby"],["06","Sójové boby"]] | []                                         | list    |
| pocet            | stav objednani: 0 = neobjednano, 1 = objednano                | 0                                    | 1                                          | integer |


