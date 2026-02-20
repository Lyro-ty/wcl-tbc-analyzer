# Domain Correctness Fixes — Design Document

**Date:** 2026-02-19 (revised)
**Scope:** Classic Fresh (Naxxramas) + TBC (Karazhan through Sunwell)
**Goal:** Fix the five core domain correctness failures: broken rotation scoring, missing healer analysis, thin game constants, no boss mechanic context, and wrong trinket/consumable IDs.

---

## 1. Spec-Specific Rotation Rules

Add `SpecRules` dataclass and `SPEC_ROTATION_RULES` dict to `constants.py`, keyed by `(class_name, spec_name)`.

### Data structure

```python
@dataclass(frozen=True)
class SpecRules:
    gcd_target: float          # Expected GCD uptime % (see per-spec values below)
    cpm_target: float          # Expected casts-per-minute (see per-spec values below)
    cd_efficiency_target: float  # Min throughput CD efficiency % for SHORT CDs (≤3 min)
    long_cd_efficiency: float  # Min throughput CD efficiency % for LONG CDs (>3 min)
    key_abilities: list[str]   # Spell names that should appear in top damage/healing
    role: str                  # "melee_dps", "caster_dps", "ranged_dps", "healer", "tank"
    healer_overheal_target: float = 35.0  # Per-spec acceptable overheal % (healers only)
```

### Per-spec targets

GCD and CPM targets assume a **standard raid encounter** (some movement, some mechanics).
Patchwerk-style fights use modifier 1.0; movement-heavy fights reduce expectations via
`encounter_gcd_modifier` (see section 3).

#### Melee DPS

| Class | Spec | GCD | CPM | Short CD | Long CD | Key Abilities |
|-------|------|-----|-----|----------|---------|---------------|
| Warrior | Arms | 88 | 28 | 85 | 60 | Mortal Strike, Whirlwind, Slam |
| Warrior | Fury | 90 | 32 | 85 | 60 | Bloodthirst, Whirlwind, Heroic Strike |
| Paladin | Retribution | 85 | 25 | 80 | 60 | Crusader Strike, Seal of Command, Judgement |
| Rogue | Assassination | 88 | 30 | 85 | 65 | Mutilate, Envenom, Slice and Dice |
| Rogue | Combat | 90 | 32 | 85 | 65 | Sinister Strike, Slice and Dice, Blade Flurry |
| Rogue | Subtlety | 85 | 28 | 80 | 60 | Hemorrhage, Slice and Dice |
| Shaman | Enhancement | 85 | 25 | 80 | 60 | Stormstrike, Earth Shock, Windfury |
| Druid | Feral | 88 | 30 | 85 | 60 | Shred, Mangle, Rip, Savage Roar |

#### Ranged DPS

| Class | Spec | GCD | CPM | Short CD | Long CD | Key Abilities |
|-------|------|-----|-----|----------|---------|---------------|
| Hunter | Beast Mastery | 82 | 22 | 85 | 60 | Steady Shot, Auto Shot, Kill Command |
| Hunter | Marksmanship | 82 | 22 | 85 | 60 | Steady Shot, Auto Shot, Arcane Shot |
| Hunter | Survival | 82 | 22 | 85 | 60 | Steady Shot, Auto Shot, Raptor Strike |

Note: Hunter GCD targets are lower because auto-shot weaving requires deliberate GCD gaps.

#### Caster DPS

| Class | Spec | GCD | CPM | Short CD | Long CD | Key Abilities |
|-------|------|-----|-----|----------|---------|---------------|
| Priest | Shadow | 88 | 25 | 80 | 60 | Shadow Word: Pain, Mind Blast, Mind Flay |
| Shaman | Elemental | 85 | 25 | 80 | 60 | Lightning Bolt, Chain Lightning |
| Mage | Arcane | 90 | 28 | 85 | 60 | Arcane Blast, Arcane Missiles |
| Mage | Fire | 85 | 22 | 85 | 60 | Fireball, Scorch, Fire Blast |
| Mage | Frost | 85 | 22 | 85 | 60 | Frostbolt, Ice Lance |
| Warlock | Affliction | 85 | 22 | 80 | 60 | Corruption, Unstable Affliction, Shadow Bolt |
| Warlock | Demonology | 85 | 22 | 80 | 60 | Shadow Bolt, Incinerate |
| Warlock | Destruction | 88 | 24 | 85 | 60 | Shadow Bolt, Incinerate, Immolate |
| Druid | Balance | 85 | 22 | 80 | 60 | Starfire, Wrath, Moonfire |

#### Healers

Healer scoring uses a **different scoring path** (see section 5). GCD and CPM targets for healers
are intentionally lower — good healers heal efficiently, not constantly. A healer at 80% GCD
uptime is likely overhealing significantly and going OOM.

