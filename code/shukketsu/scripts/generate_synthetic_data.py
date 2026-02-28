"""Generate synthetic training data for LoRA fine-tuning.

Creates 5-10 diverse training examples per tool (30 tools = 150-300 total)
with correct tool call names, parameter names/types, and template responses.
Outputs ChatML-format JSONL for fine-tuning Nemotron 3 Nano 30B.

Usage:
    generate-synthetic-data
    generate-synthetic-data --output data/scratch/custom.jsonl
"""

import argparse
import json
import logging
import random
from pathlib import Path

from shukketsu.agent.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Sample data for generating diverse examples
_REPORT_CODES = [
    "Fn2ACKZtyzc1QLJP", "fb61030ba5a20fd5f51475a7533b57aa",
    "xR4kMnP2qW8jLs6T", "aB3cD4eF5gH6iJ7k",
    "Hy7KmN9pQ2rS4tU6", "wX1yZ3aB5cD7eF9g",
]
_PLAYER_NAMES = [
    "Lyroo", "Flasheal", "Tankboy", "Stabsworth",
    "Frostweave", "Shadowbolt", "Arrowstorm", "Earthtotem",
]
_ENCOUNTERS = [
    "Gruul the Dragonkiller", "High King Maulgar", "Magtheridon",
    "Attumen the Huntsman", "Moroes", "Maiden of Virtue",
    "Opera Hall", "The Curator", "Shade of Aran",
    "Netherspite", "Prince Malchezaar", "Nightbane",
]
_CLASSES_SPECS = [
    ("Warrior", "Arms"), ("Warrior", "Fury"), ("Warrior", "Protection"),
    ("Rogue", "Combat"), ("Rogue", "Assassination"),
    ("Hunter", "Beast Mastery"), ("Hunter", "Survival"),
    ("Mage", "Fire"), ("Mage", "Arcane"),
    ("Warlock", "Destruction"), ("Warlock", "Affliction"),
    ("Priest", "Shadow"), ("Priest", "Holy"),
    ("Paladin", "Retribution"), ("Paladin", "Holy"), ("Paladin", "Protection"),
    ("Shaman", "Enhancement"), ("Shaman", "Elemental"), ("Shaman", "Restoration"),
    ("Druid", "Feral Combat"), ("Druid", "Balance"), ("Druid", "Restoration"),
]
_FIGHT_IDS = [3, 5, 8, 10, 12, 15, 18, 21]


def _rc() -> str:
    return random.choice(_REPORT_CODES)


def _pn() -> str:
    return random.choice(_PLAYER_NAMES)


def _enc() -> str:
    return random.choice(_ENCOUNTERS)


def _fid() -> int:
    return random.choice(_FIGHT_IDS)


def _cls_spec() -> tuple[str, str]:
    return random.choice(_CLASSES_SPECS)


def _example(
    user: str,
    tool_name: str,
    tool_args: dict,
    tool_response: str,
    analysis: str,
) -> dict:
    """Build a single training example in ChatML format."""
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {"name": tool_name, "arguments": tool_args},
                ],
            },
            {"role": "tool", "content": tool_response},
            {"role": "assistant", "content": analysis},
        ],
    }


def _analysis_only(user: str, analysis: str) -> dict:
    """Build a no-tool example where the LLM analyzes existing data."""
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
            {"role": "assistant", "content": analysis},
        ],
    }


def _multi_tool(
    user: str,
    tools: list[tuple[str, dict, str]],
    final_analysis: str,
) -> dict:
    """Build a multi-tool-call training example."""
    msgs: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]
    for tool_name, tool_args, tool_response in tools:
        msgs.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [{"name": tool_name, "arguments": tool_args}],
        })
        msgs.append({"role": "tool", "content": tool_response})
    msgs.append({"role": "assistant", "content": final_analysis})
    return {"messages": msgs}


# ---------------------------------------------------------------------------
# Per-tool example generators
# ---------------------------------------------------------------------------


