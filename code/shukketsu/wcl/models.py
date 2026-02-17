from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class WCLBaseModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class Fight(WCLBaseModel):
    id: int
    name: str
    start_time: int
    end_time: int
    kill: bool
    encounter_id: int = Field(alias="encounterID")
    difficulty: int = 0
    fight_percentage: float | None = None


class Actor(WCLBaseModel):
    id: int
    name: str
    type: str
    sub_type: str | None = None
    server: str | None = None


class EventPage(WCLBaseModel):
    data: list[dict] = []
    next_page_timestamp: int | None = None


class RateLimitData(WCLBaseModel):
    points_spent_this_hour: int
    limit_per_hour: int
    points_reset_in: int


class CharacterRanking(WCLBaseModel):
    encounter_id: int = Field(alias="encounterID")
    encounter_name: str
    class_: int = Field(alias="class")
    spec: str
    percentile: float
    rank_percent: float
    duration: int
    amount: float
    total: int
    start_time: int
    report_code: str
    fight_id: int = Field(alias="fightID")
    difficulty: int = 0


class ReportRanking(WCLBaseModel):
    name: str
    player_class: str = Field(alias="class")
    spec: str
    amount: float
    duration: int
    bracket_percent: float | None = None
    rank_percent: float | None = None
    best_amount: float | None = None
    total_amount: float | None = None


class SpeedRankingEntry(WCLBaseModel):
    """Individual entry from fightRankings (speed) response."""

    fight_id: int = Field(alias="fightID")
    duration: int
    report: dict  # {"code": str, "guild": {"name": str} | None}


class TableEntry(WCLBaseModel):
    """Individual entry from report table() response (damage/healing/buffs/debuffs)."""

    name: str
    guid: int = 0
    type: str | None = None
    total: int = 0
    hit_count: int = Field(0, alias="hitCount")
    crit_count: int = Field(0, alias="critCount")
    crit_pct: float = Field(0.0, alias="critPct")
    uptime: float | None = None  # For buffs/debuffs: uptime in ms
    uses: int | None = None


class TableSourceEntry(WCLBaseModel):
    """Top-level entry from report table() — one per player (source)."""

    name: str
    id: int = 0
    type: str | None = None
    total: int = 0
    entries: list[TableEntry] = []


class GuildReportEntry(WCLBaseModel):
    """Individual report entry from guild reports listing."""

    code: str
    title: str
    start_time: int
    end_time: int
    zone: dict | None = None


class ZoneRankingEntry(WCLBaseModel):
    """Individual ranking entry from characterRankings response."""

    name: str
    class_id: int = Field(alias="class")
    spec: str
    amount: float
    duration: int
    server: dict | None = None
    report_code: str
    fight_id: int = Field(alias="fightID")
    guild: dict | None = None
    bracket_data: float | None = None
    total: int = 0
