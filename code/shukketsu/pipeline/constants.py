"""TBC class/spec data and boss name lists."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ClassSpec:
    class_name: str
    spec_name: str
    role: str  # "dps", "healer", "tank"


TBC_SPECS: tuple[ClassSpec, ...] = (
    # Warrior
    ClassSpec(class_name="Warrior", spec_name="Arms", role="dps"),
    ClassSpec(class_name="Warrior", spec_name="Fury", role="dps"),
    ClassSpec(class_name="Warrior", spec_name="Protection", role="tank"),
    # Paladin
    ClassSpec(class_name="Paladin", spec_name="Holy", role="healer"),
    ClassSpec(class_name="Paladin", spec_name="Protection", role="tank"),
    ClassSpec(class_name="Paladin", spec_name="Retribution", role="dps"),
    # Hunter
    ClassSpec(class_name="Hunter", spec_name="Beast Mastery", role="dps"),
    ClassSpec(class_name="Hunter", spec_name="Marksmanship", role="dps"),
    ClassSpec(class_name="Hunter", spec_name="Survival", role="dps"),
    # Rogue
    ClassSpec(class_name="Rogue", spec_name="Assassination", role="dps"),
    ClassSpec(class_name="Rogue", spec_name="Combat", role="dps"),
    ClassSpec(class_name="Rogue", spec_name="Subtlety", role="dps"),
    # Priest
    ClassSpec(class_name="Priest", spec_name="Discipline", role="healer"),
    ClassSpec(class_name="Priest", spec_name="Holy", role="healer"),
    ClassSpec(class_name="Priest", spec_name="Shadow", role="dps"),
    # Shaman
    ClassSpec(class_name="Shaman", spec_name="Elemental", role="dps"),
    ClassSpec(class_name="Shaman", spec_name="Enhancement", role="dps"),
    ClassSpec(class_name="Shaman", spec_name="Restoration", role="healer"),
    # Mage
    ClassSpec(class_name="Mage", spec_name="Arcane", role="dps"),
    ClassSpec(class_name="Mage", spec_name="Fire", role="dps"),
    ClassSpec(class_name="Mage", spec_name="Frost", role="dps"),
    # Warlock
    ClassSpec(class_name="Warlock", spec_name="Affliction", role="dps"),
    ClassSpec(class_name="Warlock", spec_name="Demonology", role="dps"),
    ClassSpec(class_name="Warlock", spec_name="Destruction", role="dps"),
    # Druid
    ClassSpec(class_name="Druid", spec_name="Balance", role="dps"),
    ClassSpec(class_name="Druid", spec_name="Feral", role="dps"),
    ClassSpec(class_name="Druid", spec_name="Restoration", role="healer"),
)

TBC_DPS_SPECS: tuple[ClassSpec, ...] = tuple(s for s in TBC_SPECS if s.role == "dps")
TBC_HEALER_SPECS: tuple[ClassSpec, ...] = tuple(s for s in TBC_SPECS if s.role == "healer")
TBC_TANK_SPECS: tuple[ClassSpec, ...] = tuple(s for s in TBC_SPECS if s.role == "tank")

TBC_ZONES: dict[str, list[str]] = {
    "Karazhan": [
        "Attumen the Huntsman",
        "Moroes",
        "Maiden of Virtue",
        "Opera Event",
        "The Curator",
        "Shade of Aran",
        "Terestian Illhoof",
        "Netherspite",
        "Chess Event",
        "Prince Malchezaar",
        "Nightbane",
    ],
    "Gruul's Lair": [
        "High King Maulgar",
        "Gruul the Dragonkiller",
    ],
    "Magtheridon's Lair": [
        "Magtheridon",
    ],
    "Serpentshrine Cavern": [
        "Hydross the Unstable",
        "The Lurker Below",
        "Leotheras the Blind",
        "Fathom-Lord Karathress",
        "Morogrim Tidewalker",
        "Lady Vashj",
    ],
    "Tempest Keep": [
        "Al'ar",
        "Void Reaver",
        "High Astromancer Solarian",
        "Kael'thas Sunstrider",
    ],
    "Hyjal Summit": [
        "Rage Winterchill",
        "Anetheron",
        "Kaz'rogal",
        "Azgalor",
        "Archimonde",
    ],
    "Black Temple": [
        "High Warlord Naj'entus",
        "Supremus",
        "Shade of Akama",
        "Teron Gorefiend",
        "Gurtogg Bloodboil",
        "Reliquary of Souls",
        "Mother Shahraz",
        "Illidari Council",
        "Illidan Stormrage",
    ],
    "Sunwell Plateau": [
        "Kalecgos",
        "Brutallus",
        "Felmyst",
        "Eredar Twins",
        "M'uru",
        "Kil'jaeden",
    ],
}

TBC_BOSS_NAMES: frozenset[str] = frozenset(
    boss for bosses in TBC_ZONES.values() for boss in bosses
)

FRESH_ZONES: dict[str, list[str]] = {
    "Naxxramas": [
        "Anub'Rekhan", "Grand Widow Faerlina", "Maexxna",
        "Noth the Plaguebringer", "Heigan the Unclean", "Loatheb",
        "Instructor Razuvious", "Gothik the Harvester", "The Four Horsemen",
        "Patchwerk", "Grobbulus", "Gluth", "Thaddius",
        "Sapphiron", "Kel'Thuzad",
    ],
}

FRESH_BOSS_NAMES: frozenset[str] = frozenset(
    boss for bosses in FRESH_ZONES.values() for boss in bosses
)

ALL_BOSS_NAMES: frozenset[str] = TBC_BOSS_NAMES | FRESH_BOSS_NAMES


@dataclass(frozen=True)
class CooldownDef:
    spell_id: int
    name: str
    cooldown_sec: int
    duration_sec: int = 0  # Actual buff duration (0 = instant/passive)


# Classic Fresh / TBC major throughput cooldowns per class.
# spell_id values are WCL abilityGameID (WoW spell IDs).
CLASSIC_COOLDOWNS: dict[str, list[CooldownDef]] = {
    "Warrior": [
        CooldownDef(12292, "Death Wish", 180, 30),
        CooldownDef(1719, "Recklessness", 900, 15),
        CooldownDef(12328, "Sweeping Strikes", 30, 10),
    ],
    "Paladin": [
        CooldownDef(31884, "Avenging Wrath", 180, 20),
    ],
    "Hunter": [
        CooldownDef(3045, "Rapid Fire", 300, 15),
        CooldownDef(19574, "Bestial Wrath", 120, 18),
        CooldownDef(34692, "The Beast Within", 120, 18),
    ],
    "Rogue": [
        CooldownDef(13750, "Adrenaline Rush", 300, 15),
        CooldownDef(13877, "Blade Flurry", 120, 15),
        CooldownDef(14177, "Cold Blood", 180, 0),
    ],
    "Priest": [
        CooldownDef(10060, "Power Infusion", 180, 15),
        CooldownDef(33206, "Pain Suppression", 120, 8),
        CooldownDef(15487, "Silence", 45, 0),
    ],
    "Shaman": [
        CooldownDef(2825, "Bloodlust", 600, 40),
        CooldownDef(16166, "Elemental Mastery", 180, 0),
    ],
    "Mage": [
        CooldownDef(12042, "Arcane Power", 180, 15),
        CooldownDef(12051, "Evocation", 480, 8),
        CooldownDef(11129, "Combustion", 180, 0),
        CooldownDef(12472, "Icy Veins", 180, 20),
    ],
    "Warlock": [
        CooldownDef(18708, "Fel Domination", 900, 0),
        CooldownDef(18288, "Amplify Curse", 180, 0),
    ],
    "Druid": [
        CooldownDef(29166, "Innervate", 360, 20),
        CooldownDef(17116, "Nature's Swiftness", 180, 0),
        CooldownDef(33891, "Tree of Life", 0, 0),
    ],
}


# --- Consumable / Prep Check definitions ---

@dataclass(frozen=True)
class ConsumableDef:
    spell_id: int
    name: str
    category: str  # "flask", "elixir", "food", "weapon", "potion", "scroll"
    min_uptime_pct: float  # Expected minimum uptime to count as "present"


# Role mapping: spec name → role for consumable checks
ROLE_BY_SPEC: dict[str, str] = {
    # Melee DPS
    "Arms": "melee_dps", "Fury": "melee_dps",
    "Retribution": "melee_dps",
    "Combat": "melee_dps", "Assassination": "melee_dps", "Subtlety": "melee_dps",
    "Enhancement": "melee_dps",
    "Feral": "melee_dps",
    # Ranged DPS
    "Beast Mastery": "ranged_dps", "Marksmanship": "ranged_dps", "Survival": "ranged_dps",
    # Caster DPS
    "Shadow": "caster_dps",
    "Elemental": "caster_dps",
    "Arcane": "caster_dps", "Fire": "caster_dps", "Frost": "caster_dps",
    "Affliction": "caster_dps", "Demonology": "caster_dps", "Destruction": "caster_dps",
    "Balance": "caster_dps",
    # Healers
    "Holy": "healer", "Discipline": "healer",
    "Restoration": "healer",
    # Tanks
    "Protection": "tank",
}

# Consumables expected per role. spell_id values are WCL buff IDs.
REQUIRED_CONSUMABLES: dict[str, list[ConsumableDef]] = {
    "all": [
        # Food buffs (Well Fed variants)
        ConsumableDef(33254, "Well Fed (Spell Power)", "food", 80.0),
        ConsumableDef(33256, "Well Fed (Agility)", "food", 80.0),
        ConsumableDef(33259, "Well Fed (Stamina)", "food", 80.0),
        ConsumableDef(33261, "Well Fed (Strength)", "food", 80.0),
        ConsumableDef(43722, "Well Fed (Hit)", "food", 80.0),
        ConsumableDef(43763, "Well Fed (Haste)", "food", 80.0),
        ConsumableDef(43764, "Well Fed (AP)", "food", 80.0),
    ],
    "melee_dps": [
        ConsumableDef(17538, "Elixir of the Mongoose", "elixir", 80.0),
        ConsumableDef(28490, "Elixir of Major Agility", "elixir", 80.0),
        ConsumableDef(11334, "Elixir of Greater Agility", "elixir", 80.0),
        ConsumableDef(28497, "Mighty Rage Potion", "potion", 5.0),
        ConsumableDef(22730, "Scroll of Strength V", "scroll", 80.0),
    ],
    "ranged_dps": [
        ConsumableDef(28490, "Elixir of Major Agility", "elixir", 80.0),
    ],
    "caster_dps": [
        ConsumableDef(17628, "Flask of Supreme Power", "flask", 80.0),
        ConsumableDef(28509, "Elixir of Major Firepower", "elixir", 80.0),
        ConsumableDef(28503, "Elixir of Major Shadow Power", "elixir", 80.0),
        ConsumableDef(28501, "Elixir of Major Frost Power", "elixir", 80.0),
        ConsumableDef(25122, "Brilliant Wizard Oil", "weapon", 80.0),
    ],
    "healer": [
        ConsumableDef(17627, "Flask of Distilled Wisdom", "flask", 80.0),
        ConsumableDef(28502, "Elixir of Healing Power", "elixir", 80.0),
        ConsumableDef(25123, "Brilliant Mana Oil", "weapon", 80.0),
    ],
    "tank": [
        ConsumableDef(17546, "Flask of the Titans", "flask", 80.0),
        ConsumableDef(28502, "Elixir of Healing Power", "elixir", 80.0),
        ConsumableDef(28514, "Elixir of Major Fortitude", "elixir", 80.0),
        ConsumableDef(28509, "Elixir of Major Defense", "elixir", 80.0),
        ConsumableDef(17549, "Ironshield Potion", "potion", 5.0),
    ],
}


def get_expected_consumables(spec: str) -> list[ConsumableDef]:
    """Return the combined list of expected consumables for a given spec."""
    role = ROLE_BY_SPEC.get(spec, "melee_dps")
    return REQUIRED_CONSUMABLES.get("all", []) + REQUIRED_CONSUMABLES.get(role, [])


# --- CombatantInfo consumable category mapping ---
# Maps known WCL CombatantInfo aura spell IDs to (category, display_name).
# Used by combatant_info.py to classify auras from CombatantInfo events.
CONSUMABLE_CATEGORIES: dict[int, tuple[str, str]] = {
    # Flasks (Classic Fresh)
    17628: ("flask", "Flask of Supreme Power"),
    17626: ("flask", "Flask of the Titans"),
    17627: ("flask", "Flask of Distilled Wisdom"),
    17629: ("flask", "Flask of Chromatic Resistance"),
    # Battle Elixirs
    28490: ("elixir", "Elixir of Major Strength"),
    28491: ("elixir", "Elixir of Healing Power"),
    28493: ("elixir", "Elixir of Major Frost Power"),
    28501: ("elixir", "Elixir of Major Firepower"),
    28503: ("elixir", "Elixir of Major Shadow Power"),
    11390: ("elixir", "Elixir of the Mongoose"),
    # Guardian Elixirs
    28502: ("elixir", "Elixir of Major Armor"),
    28509: ("elixir", "Elixir of Major Mageblood"),
    28514: ("elixir", "Elixir of Empowerment"),
    # Food
    33254: ("food", "Well Fed"),
    33257: ("food", "Well Fed"),
    # Weapon Oils / Stones
    28898: ("weapon_oil", "Brilliant Wizard Oil"),
    28891: ("weapon_oil", "Superior Wizard Oil"),
    25123: ("weapon_oil", "Adamantite Sharpening Stone"),
    25118: ("weapon_oil", "Adamantite Weightstone"),
}

GEAR_SLOTS: dict[int, str] = {
    0: "Head", 1: "Neck", 2: "Shoulder", 3: "Shirt",
    4: "Chest", 5: "Waist", 6: "Legs", 7: "Feet",
    8: "Wrist", 9: "Hands", 10: "Ring 1", 11: "Ring 2",
    12: "Trinket 1", 13: "Trinket 2", 14: "Back",
    15: "Main Hand", 16: "Off Hand", 17: "Ranged",
}


# --- Boss Fight Phase Definitions ---

@dataclass(frozen=True)
class PhaseDef:
    name: str
    pct_start: float   # Approximate % of fight when this phase starts (0.0 = start)
    pct_end: float     # Approximate % of fight when this phase ends (1.0 = end)
    description: str = ""


# Phase definitions for Fresh Naxxramas encounters.
# These are approximate time-based splits for MVP phase annotation.
# Actual phase transitions depend on boss HP or scripted events, but
# these percentages give a useful estimate when we lack event-level data.
ENCOUNTER_PHASES: dict[str, list[PhaseDef]] = {
    "Patchwerk": [
        PhaseDef("Full Fight", 0.0, 1.0, "Single phase DPS race"),
    ],
    "Grobbulus": [
        PhaseDef("Full Fight", 0.0, 1.0, "Kite and kill, poison clouds"),
    ],
    "Gluth": [
        PhaseDef("P1 - DPS", 0.0, 0.7, "DPS boss while kiting zombies"),
        PhaseDef("P2 - Decimate", 0.7, 1.0, "Zombies decimated, burn phase"),
    ],
    "Thaddius": [
        PhaseDef("P1 - Stalagg & Feugen", 0.0, 0.35,
                 "Kill both adds within 5 seconds"),
        PhaseDef("P2 - Thaddius", 0.35, 1.0,
                 "DPS with polarity shifts"),
    ],
    "Noth the Plaguebringer": [
        PhaseDef("P1 - Ground", 0.0, 0.5, "DPS boss on ground"),
        PhaseDef("P2 - Balcony", 0.5, 1.0,
                 "Add waves while boss is immune"),
    ],
    "Heigan the Unclean": [
        PhaseDef("P1 - Platform", 0.0, 0.55, "DPS on platform phase"),
        PhaseDef("P2 - Dance", 0.55, 1.0, "Safety dance, limited DPS"),
    ],
    "Loatheb": [
        PhaseDef("Full Fight", 0.0, 1.0, "Single phase, timed heals"),
    ],
    "Anub'Rekhan": [
        PhaseDef("Full Fight", 0.0, 1.0,
                 "Single phase with locust swarm kiting"),
    ],
    "Grand Widow Faerlina": [
        PhaseDef("Full Fight", 0.0, 1.0,
                 "Single phase, manage enrage"),
    ],
    "Maexxna": [
        PhaseDef("P1 - Above 30%", 0.0, 0.7,
                 "Normal DPS with web wraps"),
        PhaseDef("P2 - Enrage", 0.7, 1.0, "Below 30%, burn phase"),
    ],
    "Instructor Razuvious": [
        PhaseDef("Full Fight", 0.0, 1.0, "Mind control tanking"),
    ],
    "Gothik the Harvester": [
        PhaseDef("P1 - Waves", 0.0, 0.55,
                 "Add waves, live/dead side"),
        PhaseDef("P2 - Gothik", 0.55, 1.0, "Boss comes down, burn"),
    ],
    "The Four Horsemen": [
        PhaseDef("Full Fight", 0.0, 1.0, "Tank rotation with marks"),
    ],
    "Sapphiron": [
        PhaseDef("P1 - Ground", 0.0, 0.6, "DPS on ground"),
        PhaseDef("P2 - Air", 0.6, 1.0, "Ice block phase, blizzard"),
    ],
    "Kel'Thuzad": [
        PhaseDef("P1 - Adds", 0.0, 0.2,
                 "Kill add waves, no boss DPS"),
        PhaseDef("P2 - Active", 0.2, 0.7, "Main DPS phase"),
        PhaseDef("P3 - Ice Tombs", 0.7, 1.0,
                 "Ice blocks and guardians"),
    ],
}
