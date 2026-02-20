# TBC Accuracy Fixes — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all incorrect spell IDs, mislabeled consumables, wrong rotation abilities, and outdated documentation so the analyzer is fully accurate for TBC raids.

**Architecture:** Pure data fixes in `constants.py` (consumables, rotation rules), one-line fix in `prompts.py`, documentation updates in `CLAUDE.md`/`README.md`, and test zone ID corrections. No architectural changes.

**Tech Stack:** Python constants, pytest, markdown docs.

---

### Task 1: Fix REQUIRED_CONSUMABLES — Replace Classic flasks with TBC flasks

**Files:**
- Modify: `code/shukketsu/pipeline/constants.py:399,406,411`
- Modify: `code/tests/pipeline/test_constants.py` (add new test)

**Step 1: Write the failing test**

Add to `TestConsumableSpellIds` in `code/tests/pipeline/test_constants.py`:

```python
def test_required_flasks_are_tbc(self):
    """Required flasks should be TBC, not Classic."""
    tbc_flask_ids = {28518, 28519, 28520, 28521, 28540}
    classic_flask_ids = {17628, 17627, 17546, 17626, 17629}
    for role, consumables in REQUIRED_CONSUMABLES.items():
        for c in consumables:
            if c.category == "flask":
                assert c.spell_id in tbc_flask_ids, (
                    f"Role '{role}' has Classic flask {c.spell_id} ({c.name}); "
                    f"should use TBC flask"
                )
                assert c.spell_id not in classic_flask_ids, (
                    f"Role '{role}' uses Classic flask {c.name}"
                )
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest code/tests/pipeline/test_constants.py::TestConsumableSpellIds::test_required_flasks_are_tbc -v`
Expected: FAIL — caster_dps has 17628, healer has 17627, tank has 17546

**Step 3: Fix the constants**

In `code/shukketsu/pipeline/constants.py`, replace:

- Line 399: `ConsumableDef(17628, "Flask of Supreme Power", "flask", 80.0)` →
  `ConsumableDef(28521, "Flask of Blinding Light", "flask", 80.0)`
- Line 406: `ConsumableDef(17627, "Flask of Distilled Wisdom", "flask", 80.0)` →
  `ConsumableDef(28519, "Flask of Mighty Restoration", "flask", 80.0)`
- Line 411: `ConsumableDef(17546, "Flask of the Titans", "flask", 80.0)` →
  `ConsumableDef(28518, "Flask of Fortification", "flask", 80.0)`

