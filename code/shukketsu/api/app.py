import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shukketsu.api.routes.analyze import router as analyze_router
from shukketsu.api.routes.health import router as health_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    from shukketsu.agent.graph import create_graph
    from shukketsu.agent.llm import create_llm
    from shukketsu.agent.tools import ALL_TOOLS, set_session_factory
    from shukketsu.api.routes.analyze import set_graph
    from shukketsu.config import get_settings
    from shukketsu.db.engine import create_db_engine, create_session_factory

    settings = get_settings()

    # Database
    engine = create_db_engine(settings)
    session_factory = create_session_factory(engine)
    set_session_factory(session_factory)
    logger.info("Database engine created: %s", settings.db.url.split("@")[-1])

    # LLM + Agent
    llm = create_llm(settings)
    graph = create_graph(llm, ALL_TOOLS)
    set_graph(graph)
    logger.info("Agent graph compiled with %d tools, model=%s", len(ALL_TOOLS), settings.llm.model)

    yield

    # Shutdown
    await engine.dispose()
    logger.info("Database engine disposed")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Shukketsu Raid Analyzer",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(analyze_router)

    return app
