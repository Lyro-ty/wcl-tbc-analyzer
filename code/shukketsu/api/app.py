import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from shukketsu.agent.graph import create_graph
from shukketsu.agent.llm import create_llm
from shukketsu.agent.tool_utils import set_session_factory
from shukketsu.agent.tools import ALL_TOOLS
from shukketsu.api.deps import set_dependencies, set_wcl_factory, verify_api_key
from shukketsu.api.routes.analyze import set_graph, set_langfuse_handler
from shukketsu.api.routes.health import set_health_deps
from shukketsu.config import get_settings
from shukketsu.db.engine import create_db_engine, create_session_factory

logger = logging.getLogger(__name__)

FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
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
    logger.info(
        "Agent graph compiled with %d tools, model=%s",
        len(ALL_TOOLS), settings.llm.model,
    )

    # Wire up DI for data routes
    set_dependencies(session_factory=session_factory, graph=graph)

    # Health check dependencies
    set_health_deps(session_factory=session_factory, llm_base_url=settings.llm.base_url)

    # Langfuse observability (optional)
    langfuse_enabled = False
    if settings.langfuse.enabled:
        try:
            from langfuse import Langfuse
            from langfuse.langchain import CallbackHandler as LangfuseCB
        except ImportError:
            logger.warning(
                "LANGFUSE__ENABLED=true but langfuse is not installed. "
                "Install with: pip install shukketsu[langfuse]"
            )
        else:
            Langfuse(
                public_key=settings.langfuse.public_key,
                secret_key=settings.langfuse.secret_key.get_secret_value(),
                host=settings.langfuse.host,
            )
            set_langfuse_handler(LangfuseCB)
            langfuse_enabled = True
            logger.info("Langfuse tracing enabled: %s", settings.langfuse.host)

    # Shared WCL client factory (one auth + rate limiter + HTTP pool)
    from shukketsu.wcl.factory import WCLFactory

    wcl_factory = WCLFactory(settings)
    await wcl_factory.start()
    set_wcl_factory(wcl_factory)
    logger.info("WCL factory started (shared auth + rate limiter + HTTP pool)")

    # Auto-ingest background service (optional)
    from shukketsu.api.routes.auto_ingest import set_service as set_auto_ingest_service
    from shukketsu.pipeline.auto_ingest import AutoIngestService

    auto_ingest = AutoIngestService(settings, session_factory, wcl_factory)
    set_auto_ingest_service(auto_ingest)
    await auto_ingest.start()

    yield

    # Shutdown
    await auto_ingest.stop()
    await wcl_factory.stop()
    if langfuse_enabled:
        from langfuse import get_client
        get_client().flush()
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
        allow_origins=["http://localhost:5173", "http://localhost:8000"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["X-API-Key", "Content-Type"],
    )

    from shukketsu.api.routes.analyze import router as analyze_router
    from shukketsu.api.routes.auto_ingest import router as auto_ingest_router
    from shukketsu.api.routes.data import router as data_router
    from shukketsu.api.routes.health import router as health_router

    # Health router has no auth
    app.include_router(health_router)
    # Protected routers require API key (when configured)
    app.include_router(data_router, dependencies=[Depends(verify_api_key)])
    app.include_router(analyze_router, dependencies=[Depends(verify_api_key)])
    app.include_router(auto_ingest_router, dependencies=[Depends(verify_api_key)])

    # Serve frontend static files (production build)
    if FRONTEND_DIST.is_dir():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{path:path}")
        async def spa_catchall(path: str):
            """Serve index.html for SPA client-side routing."""
            resolved = (FRONTEND_DIST / path).resolve()
            if resolved.is_relative_to(FRONTEND_DIST.resolve()) and resolved.is_file():
                return FileResponse(resolved)
            return FileResponse(FRONTEND_DIST / "index.html")

    return app
