"""Tests for TBC class/spec constants and boss name data."""

import pytest

from shukketsu.pipeline.constants import (
    ALL_BOSS_NAMES,
    CLASSIC_COOLDOWNS,
    CLASSIC_DOTS,
    ENCOUNTER_CONTEXTS,
    ENCOUNTER_PHASES,
    FRESH_BOSS_NAMES,
    FRESH_ZONES,
    REQUIRED_CONSUMABLES,
    ROLE_DEFAULT_RULES,
    SPEC_ROTATION_RULES,
    TBC_BOSS_NAMES,
    TBC_DPS_SPECS,
    TBC_HEALER_SPECS,
    TBC_SPECS,
    TBC_TANK_SPECS,
    TBC_ZONES,
    ClassSpec,
    CooldownDef,
    EncounterContext,
    SpecRules,
)


class TestClassSpecs:
    def test_total_spec_count(self):
        assert len(TBC_SPECS) == 27

    def test_no_duplicate_specs(self):
        combos = [(s.class_name, s.spec_name) for s in TBC_SPECS]
        assert len(combos) == len(set(combos))

    def test_all_roles_covered(self):
        roles = {s.role for s in TBC_SPECS}
        assert roles == {"dps", "healer", "tank"}

    def test_dps_specs(self):
        assert len(TBC_DPS_SPECS) == 20

    def test_healer_specs(self):
        assert len(TBC_HEALER_SPECS) == 5

    def test_tank_specs(self):
        assert len(TBC_TANK_SPECS) == 2

    def test_roles_sum_to_total(self):
        total = len(TBC_DPS_SPECS) + len(TBC_HEALER_SPECS) + len(TBC_TANK_SPECS)
        assert total == len(TBC_SPECS)

    def test_known_specs_present(self):
        spec_combos = {(s.class_name, s.spec_name) for s in TBC_SPECS}
        assert ("Rogue", "Combat") in spec_combos
        assert ("Priest", "Shadow") in spec_combos
        assert ("Paladin", "Holy") in spec_combos
        assert ("Warrior", "Protection") in spec_combos

    def test_class_spec_frozen(self):
        spec = ClassSpec(class_name="Test", spec_name="Test", role="dps")
        with pytest.raises(AttributeError):
            spec.class_name = "Other"


class TestBossNames:
    def test_zones_present(self):
        assert "Karazhan" in TBC_ZONES
        assert "Black Temple" in TBC_ZONES
        assert "Sunwell Plateau" in TBC_ZONES

    def test_boss_names_nonempty(self):
        assert len(TBC_BOSS_NAMES) > 40

    def test_known_bosses(self):
        assert "Illidan Stormrage" in TBC_BOSS_NAMES
        assert "Prince Malchezaar" in TBC_BOSS_NAMES
        assert "Kil'jaeden" in TBC_BOSS_NAMES

    def test_boss_names_match_zones(self):
        all_from_zones = set()
        for bosses in TBC_ZONES.values():
            all_from_zones.update(bosses)
        assert frozenset(all_from_zones) == TBC_BOSS_NAMES


class TestFreshBossNames:
    def test_naxxramas_present(self):
        assert "Naxxramas" in FRESH_ZONES

    def test_naxx_boss_count(self):
        assert len(FRESH_ZONES["Naxxramas"]) == 15

    def test_fresh_boss_names_nonempty(self):
        assert len(FRESH_BOSS_NAMES) == 15

    def test_known_fresh_bosses(self):
        assert "Patchwerk" in FRESH_BOSS_NAMES
        assert "Kel'Thuzad" in FRESH_BOSS_NAMES
        assert "Sapphiron" in FRESH_BOSS_NAMES
        assert "Thaddius" in FRESH_BOSS_NAMES

    def test_fresh_boss_names_match_zones(self):
        all_from_zones = set()
        for bosses in FRESH_ZONES.values():
            all_from_zones.update(bosses)
        assert frozenset(all_from_zones) == FRESH_BOSS_NAMES

    def test_all_boss_names_union(self):
        assert ALL_BOSS_NAMES == TBC_BOSS_NAMES | FRESH_BOSS_NAMES

    def test_all_boss_names_contains_both(self):
        assert "Illidan Stormrage" in ALL_BOSS_NAMES
        assert "Patchwerk" in ALL_BOSS_NAMES


