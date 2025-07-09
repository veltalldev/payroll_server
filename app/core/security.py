from fastapi import HTTPException, Request, Depends
import logging
from app.core.config import ServerConfig # Import ServerConfig

logger = logging.getLogger(__name__)

async def require_localhost(request: Request):
    """Require request to come from localhost"""
    client_host = request.client.host
    if client_host not in ["127.0.0.1", "::1", "localhost"]:
        logger.warning(f"Admin endpoint access denied from {client_host}")
        raise HTTPException(status_code=403, detail="Admin endpoints only accessible from localhost")
    return True

async def require_admin_secret(request: Request):
    """Require admin secret in header"""
    admin_secret = request.headers.get("X-Admin-Secret")
    if admin_secret != ServerConfig.ADMIN_SECRET:
        logger.warning(f"Invalid admin secret from {request.client.host}")
        raise HTTPException(status_code=403, detail="Invalid admin credentials")
    return True

async def admin_auth(request: Request):
    """Combined admin authentication"""
    if ServerConfig.LOCALHOST_ONLY_ADMIN:
        await require_localhost(request)
    await require_admin_secret(request)
    return True
