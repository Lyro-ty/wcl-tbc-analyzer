from typing import Literal

from langgraph.graph import MessagesState


class AnalyzerState(MessagesState):
    query_type: Literal[
        "my_performance", "comparison", "trend", "rotation", "general"
    ] | None = None
    grade: str | None = None
    retry_count: int = 0