Also add Flask of Pure Death as alternate caster flask (after line 399):
  `ConsumableDef(28540, "Flask of Pure Death", "flask", 80.0),`

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest code/tests/pipeline/test_constants.py::TestConsumableSpellIds -v`
Expected: PASS

**Step 5: Commit**

```bash
git add code/shukketsu/pipeline/constants.py code/tests/pipeline/test_constants.py
git commit -m "fix: replace Classic flasks with TBC flasks in REQUIRED_CONSUMABLES"
```

---

### Task 2: Add missing flask options for melee_dps and ranged_dps

**Files:**
- Modify: `code/shukketsu/pipeline/constants.py:388-397`
- Modify: `code/tests/pipeline/test_constants.py` (add new test)

**Step 1: Write the failing test**

Add to `TestConsumableSpellIds`:

```python
def test_melee_and_ranged_have_flask_option(self):
    """melee_dps and ranged_dps should include Flask of Relentless Assault."""
    for role in ("melee_dps", "ranged_dps"):
        flask_ids = {
            c.spell_id for c in REQUIRED_CONSUMABLES[role]
            if c.category == "flask"
        }
        assert 28520 in flask_ids, (
            f"Role '{role}' missing Flask of Relentless Assault (28520)"
        )
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest code/tests/pipeline/test_constants.py::TestConsumableSpellIds::test_melee_and_ranged_have_flask_option -v`
Expected: FAIL — neither role has a flask

**Step 3: Add the flask entries**

In `code/shukketsu/pipeline/constants.py`, add to `melee_dps` list (after line 388):
```python
ConsumableDef(28520, "Flask of Relentless Assault", "flask", 80.0),
```

Add to `ranged_dps` list (after line 395):
```python
ConsumableDef(28520, "Flask of Relentless Assault", "flask", 80.0),
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest code/tests/pipeline/test_constants.py::TestConsumableSpellIds -v`
Expected: PASS

**Step 5: Commit**

```bash
git add code/shukketsu/pipeline/constants.py code/tests/pipeline/test_constants.py
git commit -m "feat: add Flask of Relentless Assault to melee/ranged DPS consumables"
```

---

### Task 3: Fix REQUIRED_CONSUMABLES — Correct food buff names

**Files:**
- Modify: `code/shukketsu/pipeline/constants.py:384-386`
- Modify: `code/tests/pipeline/test_constants.py` (add new test)

**Step 1: Write the failing test**

Add to `TestConsumableSpellIds`:

```python
def test_food_buff_names_accurate(self):
    """Food buff display names should match actual TBC buff names."""
    food_by_id = {
        c.spell_id: c.name for c in REQUIRED_CONSUMABLES["all"]
        if c.category == "food"
    }
    # 43722 is "Enlightened" (+20 Spell Crit, +20 Spirit), not "Well Fed (Hit)"
    if 43722 in food_by_id:
        assert food_by_id[43722] == "Enlightened (Spell Crit)", (
            f"43722 labeled '{food_by_id[43722]}', should be 'Enlightened (Spell Crit)'"
        )
    # 43764 is "Well Fed (Hit Rating)", not "Well Fed (AP)"
    if 43764 in food_by_id:
        assert food_by_id[43764] == "Well Fed (Hit Rating)", (
            f"43764 labeled '{food_by_id[43764]}', should be 'Well Fed (Hit Rating)'"
        )
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest code/tests/pipeline/test_constants.py::TestConsumableSpellIds::test_food_buff_names_accurate -v`
Expected: FAIL

**Step 3: Fix the names**

In `code/shukketsu/pipeline/constants.py`, replace:

- Line 384: `ConsumableDef(43722, "Well Fed (Hit)", "food", 80.0)` →
  `ConsumableDef(43722, "Enlightened (Spell Crit)", "food", 80.0)`
- Line 385: Remove `ConsumableDef(43763, "Well Fed (Haste)", "food", 80.0)` entirely
  (43763 is the eating channel spell, not the buff; 43764 is the actual buff)
- Line 386: `ConsumableDef(43764, "Well Fed (AP)", "food", 80.0)` →
  `ConsumableDef(43764, "Well Fed (Hit Rating)", "food", 80.0)`

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest code/tests/pipeline/test_constants.py::TestConsumableSpellIds -v`
Expected: PASS

**Step 5: Commit**

```bash
git add code/shukketsu/pipeline/constants.py code/tests/pipeline/test_constants.py
git commit -m "fix: correct food buff names and remove eating channel spell ID"
```

---

### Task 4: Fix CONSUMABLE_CATEGORIES — Correct weapon oil/stone spell IDs

**Files:**
- Modify: `code/shukketsu/pipeline/constants.py:460-463`
- Modify: `code/tests/pipeline/test_constants.py` (add new test)

**Step 1: Write the failing test**

Add new test class to `code/tests/pipeline/test_constants.py`:

