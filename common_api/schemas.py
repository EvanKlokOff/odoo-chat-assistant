from pydantic import BaseModel, Field, validator, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


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


# ========== Analysis Schemas ==========
class AnalysisType(str, Enum):
    REVIEW = "review"
    COMPLIANCE = "compliance"


class ReviewRequest(BaseModel):
    chat_id: str
    target_datetime: datetime = Field(..., description="Target date and time for analysis")
    lookback_minutes: int = Field(60, ge=1, le=1440, description="Minutes before target")
    lookforward_minutes: int = Field(60, ge=1, le=1440, description="Minutes after target")


class ComplianceRequest(BaseModel):
    chat_id: str
    target_datetime: datetime
    description: str = Field(..., min_length=5, max_length=2000)
    lookback_minutes: int = Field(30, ge=1, le=480)
    lookforward_minutes: int = Field(30, ge=1, le=480)


class ReviewResponse(BaseModel):
    chat_id: str
    target_datetime: datetime
    time_window: Dict[str, str]
    summary: str
    key_points: List[str]
    sentiment: str
    participant_count: int
    message_count: int
    message_count_before: int
    message_count_after: int


class ComplianceResponse(BaseModel):
    chat_id: str
    target_datetime: datetime
    compliant: bool
    confidence: float
    explanation: str
    violations: List[str]
    suggestions: List[str]


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: int
    result: Optional[Dict[str, Any]] = None
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