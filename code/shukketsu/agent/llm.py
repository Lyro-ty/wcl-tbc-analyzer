from langchain_openai import ChatOpenAI

from shukketsu.config import Settings


def create_llm(settings: Settings) -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm.model,
        base_url=settings.llm.base_url,
        api_key=settings.llm.api_key,
        temperature=settings.llm.temperature,
        max_tokens=settings.llm.max_tokens,
        timeout=settings.llm.timeout,
    )
