"""
API Routes - Configuration Management
Handles /config endpoints for system configuration.
"""
from fastapi import APIRouter, Request
from fastapi import HTTPException
from api.services import config_service

router = APIRouter(prefix="/config", tags=["config"])


@router.get("")
async def get_config():
    """Get current system configuration."""
    return config_service.get_config_payload()


@router.get("/schema")
async def get_config_schema():
    """Get schema metadata for dynamic config rendering."""
    return config_service.get_config_schema_payload()


@router.get("/audit")
async def get_config_audit():
    """Get config registry audit report (deprecated/unreferenced/conflicts)."""
    return config_service.get_config_audit_payload()


@router.post("/save")
async def save_config(req: Request):
    """Save system configuration."""
    data = await req.json()
    try:
        return config_service.save_config_payload(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