| Class | Spec | GCD | CPM | Short CD | Long CD | Key Abilities | Overheal Target |
|-------|------|-----|-----|----------|---------|---------------|-----------------|
| Paladin | Holy | 55 | 18 | 70 | 50 | Flash of Light, Holy Light | 20 |
| Priest | Discipline | 60 | 20 | 75 | 55 | Power Word: Shield, Flash Heal, Prayer of Mending | 25 |
| Priest | Holy | 65 | 22 | 75 | 55 | Circle of Healing, Prayer of Healing, Flash Heal | 30 |
| Shaman | Restoration | 60 | 20 | 75 | 55 | Chain Heal, Lesser Healing Wave | 30 |
| Druid | Restoration | 65 | 22 | 70 | 50 | Lifebloom, Rejuvenation, Healing Touch | 45 |

Note: Resto Druid overheal target is 45% because HoTs are routinely sniped by other healers in
raid — this is structural, not a player error.

#### Tanks

Tank scoring uses a **different scoring path** (see section 5). Tanks are evaluated on defensive
ability usage and threat generation, not raw DPS.

| Class | Spec | GCD | CPM | Short CD | Long CD | Key Abilities |
|-------|------|-----|-----|----------|---------|---------------|
| Warrior | Protection | 88 | 30 | 85 | 50 | Shield Slam, Devastate, Thunderclap |
| Paladin | Protection | 85 | 26 | 80 | 50 | Consecration, Holy Shield, Avenger's Shield |

### Feral Bear detection

WCL reports Feral druids with spec="Feral" regardless of whether they're in cat (DPS) or bear
(tank) form. To detect the active role:

1. Check fight_performances: if `deaths` is low and the player took significant damage (from
   WCL damage-taken data), they were likely tanking.
2. Simpler heuristic: if the player's top abilities include Maul/Swipe/Lacerate, they were
   tanking. If top abilities include Shred/Rip/Mangle (Cat), they were DPSing.
3. Fallback: treat Feral as melee_dps by default; annotate in output that role detection is
   approximate.

### Fallback

If a `(class, spec)` pair is not found, derive defaults from `ROLE_BY_SPEC` role tier using
conservative middle-of-the-road values:
- melee_dps: GCD 85, CPM 28, short_cd 80, long_cd 60
- caster_dps: GCD 85, CPM 22, short_cd 80, long_cd 60
- ranged_dps: GCD 80, CPM 20, short_cd 80, long_cd 60
- healer: GCD 60, CPM 20, short_cd 70, long_cd 50
- tank: GCD 85, CPM 28, short_cd 80, long_cd 50

---

## 2. Healer HPS Fix

### Migration

The `fight_performances` table already has `hps` and `total_healing` columns (hardcoded to 0).
No schema migration needed — just a data backfill and pipeline fix.

```sql
-- Backfill: move healer DPS values to HPS where WCL's "amount" was actually HPS
UPDATE fight_performances
SET hps = dps, dps = 0.0
WHERE player_spec IN ('Holy', 'Discipline', 'Restoration');
```

**Important:** The `top_rankings` table already correctly stores metrics via the `metric` column
("dps" or "hps") and the `amount` column. No backfill needed for `top_rankings`.

### Ingest pipeline change

In `pipeline/ingest.py` `parse_rankings_to_performances()` (line 54-70): detect healer role from
spec via `ROLE_BY_SPEC`. If role is `"healer"`, store WCL `amount` in `hps` field, set
`dps = 0.0`.

```python
from shukketsu.pipeline.constants import ROLE_BY_SPEC

role = ROLE_BY_SPEC.get(r["spec"], "dps")
if role == "healer":
    dps_val = 0.0
    hps_val = r.get("amount", 0.0)
else:
    dps_val = r.get("amount", 0.0)
    hps_val = 0.0
```

### Agent tool updates

Tools that display DPS become role-aware:
- `get_my_performance` — show HPS for healers, DPS for DPS/tanks
- `get_fight_details` — include both columns, display the relevant one
- `compare_to_top` — compare HPS for healers, DPS for others
- `get_raid_execution` — show HPS alongside DPS for healer rows
- `get_top_rankings` — return HPS for healer specs (already works via `amount` column)
- `get_spec_leaderboard` — use HPS for healer specs in the ranking

Corresponding SQL queries in `db/queries/player.py`, `db/queries/raid.py`, `db/queries/api.py`
updated to select `CASE WHEN role='healer' THEN hps ELSE dps END AS metric_value`.

---

## 3. Encounter-Aware GCD Modifiers

### Problem with current PhaseDef model

