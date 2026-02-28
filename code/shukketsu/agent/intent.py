"""Intent classification for user messages.

Deterministic regex-based classifier that detects what the user wants
and extracts context (report codes, player names, encounter names,
class/spec). Used by the prefetch node to decide what data to fetch
before the LLM runs.
"""

import re
from dataclasses import dataclass, field

# WCL report codes: 16+ alphanumeric chars
_REPORT_CODE_RE = re.compile(r'(?:reports/)?([a-zA-Z0-9]{16,40})')

# Player name: capitalized word 3-15 chars, excluding common words/bosses
_PLAYER_NAME_RE = re.compile(r'\b([A-Z][a-z]{2,15})\b')
_COMMON_WORDS = frozenset({
    "The", "Can", "Please", "What", "How", "Did", "Does", "Show",
    "Tell", "Analyze", "Report", "Check", "Compare", "Pull", "Get",
    "Could", "Would", "Should", "Have", "Been", "Will", "Also",
    "Now", "Then", "Just", "Still", "Only", "Next", "Last", "Both",
    "High", "King", "Gruul", "Magtheridon", "Prince", "Maiden",
    "Moroes", "Nightbane", "Netherspite", "Curator", "Aran",
    "Attumen", "Opera", "Illhoof", "Shade", "Malchezaar",
    "Karazhan", "Raid", "Execution", "Summary", "Kills", "Wipes",
    "Better", "Where", "When", "Which", "Help", "With", "From",
    "About", "Their", "They", "That", "This", "These", "Those",
    "Beast", "Mastery", "Holy", "Shadow", "Feral", "Balance",
    "Restoration", "Protection", "Retribution", "Enhancement",
    "Elemental", "Affliction", "Destruction", "Demonology",
    "Arms", "Fury", "Combat", "Assassination", "Subtlety",
    "Arcane", "Fire", "Frost", "Discipline", "Survival",
    "Marksmanship", "Guardian", "Justicar",
})

# Keyword → specific tool mapping (ordered by specificity)
_SPECIFIC_TOOL_KEYWORDS: list[tuple[re.Pattern[str], str]] = [
    # Multi-word patterns first (more specific)
    (re.compile(r'\bgcd\s+uptime\b', re.I), "get_activity_report"),
    (re.compile(r'\bcast\s+cancel', re.I), "get_cancelled_casts"),
    (re.compile(r'\bcancel+ed\s+cast', re.I), "get_cancelled_casts"),
    (re.compile(r'\bdot\s+manag', re.I), "get_dot_management"),
    (re.compile(r'\bdot\s+refresh', re.I), "get_dot_management"),
    (re.compile(r'\bwipe\s+progress', re.I), "get_wipe_progression"),
    (re.compile(r'\bgear\s+change', re.I), "get_gear_changes"),
    (re.compile(r'\bability\s+breakdown\b', re.I), "get_ability_breakdown"),
    (re.compile(r'\bphase\s+(breakdown|analysis)\b', re.I), "get_phase_analysis"),
    # Single-word patterns
    (re.compile(r'\brotation\b', re.I), "get_rotation_score"),
    (re.compile(r'\bdeaths?\b', re.I), "get_death_analysis"),
    (re.compile(r'\bcooldowns?\b', re.I), "get_cooldown_efficiency"),
    (re.compile(r'\bconsumables?\b', re.I), "get_consumable_check"),
    (re.compile(r'\bflasks?\b', re.I), "get_consumable_check"),
    (re.compile(r'\bfood\b', re.I), "get_consumable_check"),
    (re.compile(r'\bbuffs?\b', re.I), "get_buff_analysis"),
    (re.compile(r'\bdebuffs?\b', re.I), "get_buff_analysis"),
    (re.compile(r'\babilities\b', re.I), "get_ability_breakdown"),
    (re.compile(r'\bgear\b', re.I), "get_gear_changes"),
    (re.compile(r'\benchants?\b', re.I), "get_enchant_gem_check"),
    (re.compile(r'\bgems?\b', re.I), "get_enchant_gem_check"),
    (re.compile(r'\bresource\b', re.I), "get_resource_usage"),
    (re.compile(r'\bmana\b', re.I), "get_resource_usage"),
    (re.compile(r'\brage\b', re.I), "get_resource_usage"),
    (re.compile(r'\benergy\b', re.I), "get_resource_usage"),
    (re.compile(r'\bdots?\b', re.I), "get_dot_management"),
    (re.compile(r'\bcancel', re.I), "get_cancelled_casts"),
    (re.compile(r'\boverheal', re.I), "get_overheal_analysis"),
    (re.compile(r'\bgcd\b', re.I), "get_activity_report"),
    (re.compile(r'\buptime\b', re.I), "get_activity_report"),
    (re.compile(r'\bactivity\b', re.I), "get_activity_report"),
    (re.compile(r'\bphases?\b', re.I), "get_phase_analysis"),
    (re.compile(r'\bwipes?\b', re.I), "get_wipe_progression"),
    (re.compile(r'\bsearch\b', re.I), "search_fights"),
    (re.compile(r'\bfind\b', re.I), "search_fights"),
    (re.compile(r'\bregressions?\b', re.I), "get_regressions"),
]

