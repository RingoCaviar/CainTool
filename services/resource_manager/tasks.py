from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Iterator, Optional


class TaskState(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class TaskUpdate:
    stage: str
    current_item: str = ""
    completed: int = 0
    total: int = 0
    stage_progress: float = -1.0
    bytes_completed: int = 0
    bytes_total: int = 0
    message: str = ""


@dataclass
class ResourceTask:
    name: str
    work: Iterable[TaskUpdate]
    state: TaskState = TaskState.PENDING
    stage: str = "准备"
    progress: float = -1.0
    stage_progress: float = -1.0
    current_item: str = ""
    completed: int = 0
    total: int = 0
    bytes_completed: int = 0
    bytes_total: int = 0
    result: Any = None
    error: str = ""
    log: list[str] = field(default_factory=list)
    started_at: float = 0.0
    finished_at: float = 0.0
    _iterator: Optional[Iterator[TaskUpdate]] = field(default=None, init=False, repr=False)
    _cancel_requested: bool = field(default=False, init=False, repr=False)

    def start(self) -> None:
        if self.state != TaskState.PENDING:
            return
        self._iterator = iter(self.work)
        self.started_at = time.monotonic()
        self.state = TaskState.RUNNING
        self.log.append(f"开始：{self.name}")

    def cancel(self) -> None:
        if self.state in {TaskState.PENDING, TaskState.RUNNING}:
            self._cancel_requested = True
            self.state = TaskState.CANCELLING
            self.log.append("用户请求取消，正在安全停止…")

    def tick(self, budget_seconds: float = 0.02) -> bool:
        if self.state == TaskState.PENDING:
            self.start()
        if self._cancel_requested:
            self.state = TaskState.CANCELLED
            self.finished_at = time.monotonic()
            self.log.append("任务已取消")
            return False
        if self.state != TaskState.RUNNING or self._iterator is None:
            return False

        deadline = time.monotonic() + max(0.001, budget_seconds)
        try:
            while time.monotonic() < deadline:
                self._apply(next(self._iterator))
        except StopIteration as stop:
            self.result = stop.value
            self.progress = 1.0
            self.stage_progress = 1.0
            self.state = TaskState.COMPLETED
            self.finished_at = time.monotonic()
            self.log.append(f"完成：{self.name}")
            return False
        except Exception as exc:
            self.error = str(exc)
            self.state = TaskState.FAILED
            self.finished_at = time.monotonic()
            self.log.append(f"失败：{exc}")
            return False
        return True

    def _apply(self, update: TaskUpdate) -> None:
        self.stage = update.stage
        self.current_item = update.current_item
        self.completed = update.completed
        self.total = update.total
        self.stage_progress = update.stage_progress
        self.bytes_completed = update.bytes_completed
        self.bytes_total = update.bytes_total
        if update.total > 0:
            self.progress = min(0.999, update.completed / update.total)
        if update.message:
            self.log.append(update.message)

    @property
    def elapsed(self) -> float:
        if not self.started_at:
            return 0.0
        return (self.finished_at or time.monotonic()) - self.started_at

    @property
    def bytes_per_second(self) -> float:
        return self.bytes_completed / self.elapsed if self.elapsed > 0 else 0.0

    @property
    def eta(self) -> float | None:
        speed = self.bytes_per_second
        if speed > 0 and self.bytes_total > self.bytes_completed:
            return (self.bytes_total - self.bytes_completed) / speed
        if self.total > 0 and self.completed > 0:
            return self.elapsed * (self.total - self.completed) / self.completed
        return None

    @property
    def is_finished(self) -> bool:
        return self.state in {TaskState.CANCELLED, TaskState.COMPLETED, TaskState.FAILED}
