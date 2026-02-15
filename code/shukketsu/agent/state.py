from typing import Literal

from langgraph.graph import MessagesState


class AnalyzerState(MessagesState):
    query_type: Literal["my_performance", "comparison", "trend", "general"] | None = None
    encounter_context: dict | None = None
    character_context: dict | None = None
    retry_count: int = 0