# Class → specs mapping
_CLASS_SPECS: dict[str, list[str]] = {
    "Warrior": ["Arms", "Fury", "Protection"],
    "Paladin": ["Holy", "Protection", "Retribution", "Justicar"],
    "Hunter": ["BeastMastery", "Marksmanship", "Survival"],
    "Rogue": ["Assassination", "Combat", "Subtlety"],
    "Priest": ["Discipline", "Holy", "Shadow"],
    "Shaman": ["Elemental", "Enhancement", "Restoration"],
    "Mage": ["Arcane", "Fire", "Frost"],
    "Warlock": ["Affliction", "Demonology", "Destruction"],
    "Druid": ["Balance", "Feral", "Guardian", "Restoration"],
}

# Build reverse lookup: spec_name_lower → class_name
_SPEC_TO_CLASS: dict[str, str] = {}
for _cls, _specs in _CLASS_SPECS.items():
    for _spec in _specs:
        _SPEC_TO_CLASS[_spec.lower()] = _cls

# All class names lowercase for detection
_CLASS_NAMES_LOWER = {c.lower(): c for c in _CLASS_SPECS}

# Known encounter names for extraction — sorted longest-first so we try
# the most specific match before shorter substrings.
_ENCOUNTER_NAMES = [
    "Gruul the Dragonkiller",
    "High King Maulgar",
    "Magtheridon",
    "Attumen the Huntsman",
    "Maiden of Virtue",
    "Opera Hall",
    "The Curator",
    "Shade of Aran",
    "Terestian Illhoof",
    "Prince Malchezaar",
    "Netherspite",
    "Nightbane",
    "Moroes",
]
# Build word-boundary regex for each encounter name (prevents "Aran" in "warranty")
_ENCOUNTER_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r'\b' + re.escape(name) + r'\b', re.IGNORECASE), name)
    for name in sorted(_ENCOUNTER_NAMES, key=len, reverse=True)
]
# Also add short aliases that are unambiguous
_ENCOUNTER_ALIASES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r'\bGruul\b', re.I), "Gruul the Dragonkiller"),
    (re.compile(r'\bMaulgar\b', re.I), "High King Maulgar"),
    (re.compile(r'\bAttumen\b', re.I), "Attumen the Huntsman"),
    (re.compile(r'\bMaiden\b', re.I), "Maiden of Virtue"),
    (re.compile(r'\bOpera\b', re.I), "Opera Hall"),
    (re.compile(r'\bCurator\b', re.I), "The Curator"),
    (re.compile(r'\bAran\b', re.I), "Shade of Aran"),
    (re.compile(r'\bIllhoof\b', re.I), "Terestian Illhoof"),
    (re.compile(r'\bPrince\b', re.I), "Prince Malchezaar"),
]

