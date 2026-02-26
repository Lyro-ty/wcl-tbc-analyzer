"""Benchmark agent tools (2 tools)."""

import json

from shukketsu.agent.tool_utils import _format_duration, db_tool
from shukketsu.db import queries as bq


@db_tool
async def get_encounter_benchmarks(session, encounter_name: str) -> str:
    """Get performance benchmarks for an encounter computed from top guild kills.
    Returns kill stats, death rates, composition, consumable rates.
    Use this to establish what top players/guilds achieve before analyzing a player."""
    result = await session.execute(
        bq.GET_ENCOUNTER_BENCHMARK,
        {"encounter_name": f"%{encounter_name}%"},
    )
    row = result.fetchone()
    if row is None:
        return f"No benchmark data found for '{encounter_name}'."

    data = row.benchmarks
    if isinstance(data, str):
        data = json.loads(data)

    lines = [f"Benchmarks for {row.encounter_name} (sample: {row.sample_size} kills)\n"]

    # Kill Stats
    kill = data.get("kill", {})
    lines.append("## Kill Stats")
    lines.append(f"  Avg duration: {_format_duration(int(kill.get('avg_duration_ms', 0)))}")
    lines.append(
        f"  Median duration: {_format_duration(int(kill.get('median_duration_ms', 0)))}"
    )
    lines.append(
        f"  Fastest kill: {_format_duration(int(kill.get('fastest_duration_ms', 0)))}"
    )

    # Deaths
    deaths = data.get("deaths", {})
    lines.append("\n## Deaths")
    lines.append(f"  Avg deaths/player: {deaths.get('avg_deaths_per_player', 'N/A')}")
    zero_pct = deaths.get("pct_zero_death_players")
    if zero_pct is not None:
        lines.append(f"  Zero-death rate: {zero_pct * 100:.0f}%")

    # Consumable Usage
    consumables = data.get("consumables", {})
    if consumables:
        lines.append("\n## Consumable Usage")
        for category, rate in sorted(consumables.items()):
            lines.append(f"  {category}: {rate * 100:.0f}%")

    # Common Specs (top 10)
    composition = data.get("composition", [])
    if composition:
        lines.append("\n## Common Specs (top 10)")
        for entry in composition[:10]:
            cls = entry.get("class", "Unknown")
            spec = entry.get("spec", "Unknown")
            avg_count = entry.get("avg_count", 0)
            appearances = entry.get("appearances", entry.get("count", 0))
            lines.append(
                f"  {cls} {spec}: "
                f"avg {avg_count:.1f}/raid "
                f"({appearances} appearances)"
            )

    # Spec DPS Targets
    by_spec = data.get("by_spec", {})
    if by_spec:
        lines.append("\n## Spec DPS Targets")
        sorted_specs = sorted(
            by_spec.items(),
            key=lambda kv: kv[1].get("avg_dps", 0),
            reverse=True,
        )
        for spec_key, spec_data in sorted_specs:
            parts = spec_key.split("_", 1)
            cls = parts[0]
            spec = parts[1] if len(parts) > 1 else ""
            avg_dps = spec_data.get("avg_dps", 0)
            gcd = spec_data.get("avg_gcd_uptime")
            cpm = spec_data.get("avg_cpm")
            extra = ""
            if gcd is not None:
                extra += f" | GCD: {gcd:.0f}%"
            if cpm is not None:
                extra += f" | CPM: {cpm:.1f}"
            lines.append(f"  {cls} {spec}: avg {avg_dps:,.1f} DPS{extra}")

    return "\n".join(lines)


@db_tool
async def get_spec_benchmark(
    session,
    encounter_name: str,
    class_name: str,
    spec_name: str,
) -> str:
    """Get spec-specific performance targets for an encounter from top players.
    Returns DPS target, GCD uptime target, top abilities, buff uptimes,
    and cooldown efficiency benchmarks."""
    result = await session.execute(
        bq.GET_ENCOUNTER_BENCHMARK,
        {"encounter_name": f"%{encounter_name}%"},
    )
    row = result.fetchone()
    if row is None:
        return f"No benchmark data found for '{encounter_name}'."

    data = row.benchmarks
    if isinstance(data, str):
        data = json.loads(data)

    by_spec = data.get("by_spec", {})
    spec_key = f"{class_name}_{spec_name}"
    spec_data = by_spec.get(spec_key)

    if spec_data is None:
        available = [k.replace("_", " ", 1) for k in by_spec]
        return (
            f"No benchmark data for {class_name} {spec_name} on {row.encounter_name}. "
            f"Available specs: {', '.join(sorted(available))}"
        )

    lines = [
        f"Benchmark targets for {class_name} {spec_name} on {row.encounter_name} "
        f"(sample: {spec_data.get('sample_size', 'N/A')} players)\n"
    ]

    # Performance Targets
    lines.append("## Performance Targets")
    lines.append(f"  Avg DPS: {spec_data.get('avg_dps', 0):,.1f}")
    lines.append(f"  Median DPS: {spec_data.get('median_dps', 0):,.1f}")
    lines.append(f"  P75 DPS: {spec_data.get('p75_dps', 0):,.1f}")

    # Activity
    gcd = spec_data.get("avg_gcd_uptime")
    cpm = spec_data.get("avg_cpm")
    if gcd is not None or cpm is not None:
        lines.append("\n## Activity")
        if gcd is not None:
            lines.append(f"  GCD Uptime: {gcd:.1f}%")
        if cpm is not None:
            lines.append(f"  Casts/Min: {cpm:.1f}")

    # Top Abilities
    abilities = spec_data.get("top_abilities", [])
    if abilities:
        lines.append("\n## Top Abilities")
        for ab in abilities:
            lines.append(f"  {ab['name']}: {ab['avg_damage_pct'] * 100:.1f}% of damage")

    # Key Buff Uptimes
    buffs = spec_data.get("avg_buff_uptimes", {})
    if buffs:
        lines.append("\n## Key Buff Uptimes")
        for buff_name, uptime in sorted(
            buffs.items(), key=lambda kv: kv[1], reverse=True
        ):
            lines.append(f"  {buff_name}: {uptime:.1f}%")

    # Cooldown Efficiency
    cooldowns = spec_data.get("avg_cooldown_efficiency", {})
    if cooldowns:
        lines.append("\n## Cooldown Efficiency")
        for cd_name, cd_data in cooldowns.items():
            uses = cd_data.get("avg_times_used", 0)
            eff = cd_data.get("avg_efficiency", 0)
            lines.append(f"  {cd_name}: avg {uses:.1f} uses, {eff:.0f}% efficiency")

    return "\n".join(lines)