def _gen_get_raid_execution() -> list[dict]:
    examples = []
    for _ in range(7):
        rc = _rc()
        examples.append(_example(
            f"Analyze report {rc}",
            "get_raid_execution", {"report_code": rc},
            f"Raid Execution for {rc}:\n- Kills: 5\n- Wipes: 2\n"
            f"- Total Deaths: 3\n- Avg Parse: 42%\n- Duration: 1h 23m",
            "## Overview\n\nSolid raid — 5 kills with only 2 wipes. "
            "The 42% average parse shows room for DPS improvement. "
            "3 total deaths is clean execution.\n\n"
            "## Key Issues\n1. Average parse (42%) is below 50th percentile\n"
            "2. Two wipes suggest mechanics need tightening\n\n"
            "## Positives\n- Low death count\n- Clean kill progression",
        ))
    # Alternate phrasing
    rc = _rc()
    examples.append(_example(
        f"How did our raid go in {rc}?",
        "get_raid_execution", {"report_code": rc},
        f"Raid Execution for {rc}:\n- Kills: 8\n- Wipes: 0\n"
        f"- Deaths: 1\n- Avg Parse: 67%",
        "## Overview\n\nExcellent raid night — 8/8 with zero wipes. "
        "67% average parse is above median. Single death across all pulls.",
    ))
    return examples


def _gen_get_fight_details() -> list[dict]:
    examples = []
    for _ in range(6):
        rc, fid = _rc(), _fid()
        examples.append(_example(
            f"Show me fight {fid} in report {rc}",
            "get_fight_details", {"report_code": rc, "fight_id": fid},
            f"Fight {fid}: Gruul the Dragonkiller (Kill, 4m 32s)\n"
            f"  Lyroo - Arms Warrior - 1,023 DPS (45% parse)\n"
            f"  Flasheal - Holy Priest - 892 HPS (62% parse)",
            "## Gruul Kill (4m 32s)\n\nLyroo's 45% parse is below raid average. "
            "Flasheal's healing output is solid at 62%.",
        ))
    return examples


def _gen_get_my_performance() -> list[dict]:
    examples = []
    for _ in range(6):
        pn, enc = _pn(), _enc()
        examples.append(_example(
            f"How has {pn} been doing on {enc}?",
            "get_my_performance",
            {"player_name": pn, "encounter_name": enc},
            f"Performance for {pn} on {enc}:\n"
            f"  Best: 1,245 DPS (78% parse)\n  Median: 1,089 DPS (55% parse)\n"
            f"  Kills: 4 | Deaths: 1",
            f"## {pn} on {enc}\n\n{pn}'s best parse of 78% shows potential. "
            f"The gap between best (1,245) and median (1,089) DPS suggests "
            f"inconsistency. 1 death in 4 kills is acceptable.",
        ))
    # bests_only variant
    pn, enc = _pn(), _enc()
    examples.append(_example(
        f"What are {pn}'s personal records on {enc}?",
        "get_my_performance",
        {"player_name": pn, "encounter_name": enc, "bests_only": True},
        f"Personal records for {pn} on {enc}:\n"
        f"  Best DPS: 1,456 (89% parse)\n  Best Parse: 89%",
        f"{pn}'s personal best of 89% on {enc} is competitive.",
    ))
    return examples


def _gen_get_top_rankings() -> list[dict]:
    examples = []
    for _ in range(5):
        enc = _enc()
        cls, spec = _cls_spec()
        examples.append(_example(
            f"Show top {spec} {cls} rankings on {enc}",
            "get_top_rankings",
            {"encounter_name": enc, "class_name": cls, "spec_name": spec},
            f"Top 10 {spec} {cls} on {enc}:\n"
            f"  1. Zhar - 2,345 DPS (99%)\n  2. Krel - 2,210 DPS (98%)\n"
            f"  3. Vynn - 2,108 DPS (97%)",
            f"Top {spec} {cls}s on {enc} are pushing 2,300+ DPS. "
            f"The 99th percentile benchmark is useful for setting goals.",
        ))
    return examples


def _gen_compare_to_top() -> list[dict]:
    examples = []
    for _ in range(5):
        pn, enc = _pn(), _enc()
        cls, spec = _cls_spec()
        examples.append(_example(
            f"Compare {pn} to top {spec} {cls}s on {enc}",
            "compare_to_top",
            {
                "encounter_name": enc, "player_name": pn,
                "class_name": cls, "spec_name": spec,
            },
            f"Comparison: {pn} vs Top 10 {spec} {cls} on {enc}:\n"
            f"  {pn}: 1,023 DPS (45%)\n  Top 10 avg: 2,100 DPS (96%)\n"
            f"  Gap: 1,077 DPS (51 percentile points)",
            f"{pn} is 51 points below top {spec} {cls}s on {enc}. "
            f"The 1,077 DPS gap suggests significant room for improvement.",
        ))
    return examples


