"""Ukázka použití knihovny strava-cz.

Přihlašovací údaje se berou z proměnných prostředí, aby se heslo nedostalo do kódu:

    export STRAVA_USERNAME="vase.jmeno"
    export STRAVA_PASSWORD="VaseHeslo123"
    export STRAVA_CANTEEN="3753"
    python examples/example.py

Ve výchozím stavu jen čte. **S proměnnou STRAVA_OPRAVDU_ZAPISOVAT=1 sahá na skutečný účet:
objedná první tři dny, které jdou objednat, a pak zruší VŠECHNY objednávky na účtu**, včetně
těch, které jste si udělali sami. Pouštějte ji tak jen na účtu, na kterém na tom nezáleží.
"""

import os

from strava_cz import (
    DuplicateMealError,
    InsufficientBalanceError,
    MealNotFoundError,
    MealNotOrderableError,
    MealType,
    StravaCZ,
    StravaError,
)

USERNAME = os.environ["STRAVA_USERNAME"]
PASSWORD = os.environ["STRAVA_PASSWORD"]
CANTEEN = os.environ["STRAVA_CANTEEN"]


def main() -> None:
    # Context manager se sám postará o odhlášení a uzavření spojení.
    with StravaCZ(USERNAME, PASSWORD, CANTEEN) as strava:
        # ---------------------------------------------------------- uživatel
        print(strava.user)
        print(f"\nZůstatek: {strava.user.balance:.2f} {strava.user.currency}")

        # ------------------------------------------------------- jídelníček
        strava.menu.fetch()
        print(f"\n{strava.menu!r}\n")
        strava.menu.print()

        if strava.menu.parse_warnings:
            print("Části odpovědi se nepodařilo zpracovat:")
            for warning in strava.menu.parse_warnings:
                print(f"  - {warning}")

        # ---------------------------------------------------------- filtry
        # Ve výchozím stavu se nic neskrývá; filtruje se explicitně.
        objednatelne = strava.menu.get_meals(orderable=True)
        obedy = strava.menu.get_meals(meal_types=[MealType.MAIN], orderable=True)
        polevky = strava.menu.get_meals(meal_types=[MealType.SOUP])
        objednane = strava.menu.get_meals(ordered=True)

        print(f"\nObjednatelných jídel: {len(objednatelne)}")
        print(f"  z toho hlavních jídel: {len(obedy)}")
        print(f"Polévek v jídelníčku:   {len(polevky)}")
        print(f"Už objednáno:           {len(objednane)}")

        # Filtrování podle data
        tento_tyden = strava.menu.get_days(date_from="2026-09-07", date_to="2026-09-11")
        print(f"Dnů v zadaném rozsahu:  {len(tento_tyden)}")

        # Dny, kdy se nevaří, se musí vyžádat výslovně
        volno = [d for d in strava.menu.get_days(include_no_school=True) if d.no_school]
        print(f"Dnů, kdy se nevaří:     {len(volno)}")

        # -------------------------------------------------- proč to nejde
        print("\nJídla, která teď objednat nejde:")
        for meal in strava.menu.get_meals(orderable=False)[:5]:
            print(f"  {meal.date} {meal.name[:32]:<34} {meal.order_restriction.description}")

        # ------------------------------------------------------ iterace
        print("\nPrvní tři dny:")
        for day in list(strava.menu)[:3]:
            znacka = "objednáno" if day.ordered else "nic neobjednáno"
            print(f"  {day.date:%a %d.%m.} - {len(day.meals)} jídel, {znacka}")
            for meal in day.orderable:
                print(f"      [{meal.id}] {meal.name}  ({meal.price:g} Kč)")

        # -------------------------------------------------- objednávání
        if os.environ.get("STRAVA_OPRAVDU_ZAPISOVAT") != "1":
            print("\nDál by se objednávalo a rušilo, viz začátek souboru. Končím.")
            return

        if not obedy:
            print("\nNení co objednat, končím.")
            return

        prvni = obedy[0]
        print(f"\nObjednávám [{prvni.id}] {prvni.name} na {prvni.date}")

        try:
            vysledek = strava.menu.order_meals(prvni.id)
            print(f"  {vysledek}")
            print(f"  změněno: {vysledek.changed}")
            print(f"  zůstatek po objednání: {strava.user.balance:.2f} Kč")
        except MealNotOrderableError as exc:
            print(f"  Tohle jídlo objednat nejde: {exc}")
        except InsufficientBalanceError as exc:
            print(f"  Nedostatečný zůstatek: {exc}")
        except MealNotFoundError as exc:
            print(f"  Neznámé ID jídla: {exc}")
        except DuplicateMealError as exc:
            print(f"  Duplicitní jídla: {exc}")

        # Když nechcete výjimky, nechte si vrátit přehled toho, co se povedlo.
        vysledek = strava.menu.order_meals(
            *[m.id for m in obedy[:3]],
            continue_on_error=True,
        )
        print(f"\nHromadná objednávka: {vysledek}")
        for meal_id, chyba in vysledek.failed:
            print(f"  jídlo {meal_id}: {chyba}")

        # ------------------------------------------------------- zrušení
        objednane = strava.menu.get_meals(ordered=True)
        if objednane:
            print(f"\nRuším {len(objednane)} objednávek")
            strava.menu.cancel_meals(*[m.id for m in objednane], continue_on_error=True)

        print(f"\nKonečný zůstatek: {strava.user.balance:.2f} {strava.user.currency}")


if __name__ == "__main__":
    try:
        main()
    except StravaError as exc:
        raise SystemExit(f"Chyba: {exc}") from exc
