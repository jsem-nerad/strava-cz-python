"""Práce s profily: přihlášení bez zadávání údajů v kódu.

Profil se založí jednou z příkazové řádky:

    strava-cz profile add skola --username vase.jmeno --canteen 3753

Heslo přitom skončí v klíčence operačního systému, ne v tomhle souboru ani nikde
jinde v repozitáři. Skript pak jen řekne, který profil chce.
"""

from __future__ import annotations

from strava_cz import (
    KeyringUnavailableError,
    ProfileNotFoundError,
    ProfileStore,
    StravaCZ,
)


def vypis_profily() -> None:
    """Ukáže, co je uložené. Nepřihlašuje se a heslo nikde nečte."""
    store = ProfileStore()
    profily = store.list()
    if not profily:
        print("Zatím žádné profily. Založte první: strava-cz profile add skola ...")
        print(f"Soubor by byl v {store.path}")
        return

    for profil in profily:
        vychozi = " (výchozí)" if profil.name == store.default_name else ""
        print(f"{profil.name}{vychozi}: {profil.username} @ {profil.canteen_number}")
        print(f"    heslo: {profil.secret.description}")


def main() -> None:
    vypis_profily()

    # Bez jména se vezme výchozí profil.
    with StravaCZ.from_profile("skola") as strava:
        print(f"\n{strava.user}\n")

        strava.menu.fetch()

        # Dny, na které jídelna neobjednává automaticky - objednat na ně jde,
        # ale samy se neobjednají.
        for den in strava.menu.get_days(auto_ordered=False):
            jidla = ", ".join(j.name for j in den.orderable)
            print(f"{den.date:%a %d.%m.} si musíte objednat sami: {jidla}")


if __name__ == "__main__":
    try:
        main()
    except ProfileNotFoundError as chyba:
        raise SystemExit(f"Profil není: {chyba}") from chyba
    except KeyringUnavailableError as chyba:
        # Typicky server bez grafického prostředí.
        raise SystemExit(f"Klíčenka není k dispozici: {chyba}") from chyba
