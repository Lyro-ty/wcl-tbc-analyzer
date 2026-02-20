"""Tests for the pull_rankings CLI script."""

from shukketsu.scripts.pull_rankings import parse_args


def test_parse_args_defaults():
    args = parse_args([])
    assert args.encounter is None
    assert args.zone_id is None
    assert args.class_name is None
    assert args.spec_name is None
    assert args.include_hps is False
    assert args.force is False
    assert args.stale_hours == 24
    assert args.dry_run is False


def test_parse_args_with_filters():
    args = parse_args([
        "--encounter", "Gruul",
        "--class-name", "Rogue",
        "--spec-name", "Combat",
        "--force",
        "--stale-hours", "12",
    ])
    assert args.encounter == "Gruul"
    assert args.class_name == "Rogue"
    assert args.spec_name == "Combat"
    assert args.force is True
    assert args.stale_hours == 12


def test_parse_args_dry_run():
    args = parse_args(["--dry-run"])
    assert args.dry_run is True


def test_parse_args_zone_id():
    args = parse_args(["--zone-id", "1047"])
    assert args.zone_id == 1047


def test_parse_args_include_hps():
    args = parse_args(["--include-hps"])
    assert args.include_hps is True


def test_parse_args_all_options():
    args = parse_args([
        "--encounter", "Brutallus",
        "--zone-id", "1048",
        "--class-name", "Warrior",
        "--spec-name", "Fury",
        "--include-hps",
        "--force",
        "--stale-hours", "48",
        "--dry-run",
    ])
    assert args.encounter == "Brutallus"
    assert args.zone_id == 1048
    assert args.class_name == "Warrior"
    assert args.spec_name == "Fury"
    assert args.include_hps is True
    assert args.force is True
    assert args.stale_hours == 48
    assert args.dry_run is True
