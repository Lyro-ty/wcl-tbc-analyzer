from typing import Any

from langgraph.graph import MessagesState


class AnalyzerState(MessagesState):
    intent: str | None = None
    detected_context: dict[str, Any] | None = None
    tool_error_count: int = 0
