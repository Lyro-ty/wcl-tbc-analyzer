from typing import Any


def is_boss_fight(fight_data: dict[str, Any]) -> bool:
    return fight_data.get("encounterID", 0) > 0