def _gen_get_progression() -> list[dict]:
    examples = []
    for _ in range(6):
        pn, enc = _pn(), _enc()
        examples.append(_example(
            f"Show me {pn}'s progression on {enc}",
            "get_progression",
            {"character_name": pn, "encounter_name": enc},
            f"Progression for {pn} on {enc}:\n"
            f"  Week 1: 890 DPS (32%)\n  Week 2: 1,045 DPS (48%)\n"
            f"  Week 3: 1,156 DPS (58%)\n  Trend: +15% DPS/week",
            f"{pn} is on a strong upward trend on {enc}, gaining ~15% per week. "
            f"At this rate, they'll hit 75th percentile within 2 weeks.",
        ))
    return examples


def _gen_get_deaths_and_mechanics() -> list[dict]:
    examples = []
    for _ in range(5):
        enc = _enc()
        examples.append(_example(
            f"Show death and mechanics summary for {enc}",
            "get_deaths_and_mechanics", {"encounter_name": enc},
            f"Deaths & Mechanics on {enc}:\n"
            f"  Total Deaths: 7 across 4 kills\n"
            f"  Most deaths: Stabsworth (3)\n"
            f"  Interrupts: 45/50 (90%)\n  Dispels: 12/15 (80%)",
            f"## {enc} Mechanics\n\nStabsworth dying 3 times across 4 kills "
            f"needs attention. Interrupt rate is good (90%) but dispels "
            f"could improve (80%).",
        ))
    return examples


def _gen_search_fights() -> list[dict]:
    examples = []
    for _ in range(5):
        enc = _enc()
        examples.append(_example(
            f"Find all {enc} fights",
            "search_fights", {"encounter_name": enc},
            f"Found 6 fights for {enc}:\n"
            f"  Fight 8: Kill (4m 32s) - Report abc123...\n"
            f"  Fight 12: Kill (5m 01s) - Report def456...\n"
            f"  Fight 3: Wipe at 35% (2m 15s) - Report abc123...",
            f"Found 6 {enc} attempts across recent reports. "
            f"Kill times range from 4m32s to 5m01s.",
        ))
    return examples


def _gen_get_spec_leaderboard() -> list[dict]:
    examples = []
    for _ in range(5):
        enc = _enc()
        examples.append(_example(
            f"What specs top DPS on {enc}?",
            "get_spec_leaderboard", {"encounter_name": enc},
            f"DPS Leaderboard for {enc}:\n"
            f"  1. Fire Mage - 2,456 avg DPS\n"
            f"  2. Destruction Warlock - 2,312 avg DPS\n"
            f"  3. Beast Mastery Hunter - 2,198 avg DPS",
            f"Fire Mages lead on {enc} with 2,456 avg DPS, followed by "
            f"Destruction Warlocks and BM Hunters.",
        ))
    return examples


def _gen_resolve_my_fights() -> list[dict]:
    examples = []
    examples.append(_example(
        "Show my recent fights",
        "resolve_my_fights", {},
        "Recent fights for tracked characters:\n"
        "  Lyroo - Gruul (Kill, 4m32s) - Fight 8 in Fn2ACK...\n"
        "  Lyroo - Magtheridon (Kill, 6m01s) - Fight 12 in Fn2ACK...",
        "Found recent kills for Lyroo on Gruul and Magtheridon.",
    ))
    enc = _enc()
    examples.append(_example(
        f"Find my recent {enc} fights",
        "resolve_my_fights", {"encounter_name": enc, "count": 5},
        f"Recent {enc} fights:\n  Lyroo - Kill (4m32s) - Fight 8",
        f"Found your recent {enc} kills.",
    ))
    return examples


def _gen_get_wipe_progression() -> list[dict]:
    examples = []
    for _ in range(5):
        rc, enc = _rc(), _enc()
        examples.append(_example(
            f"Show wipe-to-kill progression for {enc} in {rc}",
            "get_wipe_progression",
            {"report_code": rc, "encounter_name": enc},
            f"Wipe Progression for {enc}:\n"
            f"  Attempt 1: Wipe at 65% (1m 45s)\n"
            f"  Attempt 2: Wipe at 32% (3m 02s)\n"
            f"  Attempt 3: Kill (4m 32s)",
            f"Clean 3-attempt kill on {enc}. Each attempt showed clear "
            f"progression — 65% → 32% → Kill.",
        ))
    return examples


