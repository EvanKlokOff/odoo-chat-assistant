from pydantic import BaseModel, Field, validator, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

from common_api.enums import PeriodType


# ========== Base Responses ==========
class BaseResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None


# ========== User Schemas ==========
class UserResponse(BaseModel):
    user_id: str
    user_name: Optional[str] = None
    telegram_id: Optional[str] = None

    class Config:
        from_attributes = True


class UserDetailResponse(UserResponse):
    chat_count: int = 0
    message_count: int = 0
    last_active: Optional[datetime] = None


# ========== Chat Schemas ==========
class ChatResponse(BaseModel):
    chat_id: str
    title: str
    selected: bool = False
    last_used: Optional[datetime] = None
    message_count: int = 0

    class Config:
        from_attributes = True


class ChatDetailResponse(ChatResponse):
    user_count: int = 0
    first_message_date: Optional[datetime] = None
    last_message_date: Optional[datetime] = None
    participants: List[UserResponse] = []


# ========== Message Schemas ==========
class MessageResponse(BaseModel):
    id: int
    message_id: str
    sender_id: str
    sender_name: Optional[str] = None
    content: str
    timestamp: datetime
    reply_to_message_id: Optional[str] = None

    class Config:
        from_attributes = True


class MessageWithChunksResponse(MessageResponse):
    chunks: Optional[List[str]] = None


# ========== Request Schemas ==========
class DateRangeRequest(BaseModel):
    chat_id: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    @field_validator('end_date')
    def validate_date_range(cls, v, values):
        if v and values.get('start_date') and v < values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v


class PaginationRequest(BaseModel):
    page: int = Field(1, ge=1)
    per_page: int = Field(50, ge=1, le=500)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    per_page: int
    total_pages: int


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: int
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


# ========== Sync Schemas ==========
class SyncStatusResponse(BaseModel):
    last_sync: Optional[datetime] = None
    users_count: int
    chats_count: int
    messages_count: int
    pending_tasks: int


class IncrementalSyncRequest(BaseModel):
    last_sync: datetime
    limit: int = Field(100, ge=1, le=5000)


class IncrementalSyncResponse(BaseModel):
    last_sync: datetime
    has_more: bool
    data: Dict[str, List[Dict[str, Any]]]


# ========== Period Analysis Schemas ==========

# ========== Period Analysis Schemas ==========

class ReviewByPeriodRequest(BaseModel):
    user_id: int = Field(..., description="Telegram user ID who requested the analysis")
    chat_id: str = Field(..., description="Chat ID to analyze")
    start_date: datetime = Field(..., description="Start date for analysis")
    end_date: datetime = Field(..., description="End date for analysis")

    @field_validator('user_id')
    def validate_user_id(cls, v):
        if v <= 0:
            raise ValueError('user_id must be a positive integer')
        return v

    @field_validator('end_date')
    def validate_dates(cls, v, info):
        if 'start_date' in info.data and v <= info.data['start_date']:
            raise ValueError('end_date must be after start_date')
        return v


class ComplianceByPeriodRequest(BaseModel):
    user_id: int = Field(..., description="Telegram user ID who requested the analysis")
    chat_id: str = Field(..., description="Chat ID to analyze")
    instruction: str = Field(..., min_length=10, max_length=5000, description="Instruction to check compliance against")
    start_date: datetime = Field(..., description="Start date for analysis")
    end_date: datetime = Field(..., description="End date for analysis")

    @field_validator('user_id')
    def validate_user_id(cls, v):
        if v <= 0:
            raise ValueError('user_id must be a positive integer')
        return v

    @field_validator('end_date')
    def validate_dates(cls, v, info):
        if 'start_date' in info.data and v <= info.data['start_date']:
            raise ValueError('end_date must be after start_date')
        return v


class PeriodInfo(BaseModel):
    task_id: str
    status: str
    user_id: int
    chat_id: str
    start_date: datetime
    end_date: datetime
    created_at: datetime
    check_status_url: str


class ReviewByPeriodResponse(BaseModel):
    success: bool = True
    message: str
    task_id: str
    period_info: PeriodInfo


class ComplianceByPeriodResponse(BaseModel):
    success: bool = True
    message: str
    task_id: str
    period_info: PeriodInfo


class ReviewResultResponse(BaseModel):
    """Response when task is completed with review result"""
    task_id: str
    status: str = "completed"
    result: Dict[str, Any]
    completed_at: datetime


class ComplianceResultResponse(BaseModel):
    """Response when task is completed with compliance result"""
    task_id: str
    status: str = "completed"
    compliant: bool
    confidence: float
    explanation: str
    violations: List[str]
    suggestions: List[str]
    completed_at: datetime
