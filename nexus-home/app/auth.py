"""API key authentication middleware."""

from fastapi import Request, HTTPException, Security
from fastapi.security import APIKeyHeader
from app.config import get_settings

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    request: Request,
    api_key: str | None = Security(API_KEY_HEADER),
) -> str:
    """Verify API key from header or query parameter."""
    if api_key is None:
        api_key = request.query_params.get("api_key")
    if api_key is None:
        raise HTTPException(status_code=401, detail="Missing API key")

    settings = get_settings()
    if api_key not in settings.server.api_keys:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key
