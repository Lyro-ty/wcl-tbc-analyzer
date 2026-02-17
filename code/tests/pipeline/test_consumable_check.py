"""Tests for consumable/prep check definitions and helper."""

from shukketsu.pipeline.constants import (
    REQUIRED_CONSUMABLES,
    ROLE_BY_SPEC,
    ConsumableDef,
    get_expected_consumables,
)


class TestRoleBySpec:
    def test_melee_dps_specs(self):
        assert ROLE_BY_SPEC["Arms"] == "melee_dps"
        assert ROLE_BY_SPEC["Fury"] == "melee_dps"
        assert ROLE_BY_SPEC["Combat"] == "melee_dps"
        assert ROLE_BY_SPEC["Enhancement"] == "melee_dps"
        assert ROLE_BY_SPEC["Feral"] == "melee_dps"

    def test_caster_dps_specs(self):
        assert ROLE_BY_SPEC["Shadow"] == "caster_dps"
        assert ROLE_BY_SPEC["Fire"] == "caster_dps"
        assert ROLE_BY_SPEC["Arcane"] == "caster_dps"
        assert ROLE_BY_SPEC["Affliction"] == "caster_dps"

    def test_healer_specs(self):
        assert ROLE_BY_SPEC["Holy"] == "healer"
        assert ROLE_BY_SPEC["Discipline"] == "healer"
        assert ROLE_BY_SPEC["Restoration"] == "healer"

    def test_tank_specs(self):
        assert ROLE_BY_SPEC["Protection"] == "tank"

    def test_ranged_dps_specs(self):
        assert ROLE_BY_SPEC["Beast Mastery"] == "ranged_dps"
        assert ROLE_BY_SPEC["Marksmanship"] == "ranged_dps"


class TestRequiredConsumables:
    def test_all_role_has_food_buffs(self):
        all_consumables = REQUIRED_CONSUMABLES["all"]
        assert len(all_consumables) > 0
        assert all(isinstance(c, ConsumableDef) for c in all_consumables)
        food_items = [c for c in all_consumables if c.category == "food"]
        assert len(food_items) > 0

    def test_melee_dps_has_elixirs(self):
        melee = REQUIRED_CONSUMABLES["melee_dps"]
        elixirs = [c for c in melee if c.category == "elixir"]
        assert len(elixirs) > 0

    def test_caster_dps_has_flask_or_elixir(self):
        caster = REQUIRED_CONSUMABLES["caster_dps"]
        flasks_elixirs = [c for c in caster if c.category in ("flask", "elixir")]
        assert len(flasks_elixirs) > 0

    def test_healer_has_mana_oil(self):
        healer = REQUIRED_CONSUMABLES["healer"]
        weapon = [c for c in healer if c.category == "weapon"]
        assert len(weapon) > 0

    def test_all_entries_have_valid_fields(self):
        for role, consumables in REQUIRED_CONSUMABLES.items():
            for c in consumables:
                assert c.spell_id > 0, f"Bad spell_id for {c.name} in role {role}"
                assert c.name, f"Empty name in role {role}"
                assert c.category in (
                    "flask", "elixir", "food", "weapon", "potion", "scroll"
                ), f"Bad category {c.category} for {c.name}"
                assert 0 < c.min_uptime_pct <= 100, f"Bad uptime for {c.name}"


class TestGetExpectedConsumables:
    def test_fury_gets_all_plus_melee(self):
        result = get_expected_consumables("Fury")
        names = [c.name for c in result]
        # Should include items from "all" and "melee_dps"
        assert any("Well Fed" in n for n in names)
        assert any("Agility" in n or "Mongoose" in n for n in names)

    def test_fire_gets_all_plus_caster(self):
        result = get_expected_consumables("Fire")
        names = [c.name for c in result]
        assert any("Well Fed" in n for n in names)
        assert any("Firepower" in n or "Wizard Oil" in n for n in names)

    def test_holy_gets_all_plus_healer(self):
        result = get_expected_consumables("Holy")
        names = [c.name for c in result]
        assert any("Well Fed" in n for n in names)
        assert any("Mana Oil" in n or "Healing Power" in n for n in names)

    def test_unknown_spec_defaults_to_melee(self):
        result = get_expected_consumables("UnknownSpec")
        # Should return all + melee_dps
        melee_items = REQUIRED_CONSUMABLES["melee_dps"]
        assert any(c.name == melee_items[0].name for c in result)
