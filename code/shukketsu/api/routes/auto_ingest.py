"""Auto-ingest management endpoints."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/auto-ingest", tags=["auto-ingest"])

# Module-level service reference (set during lifespan)
_service = None


def set_service(service):
    global _service
    _service = service


def _get_service():
    if _service is None:
        raise RuntimeError("AutoIngestService not initialized")
    return _service


@router.get("/status")
async def get_status():
    """Get auto-ingest service status."""
    return _get_service().get_status()


@router.post("/trigger")
async def trigger_poll():
    """Manually trigger a poll."""
    return await _get_service().trigger_now()
