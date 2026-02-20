# Domain Correctness Fixes — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix game-mechanic accuracy across rotation scoring, healer analysis, game constants, and boss encounter context — making Shukketsu more accurate than WoWAnalyzer for Classic/TBC.

**Architecture:** Data-first approach: expand constants → add spec rules → add encounter modifiers → fix HPS pipeline → rewrite scorer with 3 role-specific engines → update prompts.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0, FastAPI, pytest, ruff

**Design doc:** `docs/plans/2026-02-19-domain-correctness-design.md`

**Test command:** `python3 -m pytest code/tests/ -v`
**Lint command:** `python3 -m ruff check code/`
**Single test:** `python3 -m pytest code/tests/path/test.py::TestClass::test_name -v`

---

## Task 1: Fix Consumable Spell ID Mismatches

Two wrong spell IDs in `REQUIRED_CONSUMABLES` produce incorrect consumable audit results today.

**Files:**
- Modify: `code/shukketsu/pipeline/constants.py:251-257,258-262,263-269`
- Test: `code/tests/pipeline/test_constants.py`

**Step 1: Write failing test**

Add to `code/tests/pipeline/test_constants.py`:

```python
class TestConsumableSpellIds:
    """Verify REQUIRED_CONSUMABLES spell IDs match CONSUMABLE_CATEGORIES names."""

    def test_caster_dps_has_correct_firepower_id(self):
        """28501 is Elixir of Major Firepower, not 28509 (Major Defense)."""
        caster_ids = {c[0] for c in REQUIRED_CONSUMABLES["caster_dps"]}
        assert 28501 in caster_ids, "Caster DPS should have 28501 (Major Firepower)"
        assert 28509 not in caster_ids, "28509 is Major Defense, not Firepower"

    def test_tank_has_correct_healing_power_id(self):
        """28491 is Elixir of Healing Power, not 28502 (Major Mageblood)."""
        tank_ids = {c[0] for c in REQUIRED_CONSUMABLES["tank"]}
        assert 28491 in tank_ids, "Tank should have 28491 (Healing Power)"

    def test_all_consumable_ids_exist_in_categories(self):
        """Every required consumable spell ID should be in CONSUMABLE_CATEGORIES."""
        cat_ids = set(CONSUMABLE_CATEGORIES.keys())
        for role, consumables in REQUIRED_CONSUMABLES.items():
            if role == "all":
                continue  # Food buffs use different IDs
            for spell_id, _name, _cat, _uptime in consumables:
                assert spell_id in cat_ids, (
                    f"Spell {spell_id} ({_name}) for {role} not in CONSUMABLE_CATEGORIES"
                )
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest code/tests/pipeline/test_constants.py::TestConsumableSpellIds -v`
Expected: FAIL — 28509 found in caster_dps instead of 28501

**Step 3: Fix the two wrong spell IDs**

In `code/shukketsu/pipeline/constants.py`:

- In `REQUIRED_CONSUMABLES["caster_dps"]`: change `(28509, "Elixir of Major Firepower", ...)` → `(28501, "Elixir of Major Firepower", ...)`
- In `REQUIRED_CONSUMABLES["tank"]`: change `(28502, "Elixir of Healing Power", ...)` → `(28491, "Elixir of Healing Power", ...)`

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest code/tests/pipeline/test_constants.py::TestConsumableSpellIds -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `python3 -m pytest code/tests/ -v`
Expected: All 713+ tests pass

**Step 6: Lint**

Run: `python3 -m ruff check code/`
Expected: Clean

**Step 7: Commit**

```bash
git add code/shukketsu/pipeline/constants.py code/tests/pipeline/test_constants.py
git commit -m "fix: correct 2 wrong spell IDs in REQUIRED_CONSUMABLES

28509 (Major Defense) → 28501 (Major Firepower) for caster_dps
28502 (Major Mageblood) → 28491 (Healing Power) for tank

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Add cd_type to CooldownDef + New Cooldowns

Expand the cooldown system with type classification and missing abilities.

**Files:**
- Modify: `code/shukketsu/pipeline/constants.py:140-193`
- Test: `code/tests/pipeline/test_constants.py`

**Step 1: Write failing tests**

Add to `code/tests/pipeline/test_constants.py`:

```python
class TestCooldownTypes:
    """Verify CooldownDef has cd_type and all entries are correctly classified."""

    def test_cooldown_def_has_cd_type(self):
        assert hasattr(CooldownDef, "__dataclass_fields__")
        assert "cd_type" in CooldownDef.__dataclass_fields__

    def test_all_cd_types_valid(self):
        valid_types = {"throughput", "interrupt", "defensive", "utility"}
        for class_name, cds in CLASSIC_COOLDOWNS.items():
            for cd in cds:
                assert cd.cd_type in valid_types, (
                    f"{class_name} {cd.name} has invalid cd_type={cd.cd_type}"
                )

    def test_interrupts_present(self):
        """Verify key interrupts are tracked (Earth Shock, not Wind Shear)."""
        warrior_cds = {cd.name for cd in CLASSIC_COOLDOWNS["Warrior"]}
        assert "Pummel" in warrior_cds

        rogue_cds = {cd.name for cd in CLASSIC_COOLDOWNS["Rogue"]}
        assert "Kick" in rogue_cds

        mage_cds = {cd.name for cd in CLASSIC_COOLDOWNS["Mage"]}
        assert "Counterspell" in mage_cds

        shaman_cds = {cd.name for cd in CLASSIC_COOLDOWNS["Shaman"]}
        assert "Earth Shock" in shaman_cds
        assert "Wind Shear" not in shaman_cds  # Does NOT exist in TBC

    def test_shield_block_not_tracked(self):
        """Shield Block (5s CD) is a rotation ability, not a defensive CD."""
        warrior_names = {cd.name for cd in CLASSIC_COOLDOWNS["Warrior"]}
        assert "Shield Block" not in warrior_names

    def test_tree_of_life_not_tracked(self):
        """Tree of Life is a shapeshift, not a cooldown."""
        druid_names = {cd.name for cd in CLASSIC_COOLDOWNS["Druid"]}
        assert "Tree of Life" not in druid_names

    def test_defensive_cds_present(self):
        warrior_cds = {cd.name: cd for cd in CLASSIC_COOLDOWNS["Warrior"]}
        assert "Shield Wall" in warrior_cds
        assert warrior_cds["Shield Wall"].cd_type == "defensive"
        assert "Last Stand" in warrior_cds
        assert warrior_cds["Last Stand"].cd_type == "defensive"

    def test_utility_cds_present(self):
        warrior_cds = {cd.name: cd for cd in CLASSIC_COOLDOWNS["Warrior"]}
        assert "Bloodrage" in warrior_cds
        assert warrior_cds["Bloodrage"].cd_type == "utility"

    def test_throughput_cds_unchanged(self):
        """Existing throughput CDs should still be present and correctly typed."""
        warrior_cds = {cd.name: cd for cd in CLASSIC_COOLDOWNS["Warrior"]}
        assert "Death Wish" in warrior_cds
        assert warrior_cds["Death Wish"].cd_type == "throughput"

    @pytest.mark.parametrize("class_name", list(CLASSIC_COOLDOWNS.keys()))
    def test_no_duplicate_spell_ids(self, class_name):
        cds = CLASSIC_COOLDOWNS[class_name]
        ids = [cd.spell_id for cd in cds]
        assert len(ids) == len(set(ids)), f"Duplicate spell IDs in {class_name}"
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest code/tests/pipeline/test_constants.py::TestCooldownTypes -v`
Expected: FAIL — cd_type not found on CooldownDef

**Step 3: Implement**

In `code/shukketsu/pipeline/constants.py`:

1. Add `cd_type` field to `CooldownDef` (line ~145):
```python
@dataclass(frozen=True)
class CooldownDef:
    spell_id: int
    name: str
    cooldown_sec: int
    duration_sec: int = 0
    cd_type: str = "throughput"  # "throughput", "interrupt", "defensive", "utility"
