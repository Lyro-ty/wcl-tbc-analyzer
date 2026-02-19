"""SQL query constants organized by domain.

Import from here for backwards compatibility:
    from shukketsu.db import queries as q
    q.MY_PERFORMANCE  # still works

Domain files:
    player.py     — Player/encounter-level queries (14)
    raid.py       — Raid-level comparison queries (4)
    table_data.py — Table-data (--with-tables) queries (4)
    event.py      — Event-data (--with-events) queries (16)
    api.py        — REST API-only queries (23)
"""

from shukketsu.db.queries.api import *  # noqa: F401, F403
from shukketsu.db.queries.event import *  # noqa: F401, F403
from shukketsu.db.queries.player import *  # noqa: F401, F403
from shukketsu.db.queries.raid import *  # noqa: F401, F403
from shukketsu.db.queries.table_data import *  # noqa: F401, F403
