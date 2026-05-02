# src/tasks/monitor_tasks.py
import logging
from src.database import crud
from src.tasks.celery_app import celery_app
from src.tasks.utils import async_celery_task, async_celery_task_bind

logger = logging.getLogger(__name__)


@celery_app.task(name="monitor_analysis_tasks")
@async_celery_task()
async def monitor_analysis_tasks():
    """Периодическая задача для отправки уведомлений"""
    logger.info("🔍 MONITOR TASK STARTED")  # Добавить
    logger.debug("🔄 Monitor task running")

    try:
        unnotified_tasks = await crud.get_unnotified_finished_tasks()
        logger.info(f"📊 Found {len(unnotified_tasks) if unnotified_tasks else 0} unnotified tasks")  # Добавить
        if not unnotified_tasks:
            return {"status": "no_tasks"}

        logger.info(f"Found {len(unnotified_tasks)} unnotified tasks")

        for task in unnotified_tasks:
            logger.info(f"📝 Processing task {task.task_id}, status={task.status}")
            # Пропускаем, если user_id похож на бота (начинается с 5 или 7 для Telegram ботов)
            if str(task.user_id).startswith(('5', '6', '7')):
                logger.warning(f"Skipping bot user {task.user_id} (bots can't receive messages)")
                await crud.mark_task_as_notified(task.task_id)
                continue

            result_text = task.result if task.result else "Анализ завершен"
            if len(result_text) > 3500:
                result_text = result_text[:3500] + "\n\n...(результат сокращен)"

            task_type = task.task_type.value if hasattr(task.task_type, 'value') else task.task_type

            if task_type == "review":
                header = "📊 *Ревью чата завершено!*"
            else:
                header = "✅ *Проверка соответствия завершена!*"

            text = (
                f"{header}\n\n"
                f"📝 *Результат:*\n{result_text}\n\n"
                f"🆔 ID задачи: `{task.task_id[:8]}...`"
            )

            # Отправляем через отдельную задачу
            send_notification.delay(
                user_id=task.user_id,
                text=text,
                task_id=task.task_id

            )

        return {"status": "success", "processed": len(unnotified_tasks)}

    except Exception as e:
        logger.error(f"Error in monitor_analysis_tasks: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


@celery_app.task(
    name="send_notification",
    bind=True,
    max_retries=2,  # Уменьшил количество ретраев
    default_retry_delay=5
)
@async_celery_task_bind()
async def send_notification(self, user_id: int, text: str, task_id: str):
    """Отправка уведомления пользователю"""
    try:
        from src.interfaces.telegram.bot import bot

        await bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode="Markdown"
        )

        await crud.mark_task_as_notified(task_id)
        logger.info(f"✅ Notified user {user_id} about task {task_id}")

    except Exception as e:
        error_msg = str(e)
        if "Forbidden" in error_msg or "bots can't send messages" in error_msg:
            # Если бот не может отправить сообщение, помечаем как уведомленное, чтобы не спамить
            logger.warning(f"Cannot notify user {user_id} (likely a bot): {error_msg}")
            await crud.mark_task_as_notified(task_id)
            return {"status": "skipped", "reason": "user_is_bot"}

        if self.request.retries < self.max_retries:
            logger.info(f"Retrying notification for task {task_id}, attempt {self.request.retries + 1}")
            raise self.retry(exc=e, countdown=5)

        logger.error(f"Failed to notify user {user_id} after {self.max_retries} retries: {e}")
        # Помечаем как уведомленное, чтобы не пытаться снова
        await crud.mark_task_as_notified(task_id)
        return {"status": "error", "error": error_msg}