_COMPARE_RE = re.compile(
    r'\b(compare|stack up|versus|vs\.?|how do we|how does our)\b',
    re.IGNORECASE,
)
_BENCHMARK_RE = re.compile(
    r'\b(benchmarks?|targets?)\b', re.IGNORECASE,
)
_LEADERBOARD_RE = re.compile(
    r'\b(leaderboard|top dps|best spec|top spec|ranking)\b', re.IGNORECASE,
)
_PROGRESSION_RE = re.compile(
    r'\b(progression|over time|trend|history)\b', re.IGNORECASE,
)
_PLAYER_ANALYSIS_RE = re.compile(
    r'\b(better|improve|could have|what.+wrong|feedback|analyze\s+\w+\s+in)\b',
    re.IGNORECASE,
)
# "Beast Mastery" as two words → BeastMastery
_BEAST_MASTERY_RE = re.compile(r'\bbeast\s+mastery\b', re.IGNORECASE)


@dataclass
class IntentResult:
    intent: str | None = None
    report_code: str | None = None
    player_names: list[str] = field(default_factory=list)
    encounter_name: str | None = None
    class_name: str | None = None
    spec_name: str | None = None
    specific_tool: str | None = None


def _extract_report_codes(text: str) -> list[str]:
    return [m.group(1) for m in _REPORT_CODE_RE.finditer(text)]


def _extract_player_names(text: str) -> list[str]:
    return [
        m.group(1) for m in _PLAYER_NAME_RE.finditer(text)
        if m.group(1) not in _COMMON_WORDS
    ]


def _extract_encounter_name(text: str) -> str | None:
    """Extract encounter name using word-boundary matching."""
    # Try full names first (longest match)
    for pattern, name in _ENCOUNTER_PATTERNS:
        if pattern.search(text):
            return name
    # Try aliases
    for pattern, name in _ENCOUNTER_ALIASES:
        if pattern.search(text):
            return name
    return None


def _extract_class_spec(text: str) -> tuple[str | None, str | None]:
    text_normalized = _BEAST_MASTERY_RE.sub("BeastMastery", text).lower()
    found_class = None
    found_spec = None

    # Check specs first (more specific than class names)
    for spec_lower, cls_proper in _SPEC_TO_CLASS.items():
        if re.search(r'\b' + re.escape(spec_lower) + r'\b', text_normalized):
            found_spec = next(
                s for s in _CLASS_SPECS[cls_proper]
                if s.lower() == spec_lower
            )
            if found_class is None:
                found_class = cls_proper
            break

    # Then check class names
    if found_class is None:
        for cls_lower, cls_proper in _CLASS_NAMES_LOWER.items():
            if re.search(r'\b' + re.escape(cls_lower) + r'\b', text_normalized):
                found_class = cls_proper
                break

    return found_class, found_spec


def _detect_specific_tool(text: str) -> str | None:
    """Detect specific tool keywords using ordered regex patterns."""
    for pattern, tool_name in _SPECIFIC_TOOL_KEYWORDS:
        if pattern.search(text):
            return tool_name
    return None


def classify_intent(text: str) -> IntentResult:
    """Classify user message into an intent with extracted context."""
    result = IntentResult()
    codes = _extract_report_codes(text)
    result.report_code = codes[0] if codes else None
    result.player_names = _extract_player_names(text)
    result.encounter_name = _extract_encounter_name(text)
    result.class_name, result.spec_name = _extract_class_spec(text)

    # Priority order: specific tool > player analysis > compare > benchmarks
    # > leaderboard > progression > report analysis > unknown

    specific = _detect_specific_tool(text)
    if specific:
        result.intent = "specific_tool"
        result.specific_tool = specific
        return result

    if (result.report_code and result.player_names
            and _PLAYER_ANALYSIS_RE.search(text)):
        result.intent = "player_analysis"
        return result

    if _COMPARE_RE.search(text):
        result.intent = "compare_to_top"
        return result

    if _BENCHMARK_RE.search(text):
        result.intent = "benchmarks"
        return result

    if _LEADERBOARD_RE.search(text):
        result.intent = "leaderboard"
        return result

    if _PROGRESSION_RE.search(text) and result.player_names:
        result.intent = "progression"
        return result

    if result.report_code:
        result.intent = "report_analysis"
        return result

    return result
