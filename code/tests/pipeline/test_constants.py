"""Tests for TBC class/spec constants and boss name data."""

import pytest

from shukketsu.pipeline.constants import (
    ALL_BOSS_NAMES,
    FRESH_BOSS_NAMES,
    FRESH_ZONES,
    REQUIRED_CONSUMABLES,
    TBC_BOSS_NAMES,
    TBC_DPS_SPECS,
    TBC_HEALER_SPECS,
    TBC_SPECS,
    TBC_TANK_SPECS,
    TBC_ZONES,
    ClassSpec,
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