The current `PhaseDef` uses `pct_start`/`pct_end` as sequential fight-time percentages. This
**cannot represent cyclic encounters** where phases repeat:
- Sapphiron: Ground → Air → Ground → Air (repeating)
- Heigan: Platform → Dance → Platform → Dance (repeating)
- Noth: Ground → Balcony → Ground → Balcony (repeating)
- Netherspite: Portal Phase (60s) → Banish Phase (30s) → repeat

### Solution: encounter_gcd_modifier (flat per-encounter)

Instead of trying to model complex phase transitions precisely, use a single pre-computed
**encounter_gcd_modifier** that encodes "what fraction of the spec's base GCD target should
we expect on this boss?"

```python
@dataclass(frozen=True)
class EncounterContext:
    name: str
    gcd_modifier: float = 1.0       # Multiplier on expected GCD target
    melee_modifier: float | None = None  # Override for melee (if different from ranged)
    notes: str = ""                  # Human-readable context for LLM output
```

The modifier is computed from real encounter data: what percentage of the fight allows full DPS?

**Calculation:** `adjusted_gcd_target = spec.gcd_target * encounter.gcd_modifier`

For melee specs, use `melee_modifier` when set (some fights punish melee more than ranged).

### Existing PhaseDef unchanged

The existing `ENCOUNTER_PHASES` dict and `PhaseDef` dataclass remain for the `get_phase_analysis`
tool — they provide per-phase breakdowns for display. The new `EncounterContext` is separate and
used only by the rotation scorer.

### Coverage

#### Naxxramas encounters

| Boss | GCD Mod | Melee Mod | Notes |
|------|---------|-----------|-------|
| Patchwerk | 1.0 | 1.0 | Pure tank-and-spank |
| Grobbulus | 0.90 | 0.85 | Kiting, injection positioning |
| Gluth | 0.85 | 0.85 | Zombie kiting, Decimate |
| Thaddius | 0.80 | 0.80 | P1 adds (no boss DPS), polarity movement |
| Anub'Rekhan | 0.90 | 0.85 | Locust Swarm kiting |
| Grand Widow Faerlina | 0.95 | 0.95 | Mostly single-phase |
| Maexxna | 0.90 | 0.90 | Web Wrap stuns, Web Spray |
| Noth the Plaguebringer | 0.70 | 0.70 | Boss immune during Balcony phases (~40% fight) |
| Heigan the Unclean | 0.60 | 0.55 | Dance phase = minimal DPS; melee worse |
| Loatheb | 0.95 | 0.95 | Single-phase, predictable |
| Instructor Razuvious | 0.90 | 0.90 | MC tanking, some downtime |
| Gothik the Harvester | 0.75 | 0.75 | P1 adds only, boss appears P2 |
| The Four Horsemen | 0.85 | 0.80 | Tank rotation movement, mark management |
| Sapphiron | 0.70 | 0.65 | Air phases = no boss DPS (~30% fight); melee worse |
| Kel'Thuzad | 0.65 | 0.60 | P1 adds (no boss, ~20%), P3 ice blocks/guardians |

#### TBC encounters

| Boss | GCD Mod | Melee Mod | Notes |
|------|---------|-----------|-------|
| Shade of Aran | 0.85 | 0.80 | Flame Wreath freezes, Blizzard dodge, Water Elementals at 40% |
| Netherspite | 0.70 | 0.65 | Banish phase (~33%) = no DPS; beam management |
| Prince Malchezaar | 0.85 | 0.80 | Infernal dodging, Enfeeble (melee worse in P2-P3) |
| Gruul | 0.85 | 0.80 | Shatter knockback + movement, Ground Slam |
| Leotheras the Blind | 0.80 | 0.75 | Demon Form = untargetable; Whirlwind dodge (melee) |
| Lady Vashj | 0.65 | 0.60 | P2 shield phase = no boss DPS; core running |
| Kael'thas Sunstrider | 0.55 | 0.50 | P1-P3 = no Kael DPS (~50% fight); complex transitions |
| Archimonde | 0.80 | 0.80 | Air Burst movement, Fire positioning |
| Illidan Stormrage | 0.70 | 0.60 | P2 Demon Form = boss airborne; P4 transitions; melee hit hard |
| M'uru | 0.80 | 0.75 | Heavy add management P1; P2 burn = full DPS |
| Kil'jaeden | 0.70 | 0.65 | Multiple transition phases; darkness mechanics |
| Brutallus | 1.0 | 1.0 | Pure DPS race (Patchwerk of TBC) |

Unknown encounters default to `gcd_modifier=1.0` — no penalty, no crash.

---

## 4. Expanded Game Constants

### 4a. Cooldowns

Add `cd_type` field to `CooldownDef`:

```python
@dataclass(frozen=True)
class CooldownDef:
    spell_id: int
    name: str
    cooldown_sec: int
    duration_sec: int = 0
    cd_type: str = "throughput"  # "throughput", "interrupt", "defensive", "utility"
```

