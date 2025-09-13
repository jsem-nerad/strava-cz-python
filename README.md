# Strava.cz Python API

High level API pro interakci s webovou aplikaci Strava.cz udelane v Pythonu ciste pomoci request knihovny.

Ve slozce [notes](https://github.com/jsem-nerad/strava-cz-python/tree/main/notes) muzete najit veskere moje poznatky, ktere jsem zjistil o internim fungovani aplikace Strava.cz.

## Features
- Prihlaseni/odhlaseni
- Vypsani prefiltrovaneho jidelnicku 
- Objednavani jidel podle ID jidla


## Usage

```python
from strava_cz import StravaCZ

strava = StravaCZ(username="your.username", password="YourPassword123", canteen_number="3753")
print(strava.user)
print(strava.get_orders_list())
print(strava.is_ordered(4))
strava.order_meal(4)
strava.order_meals(3, 6)
strava.logout()
```


## to-do

- [ ] Univerzalni datum
- [ ] Moznost detailni filtrace jidelnicku
- [ ] Lepe zorganizovat kod
- [ ] Nahrat jako knihovnu na PyPi
- [ ] Lepe zdokumentovat pouziti

## Co bude dal?

Planuji udelat aplikaci, ktera bude uzivateli automaticky objednavat obedy podle jeho preferenci.

Prosim, nepouzivejte tuto aplikaci k nekalym ucelum. Pouzivejte ji pouze s dobrymi zamery.


## Pomoz mi pls

Nasel jsi chybu nebo mas navrh na zlepseni? Skvele! Vytvor prosim [bug report](https://github.com/jsem-nerad/strava-cz-python/issues/new?labels=bug) nebo [feature request](https://github.com/jsem-nerad/strava-cz-python/issues/new?labels=enhancement), hodne mi tim muzes pomoct.

Udelal jsi sam nejake zlepseni? Jeste lepsi! Kazdy pull request je vitan.




