import logging

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

logger = logging.getLogger(__name__)

router = APIRouter()

_session_factory = None
_llm_base_url = None


def set_health_deps(session_factory=None, llm_base_url=None) -> None:
    global _session_factory, _llm_base_url
    _session_factory = session_factory
    _llm_base_url = llm_base_url


@router.get("/health")
async def health():
    db_status = "ok"
    llm_status = "ok"
    healthy = True

    # Check database
    if _session_factory:
        session = _session_factory()
        try:
            await session.execute(text("SELECT 1"))
        except Exception as e:
            logger.warning("Health check: DB unreachable: %s", e)
            db_status = "error"
            healthy = False
        finally:
            await session.close()
    else:
        db_status = "not configured"

    # Check LLM
    if _llm_base_url:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{_llm_base_url}/models")
                if resp.status_code != 200:
                    llm_status = "error"
                    healthy = False
        except Exception as e:
            logger.warning("Health check: LLM unreachable: %s", e)
            llm_status = "error"
            healthy = False
    else:
        llm_status = "not configured"

    body = {
        "status": "ok" if healthy else "degraded",
        "version": "0.1.0",
        "database": db_status,
        "llm": llm_status,
    }
    status_code = 200 if healthy else 503
    return JSONResponse(content=body, status_code=status_code)
