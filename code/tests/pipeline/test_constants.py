"""Tests for TBC class/spec constants and boss name data."""

import pytest

from shukketsu.pipeline.constants import (
    ALL_BOSS_NAMES,
    CLASSIC_COOLDOWNS,
    CLASSIC_DOTS,
    CONSUMABLE_CATEGORIES,
    ENCOUNTER_CONTEXTS,
    ENCOUNTER_PHASES,
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


class TestAllBossNames:
    def test_all_boss_names_equals_tbc(self):
        assert ALL_BOSS_NAMES == TBC_BOSS_NAMES

    def test_all_boss_names_contains_known(self):
        assert "Illidan Stormrage" in ALL_BOSS_NAMES
        assert "Gruul the Dragonkiller" in ALL_BOSS_NAMES


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

    def test_required_flasks_are_tbc(self):
        """Required flasks should be TBC, not Classic."""
        tbc_flask_ids = {28518, 28519, 28520, 28521, 28540}
        classic_flask_ids = {17628, 17627, 17546, 17626, 17629}
        for role, consumables in REQUIRED_CONSUMABLES.items():
            for c in consumables:
                if c.category == "flask":
                    assert c.spell_id in tbc_flask_ids, (
                        f"Role '{role}' has Classic flask "
                        f"{c.spell_id} ({c.name}); "
                        f"should use TBC flask"
                    )
                    assert c.spell_id not in classic_flask_ids, (
                        f"Role '{role}' uses Classic flask "
                        f"{c.name}"
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
    """Verify ENCOUNTER_PHASES for TBC bosses."""

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

    def test_brutallus_is_1_0(self):
        ctx = ENCOUNTER_CONTEXTS["Brutallus"]
        assert ctx.gcd_modifier == 1.0
        assert ctx.melee_modifier is None  # Pure DPS race

    def test_netherspite_has_melee_penalty(self):
        ctx = ENCOUNTER_CONTEXTS["Netherspite"]
        assert ctx.gcd_modifier < 1.0  # Banish phase reduces DPS uptime
        assert ctx.melee_modifier is not None
        assert ctx.melee_modifier < ctx.gcd_modifier  # Melee worse than ranged

    def test_kaelthas_is_low(self):
        ctx = ENCOUNTER_CONTEXTS["Kael'thas Sunstrider"]
        assert ctx.gcd_modifier <= 0.60  # No Kael DPS ~50%

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


class TestConsumableExpansion:
    def test_tbc_flasks_in_categories(self):
        assert 28518 in CONSUMABLE_CATEGORIES  # Flask of Fortification
        assert 28519 in CONSUMABLE_CATEGORIES  # Flask of Mighty Restoration
        assert 28520 in CONSUMABLE_CATEGORIES  # Flask of Relentless Assault
        assert 28521 in CONSUMABLE_CATEGORIES  # Flask of Blinding Light
        assert 28540 in CONSUMABLE_CATEGORIES  # Flask of Pure Death

    def test_tbc_potions_in_categories(self):
        assert 28507 in CONSUMABLE_CATEGORIES  # Haste Potion

    def test_battle_guardian_elixir_distinction(self):
        """Battle vs guardian elixirs should be distinguishable by category."""
        # Battle elixirs
        assert CONSUMABLE_CATEGORIES[28490][0] == "battle_elixir"  # Major Agility
        assert CONSUMABLE_CATEGORIES[28491][0] == "battle_elixir"  # Healing Power
        assert CONSUMABLE_CATEGORIES[28501][0] == "battle_elixir"  # Major Firepower
        # Guardian elixirs
        assert CONSUMABLE_CATEGORIES[28509][0] == "guardian_elixir"  # Major Defense
        assert CONSUMABLE_CATEGORIES[28502][0] == "guardian_elixir"  # Major Mageblood

    def test_flask_category(self):
        assert CONSUMABLE_CATEGORIES[28520][0] == "flask"  # Relentless Assault
        assert CONSUMABLE_CATEGORIES[28540][0] == "flask"  # Pure Death

    def test_potion_category(self):
        assert CONSUMABLE_CATEGORIES[28507][0] == "potion"  # Haste Potion

    def test_draenic_wisdom_is_guardian(self):
        assert 39627 in CONSUMABLE_CATEGORIES
        assert CONSUMABLE_CATEGORIES[39627][0] == "guardian_elixir"

    def test_mongoose_is_battle_elixir(self):
        assert CONSUMABLE_CATEGORIES[11390][0] == "battle_elixir"

    def test_required_consumables_battle_vs_guardian(self):
        """REQUIRED_CONSUMABLES should use battle_elixir/guardian_elixir."""
        for role, consumables in REQUIRED_CONSUMABLES.items():
            for c in consumables:
                assert c.category != "elixir", (
                    f"Role '{role}' has generic 'elixir' for {c.name}; "
                    f"should be 'battle_elixir' or 'guardian_elixir'"
                )