class TestConsumableSpellIds:
    """Verify REQUIRED_CONSUMABLES spell IDs match CONSUMABLE_CATEGORIES names."""

    def test_caster_dps_has_correct_firepower_id(self):
        """28501 is Elixir of Major Firepower, not 28509 (Major Defense)."""
        caster_ids = {c.spell_id for c in REQUIRED_CONSUMABLES["caster_dps"]}
        assert 28501 in caster_ids, "Caster DPS should have 28501 (Major Firepower)"
        assert 28509 not in caster_ids, "28509 is Major Defense, not Firepower"

    def test_tank_has_correct_healing_power_id(self):
        """28491 is Elixir of Healing Power, not 28502 (Major Mageblood)."""
        tank_ids = {c.spell_id for c in REQUIRED_CONSUMABLES["tank"]}
        assert 28491 in tank_ids, "Tank should have 28491 (Healing Power)"

    def test_no_defense_elixir_in_caster_dps(self):
        """caster_dps should not contain Major Defense (28509)."""
        caster_names = {
            c.name for c in REQUIRED_CONSUMABLES["caster_dps"]
        }
        assert "Elixir of Major Defense" not in caster_names

    def test_no_mageblood_mislabeled_as_healing_power(self):
        """Healing Power should use 28491, not 28502 (Major Mageblood)."""
        for role in ("healer", "tank"):
            for c in REQUIRED_CONSUMABLES[role]:
                if c.name == "Elixir of Healing Power":
                    assert c.spell_id == 28491, (
                        f"{role}: Healing Power has spell_id {c.spell_id},"
                        f" expected 28491"
                    )


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


TBC_P1_BOSSES = [
    # Karazhan
    "Attumen the Huntsman", "Moroes", "Maiden of Virtue", "Opera Hall",
    "The Curator", "Shade of Aran", "Terestian Illhoof", "Netherspite",
    "Chess Event", "Prince Malchezaar", "Nightbane",
    # Gruul's Lair
    "High King Maulgar", "Gruul the Dragonkiller",
    # Magtheridon's Lair
    "Magtheridon",
]


class TestEncounterPhases:
    """Verify ENCOUNTER_PHASES for TBC P1 and Fresh Naxxramas bosses."""

    @pytest.mark.parametrize("boss", TBC_P1_BOSSES)
    def test_tbc_p1_boss_has_phases(self, boss):
        assert boss in ENCOUNTER_PHASES, f"Missing phases for {boss}"

    @pytest.mark.parametrize("boss", list(ENCOUNTER_PHASES.keys()))
    def test_phases_start_at_zero(self, boss):
        phases = ENCOUNTER_PHASES[boss]
        assert phases[0].pct_start == 0.0, f"{boss} first phase doesn't start at 0.0"

    @pytest.mark.parametrize("boss", list(ENCOUNTER_PHASES.keys()))
    def test_phases_end_at_one(self, boss):
        phases = ENCOUNTER_PHASES[boss]
        assert phases[-1].pct_end == 1.0, f"{boss} last phase doesn't end at 1.0"

    @pytest.mark.parametrize("boss", list(ENCOUNTER_PHASES.keys()))
    def test_phases_contiguous(self, boss):
        """Each phase end should equal the next phase start."""
        phases = ENCOUNTER_PHASES[boss]
        for i in range(len(phases) - 1):
            assert phases[i].pct_end == phases[i + 1].pct_start, (
                f"{boss}: gap between phase {i} end ({phases[i].pct_end}) "
                f"and phase {i+1} start ({phases[i+1].pct_start})"
            )

    @pytest.mark.parametrize("boss", list(ENCOUNTER_PHASES.keys()))
    def test_phases_have_names_and_descriptions(self, boss):
        for phase in ENCOUNTER_PHASES[boss]:
            assert phase.name, f"{boss}: phase has empty name"
            assert phase.description, f"{boss}: phase '{phase.name}' has empty description"

    def test_prince_malchezaar_has_three_phases(self):
        assert len(ENCOUNTER_PHASES["Prince Malchezaar"]) == 3

    def test_magtheridon_has_two_phases(self):
        assert len(ENCOUNTER_PHASES["Magtheridon"]) == 2

    def test_kelthuzad_has_three_phases(self):
        assert len(ENCOUNTER_PHASES["Kel'Thuzad"]) == 3


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


