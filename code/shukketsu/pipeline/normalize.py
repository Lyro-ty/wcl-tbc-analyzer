from typing import Any


def compute_dps(total_damage: int, duration_ms: int) -> float:
    if duration_ms <= 0:
        return 0.0
    return total_damage / (duration_ms / 1000)


def compute_hps(total_healing: int, duration_ms: int) -> float:
    if duration_ms <= 0:
        return 0.0
    return total_healing / (duration_ms / 1000)


def is_boss_fight(fight_data: dict[str, Any]) -> bool:
    return fight_data.get("encounterID", 0) > 0
