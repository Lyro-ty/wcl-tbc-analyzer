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


# --- Boss Phase definitions ---

@dataclass(frozen=True)
class BossPhase:
    name: str
    start_pct: float | None  # HP % where phase starts (None = time-based)
    end_pct: float | None  # HP % where phase ends
    is_downtime: bool  # True = expected downtime (transitions, air phases)


# Encounter phases for boss encounters with clear phase transitions.
# Uses encounter names (not IDs) for portability.
ENCOUNTER_PHASES: dict[str, list[BossPhase]] = {
    "Heigan the Unclean": [
        BossPhase("Phase 1 (Dance)", None, None, False),
        BossPhase("Phase 2 (Platform)", None, None, True),
    ],
    "Thaddius": [
        BossPhase("Phase 1 (Stalagg & Feugen)", None, None, False),
        BossPhase("Transition", None, None, True),
        BossPhase("Phase 2 (Thaddius)", None, None, False),
    ],
    "Gothik the Harvester": [
        BossPhase("Phase 1 (Living)", None, None, False),
        BossPhase("Phase 2 (Dead)", None, None, False),
        BossPhase("Phase 3 (Combined)", None, None, False),
    ],
    "Sapphiron": [
        BossPhase("Ground Phase", None, None, False),
        BossPhase("Air Phase", None, None, True),
    ],
    "Kel'Thuzad": [
        BossPhase("Phase 1 (Adds)", None, None, False),
        BossPhase("Phase 2 (Kel'Thuzad)", None, None, False),
        BossPhase("Phase 3 (KT + Guardians)", None, None, False),
    ],
    "Lady Vashj": [
        BossPhase("Phase 1", None, None, False),
        BossPhase("Phase 2 (Tainted Cores)", None, None, False),
        BossPhase("Phase 3", None, None, False),
    ],
    "Kael'thas Sunstrider": [
        BossPhase("Phase 1 (Advisors)", None, None, False),
        BossPhase("Phase 2 (Weapons)", None, None, False),
        BossPhase("Phase 3 (Advisors Revived)", None, None, False),
        BossPhase("Phase 4 (Kael'thas)", None, None, False),
    ],
    "Archimonde": [
        BossPhase("Full Fight", None, None, False),
    ],
    "Illidan Stormrage": [
        BossPhase("Phase 1 (Normal)", None, None, False),
        BossPhase("Phase 2 (Flames)", None, None, True),
        BossPhase("Phase 3 (Demon)", None, None, False),
        BossPhase("Phase 4 (Maiev)", None, None, False),
    ],
}


# --- DoT definitions for early refresh detection ---

@dataclass(frozen=True)
class DotDef:
    spell_id: int
    name: str
    duration_ms: int
    tick_interval_ms: int
    pandemic_window_ms: int  # Safe refresh window (last 30% of duration)


CLASS_DOTS: dict[str, list[DotDef]] = {
    "Priest": [
        DotDef(25368, "Shadow Word: Pain", 18000, 3000, 5400),
        DotDef(34917, "Vampiric Touch", 15000, 3000, 4500),
        DotDef(25467, "Devouring Plague", 24000, 3000, 7200),
    ],
    "Warlock": [
        DotDef(27216, "Corruption", 18000, 3000, 5400),
        DotDef(27215, "Immolate", 15000, 3000, 4500),
        DotDef(27218, "Curse of Agony", 24000, 2000, 7200),
        DotDef(30910, "Curse of Doom", 60000, 60000, 18000),
        DotDef(30405, "Unstable Affliction", 18000, 3000, 5400),
        DotDef(27264, "Siphon Life", 30000, 3000, 9000),
    ],
    "Druid": [
        DotDef(26988, "Moonfire", 12000, 3000, 3600),
        DotDef(27013, "Insect Swarm", 12000, 2000, 3600),
    ],
    "Hunter": [
        DotDef(27016, "Serpent Sting", 15000, 3000, 4500),
    ],
}


# --- Trinket proc definitions ---

@dataclass(frozen=True)
class TrinketDef:
    spell_id: int  # Proc buff spell ID (appears in WCL buff data)
    name: str
    expected_uptime_pct: float  # Approximate expected uptime for good RNG/usage


# Classic Fresh / TBC trinket procs (WoW spell IDs for the proc buffs).
CLASSIC_TRINKETS: list[TrinketDef] = [
    TrinketDef(34775, "Dragonspine Trophy", 30.0),
    TrinketDef(42084, "Tsunami Talisman", 25.0),
    TrinketDef(35163, "Icon of the Silver Crescent", 20.0),
    TrinketDef(35166, "Bloodlust Brooch", 20.0),
    TrinketDef(35165, "Essence of the Martyr", 20.0),
    TrinketDef(39200, "Madness of the Betrayer", 20.0),
    TrinketDef(38348, "Sextant of Unstable Currents", 20.0),
    TrinketDef(33370, "Quagmirran's Eye", 20.0),
    TrinketDef(39958, "Darkmoon Card: Crusade", 20.0),
    TrinketDef(28830, "Eye of the Dead", 20.0),
    TrinketDef(33807, "Abacus of Violent Odds", 20.0),
    TrinketDef(40477, "Shard of Contempt", 30.0),
]

# Set of known trinket proc spell IDs for quick lookup.
TRINKET_SPELL_IDS: frozenset[int] = frozenset(
    t.spell_id for t in CLASSIC_TRINKETS
)


# --- Raid buff definitions for coverage checks ---

RAID_BUFFS: dict[str, list[int]] = {
    "Battle Shout": [2048, 25289],
    "Blessing of Kings": [25898],
    "Blessing of Might": [27141],
    "Blessing of Salvation": [1038],
    "Blessing of Wisdom": [27143],
    "Mark of the Wild": [26990],
    "Arcane Intellect": [27126],
    "Power Word: Fortitude": [25389],
    "Divine Spirit": [32999],
    "Shadow Protection": [39374],
    "Windfury Totem": [25587],
    "Grace of Air Totem": [25359],
    "Strength of Earth Totem": [25528],
    "Mana Spring Totem": [25570],
    "Totem of Wrath": [30708],
    "Wrath of Air Totem": [3738],
    "Trueshot Aura": [27066],
    "Leader of the Pack": [17007],
    "Moonkin Aura": [24907],
    "Heroic Presence": [6562],
    "Unleashed Rage": [30811],
}