**cd_type semantics:**
- `throughput` — DPS/HPS cooldowns. Rotation scorer checks these for efficiency.
- `interrupt` — True spell interrupts (Pummel, Kick, Counterspell, Earth Shock). Tracked in
  `get_deaths_and_mechanics`. Short CDs, on-demand usage, not penalized for low uptime.
- `defensive` — Major survival cooldowns (Shield Wall, Last Stand, Evasion). Tracked separately;
  usage is fight-dependent. Not penalized for holding strategically.
- `utility` — Raid utility (Innervate, Mana Tide, Bloodlust). Tracked for awareness, not scored.

#### New interrupt entries

**Verified against Wowhead TBC Classic database:**

| Class | Ability | Spell ID | CD (sec) | cd_type | Notes |
|-------|---------|----------|----------|---------|-------|
| Warrior | Pummel | 6552 | 10 | interrupt | 4s lockout, requires Berserker Stance |
| Rogue | Kick | 1769 | 10 | interrupt | 5s lockout, off GCD |
| Mage | Counterspell | 2139 | 24 | interrupt | 10s lockout, 30yd range |
| Shaman | Earth Shock | 25454 | 6 | interrupt | 2s lockout, ON GCD, costs mana. **Not Wind Shear** — Wind Shear does not exist until WotLK. |
| Druid | Feral Charge | 16979 | 15 | interrupt | 4s immobilize+interrupt, Bear Form only, talent required |

**NOT interrupts (reclassified):**

| Class | Ability | Spell ID | CD (sec) | cd_type | Notes |
|-------|---------|----------|----------|---------|-------|
| Paladin | Hammer of Justice | 10308 | 60 | defensive | This is a 6s **stun**, not a true interrupt. Paladins have no interrupt in TBC. |

#### New defensive entries

| Class | Ability | Spell ID | CD (sec) | Duration (sec) | cd_type | Notes |
|-------|---------|----------|----------|----------------|---------|-------|
| Warrior | Shield Wall | 871 | 1800 | 10 | defensive | Shared with Recklessness/Retaliation. 75% damage reduction. |
| Warrior | Last Stand | 12975 | 600 | 20 | defensive | +30% max HP. Protection talent. |
| Rogue | Evasion | 26669 | 180 | 15 | defensive | +50% dodge, -25% ranged hit chance |
| Rogue | Cloak of Shadows | 31224 | 60 | 5 | defensive | 90% spell resist, removes harmful magic |

**NOT a defensive cooldown:**
- **Shield Block (2565)** — 5-second CD, part of Protection Warrior's core rotation to prevent
  crushing blows. This is a rotational ability, not a major defensive CD. Do not track as a
  cooldown — it would create noise (near-100% uptime expected).

#### New utility entries

| Class | Ability | Spell ID | CD (sec) | Duration (sec) | cd_type | Notes |
|-------|---------|----------|----------|----------------|---------|-------|
| Warrior | Bloodrage | 2687 | 60 | 10 | utility | Generates rage. Critical for pull timing. |
| Warrior | Berserker Rage | 18499 | 30 | 10 | utility | Fear immunity + rage. Essential on fear bosses. |
| Shaman | Mana Tide Totem | 16190 | 300 | 12 | utility | Restores mana to party. Resto talent. |
| Shaman | Fire Elemental Totem | 2894 | 600 | 120 | utility | Significant DPS. |
| Paladin | Lay on Hands | 10310 | 3600 | 0 | utility | Emergency full heal + mana restore |
| Paladin | Divine Shield | 642 | 300 | 12 | defensive | Full immunity (but drops threat) |

#### Remove from cooldown tracking

- **Tree of Life (33891)** — currently listed as CD with 0s/0s. This is a shapeshift form, not a
  cooldown. Remove from `CLASSIC_COOLDOWNS`.

### 4b. DoTs

Add to `CLASSIC_DOTS` (verified against Wowhead TBC):

| Class | Spell | Spell ID | Duration | Tick Interval |
|-------|-------|----------|----------|---------------|
| Hunter | Serpent Sting | 27016 | 15000ms | 3000ms |
| Druid (Feral) | Rake | 27003 | 9000ms | 3000ms |
| Druid (Feral) | Rip | 27008 | 12000ms | 2000ms |

Total: 3 classes → 5 classes with DoT tracking.

### 4c. Trinkets

**CRITICAL: Trinket spell ID audit required.**

The current `CLASSIC_TRINKETS` dict uses values like 28830 (Dragonspine Trophy), 28789 (Eye of
Magtheridon), 34321 (Shard of Contempt). These are **item IDs**, not the buff spell IDs that WCL
reports in aura/buff events. The trinket tracking tool matches against buff_uptimes data, which
uses spell IDs. **If these are item IDs, the tool finds zero matches.**

