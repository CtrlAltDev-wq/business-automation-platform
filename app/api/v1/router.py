from fastapi import APIRouter

from app.api.v1.endpoints import lead

# Version 1 API router: every feature module is registered here.
api_router = APIRouter()

api_router.include_router(lead.router)
