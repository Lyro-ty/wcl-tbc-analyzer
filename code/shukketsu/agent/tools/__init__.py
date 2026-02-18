"""Agent tools package -- re-exports ALL_TOOLS for graph binding."""

from shukketsu.agent.tool_utils import set_session_factory
from shukketsu.agent.tools.event_tools import (
    get_activity_report,
    get_cancelled_casts,
    get_consumable_check,
    get_cooldown_efficiency,
    get_cooldown_windows,
    get_death_analysis,
    get_dot_management,
    get_enchant_gem_check,
    get_gear_changes,
    get_phase_analysis,
    get_resource_usage,
    get_rotation_score,
)
from shukketsu.agent.tools.player_tools import (
    compare_to_top,
    get_deaths_and_mechanics,
    get_fight_details,
    get_my_performance,
    get_progression,
    get_regressions,
    get_spec_leaderboard,
    get_top_rankings,
    get_wipe_progression,
    resolve_my_fights,
    search_fights,
)
from shukketsu.agent.tools.raid_tools import (
    compare_raid_to_top,
    compare_two_raids,
    get_raid_execution,
)
from shukketsu.agent.tools.table_tools import (
    get_ability_breakdown,
    get_buff_analysis,
    get_overheal_analysis,
    get_trinket_performance,
)

ALL_TOOLS = [
    # Player tools (11)
    get_my_performance,
    get_top_rankings,
    compare_to_top,
    get_fight_details,
    get_progression,
    get_deaths_and_mechanics,
    search_fights,
    get_spec_leaderboard,
    resolve_my_fights,
    get_wipe_progression,
    get_regressions,
    # Raid tools (3)
    compare_raid_to_top,
    compare_two_raids,
    get_raid_execution,
    # Table-data tools (4)
    get_ability_breakdown,
    get_buff_analysis,
    get_overheal_analysis,
    get_trinket_performance,
    # Event-data tools (12)
    get_death_analysis,
    get_activity_report,
    get_cooldown_efficiency,
    get_cooldown_windows,
    get_cancelled_casts,
    get_consumable_check,
    get_resource_usage,
    get_dot_management,
    get_rotation_score,
    get_gear_changes,
    get_phase_analysis,
    get_enchant_gem_check,
]

__all__ = [
    "ALL_TOOLS",
    "set_session_factory",
    # Player tools
    "get_my_performance",
    "get_top_rankings",
    "compare_to_top",
    "get_fight_details",
    "get_progression",
    "get_deaths_and_mechanics",
    "search_fights",
    "get_spec_leaderboard",
    "resolve_my_fights",
    "get_wipe_progression",
    "get_regressions",
    # Raid tools
    "compare_raid_to_top",
    "compare_two_raids",
    "get_raid_execution",
    # Table-data tools
    "get_ability_breakdown",
    "get_buff_analysis",
    "get_overheal_analysis",
    "get_trinket_performance",
    # Event-data tools
    "get_death_analysis",
    "get_activity_report",
    "get_cooldown_efficiency",
    "get_cooldown_windows",
    "get_cancelled_casts",
    "get_consumable_check",
    "get_resource_usage",
    "get_dot_management",
    "get_rotation_score",
    "get_gear_changes",
    "get_phase_analysis",
    "get_enchant_gem_check",
]
