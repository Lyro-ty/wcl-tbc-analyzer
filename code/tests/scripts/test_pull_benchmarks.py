"""Tests for the pull_benchmarks CLI script."""

from shukketsu.scripts.pull_benchmarks import parse_args


class TestParseArgs:
    def test_defaults(self):
        args = parse_args([])
        assert args.encounter is None
        assert args.zone_id is None
        assert args.max_reports == 10
        assert args.compute_only is False
        assert args.force is False

    def test_compute_only(self):
        args = parse_args(["--compute-only"])
        assert args.compute_only is True

    def test_encounter_filter(self):
        args = parse_args(["--encounter", "Gruul"])
        assert args.encounter == "Gruul"

    def test_max_reports(self):
        args = parse_args(["--max-reports", "25"])
        assert args.max_reports == 25

    def test_zone_id(self):
        args = parse_args(["--zone-id", "1048"])
        assert args.zone_id == 1048

    def test_force(self):
        args = parse_args(["--force"])
        assert args.force is True

    def test_all_options(self):
        args = parse_args([
            "--encounter", "Gruul the Dragonkiller",
            "--zone-id", "1048",
            "--max-reports", "5",
            "--compute-only",
            "--force",
        ])
        assert args.encounter == "Gruul the Dragonkiller"
        assert args.zone_id == 1048
        assert args.max_reports == 5
        assert args.compute_only is True
        assert args.force is True
