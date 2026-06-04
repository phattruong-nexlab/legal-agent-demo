from dataclasses import dataclass
from enum import Enum
from typing import Optional


class TaskStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class DocumentTask:
    """Represents the status and result of a document conversion task."""

    task_id: str
    filename: str
    status: TaskStatus = TaskStatus.PENDING
    markdown_content: Optional[str] = None
    error_message: Optional[str] = None
    processed_time_sec: Optional[float] = None