**Implementation step:** Before expanding the trinket list, audit every existing ID by:
1. Ingesting a report with `--with-tables` for a player using a known trinket
2. Checking `buff_uptimes` for what spell ID WCL reports for that trinket's proc
3. Updating `CLASSIC_TRINKETS` to use the correct buff spell IDs

**Expected uptime calculation must use correct formulas:**
- **USE trinkets:** `uptime = duration_sec / cooldown_sec` (e.g., 20s duration / 120s CD = 16.7%)
- **PROC trinkets:** Estimate from proc rate + ICD. Varies by attack speed / cast frequency.
- **Passive trinkets:** 100% (always-on stat sticks like Mark of the Champion)

**Known wrong uptimes in current data:**
- Eye of Magtheridon (28789): Listed as 25%. This trinket procs on **full spell resists only** —
  real uptime is <5% for hit-capped casters. The trinket's value is its passive +54 spell damage.

**Trinket type field:**

Add trinket type for correct uptime analysis:

```python
@dataclass(frozen=True)
class TrinketDef:
    buff_spell_id: int       # The aura spell ID that WCL reports (NOT the item ID)
    item_id: int             # The item ID for gear snapshot matching
    name: str
    expected_uptime: float   # As decimal (0.167 = 16.7%)
    trinket_type: str        # "use", "proc", "passive"
    duration_sec: int = 0    # Buff duration (for USE/PROC)
    cooldown_sec: int = 0    # ICD or USE cooldown
```

**New trinkets to add** (spell IDs to be verified during implementation):

Classic Naxxramas:
- Mark of the Champion (item 23207, passive, 100%)
- The Restrained Essence of Sapphiron (item 23046, USE, 20s/120s = 16.7%)
- Eye of the Dead (item 23001, PROC)
- Slayer's Crest (item 23041, USE, 20s/120s = 16.7%)
- Loatheb's Reflection (item 23042, USE, 20s/120s = 16.7%)

TBC Karazhan through Sunwell:
- Dragonspine Trophy (item 28830, PROC, ~20% with fast attacks)
- Icon of the Silver Crescent (item 35163, USE, 20s/120s = 16.7%)
- Tsunami Talisman (item 34484, PROC)
- Hex Shrunken Head (item 34429, USE, 20s/120s = 16.7%)
- Madness of the Betrayer (item 32505, PROC)
- Shard of Contempt (item 34472, PROC) — **NOTE: current code has item 34321 labeled "Shard of Contempt" and item 34472 labeled "Timbal's Focusing Crystal". Both IDs need verification.**
- Skull of Gul'dan (item 32483, USE, 20s/120s = 16.7%)
- Shifting Naaru Sliver (item 34429, USE)
- Berserker's Call (item 33831, USE)

### 4d. Consumables

**Before expanding, fix existing spell ID mismatches:**

Current `REQUIRED_CONSUMABLES` has wrong spell ID → name mappings:
- Tank list: 28502 labeled "Elixir of Healing Power" → 28502 is actually **Elixir of Major
  Mageblood** (+16 mp5). Elixir of Healing Power is spell **28491**.
- Caster DPS list: 28509 labeled "Elixir of Major Firepower" → 28509 is actually **Elixir of
  Major Defense** (+550 armor). Elixir of Major Firepower is spell **28501**.

**Verified TBC elixir spell IDs** (buff aura IDs from Wowhead TBC):

| Spell ID | Name | Category | Stats |
|----------|------|----------|-------|
| 28490 | Elixir of Major Agility | battle elixir | +35 Agi, +20 Crit |
| 28491 | Elixir of Healing Power | battle elixir | +50 Healing |
| 28493 | Elixir of Major Frost Power | battle elixir | +55 Frost |
| 28501 | Elixir of Major Firepower | battle elixir | +55 Fire |
| 28503 | Elixir of Major Shadow Power | battle elixir | +55 Shadow |
| 28502 | Elixir of Major Mageblood | guardian elixir | +16 mp5 |
| 28509 | Elixir of Major Defense | guardian elixir | +550 Armor |
| 28514 | Elixir of Major Fortitude | guardian elixir | +250 HP, +10 HP5 |
| 11390 | Elixir of the Mongoose | battle elixir | +25 Agi, +2% Crit |
| 33726 | Elixir of Mastery | battle+guardian | +15 all stats |
| 28104 | Adept's Elixir | battle elixir | +24 SP, +24 Crit |
| 39627 | Elixir of Draenic Wisdom | guardian elixir | +30 Int, +30 Spirit |

**New TBC consumables to add:**