def _gen_get_regressions() -> list[dict]:
    examples = []
    pn = _pn()
    examples.append(_example(
        f"Has {pn} gotten worse recently?",
        "get_regressions", {"player_name": pn},
        f"Performance trends for {pn}:\n"
        f"  Gruul: 45% → 38% (-7 points) REGRESSION\n"
        f"  Moroes: 52% → 61% (+9 points) IMPROVEMENT",
        f"{pn} is regressing on Gruul (-7 points) but improving on Moroes "
        f"(+9). Focus should be on Gruul consistency.",
    ))
    examples.append(_example(
        "Check for performance regressions",
        "get_regressions", {},
        "Regressions detected:\n  Lyroo on Gruul: -7 points\n"
        "  Tankboy on Magtheridon: -12 points",
        "Two regressions detected. Tankboy's -12 on Magtheridon is the "
        "most concerning.",
    ))
    return examples


def _gen_compare_raid_to_top() -> list[dict]:
    examples = []
    for _ in range(5):
        rc = _rc()
        examples.append(_example(
            f"How does our raid compare to top guilds? Report {rc}",
            "compare_raid_to_top", {"report_code": rc},
            "Raid vs Top Guilds:\n"
            "  Your avg kill time: 4m 45s\n  Top guilds avg: 2m 58s\n"
            "  Your avg parse: 42%\n  Top guilds avg parse: 85%",
            "Your raid is 1m47s slower than top guilds and 43 parse points "
            "behind. The DPS gap is the primary factor.",
        ))
    return examples


def _gen_compare_two_raids() -> list[dict]:
    examples = []
    for _ in range(4):
        ra, rb = _rc(), _rc()
        examples.append(_example(
            f"Compare raids {ra} and {rb}",
            "compare_two_raids", {"report_a": ra, "report_b": rb},
            "Raid Comparison:\n"
            "  Report A: 5 kills, 2 wipes, avg parse 42%\n"
            "  Report B: 6 kills, 1 wipe, avg parse 51%\n"
            "  Improvement: +9% avg parse, -1 wipe",
            "Clear improvement between the two raids. Parse jumped 9% and "
            "wipes decreased. The trend is positive.",
        ))
    return examples


def _gen_get_activity_report() -> list[dict]:
    examples = []
    for _ in range(6):
        rc, fid, pn = _rc(), _fid(), _pn()
        examples.append(_example(
            f"Check {pn}'s GCD uptime in fight {fid} of {rc}",
            "get_activity_report",
            {"report_code": rc, "fight_id": fid, "player_name": pn},
            f"Activity Report for {pn} (Fight {fid}):\n"
            f"  GCD Uptime: 82.3% (FAIR)\n  CPM: 28.5\n"
            f"  Largest Gap: 4.2s at 2:15\n  Total Downtime: 38.5s",
            f"{pn}'s GCD uptime of 82.3% is FAIR — targeting 85%+ would "
            f"add significant DPS. The 4.2s gap at 2:15 suggests a movement "
            f"or death mechanic.",
        ))
    return examples


def _gen_get_rotation_score() -> list[dict]:
    examples = []
    for _ in range(6):
        rc, fid, pn = _rc(), _fid(), _pn()
        examples.append(_example(
            f"Pull a rotation score for {pn} on fight {fid} in {rc}",
            "get_rotation_score",
            {"report_code": rc, "fight_id": fid, "player_name": pn},
            f"Rotation Score for {pn}: 72/100 (GOOD)\n"
            f"  GCD Uptime: 87.3% (GOOD)\n  CPM: 31.2 (GOOD)\n"
            f"  CD Efficiency: 68% (NEEDS WORK)",
            f"## Rotation: {pn} — 72/100 (GOOD)\n\n"
            f"GCD uptime and CPM are solid, but cooldown efficiency at 68% "
            f"is leaving throughput on the table. Use cooldowns on CD.",
        ))
    return examples


def _gen_get_cooldown_efficiency() -> list[dict]:
    examples = []
    for _ in range(6):
        rc, fid, pn = _rc(), _fid(), _pn()
        examples.append(_example(
            f"Check {pn}'s cooldown usage in fight {fid} of {rc}",
            "get_cooldown_efficiency",
            {"report_code": rc, "fight_id": fid, "player_name": pn},
            f"Cooldown Efficiency for {pn}:\n"
            f"  Recklessness: 2/3 uses (67%)\n"
            f"  Death Wish: 1/2 uses (50%)\n"
            f"  Overall: 58% efficiency",
            f"{pn}'s cooldown efficiency is low at 58%. Missed 1 Recklessness "
            f"and 1 Death Wish. These missed CDs cost ~200+ DPS.",
        ))
    return examples


