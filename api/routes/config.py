"""
API Routes - Configuration Management
Handles /config endpoints for system configuration.
"""
from fastapi import APIRouter, Request
from api.services import config_service

router = APIRouter(prefix="/config", tags=["config"])


@router.get("")
async def get_config():
    """Get current system configuration."""
    return config_service.get_config_payload()


@router.post("/save")
async def save_config(req: Request):
    """Save system configuration."""
    data = await req.json()
    return config_service.save_config_payload(data)