| Spell ID | Name | Category | Notes |
|----------|------|----------|-------|
| 28518 | Flask of Fortification | flask | +500 HP, +10 Def — tank flask |
| 28520 | Flask of Relentless Assault | flask | +120 AP — melee flask |
| 28521 | Flask of Blinding Light | flask | +80 Holy/Arcane/Nature SP |
| 28540 | Flask of Pure Death | flask | +80 Shadow/Fire/Frost SP |
| 28519 | Flask of Mighty Restoration | flask | +25 mp5 — healer flask |
| 22861 | Haste Potion | potion | +400 Haste for 15s |
| 22839 | Destruction Potion | potion | +120 SP, +2% Crit for 15s |
| 28891 | Superior Wizard Oil | weapon oil | +42 SP |
| 28898 | Brilliant Wizard Oil | weapon oil | +36 SP, +14 Crit |
| 25123 | Brilliant Mana Oil | weapon oil | +12 mp5, +25 Healing |
| 25118 | Adamantite Weightstone | weapon stone | +12 damage (blunt) |
| 25119 | Adamantite Sharpening Stone | weapon stone | +12 damage (sharp) |

**Battle vs Guardian elixir distinction:**
TBC uses a battle/guardian elixir system — players can have one of each active, OR one flask
(which counts as both). The consumable check should understand this:
- Flask present → skip elixir check
- No flask → check for at least one battle elixir AND one guardian elixir

---

## 5. Rotation Scorer Rewrite

Replace the 3-hardcoded-rule engine in `event_tools.py:get_rotation_score` with **three role-
specific scoring engines**.

### 5a. DPS Scoring (melee_dps, caster_dps, ranged_dps)

1. **Resolve spec rules.** Look up `(class_name, spec_name)` in `SPEC_ROTATION_RULES`. Fall back
   to role-based defaults.

2. **Resolve encounter context.** Look up encounter name in `ENCOUNTER_CONTEXTS`. Get
   `gcd_modifier` (or `melee_modifier` for melee specs).

3. **Score each rule:**
   - **GCD uptime:** Compare against `spec.gcd_target * encounter.gcd_modifier`
   - **CPM:** Compare against `spec.cpm_target * encounter.gcd_modifier` (CPM scales with
     available uptime)
   - **Short CD efficiency:** For CDs with `cooldown_sec ≤ 180`, compare against
     `spec.cd_efficiency_target`
   - **Long CD efficiency:** For CDs with `cooldown_sec > 180`, compare against
     `spec.long_cd_efficiency`
   - **Key ability check:** Query ability breakdown data. Flag missing key abilities from
     `spec.key_abilities` (must appear with >1% of total damage/healing)

4. **Grade (S-F):**
   - S: ≥95% rules passed
   - A: ≥85%
   - B: ≥75%
   - C: ≥60%
   - D: ≥40%
   - F: <40%

### 5b. Healer Scoring

Healers are scored on **efficiency**, not rotation. Different rules entirely:

1. **Overheal percentage:** Compare against `spec.healer_overheal_target`. Per-spell overheal
   from `get_overheal_analysis`. Flag spells with >50% overheal individually.

2. **Mana management:** From `resource_snapshots`: if `time_at_zero_pct > 10%`, flag OOM risk.
   If `time_at_zero_pct > 25%`, severe mana issues.

3. **Cooldown usage:** Check utility CDs (Innervate, Nature's Swiftness, Mana Tide Totem,
   Power Infusion, Pain Suppression). Were they used at all? Were they used at appropriate
   times (Innervate when mana <50%)?

4. **Spell mix:** Check key_abilities appear in ability breakdown. A Holy Paladin not casting
   Holy Light at all, or a Resto Shaman not using Chain Heal, indicates a problem.

5. **GCD target (soft):** Compare GCD uptime against the healer's lower target. Not a hard
   fail — healers who finish a fight with everyone alive and mana remaining were doing it right.

Grade uses the same S-F scale but weighted differently:
- Overheal: 30% weight
- Mana management: 25% weight
- Cooldown usage: 20% weight
- Spell mix: 15% weight
- GCD target: 10% weight

### 5c. Tank Scoring

Tanks are scored on **defensive execution** and **threat generation**:

1. **Defensive CD usage:** Were major defensive CDs (Shield Wall, Last Stand, Divine Shield)
   used during high-damage moments? Were they used at all on long fights?

2. **Key ability uptime:** Check that core threat/mitigation abilities are being used:
   - Prot Warrior: Shield Slam, Devastate, Thunderclap, Demo Shout
   - Prot Paladin: Consecration, Holy Shield, Avenger's Shield, Judgement

3. **GCD uptime:** Tanks should have HIGH GCD uptime (85%+) because they should always be
   pressing buttons for threat. Compare against spec target.

4. **Death analysis:** If the tank died, was it due to lack of defensive CDs, or unhealable
   spike damage? Deaths with unused defensive CDs are penalized.

Grade: same S-F scale.

### Output format

Same string return. Includes role, adjusted thresholds, and encounter context:

```
DPS score for Lyro (Fury Warrior) on Patchwerk:
  Grade: A (88%) | Rules passed: 7/8
  Encounter: Patchwerk (modifier 1.0, single phase)
  Adjusted GCD target: 90.0% | Adjusted CPM target: 32
  Violations:
    - Death Wish efficiency 78.0% < 85.0% (short CD target)

Healer score for Priestess (Holy Priest) on Sapphiron:
  Grade: B (78%) | Weighted score
  Encounter: Sapphiron (modifier 0.70, cyclic air phases)
  Overheal: 34.2% (target ≤30%) — OVER
  Mana: 8.1% time at zero — OK
  Cooldowns: Pain Suppression used 1/1 — OK
  Spell mix: Circle of Healing, Prayer of Healing, Flash Heal — OK
```

---

## 6. Agent Prompt Updates

### SYSTEM_PROMPT additions

After class/spec list (line 26), add role-awareness paragraph:
> When analyzing healers, focus on HPS, overheal efficiency, mana management, and spell selection
> — not DPS. Healers with 0 DPS is normal and correct. When analyzing tanks, focus on
> survivability, threat generation, and defensive cooldown usage — not raw DPS. A tank's DPS is
> secondary to keeping the boss positioned and staying alive.

Add interrupt clarification:
> In TBC, the Shaman interrupt is Earth Shock (not Wind Shear, which does not exist until WotLK).
> Earth Shock is on the GCD and costs mana — using it for interrupts is a DPS/mana tradeoff.
> Paladins have no true interrupt in TBC; Hammer of Justice is a 60-second stun.

### ANALYSIS_PROMPT changes

**New section between 7 and 8 — Healer Efficiency:**
> If the player is a healer, analyze: (1) HPS ranking compared to other healers, (2) overheal %
> per spec — Holy Paladin >20% is concerning, Resto Druid >45% is concerning (HoTs get sniped,
> this is normal up to 45%), (3) mana usage — >10% time at zero means OOM risk, (4) spell mix
> appropriateness — is the healer using their key spells? Compare effective healing (total - overheal)
> rather than raw HPS. Skip this section for DPS/tank players.

**Updated section 13 — Rotation Score:**
> Scores are role-aware: DPS specs are scored on GCD uptime, CPM, and cooldown efficiency. Healers
> are scored on overheal %, mana management, and spell selection. Tanks are scored on defensive
> CD usage and threat ability uptime. All scores account for boss mechanics via encounter modifiers
> — lower raw GCD on movement-heavy fights (Heigan, Sapphiron) is expected and reflected in the
> adjusted threshold. S grade is exceptional, A/B strong, C needs tuning, D/F fundamental issues.

**Updated section 11 — Phase Performance:**
> Encounters with repeating phases (Sapphiron air, Heigan dance, Noth balcony) have reduced
> expectations reflected in the encounter GCD modifier. Don't flag DPS drops during known downtime
> — focus on whether the player resumed full output when the boss became targetable again.

### No changes to GRADER_PROMPT or ROUTER_PROMPT

---

## 7. Test Strategy

### Spec rules coverage (27 parametrized tests)

Assert every spec in `SPEC_ROTATION_RULES` has sane values:
- `gcd_target` 50-95 (healers lower than DPS)
- `cpm_target` >0 for all specs
- non-empty `key_abilities`
- `cd_efficiency_target` 60-95
- `long_cd_efficiency` 40-70
- `role` in `{"melee_dps", "caster_dps", "ranged_dps", "healer", "tank"}`
- Healers have `healer_overheal_target` between 15-50

### DPS rotation scorer behavioral tests
- Fury Warrior on Patchwerk: 90% GCD, 32 CPM → A/S grade
- Fury Warrior on Patchwerk: 72% GCD, 25 CPM → D/F grade (no phase excuse)
- Fire Mage on Sapphiron: 72% GCD → B/C after 0.70 modifier adjustment (target = 59.5%)
- Fire Mage on Patchwerk: 72% GCD → D (target = 85%, no modifier)
- Missing key ability → flagged as violation
- Short CD below target → violation
- Long CD below target → separate threshold applied
- Unknown encounter → modifier 1.0, no crash
- Unknown spec → role-based defaults, no crash

### Healer scoring tests
- Holy Paladin: 18% overheal → pass (target 20%)
- Resto Druid: 42% overheal → pass (target 45%)
- Resto Druid: 55% overheal → fail (>45%)
- Holy Priest: 35% overheal → fail (target 30%)
- Healer with 0% time at zero mana → pass
- Healer with 30% time at zero mana → severe flag
- Healer missing key ability → flagged

### Tank scoring tests
- Prot Warrior using Shield Slam, Devastate, Thunderclap → pass
- Prot Warrior who died with Shield Wall unused → penalized
- Prot Warrior who died with Shield Wall on cooldown → not penalized