def _gen_get_consumable_check() -> list[dict]:
    examples = []
    for _ in range(6):
        rc, fid, pn = _rc(), _fid(), _pn()
        examples.append(_example(
            f"Check {pn}'s consumables in fight {fid} of {rc}",
            "get_consumable_check",
            {"report_code": rc, "fight_id": fid, "player_name": pn},
            f"Consumable Check for {pn}:\n"
            f"  Flask: Flask of Relentless Assault ✓\n"
            f"  Food: Roasted Clefthoof ✓\n"
            f"  Oil: Superior Wizard Oil ✗ MISSING\n"
            f"  Elixir: None detected",
            f"{pn} is missing weapon oil — Superior Wizard Oil would add "
            f"~40 DPS. Flask and food are good.",
        ))
    return examples


def _gen_get_ability_breakdown() -> list[dict]:
    examples = []
    for _ in range(5):
        rc, fid, pn = _rc(), _fid(), _pn()
        examples.append(_example(
            f"Show {pn}'s ability breakdown in fight {fid} of {rc}",
            "get_ability_breakdown",
            {"report_code": rc, "fight_id": fid, "player_name": pn},
            f"Ability Breakdown for {pn}:\n"
            f"  Mortal Strike: 28.5% (412k)\n"
            f"  Whirlwind: 22.1% (319k)\n"
            f"  Slam: 18.3% (264k)\n"
            f"  Execute: 12.7% (183k)",
            f"{pn}'s ability distribution looks correct for Arms Warrior. "
            f"Mortal Strike as top damage is expected. Execute at 12.7% "
            f"suggests good sub-20% execution.",
        ))
    return examples


def _gen_get_buff_analysis() -> list[dict]:
    examples = []
    for _ in range(5):
        rc, fid, pn = _rc(), _fid(), _pn()
        examples.append(_example(
            f"Show {pn}'s buff uptimes in fight {fid} of {rc}",
            "get_buff_analysis",
            {"report_code": rc, "fight_id": fid, "player_name": pn},
            f"Buff Analysis for {pn}:\n"
            f"  Flask of Relentless Assault: 100%\n"
            f"  Battle Shout: 92%\n"
            f"  Windfury Totem: 88%\n"
            f"  Drums of Battle: 45%",
            "Flask uptime is perfect. Battle Shout at 92% is good. "
            "Drums at 45% suggests the group isn't rotating effectively.",
        ))
    return examples


def _gen_get_overheal_analysis() -> list[dict]:
    examples = []
    for _ in range(5):
        rc, fid, pn = _rc(), _fid(), _pn()
        examples.append(_example(
            f"Check {pn}'s overhealing in fight {fid} of {rc}",
            "get_overheal_analysis",
            {"report_code": rc, "fight_id": fid, "player_name": pn},
            f"Overheal Analysis for {pn}:\n"
            f"  Greater Heal: 35% overheal\n"
            f"  Circle of Healing: 22% overheal\n"
            f"  Prayer of Mending: 8% overheal\n"
            f"  Overall: 24% overheal",
            f"{pn}'s 24% overall overhealing is slightly high. Greater Heal "
            f"at 35% overheal suggests downranking or switching to Flash Heal "
            f"for spot healing would be more mana-efficient.",
        ))
    return examples


def _gen_get_death_analysis() -> list[dict]:
    examples = []
    for _ in range(5):
        rc, fid, pn = _rc(), _fid(), _pn()
        examples.append(_example(
            f"Show death recap for {pn} in fight {fid} of {rc}",
            "get_death_analysis",
            {"report_code": rc, "fight_id": fid, "player_name": pn},
            f"Death Analysis for {pn} (Fight {fid}):\n"
            f"  Killing blow: Ground Slam (12,453 damage)\n"
            f"  -2s: Hurtful Strike (8,234)\n"
            f"  -4s: Melee (3,456)\n"
            f"  HP at -4s: 11,200 (full)",
            f"{pn} died to Ground Slam. Full HP 4s before death means this "
            f"was unavoidable tank damage, not a positioning error.",
        ))
    return examples


def _gen_get_cancelled_casts() -> list[dict]:
    examples = []
    for _ in range(5):
        rc, fid, pn = _rc(), _fid(), _pn()
        examples.append(_example(
            f"Check {pn}'s cancelled casts in fight {fid} of {rc}",
            "get_cancelled_casts",
            {"report_code": rc, "fight_id": fid, "player_name": pn},
            f"Cancelled Casts for {pn}:\n"
            f"  Total: 8 cancelled / 145 started (5.5%)\n"
            f"  Shadow Bolt: 4 cancelled\n  Immolate: 2 cancelled",
            f"{pn}'s 5.5% cancel rate is acceptable. The Shadow Bolt cancels "
            f"may be from movement — check if they correlate with mechanics.",
        ))
    return examples


