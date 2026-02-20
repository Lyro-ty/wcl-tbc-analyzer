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
    cd_type: str = "throughput"  # "throughput", "interrupt", "defensive", "utility"


# Classic Fresh / TBC major throughput cooldowns per class.
# spell_id values are WCL abilityGameID (WoW spell IDs).
CLASSIC_COOLDOWNS: dict[str, list[CooldownDef]] = {
    "Warrior": [
        CooldownDef(12292, "Death Wish", 180, 30, cd_type="throughput"),
        CooldownDef(1719, "Recklessness", 900, 15, cd_type="throughput"),
        CooldownDef(12328, "Sweeping Strikes", 30, 10, cd_type="throughput"),
        CooldownDef(6552, "Pummel", 10, 0, cd_type="interrupt"),
        CooldownDef(871, "Shield Wall", 1800, 10, cd_type="defensive"),
        CooldownDef(12975, "Last Stand", 600, 20, cd_type="defensive"),
        CooldownDef(2687, "Bloodrage", 60, 10, cd_type="utility"),
        CooldownDef(18499, "Berserker Rage", 30, 10, cd_type="utility"),
    ],
    "Paladin": [
        CooldownDef(31884, "Avenging Wrath", 180, 20, cd_type="throughput"),
        CooldownDef(10308, "Hammer of Justice", 60, 0, cd_type="defensive"),
        CooldownDef(642, "Divine Shield", 300, 12, cd_type="defensive"),
        CooldownDef(10310, "Lay on Hands", 3600, 0, cd_type="utility"),
    ],
    "Hunter": [
        CooldownDef(3045, "Rapid Fire", 300, 15, cd_type="throughput"),
        CooldownDef(19574, "Bestial Wrath", 120, 18, cd_type="throughput"),
        CooldownDef(34692, "The Beast Within", 120, 18, cd_type="throughput"),
    ],
    "Rogue": [
        CooldownDef(13750, "Adrenaline Rush", 300, 15, cd_type="throughput"),
        CooldownDef(13877, "Blade Flurry", 120, 15, cd_type="throughput"),
        CooldownDef(14177, "Cold Blood", 180, 0, cd_type="throughput"),
        CooldownDef(1769, "Kick", 10, 0, cd_type="interrupt"),
        CooldownDef(26669, "Evasion", 300, 15, cd_type="defensive"),
        CooldownDef(31224, "Cloak of Shadows", 60, 5, cd_type="defensive"),
    ],
    "Priest": [
        CooldownDef(10060, "Power Infusion", 180, 15, cd_type="throughput"),
        CooldownDef(33206, "Pain Suppression", 120, 8, cd_type="defensive"),
        CooldownDef(15487, "Silence", 45, 0, cd_type="interrupt"),
    ],
    "Shaman": [
        CooldownDef(2825, "Bloodlust", 600, 40, cd_type="throughput"),
        CooldownDef(16166, "Elemental Mastery", 180, 0, cd_type="throughput"),
        CooldownDef(25454, "Earth Shock", 6, 0, cd_type="interrupt"),
        CooldownDef(16190, "Mana Tide Totem", 300, 12, cd_type="utility"),
        CooldownDef(2894, "Fire Elemental Totem", 600, 120, cd_type="utility"),
    ],
    "Mage": [
        CooldownDef(12042, "Arcane Power", 180, 15, cd_type="throughput"),
        CooldownDef(12051, "Evocation", 480, 8, cd_type="utility"),
        CooldownDef(11129, "Combustion", 180, 0, cd_type="throughput"),
        CooldownDef(12472, "Icy Veins", 180, 20, cd_type="throughput"),
        CooldownDef(2139, "Counterspell", 24, 0, cd_type="interrupt"),
    ],
    "Warlock": [
        CooldownDef(18708, "Fel Domination", 900, 0, cd_type="utility"),
        CooldownDef(18288, "Amplify Curse", 180, 0, cd_type="throughput"),
    ],
    "Druid": [
        CooldownDef(29166, "Innervate", 360, 20, cd_type="utility"),
        CooldownDef(17116, "Nature's Swiftness", 180, 0, cd_type="utility"),
        CooldownDef(16979, "Feral Charge", 15, 0, cd_type="interrupt"),
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

# --- Per-spec rotation rules ---
# Used by the rotation scorer to set spec-appropriate thresholds instead of
# universal defaults.  gcd_target and cd_efficiency_target are percentages;
# cpm_target is casts per minute.  key_abilities lists the core rotation
# spells whose usage the scorer should check.


@dataclass(frozen=True)
class SpecRules:
    gcd_target: float
    cpm_target: float
    cd_efficiency_target: float
    long_cd_efficiency: float
    key_abilities: tuple[str, ...]
    role: str
    healer_overheal_target: float = 35.0


SPEC_ROTATION_RULES: dict[tuple[str, str], SpecRules] = {
    # --- Melee DPS ---
    ("Warrior", "Arms"): SpecRules(
        88, 28, 85, 60,
        ("Mortal Strike", "Whirlwind", "Slam"), "melee_dps",
    ),
    ("Warrior", "Fury"): SpecRules(
        90, 32, 85, 60,
        ("Bloodthirst", "Whirlwind", "Heroic Strike"), "melee_dps",
    ),
    ("Paladin", "Retribution"): SpecRules(
        85, 25, 80, 60,
        ("Crusader Strike", "Seal of Command", "Judgement"), "melee_dps",
    ),
    ("Rogue", "Assassination"): SpecRules(
        88, 30, 85, 65,
        ("Mutilate", "Envenom", "Slice and Dice"), "melee_dps",
    ),
    ("Rogue", "Combat"): SpecRules(
        90, 32, 85, 65,
        ("Sinister Strike", "Slice and Dice", "Blade Flurry"), "melee_dps",
    ),
    ("Rogue", "Subtlety"): SpecRules(
        85, 28, 80, 60,
        ("Hemorrhage", "Slice and Dice"), "melee_dps",
    ),
    ("Shaman", "Enhancement"): SpecRules(
        85, 25, 80, 60,
        ("Stormstrike", "Earth Shock", "Windfury"), "melee_dps",
    ),
    ("Druid", "Feral"): SpecRules(
        88, 30, 85, 60,
        ("Shred", "Mangle", "Rip"), "melee_dps",
    ),
    # --- Ranged DPS ---
    ("Hunter", "Beast Mastery"): SpecRules(
        82, 22, 85, 60,
        ("Steady Shot", "Auto Shot", "Kill Command"), "ranged_dps",
    ),
    ("Hunter", "Marksmanship"): SpecRules(
        82, 22, 85, 60,
        ("Steady Shot", "Auto Shot", "Arcane Shot"), "ranged_dps",
    ),
    ("Hunter", "Survival"): SpecRules(
        82, 22, 85, 60,
        ("Steady Shot", "Auto Shot", "Raptor Strike"), "ranged_dps",
    ),
    # --- Caster DPS ---
    ("Priest", "Shadow"): SpecRules(
        88, 25, 80, 60,
        ("Shadow Word: Pain", "Mind Blast", "Mind Flay"), "caster_dps",
    ),
    ("Shaman", "Elemental"): SpecRules(
        85, 25, 80, 60,
        ("Lightning Bolt", "Chain Lightning"), "caster_dps",
    ),
    ("Mage", "Arcane"): SpecRules(
        90, 28, 85, 60,
        ("Arcane Blast", "Arcane Missiles"), "caster_dps",
    ),
    ("Mage", "Fire"): SpecRules(
        85, 22, 85, 60,
        ("Fireball", "Scorch", "Fire Blast"), "caster_dps",
    ),
    ("Mage", "Frost"): SpecRules(
        85, 22, 85, 60,
        ("Frostbolt", "Ice Lance"), "caster_dps",
    ),
    ("Warlock", "Affliction"): SpecRules(
        85, 22, 80, 60,
        ("Corruption", "Unstable Affliction", "Shadow Bolt"), "caster_dps",
    ),
    ("Warlock", "Demonology"): SpecRules(
        85, 22, 80, 60,
        ("Shadow Bolt", "Incinerate"), "caster_dps",
    ),
    ("Warlock", "Destruction"): SpecRules(
        88, 24, 85, 60,
        ("Shadow Bolt", "Incinerate", "Immolate"), "caster_dps",
    ),
    ("Druid", "Balance"): SpecRules(
        85, 22, 80, 60,
        ("Starfire", "Wrath", "Moonfire"), "caster_dps",
    ),
    # --- Healers ---
    ("Paladin", "Holy"): SpecRules(
        55, 18, 70, 50,
        ("Flash of Light", "Holy Light"), "healer", 20,
    ),
    ("Priest", "Discipline"): SpecRules(
        60, 20, 75, 55,
        ("Power Word: Shield", "Flash Heal", "Prayer of Mending"), "healer", 25,
    ),
    ("Priest", "Holy"): SpecRules(
        65, 22, 75, 55,
        ("Circle of Healing", "Prayer of Healing", "Flash Heal"), "healer", 30,
    ),
    ("Shaman", "Restoration"): SpecRules(
        60, 20, 75, 55,
        ("Chain Heal", "Lesser Healing Wave"), "healer", 30,
    ),
    ("Druid", "Restoration"): SpecRules(
        65, 22, 70, 50,
        ("Lifebloom", "Rejuvenation", "Healing Touch"), "healer", 45,
    ),
    # --- Tanks ---
    ("Warrior", "Protection"): SpecRules(
        88, 30, 85, 50,
        ("Shield Slam", "Devastate", "Thunderclap"), "tank",
    ),
    ("Paladin", "Protection"): SpecRules(
        85, 26, 80, 50,
        ("Consecration", "Holy Shield", "Avenger's Shield"), "tank",
    ),
}


# Role-based fallback for unknown specs
ROLE_DEFAULT_RULES: dict[str, SpecRules] = {
    "melee_dps": SpecRules(85, 28, 80, 60, (), "melee_dps"),
    "caster_dps": SpecRules(85, 22, 80, 60, (), "caster_dps"),
    "ranged_dps": SpecRules(80, 20, 80, 60, (), "ranged_dps"),
    "healer": SpecRules(60, 20, 70, 50, (), "healer", 35),
    "tank": SpecRules(85, 28, 80, 50, (), "tank"),
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
        ConsumableDef(28501, "Elixir of Major Firepower", "elixir", 80.0),
        ConsumableDef(28503, "Elixir of Major Shadow Power", "elixir", 80.0),
        ConsumableDef(28493, "Elixir of Major Frost Power", "elixir", 80.0),
        ConsumableDef(25122, "Brilliant Wizard Oil", "weapon", 80.0),
    ],
    "healer": [
        ConsumableDef(17627, "Flask of Distilled Wisdom", "flask", 80.0),
        ConsumableDef(28491, "Elixir of Healing Power", "elixir", 80.0),
        ConsumableDef(25123, "Brilliant Mana Oil", "weapon", 80.0),
    ],
    "tank": [
        ConsumableDef(17546, "Flask of the Titans", "flask", 80.0),
        ConsumableDef(28491, "Elixir of Healing Power", "elixir", 80.0),
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
    28490: ("elixir", "Elixir of Major Agility"),
    28491: ("elixir", "Elixir of Healing Power"),
    28493: ("elixir", "Elixir of Major Frost Power"),
    28501: ("elixir", "Elixir of Major Firepower"),
    28503: ("elixir", "Elixir of Major Shadow Power"),
    11390: ("elixir", "Elixir of the Mongoose"),
    # Guardian Elixirs
    28502: ("elixir", "Elixir of Major Mageblood"),
    28509: ("elixir", "Elixir of Major Defense"),
    28514: ("elixir", "Elixir of Major Fortitude"),
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
@dataclass(frozen=True)
class DotDef:
    spell_id: int
    name: str
    duration_ms: int
    tick_interval_ms: int


CLASSIC_DOTS: dict[str, list[DotDef]] = {
    "Warlock": [
        DotDef(30108, "Unstable Affliction", 18000, 3000),
        DotDef(27216, "Corruption", 18000, 3000),
        DotDef(27218, "Curse of Agony", 24000, 2000),
        DotDef(30405, "Seed of Corruption", 18000, 3000),
        DotDef(27215, "Immolate", 15000, 3000),
    ],
    "Priest": [
        DotDef(25368, "Shadow Word: Pain", 18000, 3000),
        DotDef(25218, "Vampiric Touch", 15000, 3000),
        DotDef(25387, "Devouring Plague", 24000, 3000),
    ],
    "Druid": [
        DotDef(27013, "Moonfire", 12000, 3000),
        DotDef(27012, "Insect Swarm", 12000, 2000),
        DotDef(27003, "Rake", 9000, 3000),
        DotDef(27008, "Rip", 12000, 2000),
    ],
    "Hunter": [
        DotDef(27016, "Serpent Sting", 15000, 3000),
    ],
}

# Reverse lookup: spell_id -> DotDef
DOT_BY_SPELL_ID: dict[int, DotDef] = {}
for _class_dots in CLASSIC_DOTS.values():
    for _dot in _class_dots:
        DOT_BY_SPELL_ID[_dot.spell_id] = _dot


@dataclass(frozen=True)
class TrinketDef:
    spell_id: int
    name: str
    expected_uptime_pct: float


CLASSIC_TRINKETS: dict[int, TrinketDef] = {
    28830: TrinketDef(28830, "Dragonspine Trophy", 22.0),
    23046: TrinketDef(23046, "The Restrained Essence of Sapphiron", 15.0),
    28789: TrinketDef(28789, "Eye of Magtheridon", 25.0),
    23207: TrinketDef(23207, "Mark of the Champion", 100.0),
    23001: TrinketDef(23001, "Eye of the Dead", 30.0),
    28235: TrinketDef(28235, "Pendant of the Violet Eye", 15.0),
    28727: TrinketDef(28727, "Pendant of the Violet Eye", 15.0),
    33649: TrinketDef(33649, "Tome of Fiery Redemption", 20.0),
    34321: TrinketDef(34321, "Shard of Contempt", 30.0),
    34472: TrinketDef(34472, "Timbal's Focusing Crystal", 15.0),
}


ENCOUNTER_PHASES: dict[str, list[PhaseDef]] = {
    # --- TBC P1: Karazhan ---
    "Attumen the Huntsman": [
        PhaseDef("P1 - Midnight", 0.0, 0.35,
                 "DPS Midnight, Attumen spawns at 95%"),
        PhaseDef("P2 - Both Active", 0.35, 0.7,
                 "Kill Midnight while dodging Attumen cleave"),
        PhaseDef("P3 - Mounted", 0.7, 1.0,
                 "Attumen mounts Midnight, burn phase"),
    ],
    "Moroes": [
        PhaseDef("Full Fight", 0.0, 1.0,
                 "Kill adds then boss, manage Garrote"),
    ],
    "Maiden of Virtue": [
        PhaseDef("Full Fight", 0.0, 1.0,
                 "Single phase, Repentance every 30s"),
    ],
    "Opera Event": [
        PhaseDef("Full Fight", 0.0, 1.0,
                 "Varies by week: Oz, Romulo & Julianne, Big Bad Wolf"),
    ],
    "The Curator": [
        PhaseDef("P1 - Sparks", 0.0, 0.7,
                 "Kill Astral Flares, boss Hateful Bolts"),
        PhaseDef("P2 - Evocate", 0.7, 1.0,
                 "Curator evocates at 0 mana, +200% damage taken"),
    ],
    "Shade of Aran": [
        PhaseDef("Full Fight", 0.0, 1.0,
                 "No aggro table, rotating abilities, elementals at 40%"),
    ],
    "Terestian Illhoof": [
        PhaseDef("Full Fight", 0.0, 1.0,
                 "Kill imps, free Sacrifice targets"),
    ],
    "Netherspite": [
        PhaseDef("Portal Phase", 0.0, 0.5,
                 "Soak colored beams to buff raid/debuff boss"),
        PhaseDef("Banish Phase", 0.5, 1.0,
                 "Boss banishes, void zones, no portals"),
    ],
    "Chess Event": [
        PhaseDef("Full Fight", 0.0, 1.0,
                 "Chess minigame, no standard DPS analysis"),
    ],
    "Prince Malchezaar": [
        PhaseDef("P1 - Normal", 0.0, 0.4,
                 "Shadow damage, standard tanking"),
        PhaseDef("P2 - Axes", 0.4, 0.7,
                 "Dual wield, thrash, Shadow Nova"),
        PhaseDef("P3 - Infernals", 0.7, 1.0,
                 "Axes + Infernals, amplified Shadow Nova"),
    ],
    "Nightbane": [
        PhaseDef("Ground Phase", 0.0, 0.5,
                 "Tank and spank with Charred Earth"),
        PhaseDef("Air Phase", 0.5, 1.0,
                 "Boss flies up, Smoking Blast, Rain of Bones"),
    ],
    # --- TBC P1: Gruul's Lair ---
    "High King Maulgar": [
        PhaseDef("Full Fight", 0.0, 1.0,
                 "Kill adds (Blindeye, Olm, Kiggler, Krosh) then Maulgar"),
    ],
    "Gruul the Dragonkiller": [
        PhaseDef("Full Fight", 0.0, 1.0,
                 "DPS race, stacking Growth buff, periodic Shatter"),
    ],
    # --- TBC P1: Magtheridon's Lair ---
    "Magtheridon": [
        PhaseDef("P1 - Channelers", 0.0, 0.3,
                 "Kill 5 Hellfire Channelers before Magtheridon activates"),
        PhaseDef("P2 - Magtheridon", 0.3, 1.0,
                 "Click cubes for Banish, dodge Blast Nova, burn boss"),
    ],
    # --- Classic Fresh: Naxxramas ---
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
