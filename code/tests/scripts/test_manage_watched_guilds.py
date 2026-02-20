"""Tests for the manage_watched_guilds CLI script."""

from shukketsu.scripts.manage_watched_guilds import parse_args


class TestParseArgs:
    def test_add(self):
        args = parse_args([
            "--add", "APES",
            "--guild-id", "12345",
            "--server", "whitemane",
            "--region", "US",
        ])
        assert args.add == "APES"
        assert args.guild_id == 12345
        assert args.server == "whitemane"
        assert args.region == "US"

    def test_list(self):
        args = parse_args(["--list"])
        assert args.list_guilds is True

    def test_remove(self):
        args = parse_args(["--remove", "APES"])
        assert args.remove == "APES"

    def test_defaults(self):
        args = parse_args([])
        assert args.add is None
        assert args.guild_id is None
        assert args.server is None
        assert args.region == "US"
        assert args.list_guilds is False
        assert args.remove is None

    def test_add_defaults_region(self):
        args = parse_args([
            "--add", "Progress",
            "--guild-id", "99999",
            "--server", "firemaw",
        ])
        assert args.add == "Progress"
        assert args.region == "US"

    def test_add_eu_region(self):
        args = parse_args([
            "--add", "Progress",
            "--guild-id", "99999",
            "--server", "firemaw",
            "--region", "EU",
        ])
        assert args.region == "EU"