def _gen_get_resource_usage() -> list[dict]:
    examples = []
    for _ in range(5):
        rc, fid, pn = _rc(), _fid(), _pn()
        examples.append(_example(
            f"Show {pn}'s resource usage in fight {fid} of {rc}",
            "get_resource_usage",
            {"report_code": rc, "fight_id": fid, "player_name": pn},
            f"Resource Usage for {pn}:\n"
            f"  Resource: Mana\n  Avg: 65%\n  Min: 12%\n"
            f"  Time at zero: 0s\n  Potions used: 1",
            f"{pn} managed mana well — never hit zero despite only 1 potion. "
            f"Average 65% means room for more aggressive casting.",
        ))
    return examples


def _gen_get_dot_management() -> list[dict]:
    examples = []
    for _ in range(5):
        rc, fid, pn = _rc(), _fid(), _pn()
        examples.append(_example(
            f"Check {pn}'s DoT management in fight {fid} of {rc}",
            "get_dot_management",
            {"report_code": rc, "fight_id": fid, "player_name": pn},
            f"DoT Management for {pn}:\n"
            f"  Corruption: 94% uptime, 2 early refreshes\n"
            f"  Immolate: 87% uptime, 5 early refreshes\n"
            f"  Clipped ticks: 3",
            f"{pn}'s Corruption uptime is excellent (94%). Immolate at 87% "
            f"with 5 early refreshes suggests refreshing too early — wait for "
            f"the last tick before reapplying.",
        ))
    return examples


def _gen_get_gear_changes() -> list[dict]:
    examples = []
    for _ in range(4):
        pn = _pn()
        rc_old, rc_new = _rc(), _rc()
        examples.append(_example(
            f"Compare {pn}'s gear between {rc_old} and {rc_new}",
            "get_gear_changes",
            {
                "player_name": pn,
                "report_code_old": rc_old, "report_code_new": rc_new,
            },
            f"Gear Changes for {pn}:\n"
            f"  Chest: +8 ilvl (T4 → T4.5)\n"
            f"  Weapon: +12 ilvl (new drop)\n"
            f"  Overall: +3.2 avg ilvl",
            f"{pn} upgraded chest and weapon for +3.2 avg ilvl. "
            f"The weapon upgrade alone should add ~50-80 DPS.",
        ))
    return examples


def _gen_get_phase_analysis() -> list[dict]:
    examples = []
    for _ in range(5):
        rc, fid, pn = _rc(), _fid(), _pn()
        examples.append(_example(
            f"Show phase breakdown for {pn} in fight {fid} of {rc}",
            "get_phase_analysis",
            {"report_code": rc, "fight_id": fid, "player_name": pn},
            f"Phase Analysis for {pn} (Fight {fid}):\n"
            f"  Phase 1 (0-30%): 1,234 DPS\n"
            f"  Phase 2 (30-60%): 1,089 DPS\n"
            f"  Phase 3 (60-100%): 956 DPS",
            f"{pn}'s DPS drops from 1,234 to 956 across phases. "
            f"The phase 3 drop likely correlates with movement mechanics.",
        ))
    return examples


def _gen_get_enchant_gem_check() -> list[dict]:
    examples = []
    for _ in range(5):
        rc, fid, pn = _rc(), _fid(), _pn()
        examples.append(_example(
            f"Check {pn}'s enchants and gems in fight {fid} of {rc}",
            "get_enchant_gem_check",
            {"report_code": rc, "fight_id": fid, "player_name": pn},
            f"Enchant/Gem Check for {pn}:\n"
            f"  Missing enchant: Gloves (no enchant)\n"
            f"  Missing enchant: Boots (no enchant)\n"
            f"  Empty gem slot: Chest (1 empty)\n"
            f"  Enchanted: 7/9 slots",
            f"{pn} is missing enchants on gloves and boots, plus an empty gem "
            f"socket. These are free DPS — roughly 30-50 DPS combined.",
        ))
    return examples


def _gen_get_encounter_benchmarks() -> list[dict]:
    examples = []
    for _ in range(5):
        enc = _enc()
        examples.append(_example(
            f"Show benchmarks for {enc}",
            "get_encounter_benchmarks", {"encounter_name": enc},
            f"Benchmarks for {enc}:\n"
            f"  Top guild avg kill time: 2m 58s\n"
            f"  Avg deaths: 0.3\n  Zero-death rate: 78%\n"
            f"  Avg parse: 85%",
            f"Top guilds kill {enc} in under 3 minutes with near-zero deaths. "
            f"85% avg parse is the target for competitive performance.",
        ))
    return examples


