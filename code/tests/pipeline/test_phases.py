"""Tests for per-phase fight breakdown feature."""

from shukketsu.pipeline.constants import ENCOUNTER_PHASES, PhaseDef


class TestPhaseDefinitions:
    def test_patchwerk_is_single_phase(self):
        phases = ENCOUNTER_PHASES["Patchwerk"]
        assert len(phases) == 1
        assert phases[0].name == "Full Fight"
        assert phases[0].pct_start == 0.0
        assert phases[0].pct_end == 1.0

    def test_kelthuzad_has_three_phases(self):
        phases = ENCOUNTER_PHASES["Kel'Thuzad"]
        assert len(phases) == 3
        assert phases[0].name == "P1 - Adds"
        assert phases[1].name == "P2 - Active"
        assert phases[2].name == "P3 - Ice Tombs"

    def test_thaddius_has_two_phases(self):
        phases = ENCOUNTER_PHASES["Thaddius"]
        assert len(phases) == 2
        assert phases[0].name == "P1 - Stalagg & Feugen"
        assert phases[1].name == "P2 - Thaddius"

    def test_all_naxx_bosses_have_phases(self):
        """Every Fresh Naxx boss should have phase definitions."""
        from shukketsu.pipeline.constants import FRESH_ZONES

        for boss in FRESH_ZONES["Naxxramas"]:
            assert boss in ENCOUNTER_PHASES, f"Missing phase definition for {boss}"
            phases = ENCOUNTER_PHASES[boss]
            assert len(phases) >= 1, f"Empty phase list for {boss}"

    def test_phases_cover_full_fight(self):
        """Each encounter's phases should span from 0.0 to 1.0."""
        for encounter, phases in ENCOUNTER_PHASES.items():
            assert phases[0].pct_start == 0.0, (
                f"{encounter}: first phase should start at 0.0"
            )
            assert phases[-1].pct_end == 1.0, (
                f"{encounter}: last phase should end at 1.0"
            )

    def test_phases_are_contiguous(self):
        """Each phase should start where the previous one ends."""
        for encounter, phases in ENCOUNTER_PHASES.items():
            for i in range(1, len(phases)):
                assert phases[i].pct_start == phases[i - 1].pct_end, (
                    f"{encounter}: phase {i} gap between "
                    f"{phases[i - 1].pct_end} and {phases[i].pct_start}"
                )

    def test_phase_def_fields(self):
        phase = PhaseDef("Test Phase", 0.0, 0.5, "A test phase")
        assert phase.name == "Test Phase"
        assert phase.pct_start == 0.0
        assert phase.pct_end == 0.5
        assert phase.description == "A test phase"

    def test_phase_def_default_description(self):
        phase = PhaseDef("Test", 0.0, 1.0)
        assert phase.description == ""

    def test_all_phases_have_names(self):
        """Every phase should have a non-empty name."""
        for encounter, phases in ENCOUNTER_PHASES.items():
            for phase in phases:
                assert phase.name, f"{encounter}: phase has empty name"

    def test_multi_phase_encounters_exist(self):
        """At least some encounters should have multiple phases."""
        multi = [
            e for e, phases in ENCOUNTER_PHASES.items() if len(phases) > 1
        ]
        assert len(multi) >= 5, "Expected at least 5 multi-phase encounters"


class TestPhaseTimeEstimation:
    def test_single_phase_covers_full_duration(self):
        """A single-phase boss should have phase duration == fight duration."""
        phases = ENCOUNTER_PHASES["Patchwerk"]
        fight_duration_ms = 180000
        phase = phases[0]
        estimated_start = int(fight_duration_ms * phase.pct_start)
        estimated_end = int(fight_duration_ms * phase.pct_end)
        assert estimated_start == 0
        assert estimated_end == 180000

    def test_multi_phase_time_splits(self):
        """Multi-phase boss should split time proportionally."""
        phases = ENCOUNTER_PHASES["Kel'Thuzad"]
        fight_duration_ms = 300000  # 5 minutes

        # P1: 0.0 - 0.2 = 60s
        p1_start = int(fight_duration_ms * phases[0].pct_start)
        p1_end = int(fight_duration_ms * phases[0].pct_end)
        assert p1_start == 0
        assert p1_end == 60000

        # P2: 0.2 - 0.7 = 150s
        p2_start = int(fight_duration_ms * phases[1].pct_start)
        p2_end = int(fight_duration_ms * phases[1].pct_end)
        assert p2_start == 60000
        assert p2_end == 210000

        # P3: 0.7 - 1.0 = 90s
        p3_start = int(fight_duration_ms * phases[2].pct_start)
        p3_end = int(fight_duration_ms * phases[2].pct_end)
        assert p3_start == 210000
        assert p3_end == 300000