```python
class TestWeaponEnhancementIds:
    """Verify weapon oil/stone spell IDs are correct TBC buff IDs."""

    def test_blessed_wizard_oil_label(self):
        """28898 is Blessed Wizard Oil, not Brilliant Wizard Oil."""
        assert 28898 in CONSUMABLE_CATEGORIES
        assert CONSUMABLE_CATEGORIES[28898][1] == "Blessed Wizard Oil"

    def test_superior_wizard_oil_id(self):
        """Superior Wizard Oil buff is spell 28019, not 28891."""
        assert 28019 in CONSUMABLE_CATEGORIES
        assert CONSUMABLE_CATEGORIES[28019][1] == "Superior Wizard Oil"
        # 28891 (Consecrated Weapon) should not be in the dict
        assert 28891 not in CONSUMABLE_CATEGORIES

    def test_adamantite_sharpening_stone_id(self):
        """Adamantite Sharpening Stone buff is spell 29656, not 25123."""
        assert 29656 in CONSUMABLE_CATEGORIES
        assert CONSUMABLE_CATEGORIES[29656][1] == "Adamantite Sharpening Stone"

    def test_adamantite_weightstone_id(self):
        """Adamantite Weightstone buff is spell 34608, not 25118."""
        assert 34608 in CONSUMABLE_CATEGORIES
        assert CONSUMABLE_CATEGORIES[34608][1] == "Adamantite Weightstone"

    def test_brilliant_mana_oil_not_mislabeled(self):
        """25123 is Brilliant Mana Oil — should not be labeled as sharpening stone."""
        if 25123 in CONSUMABLE_CATEGORIES:
            assert CONSUMABLE_CATEGORIES[25123][1] != "Adamantite Sharpening Stone"
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest code/tests/pipeline/test_constants.py::TestWeaponEnhancementIds -v`
Expected: FAIL on multiple assertions

**Step 3: Fix the spell IDs and names**

In `code/shukketsu/pipeline/constants.py`, replace lines 459-463:

```python
    # Weapon Oils / Stones (buff spell IDs from Wowhead TBC)
    25122: ("weapon_oil", "Brilliant Wizard Oil"),
    25123: ("weapon_oil", "Brilliant Mana Oil"),
    28898: ("weapon_oil", "Blessed Wizard Oil"),
    28019: ("weapon_oil", "Superior Wizard Oil"),
    28013: ("weapon_oil", "Superior Mana Oil"),
    29656: ("weapon_stone", "Adamantite Sharpening Stone"),
    34608: ("weapon_stone", "Adamantite Weightstone"),
```

Note: This replaces the old entries (28891 Consecrated Weapon, 25118 Minor Mana Oil)
and adds proper IDs plus Superior Mana Oil (28013).

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest code/tests/pipeline/test_constants.py::TestWeaponEnhancementIds -v`
Expected: PASS

**Step 5: Commit**

```bash
git add code/shukketsu/pipeline/constants.py code/tests/pipeline/test_constants.py
git commit -m "fix: correct weapon oil/stone spell IDs in CONSUMABLE_CATEGORIES"
```

---

### Task 5: Fix rotation key abilities — Enhancement Shaman, Survival Hunter, Arms Warrior

**Files:**
- Modify: `code/shukketsu/pipeline/constants.py:253,275-277,292-294`
- Modify: `code/tests/pipeline/test_constants.py` (add new test)

**Step 1: Write the failing test**

Add to `TestSpecRules` in `code/tests/pipeline/test_constants.py`:

```python
def test_no_passive_procs_in_key_abilities(self):
    """Key abilities must be active casts, not passive procs."""
    passive_procs = {"Windfury", "Windfury Weapon"}
    for key, rules in SPEC_ROTATION_RULES.items():
        for ab in rules.key_abilities:
            assert ab not in passive_procs, (
                f"{key}: '{ab}' is a passive proc, not a castable ability"
            )

