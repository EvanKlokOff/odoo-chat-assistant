# src/tasks/monitor_tasks.py
import logging

import asyncio

from src.config import settings
from src.interfaces.telegram.utils import clean_llm_response, split_long_message
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

    # Логируем DATABASE_URL для отладки
    logger.info(f"📊 DATABASE_URL in monitor: {settings.database_url}")

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
            # if len(result_text) > 3500:
            #     result_text = result_text[:3500] + "\n\n...(результат сокращен)"

            task_type = task.task_type.value if hasattr(task.task_type, 'value') else task.task_type

            message_parts, parse_mode = clean_llm_response(
                text=result_text,
                task_id=task.task_id,
                task_type=task_type
            )

            send_notification.delay(
                user_id=task.user_id,
                message_parts=message_parts,
                parse_mode=parse_mode,
                task_id=task.task_id
            )

        return {"status": "success", "processed": len(unnotified_tasks)}

    except Exception as e:
        logger.error(f"Error in monitor_analysis_tasks: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


@celery_app.task(
    name="send_notification",
    bind=True,
    max_retries=3,  # Уменьшил количество ретраев
    default_retry_delay=5
)
@async_celery_task_bind()
async def send_notification(self, user_id: int, message_parts: list[str], parse_mode:str,
                            #text: str,
                            task_id: str):
    """Отправка уведомления пользователю"""
    try:
        from src.interfaces.telegram.bot import bot

        for i, part in enumerate(message_parts):
            try:
                if parse_mode:
                    await bot.send_message(
                        chat_id=user_id,
                        text=part,
                        parse_mode=parse_mode
                    )
                else:
                    await bot.send_message(
                        chat_id=user_id,
                        text=part
                    )
                if i < len(message_parts) - 1:
                    await asyncio.sleep(0.5)
            except Exception as part_error:
                logger.error(f"Error sending part {i + 1}: {part_error}")
                # Если часть не отправилась с Markdown, пробуем без форматирования
                if parse_mode and "can't parse entities" in str(part_error):
                    logger.warning(f"Part {i + 1} failed with Markdown, retrying as plain text")
                    await bot.send_message(
                        chat_id=user_id,
                        text=part  # Отправляем как есть, без парсинга
                    )
                else:
                    raise
            await crud.mark_task_as_notified(task_id)
            logger.info(f"✅ Notified user {user_id} about task {task_id} ({len(message_parts)} parts)")

            return {"status": "success", "parts_sent": len(message_parts)}

        logger.info(f"✅ Notified user {user_id} about task {task_id}")

    except Exception as e:
        error_msg = str(e)
        if "Forbidden" in error_msg or "bots can't send messages" in error_msg:
            # Если бот не может отправить сообщение, помечаем как уведомленное, чтобы не спамить
            logger.warning(f"Cannot notify user {user_id} (likely a bot): {error_msg}")
            await crud.mark_task_as_notified(task_id)
            return {"status": "skipped", "reason": "user_is_bot"}

        if "can't parse entities" in error_msg:
            logger.warning(f"Parse error, retrying as plain text")
            try:
                from src.interfaces.telegram.bot import bot
                # Объединяем все части в один текст для plain text
                plain_text = "\n\n".join(message_parts)
                # Разбиваем заново без Markdown
                plain_parts = split_long_message(plain_text)

                for part in plain_parts:
                    await bot.send_message(chat_id=user_id, text=part)

                await crud.mark_task_as_notified(task_id)
                return {"status": "success", "fallback": "plain_text"}
            except Exception as fallback_error:
                logger.error(f"Plain text fallback failed: {fallback_error}")

            # Ретраи
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying notification for task {task_id}, attempt {self.request.retries + 1}")
            raise self.retry(exc=e, countdown=5 * (self.request.retries + 1))


        logger.error(f"Failed to notify user {user_id} after {self.max_retries} retries: {e}")
        # Помечаем как уведомленное, чтобы не пытаться снова
        await crud.mark_task_as_notified(task_id)
        return {"status": "error", "error": error_msg}