class TestSpecRules:
    def test_spec_rules_dataclass_exists(self):
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
        assert isinstance(SPEC_ROTATION_RULES, dict)

    @pytest.mark.parametrize(
        "class_name,spec_name",
        [(s.class_name, s.spec_name) for s in TBC_SPECS],
    )
    def test_every_spec_has_rules(self, class_name, spec_name):
        key = (class_name, spec_name)
        assert key in SPEC_ROTATION_RULES, f"Missing rules for {key}"

    @pytest.mark.parametrize(
        "class_name,spec_name",
        [(s.class_name, s.spec_name) for s in TBC_SPECS],
    )
    def test_spec_rules_sane_values(self, class_name, spec_name):
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
        rules = SPEC_ROTATION_RULES[("Paladin", "Holy")]
        assert rules.healer_overheal_target <= 25  # Reactive single-target

    def test_resto_druid_high_overheal_target(self):
        rules = SPEC_ROTATION_RULES[("Druid", "Restoration")]
        assert rules.healer_overheal_target >= 40  # HoTs get sniped

    def test_spec_rules_frozen(self):
        rules = SPEC_ROTATION_RULES[("Warrior", "Fury")]
        with pytest.raises(AttributeError):
            rules.gcd_target = 50.0

    def test_key_abilities_are_tuples(self):
        """key_abilities should be tuples for true immutability on frozen dataclass."""
        for key, rules in SPEC_ROTATION_RULES.items():
            assert isinstance(rules.key_abilities, tuple), (
                f"{key}: key_abilities should be tuple, got {type(rules.key_abilities)}"
            )

    def test_role_default_rules_covers_all_roles(self):
        expected = {"melee_dps", "caster_dps", "ranged_dps", "healer", "tank"}
        assert set(ROLE_DEFAULT_RULES.keys()) == expected

    def test_role_default_rules_have_empty_abilities(self):
        for role, rules in ROLE_DEFAULT_RULES.items():
            assert len(rules.key_abilities) == 0, (
                f"Fallback for {role} should have empty key_abilities"
            )
            assert rules.role == role


class TestEncounterContexts:
    def test_encounter_context_dataclass_exists(self):
        fields = set(EncounterContext.__dataclass_fields__.keys())
        assert "name" in fields
        assert "gcd_modifier" in fields
        assert "melee_modifier" in fields
        assert "notes" in fields

    def test_encounter_contexts_dict_exists(self):
        assert isinstance(ENCOUNTER_CONTEXTS, dict)

    def test_patchwerk_is_1_0(self):
        ctx = ENCOUNTER_CONTEXTS["Patchwerk"]
        assert ctx.gcd_modifier == 1.0
        assert ctx.melee_modifier is None  # No melee override needed

    def test_sapphiron_has_melee_penalty(self):
        ctx = ENCOUNTER_CONTEXTS["Sapphiron"]
        assert ctx.gcd_modifier < 1.0  # Air phases reduce DPS uptime
        assert ctx.melee_modifier is not None
        assert ctx.melee_modifier < ctx.gcd_modifier  # Melee worse than ranged

    def test_heigan_is_low(self):
        ctx = ENCOUNTER_CONTEXTS["Heigan the Unclean"]
        assert ctx.gcd_modifier <= 0.65  # Dance phase = minimal DPS

    def test_unknown_encounter_defaults_to_1(self):
        assert "NonexistentBoss" not in ENCOUNTER_CONTEXTS

    @pytest.mark.parametrize(
        "boss_name",
        list(ENCOUNTER_CONTEXTS.keys()),
    )
    def test_modifiers_in_valid_range(self, boss_name):
        ctx = ENCOUNTER_CONTEXTS[boss_name]
        assert 0.3 <= ctx.gcd_modifier <= 1.0
        if ctx.melee_modifier is not None:
            assert 0.3 <= ctx.melee_modifier <= 1.0
            assert ctx.melee_modifier <= ctx.gcd_modifier
