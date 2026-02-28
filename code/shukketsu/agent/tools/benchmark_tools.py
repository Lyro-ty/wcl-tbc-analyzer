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
    kill = data.get("kill_stats", {})
    lines.append("## Kill Stats")
    lines.append(f"  Avg duration: {_format_duration(int(kill.get('avg_duration_ms', 0)))}")
    lines.append(
        f"  Median duration: {_format_duration(int(kill.get('median_duration_ms', 0)))}"
    )
    lines.append(
        f"  Fastest kill: {_format_duration(int(kill.get('min_duration_ms', 0)))}"
    )

    # Deaths
    deaths = data.get("deaths", {})
    lines.append("\n## Deaths")
    avg_deaths = deaths.get("avg_deaths")
    lines.append(
        f"  Avg deaths/player: {avg_deaths:.1f}" if avg_deaths is not None else
        "  Avg deaths/player: N/A"
    )
    zero_pct = deaths.get("zero_death_pct")
    if zero_pct is not None:
        lines.append(f"  Zero-death rate: {zero_pct:.0f}%")

    # Consumable Usage
    consumables = data.get("consumables", [])
    if consumables:
        lines.append("\n## Consumable Usage")
        for entry in consumables:
            category = entry.get("category", "unknown")
            usage_pct = entry.get("usage_pct", 0)
            lines.append(f"  {category}: {usage_pct * 100:.0f}%")

    # Common Specs (top 10)
    composition = data.get("composition", [])
    if composition:
        lines.append("\n## Common Specs (top 10)")
        for entry in composition[:10]:
            cls = entry.get("class", "Unknown")
            spec = entry.get("spec", "Unknown")
            avg_count = entry.get("avg_count", 0)
            lines.append(f"  {cls} {spec}: avg {avg_count:.1f}/raid")

    # Spec DPS Targets (top 15)
    by_spec = data.get("by_spec", {})
    if by_spec:
        lines.append("\n## Spec DPS Targets")
        sorted_specs = sorted(
            by_spec.items(),
            key=lambda kv: kv[1].get("dps", {}).get("avg_dps", 0),
            reverse=True,
        )
        for spec_label, spec_data in sorted_specs[:15]:
            dps_data = spec_data.get("dps", {})
            gcd_data = spec_data.get("gcd", {})
            avg_dps = dps_data.get("avg_dps", 0)
            if avg_dps == 0:
                continue
            gcd = gcd_data.get("avg_gcd_uptime")
            cpm = gcd_data.get("avg_cpm")
            extra = ""
            if gcd is not None:
                extra += f" | GCD: {gcd:.0f}%"
            if cpm is not None:
                extra += f" | CPM: {cpm:.1f}"
            lines.append(f"  {spec_label}: avg {avg_dps:,.1f} DPS{extra}")

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
    spec_key = f"{spec_name} {class_name}"
    spec_data = by_spec.get(spec_key)

    if spec_data is None:
        available = sorted(by_spec.keys())
        return (
            f"No benchmark data for {spec_name} {class_name} on {row.encounter_name}. "
            f"Available specs: {', '.join(available)}"
        )

    dps_data = spec_data.get("dps", {})
    gcd_data = spec_data.get("gcd", {})

    lines = [
        f"Benchmark targets for {spec_name} {class_name} on {row.encounter_name} "
        f"(sample: {dps_data.get('sample_size', 'N/A')} players)\n"
    ]

    # Performance Targets
    lines.append("## Performance Targets")
    lines.append(f"  Avg DPS: {dps_data.get('avg_dps', 0):,.1f}")
    lines.append(f"  Median DPS: {dps_data.get('median_dps', 0):,.1f}")
    lines.append(f"  P75 DPS: {dps_data.get('p75_dps', 0):,.1f}")

    # Activity
    gcd = gcd_data.get("avg_gcd_uptime")
    cpm = gcd_data.get("avg_cpm")
    if gcd is not None or cpm is not None:
        lines.append("\n## Activity")
        if gcd is not None:
            lines.append(f"  GCD Uptime: {gcd:.1f}%")
        if cpm is not None:
            lines.append(f"  Casts/Min: {cpm:.1f}")

    # Top Abilities
    abilities = spec_data.get("abilities", [])
    if abilities:
        lines.append("\n## Top Abilities")
        for ab in abilities:
            lines.append(
                f"  {ab['ability_name']}: {ab['avg_damage_pct'] * 100:.1f}% of damage"
            )

    # Key Buff Uptimes
    buffs = spec_data.get("buffs", [])
    if buffs:
        lines.append("\n## Key Buff Uptimes")
        for b in sorted(buffs, key=lambda x: x["avg_uptime"], reverse=True):
            lines.append(f"  {b['buff_name']}: {b['avg_uptime']:.1f}%")

    # Cooldown Efficiency
    cooldowns = spec_data.get("cooldowns", [])
    if cooldowns:
        lines.append("\n## Cooldown Efficiency")
        for cd in cooldowns:
            lines.append(
                f"  {cd['ability_name']}: "
                f"avg {cd['avg_uses']:.1f} uses, "
                f"{cd['avg_efficiency']:.0f}% efficiency"
            )

    return "\n".join(lines)
