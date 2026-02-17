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


# Classic Fresh / TBC major throughput cooldowns per class.
# spell_id values are WCL abilityGameID (WoW spell IDs).
CLASSIC_COOLDOWNS: dict[str, list[CooldownDef]] = {
    "Warrior": [
        CooldownDef(12292, "Death Wish", 180),
        CooldownDef(1719, "Recklessness", 900),
        CooldownDef(12328, "Sweeping Strikes", 30),
    ],
    "Paladin": [
        CooldownDef(31884, "Avenging Wrath", 180),
    ],
    "Hunter": [
        CooldownDef(3045, "Rapid Fire", 300),
        CooldownDef(19574, "Bestial Wrath", 120),
        CooldownDef(34692, "The Beast Within", 120),
    ],
    "Rogue": [
        CooldownDef(13750, "Adrenaline Rush", 300),
        CooldownDef(13877, "Blade Flurry", 120),
        CooldownDef(14177, "Cold Blood", 180),
    ],
    "Priest": [
        CooldownDef(10060, "Power Infusion", 180),
        CooldownDef(33206, "Pain Suppression", 120),
        CooldownDef(15487, "Silence", 45),
    ],
    "Shaman": [
        CooldownDef(2825, "Bloodlust", 600),
        CooldownDef(16166, "Elemental Mastery", 180),
    ],
    "Mage": [
        CooldownDef(12042, "Arcane Power", 180),
        CooldownDef(12051, "Evocation", 480),
        CooldownDef(11129, "Combustion", 180),
        CooldownDef(12472, "Icy Veins", 180),
    ],
    "Warlock": [
        CooldownDef(18708, "Fel Domination", 900),
        CooldownDef(18288, "Amplify Curse", 180),
    ],
    "Druid": [
        CooldownDef(29166, "Innervate", 360),
        CooldownDef(17116, "Nature's Swiftness", 180),
        CooldownDef(33891, "Tree of Life", 0),  # Passive/stance — tracked for detection only
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
