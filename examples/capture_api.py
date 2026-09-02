"""Nahraje odpověď z API do souboru, aby se z ní dal udělat test fixture.

Osobní údaje z přihlašovací odpovědi se nahradí zástupnými hodnotami, ale
**výsledek si před commitem stejně projděte**.

    export STRAVA_USERNAME="vase.jmeno"
    export STRAVA_PASSWORD="VaseHeslo123"
    export STRAVA_CANTEEN="3753"
    python examples/capture_api.py objednavky > tests/fixtures/menu_nove.json
"""

import argparse
import json
import os
import sys

from strava_cz import StravaCZ

#: Pole přihlašovací odpovědi, která identifikují konkrétního člověka.
PERSONAL_FIELDS = {
    "jmeno": "Testovací Uživatel",
    "email": "test@example.com",
    "id": "test.user",
    "vs": "0",
    "evCislo": "0",
    "bakalarId": "0",
    "trida": "1.",
}


def sanitise(data: object) -> object:
    """Nahradí osobní údaje a session identifikátory zástupnými hodnotami."""
    if isinstance(data, dict):
        clean = {}
        for key, value in data.items():
            if key == "sid":
                clean[key] = "01C6FCF02A7146159BC5F245A57AF29F"
            elif key in PERSONAL_FIELDS and isinstance(value, str):
                clean[key] = PERSONAL_FIELDS[key]
            else:
                clean[key] = sanitise(value)
        return clean
    if isinstance(data, list):
        return [sanitise(item) for item in data]
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "endpoint",
        nargs="?",
        default="objednavky",
        help="který endpoint nahrát (výchozí: objednavky)",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="neodstraňovat osobní údaje",
    )
    args = parser.parse_args()

    with StravaCZ(
        os.environ["STRAVA_USERNAME"],
        os.environ["STRAVA_PASSWORD"],
        os.environ["STRAVA_CANTEEN"],
    ) as strava:
        user = strava.user
        if args.endpoint == "login":
            # Přihlášení proběhlo už v konstruktoru, znovu ho zopakovat nejde.
            print("Odpověď z /api/login si vypište přímo z klienta.", file=sys.stderr)
        payload = {
            "cislo": user.canteen_number,
            "sid": user.sid,
            "s5url": user.s5url,
            "url": user.s5url,
            "lang": strava.language,
            "konto": user.balance,
            "podminka": "",
            "ignoreCert": False,
        }
        data = strava._request(args.endpoint, payload, authenticated=True)

    if not args.raw:
        data = sanitise(data)
    json.dump(data, sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
