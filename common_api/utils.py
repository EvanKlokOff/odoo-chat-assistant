from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import HTTPException, Depends, Security
from common_api.config import settings
from typing import Optional, Dict
from src.database.session import get_db

security = HTTPBearer()


async def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify API key from Authorization header"""
    api_key = credentials.credentials

    # Проверяем, что api_tokens - это список
    if not settings.api_tokens or api_key not in settings.api_tokens:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return api_key


async def verify_admin_key(
        credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> str:
    """Verify admin API key"""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    api_key = credentials.credentials

    if not settings.admin_api_key or api_key != settings.admin_api_key:
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required"
        )

    return api_key


async def get_pagination(
        page: int = 1,
        per_page: int = 50
) -> Dict[str, int]:
    """Parse pagination parameters"""
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 50
    if per_page > 500:
        per_page = 500

    return {
        "page": page,
        "per_page": per_page,
        "offset": (page - 1) * per_page,
        "limit": per_page
    }