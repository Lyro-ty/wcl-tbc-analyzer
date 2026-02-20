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
        "Opera Hall",
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
}

TBC_BOSS_NAMES: frozenset[str] = frozenset(
    boss for bosses in TBC_ZONES.values() for boss in bosses
)

ALL_BOSS_NAMES: frozenset[str] = TBC_BOSS_NAMES


@dataclass(frozen=True)
class CooldownDef:
    spell_id: int
    name: str
    cooldown_sec: int
    duration_sec: int = 0  # Actual buff duration (0 = instant/passive)
    cd_type: str = "throughput"  # "throughput", "interrupt", "defensive", "utility"


# Classic / TBC major throughput cooldowns per class.
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
    category: str  # flask, battle_elixir, guardian_elixir, food, weapon, potion, scroll
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
        ("Mortal Strike", "Whirlwind", "Execute"), "melee_dps",
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
        ("Stormstrike", "Earth Shock", "Shamanistic Rage"), "melee_dps",
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
        ("Steady Shot", "Auto Shot", "Multi-Shot"), "ranged_dps",
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
        ConsumableDef(43722, "Enlightened (Spell Crit)", "food", 80.0),
        ConsumableDef(43764, "Well Fed (Hit Rating)", "food", 80.0),
    ],
    "melee_dps": [
        ConsumableDef(28520, "Flask of Relentless Assault", "flask", 80.0),
        ConsumableDef(17538, "Elixir of the Mongoose", "battle_elixir", 80.0),
        ConsumableDef(28490, "Elixir of Major Agility", "battle_elixir", 80.0),
        ConsumableDef(11334, "Elixir of Greater Agility", "battle_elixir", 80.0),
        ConsumableDef(28497, "Mighty Rage Potion", "potion", 5.0),
        ConsumableDef(22730, "Scroll of Strength V", "scroll", 80.0),
    ],
    "ranged_dps": [
        ConsumableDef(28520, "Flask of Relentless Assault", "flask", 80.0),
        ConsumableDef(28490, "Elixir of Major Agility", "battle_elixir", 80.0),
    ],
    "caster_dps": [
        ConsumableDef(28521, "Flask of Blinding Light", "flask", 80.0),
        ConsumableDef(28540, "Flask of Pure Death", "flask", 80.0),
        ConsumableDef(28501, "Elixir of Major Firepower", "battle_elixir", 80.0),
        ConsumableDef(28503, "Elixir of Major Shadow Power", "battle_elixir", 80.0),
        ConsumableDef(28493, "Elixir of Major Frost Power", "battle_elixir", 80.0),
        ConsumableDef(25122, "Brilliant Wizard Oil", "weapon", 80.0),
    ],
    "healer": [
        ConsumableDef(28519, "Flask of Mighty Restoration", "flask", 80.0),
        ConsumableDef(28491, "Elixir of Healing Power", "battle_elixir", 80.0),
        ConsumableDef(25123, "Brilliant Mana Oil", "weapon", 80.0),
    ],
    "tank": [
        ConsumableDef(28518, "Flask of Fortification", "flask", 80.0),
        ConsumableDef(28491, "Elixir of Healing Power", "battle_elixir", 80.0),
        ConsumableDef(28514, "Elixir of Major Fortitude", "guardian_elixir", 80.0),
        ConsumableDef(28509, "Elixir of Major Defense", "guardian_elixir", 80.0),
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
    # Flasks (Classic — still valid in TBC CombatantInfo)
    17628: ("flask", "Flask of Supreme Power"),
    17626: ("flask", "Flask of the Titans"),
    17627: ("flask", "Flask of Distilled Wisdom"),
    17629: ("flask", "Flask of Chromatic Resistance"),
    # Flasks (TBC)
    28518: ("flask", "Flask of Fortification"),
    28519: ("flask", "Flask of Mighty Restoration"),
    28520: ("flask", "Flask of Relentless Assault"),
    28521: ("flask", "Flask of Blinding Light"),
    28540: ("flask", "Flask of Pure Death"),
    # Battle Elixirs (one allowed, OR flask replaces both elixir slots)
    28490: ("battle_elixir", "Elixir of Major Agility"),
    28491: ("battle_elixir", "Elixir of Healing Power"),
    28493: ("battle_elixir", "Elixir of Major Frost Power"),
    28501: ("battle_elixir", "Elixir of Major Firepower"),
    28503: ("battle_elixir", "Elixir of Major Shadow Power"),
    11390: ("battle_elixir", "Elixir of the Mongoose"),
    # Guardian Elixirs (one allowed, OR flask replaces both elixir slots)
    28502: ("guardian_elixir", "Elixir of Major Mageblood"),
    28509: ("guardian_elixir", "Elixir of Major Defense"),
    28514: ("guardian_elixir", "Elixir of Major Fortitude"),
    39627: ("guardian_elixir", "Elixir of Draenic Wisdom"),
    # Potions (TBC combat potions)
    28507: ("potion", "Haste Potion"),
    28508: ("potion", "Destruction Potion"),
    # Food
    33254: ("food", "Well Fed"),
    33257: ("food", "Well Fed"),
    # Weapon Oils / Stones (buff spell IDs verified on Wowhead TBC)
    25122: ("weapon_oil", "Brilliant Wizard Oil"),
    25123: ("weapon_oil", "Brilliant Mana Oil"),
    28898: ("weapon_oil", "Blessed Wizard Oil"),
    28019: ("weapon_oil", "Superior Wizard Oil"),
    28013: ("weapon_oil", "Superior Mana Oil"),
    29656: ("weapon_stone", "Adamantite Sharpening Stone"),
    34608: ("weapon_stone", "Adamantite Weightstone"),
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
    28789: TrinketDef(28789, "Eye of Magtheridon", 25.0),
    28235: TrinketDef(28235, "Pendant of the Violet Eye", 15.0),
    28727: TrinketDef(28727, "Pendant of the Violet Eye", 15.0),
    33649: TrinketDef(33649, "Tome of Fiery Redemption", 20.0),
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
    "Opera Hall": [
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
}


# --- Encounter-specific GCD modifiers ---
# Pre-computed modifier per boss to account for downtime phases, movement,
# and untargetable windows.  Used by the rotation scorer to adjust GCD
# uptime expectations.  melee_modifier overrides gcd_modifier for melee
# specs when the fight punishes melee more than ranged.

@dataclass(frozen=True)
class EncounterContext:
    name: str
    gcd_modifier: float = 1.0
    melee_modifier: float | None = None  # Override for melee if different
    notes: str = ""


ENCOUNTER_CONTEXTS: dict[str, EncounterContext] = {
    # --- TBC: Karazhan ---
    "Shade of Aran": EncounterContext(
        "Shade of Aran", 0.85, 0.80, "Flame Wreath, Blizzard dodge",
    ),
    "Netherspite": EncounterContext(
        "Netherspite", 0.70, 0.65, "Banish phase ~33% = no DPS",
    ),
    "Prince Malchezaar": EncounterContext(
        "Prince Malchezaar", 0.85, 0.80, "Infernal dodging, Enfeeble",
    ),
    # --- TBC: Gruul's Lair ---
    "Gruul the Dragonkiller": EncounterContext(
        "Gruul the Dragonkiller", 0.85, 0.80, "Shatter knockback",
    ),
}