```

2. Add `cd_type="throughput"` to all existing entries (they're already throughput CDs).

3. Remove Tree of Life (33891) from Druid entry.

4. Add new entries per class. Example for Warrior:
```python
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
```

Full new entries by class:
- **Warrior:** +Pummel (6552, interrupt), Shield Wall (871, defensive), Last Stand (12975, defensive), Bloodrage (2687, utility), Berserker Rage (18499, utility)
- **Rogue:** +Kick (1769, interrupt), Evasion (26669, defensive), Cloak of Shadows (31224, defensive)
- **Mage:** +Counterspell (2139, interrupt)
- **Shaman:** +Earth Shock (25454, interrupt), Mana Tide Totem (16190, utility), Fire Elemental Totem (2894, utility)
- **Druid:** +Feral Charge (16979, interrupt). Remove Tree of Life.
- **Paladin:** +Hammer of Justice (10308, defensive), Lay on Hands (10310, utility), Divine Shield (642, defensive)

**Step 4: Run tests**

Run: `python3 -m pytest code/tests/pipeline/test_constants.py::TestCooldownTypes -v`
Expected: PASS

**Step 5: Run full suite + lint**

Run: `python3 -m pytest code/tests/ -v && python3 -m ruff check code/`
Expected: All pass, lint clean

**Step 6: Commit**

```bash
git add code/shukketsu/pipeline/constants.py code/tests/pipeline/test_constants.py
git commit -m "feat: add cd_type to CooldownDef + 15 new cooldowns

Add interrupt/defensive/utility classification. New entries:
- Interrupts: Pummel, Kick, Counterspell, Earth Shock, Feral Charge
- Defensive: Shield Wall, Last Stand, Evasion, Cloak of Shadows,
  Hammer of Justice, Divine Shield
- Utility: Bloodrage, Berserker Rage, Mana Tide Totem,
  Fire Elemental Totem, Lay on Hands