def test_survival_hunter_is_ranged(self):
    """Survival Hunter should not have melee-only abilities as key."""
    rules = SPEC_ROTATION_RULES[("Hunter", "Survival")]
    melee_only = {"Raptor Strike", "Mongoose Bite"}
    for ab in rules.key_abilities:
        assert ab not in melee_only, (
            f"Survival Hunter has melee ability '{ab}' but is a ranged spec"
        )
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest code/tests/pipeline/test_constants.py::TestSpecRules::test_no_passive_procs_in_key_abilities code/tests/pipeline/test_constants.py::TestSpecRules::test_survival_hunter_is_ranged -v`
Expected: FAIL — Enhancement has "Windfury", Survival has "Raptor Strike"

**Step 3: Fix the rotation rules**

In `code/shukketsu/pipeline/constants.py`:

- Line 253 (Arms Warrior): Change key_abilities from
  `("Mortal Strike", "Whirlwind", "Slam")` →
  `("Mortal Strike", "Whirlwind", "Execute")`
  (Execute is more universally used than Slam in TBC Arms)

- Lines 275-278 (Enhancement Shaman): Change key_abilities from
  `("Stormstrike", "Earth Shock", "Windfury")` →
  `("Stormstrike", "Earth Shock", "Shamanistic Rage")`
  (Windfury is a passive proc; Shamanistic Rage is a key active CD)

- Lines 292-294 (Survival Hunter): Change key_abilities from
  `("Steady Shot", "Auto Shot", "Raptor Strike")` →
  `("Steady Shot", "Auto Shot", "Multi-Shot")`
  (Raptor Strike is melee; Multi-Shot is the standard ranged filler)

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest code/tests/pipeline/test_constants.py::TestSpecRules -v`
Expected: PASS

**Step 5: Commit**

```bash
git add code/shukketsu/pipeline/constants.py code/tests/pipeline/test_constants.py
git commit -m "fix: correct rotation key abilities for Arms, Enhancement, Survival"
```

---

### Task 6: Fix prompts.py — "Feral Combat" → "Feral"

**Files:**
- Modify: `code/shukketsu/agent/prompts.py:22`
- Modify: `code/tests/agent/test_graph.py` (if it references spec names)

**Step 1: Write the failing test**

Add a test in `code/tests/pipeline/test_constants.py` `TestClassSpecs`:

```python
def test_druid_feral_spec_name(self):
    """Druid melee DPS spec is 'Feral', not 'Feral Combat'."""
    druid_specs = {s.spec_name for s in TBC_SPECS if s.class_name == "Druid"}
    assert "Feral" in druid_specs
    assert "Feral Combat" not in druid_specs
```

**Step 2: Run test to verify it passes (constants already correct)**

Run: `python3 -m pytest code/tests/pipeline/test_constants.py::TestClassSpecs::test_druid_feral_spec_name -v`
Expected: PASS (constants.py already uses "Feral")

**Step 3: Fix prompts.py**

In `code/shukketsu/agent/prompts.py`, line 22:
Change `- **Druid** (Balance, Feral Combat, Restoration)` →
`- **Druid** (Balance, Feral, Restoration)`

**Step 4: Run full test suite for agent**

Run: `python3 -m pytest code/tests/agent/ -v`
Expected: PASS

**Step 5: Commit**

```bash
git add code/shukketsu/agent/prompts.py code/tests/pipeline/test_constants.py
git commit -m "fix: align prompts.py Druid spec name with constants ('Feral')"
```

---

### Task 7: Fix test_pull_rankings.py — Use TBC zone IDs

**Files:**
- Modify: `code/tests/scripts/test_pull_rankings.py:39,51,60`

**Step 1: Fix the zone IDs**

In `code/tests/scripts/test_pull_rankings.py`:

- Line 39: Change `parse_args(["--zone-id", "2018"])` →
  `parse_args(["--zone-id", "1047"])`
- Line 40: Change `assert args.zone_id == 2018` →
  `assert args.zone_id == 1047`
- Line 51: Change `"--zone-id", "1015"` →
  `"--zone-id", "1048"`
- Line 60: Change `assert args.zone_id == 1015` →
  `assert args.zone_id == 1048`

**Step 2: Run tests**

