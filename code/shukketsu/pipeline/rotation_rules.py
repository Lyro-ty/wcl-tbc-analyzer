"""Per-spec rotation validation rules (APL framework)."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RotationRule:
    priority: int  # Lower = higher priority
    spell_id: int
    name: str
    rule_type: str  # "cast_count", "uptime", "priority_order", "cd_usage"
    description: str
    # Thresholds (meaning depends on rule_type)
    min_value: float = 0.0  # Minimum expected value to pass


@dataclass
class RuleResult:
    rule_name: str
    description: str
    passed: bool
    actual_value: float
    expected_value: float
    detail: str = ""


@dataclass
class RotationReport:
    spec: str
    rules_checked: int
    rules_passed: int
    score_pct: float
    violations: list[dict] = field(default_factory=list)


# 3 spec rotation definitions
SPEC_ROTATIONS: dict[str, list[RotationRule]] = {
    "Fury": [
        RotationRule(
            1, 23881, "Bloodthirst",
            "cd_usage", "Bloodthirst used on cooldown (6s CD)",
            min_value=60.0,
        ),
        RotationRule(
            2, 25231, "Whirlwind",
            "cd_usage", "Whirlwind used on cooldown (10s CD)",
            min_value=50.0,
        ),
        RotationRule(
            3, 29707, "Heroic Strike",
            "cast_count", "Heroic Strike used as rage dump (>10 casts/min)",
            min_value=10.0,
        ),
        RotationRule(
            4, 29801, "Rampage",
            "uptime", "Rampage buff maintained (>80% uptime)",
            min_value=80.0,
        ),
    ],
    "Combat": [
        RotationRule(
            1, 6774, "Slice and Dice",
            "uptime", "Slice and Dice uptime >90%",
            min_value=90.0,
        ),
        RotationRule(
            2, 26862, "Sinister Strike",
            "cast_count", "Sinister Strike as primary builder (>15/min)",
            min_value=15.0,
        ),
        RotationRule(
            3, 13877, "Blade Flurry",
            "cd_usage", "Blade Flurry used on cooldown (2min CD)",
            min_value=60.0,
        ),
        RotationRule(
            4, 13750, "Adrenaline Rush",
            "cd_usage", "Adrenaline Rush used on cooldown (5min CD)",
            min_value=50.0,
        ),
    ],
    "Arcane": [
        RotationRule(
            1, 30451, "Arcane Blast",
            "cast_count", "Arcane Blast as primary spell (>20/min)",
            min_value=20.0,
        ),
        RotationRule(
            2, 12042, "Arcane Power",
            "cd_usage", "Arcane Power used on cooldown (3min CD)",
            min_value=60.0,
        ),
        RotationRule(
            3, 12051, "Evocation",
            "cd_usage", "Evocation used for mana recovery",
            min_value=50.0,
        ),
        RotationRule(
            4, 12043, "Presence of Mind",
            "cd_usage", "Presence of Mind used on cooldown (3min CD)",
            min_value=50.0,
        ),
    ],
}


def evaluate_rotation(
    cast_events: list[dict],
    buff_uptimes: dict[int, float],
    spec: str,
    fight_duration_ms: int,
) -> RotationReport:
    """Evaluate a player's rotation against spec-specific rules.

    Args:
        cast_events: Player's cast events (sorted by timestamp).
        buff_uptimes: Dict[spell_id -> uptime_pct] from buff_uptimes table.
        spec: Player's spec name.
        fight_duration_ms: Total fight duration.

    Returns:
        RotationReport with score and per-rule results.
    """
    rules = SPEC_ROTATIONS.get(spec, [])
    if not rules:
        return RotationReport(
            spec=spec, rules_checked=0, rules_passed=0, score_pct=0.0,
        )

    fight_min = fight_duration_ms / 60_000
    fight_sec = fight_duration_ms / 1000

    # Count casts per spell
    spell_counts: dict[int, int] = {}
    spell_timestamps: dict[int, list[int]] = {}
    for event in cast_events:
        sid = event.get("abilityGameID", 0)
        spell_counts[sid] = spell_counts.get(sid, 0) + 1
        spell_timestamps.setdefault(sid, []).append(
            event.get("timestamp", 0)
        )

    violations = []
    rules_passed = 0

    for rule in rules:
        actual = 0.0
        passed = False
        detail = ""

        if rule.rule_type == "cast_count":
            count = spell_counts.get(rule.spell_id, 0)
            actual = round(count / fight_min, 1) if fight_min > 0 else 0
            passed = actual >= rule.min_value
            detail = f"{count} casts ({actual}/min)"

        elif rule.rule_type == "uptime":
            actual = buff_uptimes.get(rule.spell_id, 0.0)
            passed = actual >= rule.min_value
            detail = f"{actual}% uptime"

        elif rule.rule_type == "cd_usage":
            count = spell_counts.get(rule.spell_id, 0)
            # Estimate max uses from fight duration + CD
            cd_map = {
                23881: 6, 25231: 10, 13877: 120, 13750: 300,
                12042: 180, 12051: 480, 12043: 180,
            }
            cd_sec = cd_map.get(rule.spell_id, 180)
            max_uses = (
                int(fight_sec // cd_sec) + 1 if fight_sec > 0 else 1
            )
            actual = (
                round(count / max_uses * 100, 1) if max_uses > 0 else 0
            )
            passed = actual >= rule.min_value
            detail = f"{count}/{max_uses} uses ({actual}%)"

        if passed:
            rules_passed += 1
        else:
            violations.append({
                "rule": rule.name,
                "description": rule.description,
                "actual": actual,
                "expected": rule.min_value,
                "detail": detail,
            })

    score = (
        round(rules_passed / len(rules) * 100, 1) if rules else 0.0
    )

    return RotationReport(
        spec=spec,
        rules_checked=len(rules),
        rules_passed=rules_passed,
        score_pct=score,
        violations=violations,
    )
