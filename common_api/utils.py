from datetime import datetime, timedelta

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import HTTPException, Depends, Security
from common_api.config import settings
from typing import Optional, Dict

from common_api.enums import PeriodType
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


def get_date_range_from_period(
        period_type: PeriodType,
        start_datetime: Optional[datetime] = None,
        end_datetime: Optional[datetime] = None
) -> tuple:
    """Получает start_date и end_date на основе типа периода"""
    now = datetime.now()

    if period_type == PeriodType.HOUR:
        start_date = now - timedelta(hours=1)
        end_date = now
    elif period_type == PeriodType.DAY:
        start_date = now - timedelta(days=1)
        end_date = now
    elif period_type == PeriodType.WEEK:
        start_date = now - timedelta(days=7)
        end_date = now
    elif period_type == PeriodType.MONTH:
        start_date = now - timedelta(days=30)
        end_date = now
    elif period_type == PeriodType.CUSTOM:
        if not start_datetime or not end_datetime:
            raise ValueError("For CUSTOM period, start_datetime and end_datetime are required")
        start_date = start_datetime
        end_date = end_datetime
    else:
        start_date = now - timedelta(days=1)
        end_date = now

    return start_date, end_date
