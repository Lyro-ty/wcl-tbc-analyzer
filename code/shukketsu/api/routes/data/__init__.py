"""Data API routes package."""

from fastapi import APIRouter

from shukketsu.api.routes.data.characters import router as characters_router
from shukketsu.api.routes.data.comparison import router as comparison_router
from shukketsu.api.routes.data.events import router as events_router
from shukketsu.api.routes.data.fights import router as fights_router
from shukketsu.api.routes.data.rankings import router as rankings_router
from shukketsu.api.routes.data.reports import router as reports_router

router = APIRouter(prefix="/api/data", tags=["data"])
router.include_router(reports_router)
router.include_router(fights_router)
router.include_router(characters_router)
router.include_router(rankings_router)
router.include_router(comparison_router)
router.include_router(events_router)
