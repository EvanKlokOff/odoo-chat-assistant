import logging
from typing import Any
from src.database.enums import TaskType
logger = logging.getLogger(__name__)

def transform_result_for_odoo(result_str: str, task_type: str) -> dict[str, Any]:
    """
    Преобразует строковый результат LLM в структурированный словарь для Odoo
    """
    if not result_str:
        logger.warning("result_str is empty, returning empty dict")
        return {}

    if task_type == TaskType.REVIEW:
        logger.info("Transforming as REVIEW")
        return transform_review_result(result_str)
    else:
        logger.info(f"Transforming as COMPLIANCE (task_type={task_type})")
        return transform_compliance_result(result_str)


def transform_review_result(text: str) -> dict:
    """Преобразует результат review анализа - только краткая выжимка"""

    # Извлекаем основную суть (первые 2-3 предложения или специальную секцию)

    return {
        "summary": text,
        "sentiment": "neutral",  # Можно не определять, либо определить по желанию
        "key_points": [],
        "participant_count": 0,
        "message_count": 0,
        "communication_style": "",
        "recommendations": []
    }


def transform_compliance_result(text: str) -> dict:
    """Преобразует результат compliance проверки - комментарий о соответствии"""

    # Определяем соответствует или нет
    is_compliant = "соответствует" in text and "не соответствует" not in text

    return {
        "compliant": is_compliant,
        "confidence": 0.8,
        "explanation": text,
        "violations": [],
        "suggestions": [],
        "severe_violations": 0,
        "minor_violations": 0
    }