Run: `python3 -m pytest code/tests/scripts/test_pull_rankings.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add code/tests/scripts/test_pull_rankings.py
git commit -m "fix: use TBC zone IDs (1047, 1048) in pull_rankings tests"
```

---

### Task 8: Update documentation — CLAUDE.md and README.md

**Files:**
- Modify: `CLAUDE.md:7,9,294-297,323`
- Modify: `README.md:3,93,102,105`

**Step 1: Update CLAUDE.md**

- Line 7: Change `World of Warcraft Classic Fresh` →
  `World of Warcraft TBC Classic (The Burning Crusade)`

- Line 9: Replace entire line with:
  `**Game context:** WoW TBC Classic (The Burning Crusade). TBC zone IDs: Karazhan (1047), Gruul's Lair/Magtheridon (1048), SSC (1049), TK (1050), Hyjal (1051), BT (1052), Sunwell (1053). Reports may contain fights from multiple zones/raids.`

- Lines 294-297: Replace examples with:
  ```
  pull-rankings --encounter "Gruul the Dragonkiller" --zone-id 1048
  pull-speed-rankings --zone-id 1047 --force
  register-character --name Lyro --server Whitemane --region US --class-name Warrior --spec Arms
  seed-encounters --zone-ids 1047,1048
  ```

- Line 323: Replace with:
  `- TBC zone IDs: Karazhan (1047), Gruul's Lair/Magtheridon (1048), and higher tiers (1049+)`

**Step 2: Update README.md**

- Line 3: Change `Built for WoW Classic Fresh (Naxxramas) with support for TBC content.` →
  `Built for WoW TBC Classic (The Burning Crusade).`

- Line 93: Change `seed-encounters --zone-ids 2017` →
  `seed-encounters --zone-ids 1047,1048`

- Line 102: Change `pull-rankings --encounter "Patchwerk" --zone-id 2017` →
  `pull-rankings --encounter "Gruul the Dragonkiller" --zone-id 1048`

- Line 105: Change `pull-speed-rankings --zone-id 2017` →
  `pull-speed-rankings --zone-id 1047`

**Step 3: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: update documentation to reflect TBC-only focus"
```

---

### Task 9: Run full test suite — Verify nothing is broken

**Step 1: Run all tests**

Run: `python3 -m pytest code/tests/ -v`
Expected: All tests pass (924+)

**Step 2: Run linter**

Run: `python3 -m ruff check code/`
Expected: No errors

---

## Summary of All Changes

| File | Change | Impact |
|------|--------|--------|
| `constants.py:399` | Classic flask → TBC Flask of Blinding Light | Consumable checker accuracy |
| `constants.py:399+` | Add Flask of Pure Death for casters | Broader caster coverage |
| `constants.py:406` | Classic flask → TBC Flask of Mighty Restoration | Consumable checker accuracy |
| `constants.py:411` | Classic flask → TBC Flask of Fortification | Consumable checker accuracy |
| `constants.py:388+` | Add Flask of Relentless Assault to melee/ranged | Missing flask option |
| `constants.py:384-386` | Fix food buff names, remove channel spell | Display accuracy |
| `constants.py:460-463` | Fix 4 weapon oil/stone spell IDs | False positive/negative bugs |
| `constants.py:253` | Arms: Slam → Execute | Rotation score accuracy |
| `constants.py:277` | Enhancement: Windfury → Shamanistic Rage | Rotation score accuracy |
| `constants.py:294` | Survival: Raptor Strike → Multi-Shot | Rotation score accuracy |
| `prompts.py:22` | "Feral Combat" → "Feral" | Consistency with constants |
| `test_constants.py` | 6 new tests | Regression prevention |
| `test_pull_rankings.py` | Zone IDs 2018/1015 → 1047/1048 | Test data accuracy |
| `CLAUDE.md` | Remove Naxx/Classic Fresh references | Documentation accuracy |
| `README.md` | Remove Naxx/Classic Fresh references | Documentation accuracy |
