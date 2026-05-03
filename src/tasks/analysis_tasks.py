import logging

from src.analyzers.graph import create_analysis_graph
from src.analyzers.state import AgentState
from src.database import crud
from src.tasks.utils import async_celery_task_bind
from src.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="run_compliance_analysis",
    queue="analysis",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    time_limit=300,
    soft_time_limit=280
)
@async_celery_task_bind()
async def run_compliance_analysis(
        self,
        user_id: int,
        chat_id: str,
        instruction: str,
        date_start: str | None,
        date_end: str | None,
        task_id: str
) -> dict:
    """Асинхронная проверка соответствия инструкции"""
    try:
        logger.info(f"Starting compliance analysis for user {user_id}, chat {chat_id}")

        await crud.update_analysis_task(
            task_id=task_id,
            status="running",
            progress=10,
            message="Загрузка сообщений..."
        )

        state: AgentState = {
            "query_type": "compliance",
            "chat_id": chat_id,
            "messages": [],
            "date_start": date_start,
            "date_end": date_end,
            "instruction": instruction,
            "chat_messages": [],
            "analysis_result": None,
            "deviations": None,
            "current_step": "start",
            "error": None
        }

        await crud.update_analysis_task(
            task_id=task_id,
            progress=30,
            message="Проверка соответствия..."
        )

        graph = create_analysis_graph()
        final_state = await graph.ainvoke(state)

        await crud.update_analysis_task(
            task_id=task_id,
            progress=90,
            message="Формирование результата..."
        )

        result = final_state.get("analysis_result", "Не удалось выполнить анализ.")

        await crud.update_analysis_task(
            task_id=task_id,
            status="completed",
            progress=100,
            result=result,
            message="Проверка завершена",
            is_notified=False
        )

        return {
            "status": "success",
            "task_id": task_id,
            "result": result,
            "user_id": user_id,
            "chat_id": chat_id
        }

    except Exception as e:
        logger.error(f"Compliance analysis failed: {e}", exc_info=True)

        await crud.update_analysis_task(
            task_id=task_id,
            status="failed",
            error=str(e),
            message="Ошибка при проверке",
            is_notified=False
        )

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)

        return {
            "status": "error",
            "task_id": task_id,
            "error": str(e)
        }


@celery_app.task(
    name="run_review_analysis",
    queue="analysis",  # Новая очередь для анализа
    bind=True,
    time_limit=300,  # 5 минут на анализ
    soft_time_limit=280
)
@async_celery_task_bind(max_retries=3, default_retry_delay=60)
async def run_review_analysis(
        self,
        user_id: int,
        chat_id: str,
        date_start: str | None,
        date_end: str | None,
        task_id: str
) -> dict:
    """
    Асинхронный анализ переписки

    Args:
        user_id: ID пользователя в Telegram
        chat_id: ID чата для анализа
        date_start: Начало периода (ISO format)
        date_end: Конец периода (ISO format)
        task_id: Уникальный ID задачи для отслеживания
    """
    try:
        logger.info(f"Starting review analysis for user {user_id}, chat {chat_id}")

        # Обновляем статус задачи
        await crud.update_analysis_task(
            task_id=task_id,
            status="running",
            progress=10,
            message="Загрузка сообщений..."
        )

        # Подготавливаем состояние
        state: AgentState = {
            "query_type": "review",
            "chat_id": chat_id,
            "messages": [],
            "date_start": date_start,
            "date_end": date_end,
            "instruction": None,
            "chat_messages": [],
            "analysis_result": None,
            "deviations": None,
            "current_step": "start",
            "error": None
        }

        await crud.update_analysis_task(
            task_id=task_id,
            progress=30,
            message="Анализ сообщений..."
        )

        # Запускаем граф анализа
        graph = create_analysis_graph()
        final_state = await graph.ainvoke(state)

        await crud.update_analysis_task(
            task_id=task_id,
            progress=90,
            message="Формирование результата..."
        )

        result = final_state.get("analysis_result", "Не удалось выполнить анализ.")

        # Сохраняем результат
        await crud.update_analysis_task(
            task_id=task_id,
            status="completed",
            progress=100,
            result=result,
            message="Анализ завершен",
            is_notified=False
        )

        logger.info(f"Review analysis completed for task {task_id}")

        return {
            "status": "success",
            "task_id": task_id,
            "result": result,
            "user_id": user_id,
            "chat_id": chat_id
        }

    except Exception as e:
        logger.error(f"Review analysis failed: {e}", exc_info=True)

        # Обновляем статус ошибки
        await crud.update_analysis_task(
            task_id=task_id,
            status="failed",
            error=str(e),
            message="Ошибка при анализе",
            is_notified=False
        )

        # Retry если нужно
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)

        return {
            "status": "error",
            "task_id": task_id,
            "error": str(e)
        }
