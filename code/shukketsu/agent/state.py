from langgraph.graph import MessagesState


class AnalyzerState(MessagesState):
    intent: str | None = None
    tool_error_count: int = 0
    player_names: list[str] = []