Remove Tree of Life (shapeshift, not CD) and Shield Block (rotation ability).
Earth Shock replaces Wind Shear (which doesn't exist in TBC).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Add Hunter + Feral Druid DoTs

**Files:**
- Modify: `code/shukketsu/pipeline/constants.py:340-357`
- Test: `code/tests/pipeline/test_constants.py`

**Step 1: Write failing test**

```python
class TestDotExpansion:
    def test_hunter_dots_present(self):
        assert "Hunter" in CLASSIC_DOTS
        names = {d.name for d in CLASSIC_DOTS["Hunter"]}
        assert "Serpent Sting" in names

    def test_feral_druid_dots_present(self):
        """Feral DoTs are under the existing 'Druid' key alongside Balance DoTs."""
        druid_dots = {d.name for d in CLASSIC_DOTS["Druid"]}
        assert "Rake" in druid_dots
        assert "Rip" in druid_dots
        # Existing Balance dots still present
        assert "Moonfire" in druid_dots
        assert "Insect Swarm" in druid_dots

    def test_dot_values_correct(self):
        hunter_dots = {d.name: d for d in CLASSIC_DOTS["Hunter"]}
        ss = hunter_dots["Serpent Sting"]
        assert ss.spell_id == 27016
        assert ss.duration_ms == 15000
        assert ss.tick_interval_ms == 3000

        druid_dots = {d.name: d for d in CLASSIC_DOTS["Druid"]}
        rake = druid_dots["Rake"]
        assert rake.spell_id == 27003
        assert rake.duration_ms == 9000
        assert rake.tick_interval_ms == 3000

        rip = druid_dots["Rip"]
        assert rip.spell_id == 27008
        assert rip.duration_ms == 12000
        assert rip.tick_interval_ms == 2000
```

**Step 2: Run test → FAIL**

**Step 3: Add entries to CLASSIC_DOTS**

In `code/shukketsu/pipeline/constants.py`, add after the Druid section (~line 356):

```python
"Hunter": [
    DotDef(27016, "Serpent Sting", 15000, 3000),
],
```

And append to existing "Druid" list:
```python
DotDef(27003, "Rake", 9000, 3000),
DotDef(27008, "Rip", 12000, 2000),
```

**Step 4: Run test → PASS**

**Step 5: Full suite + lint**

**Step 6: Commit**

```bash
git add code/shukketsu/pipeline/constants.py code/tests/pipeline/test_constants.py
git commit -m "feat: add Hunter + Feral Druid DoTs to CLASSIC_DOTS

Serpent Sting (27016, 15s/3s), Rake (27003, 9s/3s), Rip (27008, 12s/2s)
Verified spell IDs against Wowhead TBC Classic.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Add SpecRules Dataclass + All 27 Specs

**Files:**
- Modify: `code/shukketsu/pipeline/constants.py` (add after ROLE_BY_SPEC ~line 227)
- Test: `code/tests/pipeline/test_constants.py`

**Step 1: Write failing tests**

```python
class TestSpecRules:
    def test_spec_rules_dataclass_exists(self):
        from shukketsu.pipeline.constants import SpecRules
        assert hasattr(SpecRules, "__dataclass_fields__")
        fields = set(SpecRules.__dataclass_fields__.keys())
        assert "gcd_target" in fields
        assert "cpm_target" in fields
        assert "cd_efficiency_target" in fields
        assert "long_cd_efficiency" in fields
        assert "key_abilities" in fields
        assert "role" in fields
        assert "healer_overheal_target" in fields

    def test_spec_rotation_rules_dict_exists(self):
        from shukketsu.pipeline.constants import SPEC_ROTATION_RULES
        assert isinstance(SPEC_ROTATION_RULES, dict)

    @pytest.mark.parametrize(
        "class_name,spec_name",
        [(s.class_name, s.spec_name) for s in TBC_SPECS],
    )
    def test_every_spec_has_rules(self, class_name, spec_name):
        from shukketsu.pipeline.constants import SPEC_ROTATION_RULES
        key = (class_name, spec_name)
        assert key in SPEC_ROTATION_RULES, f"Missing rules for {key}"

    @pytest.mark.parametrize(
        "class_name,spec_name",
        [(s.class_name, s.spec_name) for s in TBC_SPECS],
    )
    def test_spec_rules_sane_values(self, class_name, spec_name):
        from shukketsu.pipeline.constants import SPEC_ROTATION_RULES
        rules = SPEC_ROTATION_RULES[(class_name, spec_name)]
        assert 50 <= rules.gcd_target <= 95
        assert rules.cpm_target > 0
        assert 60 <= rules.cd_efficiency_target <= 95
        assert 40 <= rules.long_cd_efficiency <= 70
        assert len(rules.key_abilities) > 0
        assert rules.role in {
            "melee_dps", "caster_dps", "ranged_dps", "healer", "tank"
        }

    def test_healer_specs_have_overheal_targets(self):
        from shukketsu.pipeline.constants import SPEC_ROTATION_RULES
        healer_keys = [
            ("Paladin", "Holy"),
            ("Priest", "Discipline"),
            ("Priest", "Holy"),
            ("Shaman", "Restoration"),
            ("Druid", "Restoration"),
        ]
        for key in healer_keys:
            rules = SPEC_ROTATION_RULES[key]
            assert rules.role == "healer"
            assert 15 <= rules.healer_overheal_target <= 50

    def test_holy_paladin_low_overheal_target(self):
        from shukketsu.pipeline.constants import SPEC_ROTATION_RULES
        rules = SPEC_ROTATION_RULES[("Paladin", "Holy")]
        assert rules.healer_overheal_target <= 25  # Reactive single-target

    def test_resto_druid_high_overheal_target(self):
        from shukketsu.pipeline.constants import SPEC_ROTATION_RULES
        rules = SPEC_ROTATION_RULES[("Druid", "Restoration")]
        assert rules.healer_overheal_target >= 40  # HoTs get sniped
```

**Step 2: Run → FAIL**

**Step 3: Implement**

Add to `code/shukketsu/pipeline/constants.py` after ROLE_BY_SPEC:

```python
@dataclass(frozen=True)
class SpecRules:
    gcd_target: float
    cpm_target: float
    cd_efficiency_target: float
    long_cd_efficiency: float
    key_abilities: list[str]
    role: str
    healer_overheal_target: float = 35.0


SPEC_ROTATION_RULES: dict[tuple[str, str], SpecRules] = {
    # --- Melee DPS ---
    ("Warrior", "Arms"): SpecRules(88, 28, 85, 60, ["Mortal Strike", "Whirlwind", "Slam"], "melee_dps"),
    ("Warrior", "Fury"): SpecRules(90, 32, 85, 60, ["Bloodthirst", "Whirlwind", "Heroic Strike"], "melee_dps"),
    ("Paladin", "Retribution"): SpecRules(85, 25, 80, 60, ["Crusader Strike", "Seal of Command", "Judgement"], "melee_dps"),
    ("Rogue", "Assassination"): SpecRules(88, 30, 85, 65, ["Mutilate", "Envenom", "Slice and Dice"], "melee_dps"),
    ("Rogue", "Combat"): SpecRules(90, 32, 85, 65, ["Sinister Strike", "Slice and Dice", "Blade Flurry"], "melee_dps"),
    ("Rogue", "Subtlety"): SpecRules(85, 28, 80, 60, ["Hemorrhage", "Slice and Dice"], "melee_dps"),
    ("Shaman", "Enhancement"): SpecRules(85, 25, 80, 60, ["Stormstrike", "Earth Shock", "Windfury"], "melee_dps"),
    ("Druid", "Feral"): SpecRules(88, 30, 85, 60, ["Shred", "Mangle", "Rip"], "melee_dps"),
    # --- Ranged DPS ---
    ("Hunter", "Beast Mastery"): SpecRules(82, 22, 85, 60, ["Steady Shot", "Auto Shot", "Kill Command"], "ranged_dps"),
    ("Hunter", "Marksmanship"): SpecRules(82, 22, 85, 60, ["Steady Shot", "Auto Shot", "Arcane Shot"], "ranged_dps"),
    ("Hunter", "Survival"): SpecRules(82, 22, 85, 60, ["Steady Shot", "Auto Shot", "Raptor Strike"], "ranged_dps"),
    # --- Caster DPS ---
    ("Priest", "Shadow"): SpecRules(88, 25, 80, 60, ["Shadow Word: Pain", "Mind Blast", "Mind Flay"], "caster_dps"),
    ("Shaman", "Elemental"): SpecRules(85, 25, 80, 60, ["Lightning Bolt", "Chain Lightning"], "caster_dps"),
    ("Mage", "Arcane"): SpecRules(90, 28, 85, 60, ["Arcane Blast", "Arcane Missiles"], "caster_dps"),
    ("Mage", "Fire"): SpecRules(85, 22, 85, 60, ["Fireball", "Scorch", "Fire Blast"], "caster_dps"),
    ("Mage", "Frost"): SpecRules(85, 22, 85, 60, ["Frostbolt", "Ice Lance"], "caster_dps"),
    ("Warlock", "Affliction"): SpecRules(85, 22, 80, 60, ["Corruption", "Unstable Affliction", "Shadow Bolt"], "caster_dps"),
    ("Warlock", "Demonology"): SpecRules(85, 22, 80, 60, ["Shadow Bolt", "Incinerate"], "caster_dps"),
    ("Warlock", "Destruction"): SpecRules(88, 24, 85, 60, ["Shadow Bolt", "Incinerate", "Immolate"], "caster_dps"),
    ("Druid", "Balance"): SpecRules(85, 22, 80, 60, ["Starfire", "Wrath", "Moonfire"], "caster_dps"),
    # --- Healers ---
    ("Paladin", "Holy"): SpecRules(55, 18, 70, 50, ["Flash of Light", "Holy Light"], "healer", 20),
    ("Priest", "Discipline"): SpecRules(60, 20, 75, 55, ["Power Word: Shield", "Flash Heal", "Prayer of Mending"], "healer", 25),
    ("Priest", "Holy"): SpecRules(65, 22, 75, 55, ["Circle of Healing", "Prayer of Healing", "Flash Heal"], "healer", 30),
    ("Shaman", "Restoration"): SpecRules(60, 20, 75, 55, ["Chain Heal", "Lesser Healing Wave"], "healer", 30),
    ("Druid", "Restoration"): SpecRules(65, 22, 70, 50, ["Lifebloom", "Rejuvenation", "Healing Touch"], "healer", 45),
    # --- Tanks ---
    ("Warrior", "Protection"): SpecRules(88, 30, 85, 50, ["Shield Slam", "Devastate", "Thunderclap"], "tank"),
    ("Paladin", "Protection"): SpecRules(85, 26, 80, 50, ["Consecration", "Holy Shield", "Avenger's Shield"], "tank"),
}


# Role-based fallback for unknown specs
ROLE_DEFAULT_RULES: dict[str, SpecRules] = {
    "melee_dps": SpecRules(85, 28, 80, 60, [], "melee_dps"),
    "caster_dps": SpecRules(85, 22, 80, 60, [], "caster_dps"),
    "ranged_dps": SpecRules(80, 20, 80, 60, [], "ranged_dps"),
    "healer": SpecRules(60, 20, 70, 50, [], "healer", 35),
    "tank": SpecRules(85, 28, 80, 50, [], "tank"),
}
```

**Step 4: Run → PASS**

**Step 5: Full suite + lint**

**Step 6: Commit**

```bash
git add code/shukketsu/pipeline/constants.py code/tests/pipeline/test_constants.py
git commit -m "feat: add SpecRules dataclass with all 27 TBC specs

Per-spec GCD targets (55-90%), CPM targets (18-32), CD efficiency
thresholds (short/long), key abilities, and healer overheal targets
(Holy Paladin 20%, Resto Druid 45%). Includes role-based fallbacks.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Add EncounterContext for All Bosses

**Files:**
- Modify: `code/shukketsu/pipeline/constants.py` (add after ENCOUNTER_PHASES ~line 451)
- Test: `code/tests/pipeline/test_constants.py`

**Step 1: Write failing tests**

```python
class TestEncounterContexts:
    def test_encounter_context_dataclass_exists(self):
        from shukketsu.pipeline.constants import EncounterContext
        fields = set(EncounterContext.__dataclass_fields__.keys())
        assert "name" in fields
        assert "gcd_modifier" in fields
        assert "melee_modifier" in fields
        assert "notes" in fields

    def test_encounter_contexts_dict_exists(self):
        from shukketsu.pipeline.constants import ENCOUNTER_CONTEXTS
        assert isinstance(ENCOUNTER_CONTEXTS, dict)

    def test_patchwerk_is_1_0(self):
        from shukketsu.pipeline.constants import ENCOUNTER_CONTEXTS
        ctx = ENCOUNTER_CONTEXTS["Patchwerk"]
        assert ctx.gcd_modifier == 1.0
        assert ctx.melee_modifier is None  # No melee override needed

    def test_sapphiron_has_melee_penalty(self):
        from shukketsu.pipeline.constants import ENCOUNTER_CONTEXTS
        ctx = ENCOUNTER_CONTEXTS["Sapphiron"]
        assert ctx.gcd_modifier < 1.0  # Air phases reduce DPS uptime
        assert ctx.melee_modifier is not None
        assert ctx.melee_modifier < ctx.gcd_modifier  # Melee worse than ranged

    def test_heigan_is_low(self):
        from shukketsu.pipeline.constants import ENCOUNTER_CONTEXTS
        ctx = ENCOUNTER_CONTEXTS["Heigan the Unclean"]
        assert ctx.gcd_modifier <= 0.65  # Dance phase = minimal DPS

    def test_unknown_encounter_defaults_to_1(self):
        from shukketsu.pipeline.constants import ENCOUNTER_CONTEXTS
        assert "NonexistentBoss" not in ENCOUNTER_CONTEXTS

    @pytest.mark.parametrize(
        "boss_name",
        list(ENCOUNTER_CONTEXTS.keys()) if hasattr(constants, "ENCOUNTER_CONTEXTS") else [],
    )
    def test_modifiers_in_valid_range(self, boss_name):
        from shukketsu.pipeline.constants import ENCOUNTER_CONTEXTS
        ctx = ENCOUNTER_CONTEXTS[boss_name]
        assert 0.3 <= ctx.gcd_modifier <= 1.0
        if ctx.melee_modifier is not None:
            assert 0.3 <= ctx.melee_modifier <= 1.0
            assert ctx.melee_modifier <= ctx.gcd_modifier
```

Note: the parametrize test should import `ENCOUNTER_CONTEXTS` inside the test function body. The subagent should write this so the parametrize works correctly — use a module-level import of `constants` and reference `constants.ENCOUNTER_CONTEXTS` in the parametrize decorator after the dataclass is created.

**Step 2: Run → FAIL**

**Step 3: Implement**

Add to `code/shukketsu/pipeline/constants.py`:

```python
@dataclass(frozen=True)
class EncounterContext:
    name: str
    gcd_modifier: float = 1.0
    melee_modifier: float | None = None  # Override for melee if different
    notes: str = ""


ENCOUNTER_CONTEXTS: dict[str, EncounterContext] = {
    # --- Naxxramas ---
    "Patchwerk": EncounterContext("Patchwerk", 1.0, notes="Pure tank-and-spank"),
    "Grobbulus": EncounterContext("Grobbulus", 0.90, 0.85, "Kiting, injection positioning"),
    "Gluth": EncounterContext("Gluth", 0.85, notes="Zombie kiting, Decimate"),
    "Thaddius": EncounterContext("Thaddius", 0.80, notes="P1 adds (no boss), polarity movement"),
    "Anub'Rekhan": EncounterContext("Anub'Rekhan", 0.90, 0.85, "Locust Swarm kiting"),
    "Grand Widow Faerlina": EncounterContext("Grand Widow Faerlina", 0.95, notes="Mostly single-phase"),
    "Maexxna": EncounterContext("Maexxna", 0.90, notes="Web Wrap stuns, Web Spray"),
    "Noth the Plaguebringer": EncounterContext("Noth the Plaguebringer", 0.70, notes="Boss immune during Balcony phases"),
    "Heigan the Unclean": EncounterContext("Heigan the Unclean", 0.60, 0.55, "Dance phase = minimal DPS"),
    "Loatheb": EncounterContext("Loatheb", 0.95, notes="Single-phase, predictable"),
    "Instructor Razuvious": EncounterContext("Instructor Razuvious", 0.90, notes="MC tanking"),
    "Gothik the Harvester": EncounterContext("Gothik the Harvester", 0.75, notes="P1 adds only"),
    "The Four Horsemen": EncounterContext("The Four Horsemen", 0.85, 0.80, "Tank rotation movement"),
    "Sapphiron": EncounterContext("Sapphiron", 0.70, 0.65, "Cyclic air phases, no boss DPS ~30%"),
    "Kel'Thuzad": EncounterContext("Kel'Thuzad", 0.65, 0.60, "P1 adds ~20%, P3 ice blocks"),
    # --- TBC ---
    "Shade of Aran": EncounterContext("Shade of Aran", 0.85, 0.80, "Flame Wreath, Blizzard dodge"),
    "Netherspite": EncounterContext("Netherspite", 0.70, 0.65, "Banish phase ~33% = no DPS"),
    "Prince Malchezaar": EncounterContext("Prince Malchezaar", 0.85, 0.80, "Infernal dodging, Enfeeble"),
    "Gruul the Dragonkiller": EncounterContext("Gruul the Dragonkiller", 0.85, 0.80, "Shatter knockback"),
    "Leotheras the Blind": EncounterContext("Leotheras the Blind", 0.80, 0.75, "Demon Form untargetable"),
    "Lady Vashj": EncounterContext("Lady Vashj", 0.65, 0.60, "P2 shield = no boss DPS"),
    "Kael'thas Sunstrider": EncounterContext("Kael'thas Sunstrider", 0.55, 0.50, "P1-P3 no Kael DPS ~50%"),
    "Archimonde": EncounterContext("Archimonde", 0.80, notes="Air Burst movement, fire"),
    "Illidan Stormrage": EncounterContext("Illidan Stormrage", 0.70, 0.60, "P2 boss airborne, transitions"),
    "M'uru": EncounterContext("M'uru", 0.80, 0.75, "Heavy add management P1"),
    "Kil'jaeden": EncounterContext("Kil'jaeden", 0.70, 0.65, "Multiple transition phases"),
    "Brutallus": EncounterContext("Brutallus", 1.0, notes="Pure DPS race"),
}
```

**Step 4-6: Run tests, full suite, commit**

```bash
git commit -m "feat: add EncounterContext with GCD modifiers for 27 bosses

Pre-computed encounter_gcd_modifier per boss accounts for downtime
phases (Sapphiron air 0.70, Heigan dance 0.60, KT adds 0.65, etc).
Separate melee_modifier for fights that punish melee more than ranged.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 6: Fix Healer HPS in Ingest Pipeline

**Files:**
- Modify: `code/shukketsu/pipeline/ingest.py:44-72`
- Test: `code/tests/pipeline/test_ingest.py`

**Step 1: Write failing tests**

Add to `code/tests/pipeline/test_ingest.py`:

```python
class TestHealerHpsRouting:
    """Verify parse_rankings_to_performances routes HPS correctly for healers."""

    def test_healer_amount_stored_as_hps(self):
        rankings = [
            {
                "name": "HolyPriest",
                "class": "Priest",
                "spec": "Holy",
                "server": {"name": "Whitemane"},
                "total": 500000,
                "amount": 1200.5,  # This is HPS for a healer
                "rankPercent": 85.0,
                "deaths": 0,
                "interrupts": 0,
                "dispels": 3,
            }
        ]
        result = parse_rankings_to_performances(rankings, fight_id=1, my_character_names=set())
        perf = result[0]
        assert perf.hps == 1200.5, "Healer amount should go to hps"
        assert perf.dps == 0.0, "Healer dps should be 0"

    def test_dps_amount_stored_as_dps(self):
        rankings = [
            {
                "name": "FuryWarrior",
                "class": "Warrior",
                "spec": "Fury",
                "server": {"name": "Whitemane"},
                "total": 1000000,
                "amount": 2500.0,  # This is DPS
                "rankPercent": 90.0,
                "deaths": 0,
                "interrupts": 0,
                "dispels": 0,
            }
        ]
        result = parse_rankings_to_performances(rankings, fight_id=1, my_character_names=set())
        perf = result[0]
        assert perf.dps == 2500.0, "DPS amount should go to dps"
        assert perf.hps == 0.0, "DPS hps should be 0"

    def test_tank_amount_stored_as_dps(self):
        """Tanks are ranked by DPS on WCL, not by mitigation."""
        rankings = [
            {
                "name": "ProtWarrior",
                "class": "Warrior",
                "spec": "Protection",
                "server": {"name": "Whitemane"},
                "total": 300000,
                "amount": 800.0,
                "rankPercent": 70.0,
                "deaths": 0,
                "interrupts": 0,
                "dispels": 0,
            }
        ]
        result = parse_rankings_to_performances(rankings, fight_id=1, my_character_names=set())
        perf = result[0]
        assert perf.dps == 800.0
        assert perf.hps == 0.0

    def test_restoration_shaman_is_healer(self):
        rankings = [
            {
                "name": "RestoSham",
                "class": "Shaman",
                "spec": "Restoration",
                "server": {"name": "Whitemane"},
                "total": 600000,
                "amount": 1500.0,
                "rankPercent": 88.0,
                "deaths": 0,
                "interrupts": 0,
                "dispels": 5,
            }
        ]
        result = parse_rankings_to_performances(rankings, fight_id=1, my_character_names=set())
        perf = result[0]
        assert perf.hps == 1500.0
        assert perf.dps == 0.0
```

**Step 2: Run → FAIL**

**Step 3: Implement**

In `code/shukketsu/pipeline/ingest.py`, modify `parse_rankings_to_performances` (lines 54-70):

Add import at top:
```python
from shukketsu.pipeline.constants import ROLE_BY_SPEC
```

Change lines 61-63 from:
```python
            dps=r.get("amount", 0.0),
            total_healing=0,
            hps=0.0,
```

To:
```python
            dps=0.0 if ROLE_BY_SPEC.get(r["spec"]) == "healer" else r.get("amount", 0.0),
            total_healing=0,
            hps=r.get("amount", 0.0) if ROLE_BY_SPEC.get(r["spec"]) == "healer" else 0.0,
```

**Step 4: Run tests → PASS**

**Step 5: Full suite + lint**

**Step 6: Commit**

```bash
git add code/shukketsu/pipeline/ingest.py code/tests/pipeline/test_ingest.py
git commit -m "fix: route healer WCL amount to hps column, not dps

parse_rankings_to_performances now checks ROLE_BY_SPEC to detect
healer specs (Holy, Discipline, Restoration) and stores their WCL
amount in hps instead of dps.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 7: Alembic Migration to Backfill Existing Healer Data

**Files:**
- Create: `code/alembic/versions/XXX_backfill_healer_hps.py`

**Step 1: Generate migration**

```bash
cd /home/lyro/nvidia-workbench/wcl-tbc-analyzer
alembic revision -m "backfill healer hps from dps column"
```

**Step 2: Write migration**

```python
"""backfill healer hps from dps column

Revision ID: <auto>
"""

from alembic import op


# revision identifiers
revision = "<auto>"
down_revision = "<previous>"


def upgrade() -> None:
    op.execute(
        """
        UPDATE fight_performances
        SET hps = dps, dps = 0.0
        WHERE player_spec IN ('Holy', 'Discipline', 'Restoration')
          AND dps > 0.0
          AND hps = 0.0
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE fight_performances
        SET dps = hps, hps = 0.0
        WHERE player_spec IN ('Holy', 'Discipline', 'Restoration')
          AND hps > 0.0
          AND dps = 0.0
        """
    )
```

**Step 3: Commit**

```bash
git add code/alembic/versions/
git commit -m "migrate: backfill healer hps from dps column

Moves existing healer DPS values (which were actually HPS) to the
correct hps column for Holy, Discipline, and Restoration specs.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 8: Update SQL Queries for Role-Aware DPS/HPS

This task updates all SQL queries that display DPS to also handle HPS for healers.

**Files:**
- Modify: `code/shukketsu/db/queries/player.py` (lines 27, 53, 78, 133-143, 152-154, 189, 205, 249)
- Modify: `code/shukketsu/db/queries/raid.py` (lines 35, 69, 89, 124-125)
- Modify: `code/shukketsu/db/queries/api.py` (lines 66, 175-176, 189, 218, 229, 268, 281)
- Test: `code/tests/db/test_queries_logic.py`

**Step 1: Write failing test**

The queries use raw SQL text, so we test the string content:

```python
class TestRoleAwareQueries:
    """Verify key queries select hps alongside dps."""

    def test_my_performance_selects_hps(self):
        from shukketsu.db.queries.player import MY_PERFORMANCE
        query_text = MY_PERFORMANCE.text
        assert "fp.hps" in query_text

    def test_fight_details_selects_hps(self):
        from shukketsu.db.queries.player import FIGHT_DETAILS
        query_text = FIGHT_DETAILS.text
        assert "fp.hps" in query_text

    def test_spec_leaderboard_has_hps_variant(self):
        """Leaderboard should include hps for healer ranking."""
        from shukketsu.db.queries.player import SPEC_LEADERBOARD
        query_text = SPEC_LEADERBOARD.text
        assert "fp.hps" in query_text or "hps" in query_text

    def test_raid_execution_has_hps(self):
        from shukketsu.db.queries.raid import RAID_EXECUTION_SUMMARY
        query_text = RAID_EXECUTION_SUMMARY.text
        assert "hps" in query_text
```

**Step 2: Run → likely already partially passes (some queries already select fp.hps)**

**Step 3: Update queries**

The key pattern: wherever a query selects `fp.dps`, also select `fp.hps` so tools can choose which to display. For aggregate queries (AVG, MAX), add parallel hps aggregates:

In `player.py` SPEC_LEADERBOARD (lines 133-143): add `ROUND(AVG(fp.hps)::numeric, 1) AS avg_hps`

In `raid.py` RAID_EXECUTION_SUMMARY (lines 124-125): add `ROUND(AVG(fp.hps)::numeric, 1) AS raid_avg_hps`

**Important:** Don't change queries that already select both. Only add `hps` aggregates to queries that aggregate `dps` without `hps`.

**Step 4-6: Tests, suite, commit**

```bash
git commit -m "feat: add hps columns to aggregate SQL queries

SPEC_LEADERBOARD and RAID_EXECUTION_SUMMARY now include hps
aggregates alongside dps, enabling role-aware display in tools.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 9: Update Agent Tools for Role-Aware Display

**Files:**
- Modify: `code/shukketsu/agent/tools/player_tools.py` (lines 41-42, 63, 120-132, 165, 198, 274, 317, 352, 399-400)
- Modify: `code/shukketsu/agent/tools/raid_tools.py`
- Test: `code/tests/agent/test_tools.py`

**Step 1: Write failing tests**

```python
class TestRoleAwareToolDisplay:
    """Tools should show HPS for healers, DPS for others."""

    async def test_get_my_performance_healer_shows_hps(self):
        """When a healer's data is formatted, show HPS not DPS."""
        # Mock session returning a healer row
        # Assert output contains "HPS:" not "DPS:" for the healer line

    async def test_get_my_performance_dps_shows_dps(self):
        """When a DPS player's data is formatted, show DPS."""
        # Assert output contains "DPS:" for the DPS line
```

The subagent should follow the existing test patterns in `test_tools.py` — mock the session, mock `session.execute` to return appropriate Row objects, and assert on the string output.

**Step 3: Implement**

Add a helper to `player_tools.py`:

```python
from shukketsu.pipeline.constants import ROLE_BY_SPEC

def _metric_label(spec: str) -> tuple[str, str]:
    """Return (label, field) for the primary metric based on spec role."""
    if ROLE_BY_SPEC.get(spec) == "healer":
        return "HPS", "hps"
    return "DPS", "dps"
```

Then update each formatting line. Example for `get_my_performance` line 63:
```python
# Before:
f"DPS: {r.dps:,.1f} |"
# After:
label, _field = _metric_label(r.player_spec)
val = r.hps if label == "HPS" else r.dps
f"{label}: {val:,.1f} |"
```

Apply the same pattern to all 10+ formatting locations listed in the Files section.

**Step 4-6: Tests, suite, commit**

```bash
git commit -m "feat: agent tools display HPS for healers, DPS for others

All player_tools and raid_tools now use _metric_label() to detect
healer specs via ROLE_BY_SPEC and display HPS instead of DPS.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 10: Rewrite Rotation Scorer — DPS Path

**Files:**
- Modify: `code/shukketsu/agent/tools/event_tools.py:484-580`
- Test: `code/tests/agent/test_tools.py`

**Step 1: Write failing tests**

```python
class TestDpsRotationScorer:
    async def test_fury_warrior_patchwerk_high_gcd(self):
        """90% GCD on Patchwerk (modifier 1.0) should score A or S."""
        # Mock: spec=Fury, encounter=Patchwerk, gcd=90%, cpm=32, cds all >85%
        # Assert grade in ("S", "A")

    async def test_fury_warrior_patchwerk_low_gcd(self):
        """72% GCD on Patchwerk should score D or F (no phase excuse)."""
        # Mock: spec=Fury, encounter=Patchwerk, gcd=72%
        # Assert grade in ("D", "F")

    async def test_fire_mage_sapphiron_adjusted(self):
        """72% GCD on Sapphiron (modifier 0.70) → adjusted target ~59.5%. Should pass."""
        # Mock: spec=Fire, encounter=Sapphiron, gcd=72%
        # Adjusted target = 85 * 0.70 = 59.5. 72 > 59.5, so this passes.
        # Assert grade >= "B"

    async def test_short_cd_uses_cd_efficiency_target(self):
        """Death Wish (180s, short CD) compared against spec.cd_efficiency_target."""
        # Mock: Fury Warrior, Death Wish at 70% efficiency
        # Fury cd_efficiency_target = 85. 70 < 85 → violation

    async def test_long_cd_uses_long_cd_efficiency(self):
        """Recklessness (900s, long CD) compared against spec.long_cd_efficiency."""
        # Mock: Fury Warrior, Recklessness at 55% efficiency
        # Fury long_cd_efficiency = 60. 55 < 60 → violation

    async def test_unknown_encounter_uses_modifier_1(self):
        """Unknown boss should not crash, uses modifier 1.0."""
        # Mock: encounter_name="Unknown Boss"
        # Assert no exception, modifier 1.0 applied

    async def test_unknown_spec_uses_role_defaults(self):
        """Unknown spec should fall back to ROLE_DEFAULT_RULES."""
        # Mock: class=Warrior, spec=Unknown
        # Assert no exception, defaults applied

    async def test_key_ability_missing_flagged(self):
        """If a key ability doesn't appear in top damage, flag it."""
        # Mock: Fury Warrior but no Bloodthirst in ability breakdown
        # Assert violation mentions "Bloodthirst"

    async def test_output_includes_encounter_context(self):
        """Output should show the adjusted threshold and encounter name."""
        # Assert output contains "Adjusted GCD target:" and encounter name

    async def test_melee_uses_melee_modifier(self):
        """Melee spec on Sapphiron uses melee_modifier (0.65), not gcd_modifier (0.70)."""
        # Mock: Fury Warrior on Sapphiron
        # Adjusted target = 90 * 0.65 = 58.5 (not 90 * 0.70 = 63.0)
```

**Step 2: Run → FAIL**

**Step 3: Implement**

Replace the body of `get_rotation_score` in `event_tools.py` (lines 484-580). The new implementation:

```python
@db_tool
async def get_rotation_score(
    session: AsyncSession,
    report_code: str,
    fight_id: int,
    player_name: str,
) -> str:
    """Score rotation quality for a player in a fight. Requires --with-events data."""
    from shukketsu.pipeline.constants import (
        ENCOUNTER_CONTEXTS,
        ROLE_BY_SPEC,
        ROLE_DEFAULT_RULES,
        SPEC_ROTATION_RULES,
        EncounterContext,
    )

    # Get player info
    info_result = await session.execute(
        PLAYER_FIGHT_INFO, {"report_code": report_code, "fight_id": fight_id, "player_name": f"%{player_name}%"}
    )
    info = info_result.first()
    if not info:
        return f"No data found for {player_name} in fight {fight_id}. Was --with-events used?"

    spec_key = (info.player_class, info.player_spec)
    role = ROLE_BY_SPEC.get(info.player_spec, "dps")
    rules = SPEC_ROTATION_RULES.get(spec_key)
    if not rules:
        rules = ROLE_DEFAULT_RULES.get(role, ROLE_DEFAULT_RULES["melee_dps"])

    # Route to role-specific scorer
    if rules.role == "healer":
        return await _score_healer(session, report_code, fight_id, player_name, info, rules)
    if rules.role == "tank":
        return await _score_tank(session, report_code, fight_id, player_name, info, rules)
    return await _score_dps(session, report_code, fight_id, player_name, info, rules)
```

Then implement `_score_dps`:

```python
async def _score_dps(session, report_code, fight_id, player_name, info, rules):
    # Resolve encounter context
    encounter_name = info.encounter_name if hasattr(info, "encounter_name") else ""
    ctx = ENCOUNTER_CONTEXTS.get(encounter_name, EncounterContext(encounter_name))

    # Choose modifier: melee uses melee_modifier when available
    modifier = ctx.gcd_modifier
    if rules.role == "melee_dps" and ctx.melee_modifier is not None:
        modifier = ctx.melee_modifier

    adjusted_gcd = rules.gcd_target * modifier
    adjusted_cpm = rules.cpm_target * modifier

    rules_checked = 0
    rules_passed = 0
    violations = []

    # Rule 1: GCD uptime
    metrics_result = await session.execute(
        FIGHT_CAST_METRICS,
        {"report_code": report_code, "fight_id": fight_id, "player_name": f"%{player_name}%"},
    )
    metrics = metrics_result.first()
    if metrics:
        rules_checked += 1
        if metrics.gcd_uptime_pct >= adjusted_gcd:
            rules_passed += 1
        else:
            violations.append(f"GCD uptime {metrics.gcd_uptime_pct:.1f}% < {adjusted_gcd:.1f}%")

        # Rule 2: CPM
        rules_checked += 1
        if metrics.casts_per_minute >= adjusted_cpm:
            rules_passed += 1
        else:
            violations.append(f"CPM {metrics.casts_per_minute:.1f} < {adjusted_cpm:.1f}")

    # Rule 3: Cooldown efficiency (short vs long thresholds)
    cd_result = await session.execute(
        FIGHT_COOLDOWNS,
        {"report_code": report_code, "fight_id": fight_id, "player_name": f"%{player_name}%"},
    )
    for r in cd_result:
        rules_checked += 1
        # Determine if short or long CD
        threshold = rules.cd_efficiency_target
        cd_label = "short CD"
        if hasattr(r, "cooldown_sec") and r.cooldown_sec and r.cooldown_sec > 180:
            threshold = rules.long_cd_efficiency
            cd_label = "long CD"
        if r.efficiency_pct >= threshold:
            rules_passed += 1
        else:
            violations.append(
                f"{r.ability_name} efficiency {r.efficiency_pct:.1f}% < {threshold:.1f}% ({cd_label})"
            )

    # Rule 4: Key abilities present (check ability breakdown)
    if rules.key_abilities:
        ability_result = await session.execute(
            ABILITY_BREAKDOWN,
            {"report_code": report_code, "fight_id": fight_id, "player_name": f"%{player_name}%"},
        )
        found_abilities = {r.ability_name for r in ability_result}
        for ability in rules.key_abilities:
            rules_checked += 1
            if any(ability.lower() in found.lower() for found in found_abilities):
                rules_passed += 1
            else:
                violations.append(f"Key ability missing: {ability}")

    # Grade
    if rules_checked == 0:
        return f"No rotation data for {player_name}. Was --with-events used?"

    score = (rules_passed / rules_checked) * 100
    grade = _letter_grade(score)

    lines = [
        f"DPS score for {player_name} ({info.player_spec} {info.player_class}) on {encounter_name}:",
        f"  Grade: {grade} ({score:.0f}%) | Rules passed: {rules_passed}/{rules_checked}",
        f"  Encounter: {encounter_name} (modifier {modifier:.2f})",
        f"  Adjusted GCD target: {adjusted_gcd:.1f}% | Adjusted CPM target: {adjusted_cpm:.1f}",
    ]
    if violations:
        lines.append("  Violations:")
        for v in violations:
            lines.append(f"    - {v}")
    return "\n".join(lines)


def _letter_grade(score: float) -> str:
    if score >= 95:
        return "S"
    if score >= 85:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    if score >= 40:
        return "D"
    return "F"
```

**Step 4-6: Tests, suite, commit**

```bash
git commit -m "feat: rewrite rotation scorer with spec-aware DPS engine

Replaces 3 hardcoded rules with spec-specific thresholds from
SPEC_ROTATION_RULES. Applies encounter GCD modifiers from
ENCOUNTER_CONTEXTS. Separate short/long CD efficiency targets.
Key ability presence check via ability breakdown data.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 11: Add Healer Scoring Path

**Files:**
- Modify: `code/shukketsu/agent/tools/event_tools.py`
- Test: `code/tests/agent/test_tools.py`

**Step 1: Write failing tests**

```python
class TestHealerScorer:
    async def test_holy_paladin_low_overheal_passes(self):
        """18% overheal for Holy Paladin (target 20%) should pass."""
        # Mock: spec=Holy Paladin, overheal=18%
        # Assert overheal line shows "OK"

    async def test_resto_druid_42_overheal_passes(self):
        """42% overheal for Resto Druid (target 45%) should pass."""
        # Mock: spec=Restoration Druid, overheal=42%

    async def test_holy_priest_35_overheal_fails(self):
        """35% overheal for Holy Priest (target 30%) should flag."""
        # Mock: spec=Holy Priest, overheal=35%
        # Assert overheal line shows "OVER"

    async def test_healer_oom_flagged(self):
        """Healer with >10% time at zero mana should be flagged."""
        # Mock: time_at_zero_pct=15%
        # Assert output mentions "OOM" or "mana"

    async def test_healer_output_format(self):
        """Output should be healer-specific, not DPS format."""
        # Assert output contains "Healer score" not "DPS score"
```

**Step 3: Implement `_score_healer`**

```python
async def _score_healer(session, report_code, fight_id, player_name, info, rules):
    encounter_name = info.encounter_name if hasattr(info, "encounter_name") else ""
    total_weight = 0.0
    weighted_score = 0.0
    details = []

    # 1. Overheal % (30% weight)
    overheal_result = await session.execute(
        OVERHEAL_BREAKDOWN,
        {"report_code": report_code, "fight_id": fight_id, "player_name": f"%{player_name}%"},
    )
    overheal_rows = list(overheal_result)
    if overheal_rows:
        total_oh = sum(getattr(r, "overheal", 0) for r in overheal_rows)
        total_heal = sum(getattr(r, "total", 0) for r in overheal_rows)
        oh_pct = (total_oh / total_heal * 100) if total_heal > 0 else 0
        target = rules.healer_overheal_target
        if oh_pct <= target:
            weighted_score += 30.0
            details.append(f"  Overheal: {oh_pct:.1f}% (target <={target:.0f}%) — OK")
        else:
            ratio = max(0, 1 - (oh_pct - target) / target)
            weighted_score += 30.0 * ratio
            details.append(f"  Overheal: {oh_pct:.1f}% (target <={target:.0f}%) — OVER")
        total_weight += 30.0

    # 2. Mana management (25% weight)
    resource_result = await session.execute(
        RESOURCE_USAGE,
        {"report_code": report_code, "fight_id": fight_id, "player_name": f"%{player_name}%"},
    )
    resource = resource_result.first()
    if resource and hasattr(resource, "time_at_zero_pct"):
        tzp = resource.time_at_zero_pct or 0
        if tzp <= 5:
            weighted_score += 25.0
            details.append(f"  Mana: {tzp:.1f}% time at zero — OK")
        elif tzp <= 10:
            weighted_score += 15.0
            details.append(f"  Mana: {tzp:.1f}% time at zero — caution")
        else:
            details.append(f"  Mana: {tzp:.1f}% time at zero — OOM risk")
        total_weight += 25.0

    # 3. Key abilities (15% weight)
    if rules.key_abilities:
        ability_result = await session.execute(
            ABILITY_BREAKDOWN,
            {"report_code": report_code, "fight_id": fight_id, "player_name": f"%{player_name}%"},
        )
        found = {r.ability_name for r in ability_result}
        present = sum(
            1 for a in rules.key_abilities
            if any(a.lower() in f.lower() for f in found)
        )
        ratio = present / len(rules.key_abilities) if rules.key_abilities else 1
        weighted_score += 15.0 * ratio
        total_weight += 15.0
        missing = [a for a in rules.key_abilities if not any(a.lower() in f.lower() for f in found)]
        if missing:
            details.append(f"  Spell mix: missing {', '.join(missing)}")
        else:
            details.append(f"  Spell mix: {', '.join(rules.key_abilities)} — OK")

    # Final score
    if total_weight == 0:
        return f"No healer data for {player_name}. Was --with-events used?"

    score = (weighted_score / total_weight) * 100
    grade = _letter_grade(score)

    lines = [
        f"Healer score for {player_name} ({info.player_spec} {info.player_class}) on {encounter_name}:",
        f"  Grade: {grade} ({score:.0f}%) | Weighted score",
    ] + details
    return "\n".join(lines)
```

**Step 4-6: Tests, suite, commit**

```bash
git commit -m "feat: add healer scoring path (overheal, mana, spell mix)

Healers scored on overheal% (30% weight), mana management (25%),
and spell mix (15%). Per-spec overheal targets: Holy Paladin 20%,
Resto Druid 45%, others 25-30%.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 12: Add Tank Scoring Path

**Files:**
- Modify: `code/shukketsu/agent/tools/event_tools.py`
- Test: `code/tests/agent/test_tools.py`

**Step 1: Write failing tests**

```python
class TestTankScorer:
    async def test_prot_warrior_with_key_abilities_passes(self):
        """Prot Warrior using Shield Slam + Devastate + Thunderclap → good score."""

    async def test_tank_died_with_unused_defensive(self):
        """Tank who died with Shield Wall unused should be penalized."""

    async def test_tank_output_format(self):
        """Output should say 'Tank score' not 'DPS score'."""
```

**Step 3: Implement `_score_tank`**

Similar structure to healer scorer. Key rules:
1. Key ability presence (Shield Slam, Devastate, Thunderclap for Prot Warrior) — 40% weight
2. GCD uptime vs spec target — 30% weight
3. Defensive CD usage awareness — 30% weight (check if any defensive CDs were tracked)

**Step 4-6: Tests, suite, commit**

```bash
git commit -m "feat: add tank scoring path (key abilities, GCD, defensive CDs)

Tanks scored on key ability usage (40%), GCD uptime (30%), and
defensive cooldown awareness (30%).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 13: Update Agent Prompts

**Files:**
- Modify: `code/shukketsu/agent/prompts.py:1-30,183-239`
- Test: `code/tests/agent/test_tools.py` (or a new test for prompt content)

**Step 1: Write test**

```python
class TestPromptContent:
    def test_system_prompt_mentions_healer_hps(self):
        from shukketsu.agent.prompts import SYSTEM_PROMPT
        assert "HPS" in SYSTEM_PROMPT
        assert "healer" in SYSTEM_PROMPT.lower()

    def test_system_prompt_mentions_earth_shock(self):
        from shukketsu.agent.prompts import SYSTEM_PROMPT
        assert "Earth Shock" in SYSTEM_PROMPT
        assert "Wind Shear" not in SYSTEM_PROMPT

    def test_analysis_prompt_has_healer_section(self):
        from shukketsu.agent.prompts import ANALYSIS_PROMPT
        assert "overheal" in ANALYSIS_PROMPT.lower()
        assert "mana" in ANALYSIS_PROMPT.lower()

    def test_analysis_prompt_mentions_encounter_modifiers(self):
        from shukketsu.agent.prompts import ANALYSIS_PROMPT
        assert "encounter modifier" in ANALYSIS_PROMPT.lower() or "adjusted threshold" in ANALYSIS_PROMPT.lower()
```

**Step 3: Implement**

Add to SYSTEM_PROMPT after the class/spec list:
```
When analyzing healers, focus on HPS, overheal efficiency, mana management, and spell selection — not DPS. Healers with 0 DPS is normal and correct. When analyzing tanks, focus on survivability, threat generation, and defensive cooldown usage — not raw DPS.

In TBC, the Shaman interrupt is Earth Shock (not Wind Shear, which does not exist until WotLK). Earth Shock is on the GCD and costs mana. Paladins have no true interrupt in TBC; Hammer of Justice is a 60-second stun.
```

Update ANALYSIS_PROMPT section on rotation scoring and add healer efficiency section per design doc.

**Step 4-6: Tests, suite, commit**

```bash
git commit -m "feat: update agent prompts for role-aware analysis

Add healer/tank analysis guidance to SYSTEM_PROMPT. Add healer
efficiency section to ANALYSIS_PROMPT. Correct TBC interrupt info
(Earth Shock, not Wind Shear). Update rotation score section for
encounter modifiers.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 14: Add New Consumables + Battle/Guardian Logic

**Files:**
- Modify: `code/shukketsu/pipeline/constants.py:282-307`
- Modify: `code/shukketsu/agent/tools/event_tools.py` (consumable check logic)
- Test: `code/tests/pipeline/test_consumable_check.py`

**Step 1: Write tests**

```python
class TestConsumableExpansion:
    def test_tbc_flasks_in_categories(self):
        assert 28520 in CONSUMABLE_CATEGORIES  # Flask of Relentless Assault
        assert 28540 in CONSUMABLE_CATEGORIES  # Flask of Pure Death

    def test_battle_guardian_distinction(self):
        """Consumable categories should distinguish battle vs guardian elixirs."""
        # 28490 = Major Agility = battle elixir
        # 28509 = Major Defense = guardian elixir
        cat_28490 = CONSUMABLE_CATEGORIES[28490]
        cat_28509 = CONSUMABLE_CATEGORIES[28509]
        # Both should be in the 'elixir' category but distinguishable
```

**Step 3: Implement**

Add new entries to CONSUMABLE_CATEGORIES. Add TBC flasks (28518, 28519, 28520, 28521, 28540). Add potions (22861 Haste, 22839 Destruction).

**Step 4-6: Tests, suite, commit**

```bash
git commit -m "feat: expand consumable constants with TBC flasks and potions

Add Flask of Relentless Assault, Flask of Pure Death, Flask of
Blinding Light, Flask of Fortification, Flask of Mighty Restoration,
Haste Potion, Destruction Potion, and weapon oils/stones.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Dependency Graph

```
Task 1 (consumable fix)     ─── independent, do first
Task 2 (cd_type + CDs)      ─┐
Task 3 (DoTs)                ─┼─ independent, parallelizable
Task 4 (SpecRules)           ─┤
Task 5 (EncounterContexts)   ─┘
Task 6 (HPS ingest fix)      ─── independent
Task 7 (HPS migration)       ─── depends on 6
Task 8 (SQL queries)         ─── depends on 7
Task 9 (tool display)        ─── depends on 8
Task 10 (DPS scorer)         ─── depends on 2, 4, 5
Task 11 (healer scorer)      ─── depends on 4, 10
Task 12 (tank scorer)        ─── depends on 4, 10
Task 13 (prompts)            ─── depends on 9, 10, 11, 12
Task 14 (consumables)        ─── independent, can run anytime
```

**Parallelization groups:**
- **Batch 1:** Tasks 1, 2, 3, 4, 5, 6, 14 (all independent)
- **Batch 2:** Tasks 7, 8, 10 (depend on batch 1)
- **Batch 3:** Tasks 9, 11, 12 (depend on batch 2)
- **Batch 4:** Task 13 (depends on batch 3)