def _gen_get_spec_benchmark() -> list[dict]:
    examples = []
    for _ in range(5):
        enc = _enc()
        cls, spec = _cls_spec()
        examples.append(_example(
            f"What should a {spec} {cls} be doing on {enc}?",
            "get_spec_benchmark",
            {"encounter_name": enc, "class_name": cls, "spec_name": spec},
            f"Benchmark for {spec} {cls} on {enc}:\n"
            f"  Target DPS: 1,800+\n  GCD Uptime: 88%+\n"
            f"  CD Efficiency: 85%+\n"
            f"  Top ability: Mortal Strike (28% damage)",
            f"A good {spec} {cls} should target 1,800+ DPS on {enc} with "
            f"88%+ GCD uptime. Focus on cooldown usage (85%+ efficiency).",
        ))
    return examples


def _gen_multi_tool_examples() -> list[dict]:
    """Generate multi-tool chain examples for common workflows."""
    examples = []

    # Player analysis workflow: raid execution → activity report
    rc, pn = _rc(), _pn()
    examples.append(_multi_tool(
        f"What could {pn} do better in report {rc}?",
        [
            (
                "get_raid_execution", {"report_code": rc},
                "Raid: 5 kills, 1 wipe, avg parse 45%",
            ),
            (
                "get_activity_report",
                {"report_code": rc, "fight_id": 8, "player_name": pn},
                "Activity: GCD uptime 78%, CPM 26",
            ),
        ],
        f"## {pn}'s Performance\n\n{pn}'s 78% GCD uptime is the biggest "
        f"issue — targeting 85%+ would add significant DPS.",
    ))

    # Benchmark comparison workflow
    rc = _rc()
    examples.append(_multi_tool(
        f"How does report {rc} compare to benchmarks?",
        [
            (
                "get_raid_execution", {"report_code": rc},
                "Raid: 5 kills, avg parse 42%, avg duration 4m45s",
            ),
            (
                "get_encounter_benchmarks",
                {"encounter_name": "Gruul the Dragonkiller"},
                "Benchmark: avg kill 2m58s, avg parse 85%",
            ),
        ],
        "Your Gruul kills (4m45s) are nearly 2 minutes slower than "
        "top guilds (2m58s). The 43-point parse gap is the primary factor.",
    ))

    # Specific tool after context
    rc, pn = _rc(), _pn()
    examples.append(_multi_tool(
        f"Check {pn}'s rotation and cooldowns in fight 8 of {rc}",
        [
            (
                "get_rotation_score",
                {"report_code": rc, "fight_id": 8, "player_name": pn},
                "Rotation: 72/100, GCD 87%, CPM 31, CD eff 58%",
            ),
            (
                "get_cooldown_efficiency",
                {"report_code": rc, "fight_id": 8, "player_name": pn},
                "CDs: Recklessness 2/3 (67%), Death Wish 1/2 (50%)",
            ),
        ],
        f"## {pn}'s Rotation & Cooldowns\n\n"
        f"**Rotation: 72/100 (GOOD)** — GCD uptime and CPM are solid.\n\n"
        f"**Cooldowns: 58% (NEEDS WORK)** — Missed 1 Recklessness and "
        f"1 Death Wish. Fixing this alone would add ~150 DPS.",
    ))

    return examples


def _gen_conversation_context_examples() -> list[dict]:
    """Generate examples where the LLM uses prior conversation context."""
    examples = []

    # Follow-up question referencing prior report
    rc, pn = _rc(), _pn()
    example = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyze report {rc}"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {"name": "get_raid_execution", "arguments": {"report_code": rc}},
                ],
            },
            {"role": "tool", "content": "Raid: 5 kills, avg parse 42%"},
            {
                "role": "assistant",
                "content": "Good raid — 5 kills. Average parse of 42% shows "
                "room for improvement.",
            },
            {"role": "user", "content": f"Now check {pn}'s cooldowns"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "name": "get_cooldown_efficiency",
                        "arguments": {
                            "report_code": rc,
                            "fight_id": 8,
                            "player_name": pn,
                        },
                    },
                ],
            },
            {
                "role": "tool",
                "content": f"Cooldown efficiency for {pn}: 62%",
            },
            {
                "role": "assistant",
                "content": f"{pn}'s cooldown efficiency of 62% is below the "
                f"70% threshold. Focus on using cooldowns on CD.",
            },
        ],
    }
    examples.append(example)

    return examples


