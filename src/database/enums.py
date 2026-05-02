import enum

class TaskType(enum.Enum):
    """Типы задач, решаемых ботом"""
    REVIEW = "review"
    COMPLIANCE = "compliance"

class TaskStatus(enum.Enum):
    """Статус задачи"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"