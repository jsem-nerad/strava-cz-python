"""Allow ``python -m strava_cz`` as well as the installed ``strava-cz`` command."""

from .cli import main

raise SystemExit(main())