### Healer HPS tests
- `parse_rankings_to_performances()` routes `amount` to `hps` for healer specs
- `parse_rankings_to_performances()` routes `amount` to `dps` for DPS specs
- Agent tools display HPS for healers, DPS for others
- Backfill migration moves existing healer DPS values to HPS

### Encounter context tests
- Patchwerk returns modifier 1.0
- Sapphiron returns gcd=0.70, melee=0.65
- Heigan returns gcd=0.60, melee=0.55
- Unknown encounter returns 1.0

### Constants integrity tests
- All spell IDs positive integers, no duplicates within categories
- All `CooldownDef.cd_type` in `{"throughput", "interrupt", "defensive", "utility"}`
- All `SpecRules.role` in `{"melee_dps", "caster_dps", "ranged_dps", "healer", "tank"}`
- All consumable spell IDs verified: spell name matches actual buff effect
- Earth Shock (25454) present as Shaman interrupt; Wind Shear absent
- Shield Block (2565) NOT in cooldown tracking
- Tree of Life (33891) NOT in cooldown tracking

### Trinket spell ID audit tests
- For each trinket in `CLASSIC_TRINKETS`: verify `buff_spell_id != item_id` (they should be
  different for most trinkets)
- Expected uptime for USE trinkets matches `duration / cooldown` formula
- No trinket has expected_uptime > 1.0

---

## 8. Implementation Order

1. **Consumable spell ID fixes** — fix the 2 wrong spell IDs in `REQUIRED_CONSUMABLES` before
   anything else, since they affect existing analysis
2. **Constants expansion** (section 4a-4d) — new CDs, DoTs, consumables. Trinket expansion
   blocked on spell ID audit.
3. **Spec rotation rules** (section 1) — SpecRules dataclass + all 27 specs
4. **Encounter contexts** (section 3) — EncounterContext dataclass + all encounters
5. **Healer HPS fix** (section 2) — backfill migration + pipeline + query changes
6. **Trinket spell ID audit** (section 4c) — requires a real WCL report with known trinkets
7. **Rotation scorer rewrite** (section 5) — three scoring paths, depends on 2-5
8. **Agent prompt updates** (section 6) — depends on 5, 7
9. **Tests** — written alongside each section (TDD)

Steps 2-4 are independent and can be parallelized. Step 5 is independent of 2-4 but has
migration risk so it runs alone. Step 6 requires real WCL data. Steps 7-8 depend on everything
before them.

---

## Appendix A: Game Mechanics Reference

### GCD mechanics in TBC Classic

- Base GCD: 1.5 seconds for all abilities
- Spell haste reduces caster GCD to minimum **1.0 second**
- Melee and ranged physical abilities: GCD is **NOT reduced by haste** (always 1.5s)
- Current codebase uses fixed 1500ms GCD — correct for melee, incorrect for haste-stacked casters

### TBC interrupts (verified against Wowhead TBC)

| Ability | Class | Spell ID | CD | Lockout | GCD? | Notes |
|---------|-------|----------|-----|---------|------|-------|
| Pummel | Warrior | 6552 | 10s | 4s | No | Requires Berserker Stance |
| Kick | Rogue | 1769 | 10s | 5s | No | |
| Counterspell | Mage | 2139 | 24s | 10s | No | 30yd range |
| Earth Shock | Shaman | 25454 | 6s (5s talented) | 2s | **Yes** | Also deals damage; DPS loss to use |
| Feral Charge | Druid | 16979 | 15s | 4s | No | Bear Form + talent required |

**Wind Shear does NOT exist in TBC Classic.** It was added in patch 3.0.2 (WotLK pre-patch).

**Hammer of Justice** (Paladin, spell 10308, 60s CD) is a **stun**, not an interrupt. It does
interrupt casting by stunning but is fundamentally a CC ability with a long cooldown.

### Shield Block is a rotation ability

Shield Block (spell 2565) has a 5-second CD and blocks 1 attack. Protection Warriors press it
every 5 seconds as part of their standard rotation to prevent crushing blows. It is NOT a major
defensive cooldown — do not track alongside Shield Wall (30-min CD) and Last Stand (10-min CD).

### Healer overheal profiles

Different healer specs have fundamentally different overheal patterns:
- **Holy Paladin:** 15-25% — single-target reactive healing, low natural overheal
- **Disc Priest:** 20-30% — PW:Shield has 0% overheal, but Prayer of Healing can
- **Holy Priest:** 25-35% — raid healing with CoH/PoH hits healthy targets
- **Resto Shaman:** 25-35% — Chain Heal bounces overheal on later targets
- **Resto Druid:** 35-50% — HoTs get sniped by other healers; structural, not player error