def _gen_error_recovery_examples() -> list[dict]:
    """Generate examples where the LLM recovers from tool errors."""
    examples = []

    enc = _enc()
    example = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Search for {enc}"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {"name": "search_fights", "arguments": {}},
                ],
            },
            {
                "role": "tool",
                "content": "Error: encounter_name: Field required",
            },
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "name": "search_fights",
                        "arguments": {"encounter_name": enc},
                    },
                ],
            },
            {
                "role": "tool",
                "content": f"Found 4 fights for {enc}",
            },
            {
                "role": "assistant",
                "content": f"Found 4 {enc} fights across recent reports.",
            },
        ],
    }
    examples.append(example)

    return examples


# Map tool name → generator function
_TOOL_GENERATORS = {
    "get_raid_execution": _gen_get_raid_execution,
    "get_fight_details": _gen_get_fight_details,
    "get_my_performance": _gen_get_my_performance,
    "get_top_rankings": _gen_get_top_rankings,
    "compare_to_top": _gen_compare_to_top,
    "get_progression": _gen_get_progression,
    "get_deaths_and_mechanics": _gen_get_deaths_and_mechanics,
    "search_fights": _gen_search_fights,
    "get_spec_leaderboard": _gen_get_spec_leaderboard,
    "resolve_my_fights": _gen_resolve_my_fights,
    "get_wipe_progression": _gen_get_wipe_progression,
    "get_regressions": _gen_get_regressions,
    "compare_raid_to_top": _gen_compare_raid_to_top,
    "compare_two_raids": _gen_compare_two_raids,
    "get_activity_report": _gen_get_activity_report,
    "get_rotation_score": _gen_get_rotation_score,
    "get_cooldown_efficiency": _gen_get_cooldown_efficiency,
    "get_consumable_check": _gen_get_consumable_check,
    "get_ability_breakdown": _gen_get_ability_breakdown,
    "get_buff_analysis": _gen_get_buff_analysis,
    "get_overheal_analysis": _gen_get_overheal_analysis,
    "get_death_analysis": _gen_get_death_analysis,
    "get_cancelled_casts": _gen_get_cancelled_casts,
    "get_resource_usage": _gen_get_resource_usage,
    "get_dot_management": _gen_get_dot_management,
    "get_gear_changes": _gen_get_gear_changes,
    "get_phase_analysis": _gen_get_phase_analysis,
    "get_enchant_gem_check": _gen_get_enchant_gem_check,
    "get_encounter_benchmarks": _gen_get_encounter_benchmarks,
    "get_spec_benchmark": _gen_get_spec_benchmark,
}


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic training data for all 30 tools"
    )
    parser.add_argument(
        "--output", type=str,
        default="data/scratch/training_data_synthetic.jsonl",
        help="Output JSONL file path",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducibility",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    random.seed(args.seed)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    all_examples: list[dict] = []
    tool_counts: dict[str, int] = {}

    # Generate per-tool examples
    for tool_name, gen_fn in _TOOL_GENERATORS.items():
        examples = gen_fn()
        tool_counts[tool_name] = len(examples)
        all_examples.extend(examples)

    # Add multi-tool chain examples
    multi = _gen_multi_tool_examples()
    all_examples.extend(multi)

    # Add conversation context examples
    context = _gen_conversation_context_examples()
    all_examples.extend(context)

    # Add error recovery examples
    recovery = _gen_error_recovery_examples()
    all_examples.extend(recovery)

    # Shuffle
    random.shuffle(all_examples)

    # Write
    with open(output_path, "w") as f:
        for example in all_examples:
            f.write(json.dumps(example) + "\n")

    logger.info(
        "Generated %d examples (%d per-tool + %d multi-tool + %d context "
        "+ %d recovery) → %s",
        len(all_examples),
        sum(tool_counts.values()),
        len(multi), len(context), len(recovery),
        output_path,
    )

    # Print tool coverage
    logger.info("Tool coverage:")
    for tool_name, count in sorted(tool_counts.items()):
        logger.info("  %s: %d examples", tool_name, count)

    uncovered = set(_TOOL_GENERATORS.keys()) - set(tool_counts.keys())
    if uncovered:
        logger.warning("Uncovered tools: %s", uncovered)
    else:
        logger.info("All 30 tools covered!")


if __name__ == "__main__":
    main()
