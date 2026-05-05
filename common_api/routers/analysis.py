from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta
import uuid
import logging

from common_api.utils import get_db, verify_api_key
from common_api.schemas import (
    ReviewRequest, ReviewResponse,
    ComplianceRequest, ComplianceResponse,
    TaskStatusResponse
)
from src.database.crud import (
    get_chat_messages_by_chat_id,
    create_analysis_task,
    update_analysis_task,
    get_analysis_task
)
from src.database import enums

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/review", response_model=ReviewResponse)
async def review_chat(
        request: ReviewRequest,
        db: AsyncSession = Depends(get_db),
        api_key: str = Depends(verify_api_key),
):
    """
    Get a review of chat conversation at a specific moment.
    """
    try:
        time_start = request.target_datetime - timedelta(minutes=request.lookback_minutes)
        time_end = request.target_datetime + timedelta(minutes=request.lookforward_minutes)

        messages = await get_chat_messages_by_chat_id(
            chat_id=request.chat_id,
            date_start=time_start,
            date_end=time_end
        )

        if not messages:
            raise HTTPException(
                status_code=404,
                detail=f"No messages found in time window for chat {request.chat_id}"
            )

        # Analyze participants
        participants = set()
        messages_before = 0
        messages_after = 0

        for msg in messages:
            participants.add(msg.sender_name or f"User_{msg.sender_id}")
            if msg.timestamp <= request.target_datetime:
                messages_before += 1
            else:
                messages_after += 1

        # Simple keyword extraction
        all_text = " ".join([msg.content for msg in messages])
        keywords = extract_keywords(all_text)

        # Simple sentiment analysis
        sentiment = analyze_sentiment(all_text)

        # Generate summary
        summary = generate_review_summary(messages, request.target_datetime, participants)

        return ReviewResponse(
            chat_id=request.chat_id,
            target_datetime=request.target_datetime,
            time_window={
                "start": time_start.isoformat(),
                "end": time_end.isoformat()
            },
            summary=summary,
            key_points=keywords[:5],
            sentiment=sentiment,
            participant_count=len(participants),
            message_count=len(messages),
            message_count_before=messages_before,
            message_count_after=messages_after
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Review failed for chat {request.chat_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/review/async", response_model=TaskStatusResponse)
async def review_chat_async(
        request: ReviewRequest,
        background_tasks: BackgroundTasks,
        api_key: str = Depends(verify_api_key),
):
    """
    Async review - creates a task and returns task_id.
    Use GET /analysis/task/{task_id} to check status.
    """
    task_id = str(uuid.uuid4())

    # Create task in database
    task = await create_analysis_task(
        user_id=0,  # Will be set from API key
        chat_id=request.chat_id,
        task_type=enums.TaskType.REVIEW.value,
        task_id=task_id
    )

    # Add to background tasks
    background_tasks.add_task(
        process_review_task,
        task_id,
        request
    )

    return TaskStatusResponse(
        task_id=task_id,
        status=task.status,
        progress=task.progress,
        created_at=task.created_at,
        completed_at=task.completed_at
    )


@router.post("/compliance", response_model=ComplianceResponse)
async def check_compliance(
        request: ComplianceRequest,
        db: AsyncSession = Depends(get_db),
        api_key: str = Depends(verify_api_key),
):
    """
    Check if conversation complies with given description.
    """
    try:
        time_start = request.target_datetime - timedelta(minutes=request.lookback_minutes)
        time_end = request.target_datetime + timedelta(minutes=request.lookforward_minutes)

        messages = await get_chat_messages_by_chat_id(
            chat_id=request.chat_id,
            date_start=time_start,
            date_end=time_end
        )

        if not messages:
            raise HTTPException(
                status_code=404,
                detail=f"No messages found in time window for chat {request.chat_id}"
            )

        # Check compliance
        chat_text = " ".join([msg.content.lower() for msg in messages])
        description_lower = request.description.lower()

        # Simple keyword matching
        description_keywords = set(description_lower.split())
        chat_keywords = set(chat_text.split())

        # Calculate similarity
        common = description_keywords & chat_keywords
        similarity = len(common) / max(len(description_keywords), 1)

        compliant = similarity >= 0.3

        # Find violations
        violations = []
        for keyword in description_keywords:
            if keyword not in chat_keywords and len(keyword) > 3:
                violations.append(f"Keyword '{keyword}' not found in conversation")

        # Generate suggestions
        suggestions = []
        if not compliant:
            suggestions.append("Consider including the mentioned topics in the conversation")

        return ComplianceResponse(
            chat_id=request.chat_id,
            target_datetime=request.target_datetime,
            compliant=compliant,
            confidence=similarity,
            explanation=f"Conversation similarity with description: {similarity:.1%}",
            violations=violations[:5],
            suggestions=suggestions
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Compliance check failed for chat {request.chat_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compliance/async", response_model=TaskStatusResponse)
async def check_compliance_async(
        request: ComplianceRequest,
        background_tasks: BackgroundTasks,
        api_key: str = Depends(verify_api_key),
):
    """Async compliance check"""
    task_id = str(uuid.uuid4())

    task = await create_analysis_task(
        user_id=0,
        chat_id=request.chat_id,
        task_type=enums.TaskType.COMPLIANCE.value,
        task_id=task_id
    )

    background_tasks.add_task(
        process_compliance_task,
        task_id,
        request
    )

    return TaskStatusResponse(
        task_id=task_id,
        status=task.status,
        progress=task.progress,
        created_at=task.created_at,
        completed_at=task.completed_at
    )


@router.get("/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
        task_id: str,
        api_key: str = Depends(verify_api_key),
):
    """Get analysis task status and result"""
    task = await get_analysis_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return TaskStatusResponse(
        task_id=task.task_id,
        status=task.status,
        progress=task.progress,
        result=task.result,
        error=task.error,
        created_at=task.created_at,
        completed_at=task.completed_at
    )


# ========== Helper Functions ==========

def extract_keywords(text: str, top_n: int = 10) -> list:
    """Extract keywords from text"""
    import re
    from collections import Counter

    words = re.findall(r'\b\w+\b', text.lower())
    stop_words = {'и', 'в', 'на', 'с', 'по', 'к', 'у', 'за', 'из', 'о', 'для',
                  'как', 'что', 'это', 'был', 'не', 'да', 'нет', 'или', 'но',
                  'а', 'же', 'ли', 'бы', 'еще', 'уже', 'вот', 'все', 'так'}

    filtered = [w for w in words if w not in stop_words and len(w) > 3]
    return [word for word, count in Counter(filtered).most_common(top_n)]


def analyze_sentiment(text: str) -> str:
    """Simple sentiment analysis"""
    positive = {'хорошо', 'отлично', 'спасибо', 'класс', 'прекрасно', 'рад', 'здорово'}
    negative = {'плохо', 'ужасно', 'проблема', 'ошибка', 'негатив', 'жаль', 'обидно'}

    text_lower = text.lower()
    pos_count = sum(1 for w in positive if w in text_lower)
    neg_count = sum(1 for w in negative if w in text_lower)

    if pos_count > neg_count:
        return "positive"
    elif neg_count > pos_count:
        return "negative"
    return "neutral"


def generate_review_summary(messages, target_time, participants) -> str:
    """Generate a summary of the conversation"""
    participant_list = list(participants)[:5]
    participant_text = ", ".join(participant_list)

    return (
        f"At {target_time.strftime('%Y-%m-%d %H:%M')}, the chat had "
        f"{len(participants)} participant(s): {participant_text}. "
        f"Total messages in analysis window: {len(messages)}."
    )


async def process_review_task(task_id: str, request: ReviewRequest):
    """Background task for review processing"""
    try:
        await update_analysis_task(task_id, status="running", progress=10)

        time_start = request.target_datetime - timedelta(minutes=request.lookback_minutes)
        time_end = request.target_datetime + timedelta(minutes=request.lookforward_minutes)

        messages = await get_chat_messages_by_chat_id(
            chat_id=request.chat_id,
            date_start=time_start,
            date_end=time_end
        )

        await update_analysis_task(task_id, progress=50)

        # Analyze
        participants = set()
        all_text = []

        for msg in messages:
            participants.add(msg.sender_name or f"User_{msg.sender_id}")
            all_text.append(msg.content)

        sentiment = analyze_sentiment(" ".join(all_text))
        keywords = extract_keywords(" ".join(all_text))

        result = {
            "chat_id": request.chat_id,
            "target_datetime": request.target_datetime.isoformat(),
            "summary": generate_review_summary(messages, request.target_datetime, participants),
            "key_points": keywords[:5],
            "sentiment": sentiment,
            "participant_count": len(participants),
            "message_count": len(messages)
        }

        await update_analysis_task(task_id, status="completed", progress=100, result=result)

    except Exception as e:
        logger.error(f"Review task {task_id} failed: {e}")
        await update_analysis_task(task_id, status="failed", error=str(e))


async def process_compliance_task(task_id: str, request: ComplianceRequest):
    """Background task for compliance processing"""
    try:
        await update_analysis_task(task_id, status="running", progress=10)

        time_start = request.target_datetime - timedelta(minutes=request.lookback_minutes)
        time_end = request.target_datetime + timedelta(minutes=request.lookforward_minutes)

        messages = await get_chat_messages_by_chat_id(
            chat_id=request.chat_id,
            date_start=time_start,
            date_end=time_end
        )

        await update_analysis_task(task_id, progress=50)

        # Check compliance
        chat_text = " ".join([msg.content.lower() for msg in messages])
        description_keywords = set(request.description.lower().split())
        chat_keywords = set(chat_text.split())

        common = description_keywords & chat_keywords
        similarity = len(common) / max(len(description_keywords), 1)
        compliant = similarity >= 0.3

        # Find missing keywords
        missing = [kw for kw in description_keywords if kw not in chat_keywords and len(kw) > 3]

        result = {
            "chat_id": request.chat_id,
            "target_datetime": request.target_datetime.isoformat(),
            "compliant": compliant,
            "confidence": similarity,
            "explanation": f"Similarity: {similarity:.1%}. {len(common)} out of {len(description_keywords)} keywords found.",
            "violations": missing[:10],
            "suggestions": [f"Include '{kw}' in conversation" for kw in missing[:3]]
        }

        await update_analysis_task(task_id, status="completed", progress=100, result=result)

    except Exception as e:
        logger.error(f"Compliance task {task_id} failed: {e}")
        await update_analysis_task(task_id, status="failed", error=str(e))