from fastapi import APIRouter

from app.api.v1.endpoints import dashboard, intake, integrations, lead, webhook

# Version 1 API router: every feature module is registered here.
api_router = APIRouter()

api_router.include_router(lead.router)
api_router.include_router(dashboard.router)
api_router.include_router(webhook.router)
api_router.include_router(intake.router)
api_router.include_router(integrations.router)
