from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

JobType = Literal["scan", "llm", "upload", "image_transform"]
JobStatus = Literal["pending", "running", "done", "cancelled", "error"]


@dataclass
class Job:
    id: str
    type: JobType
    status: JobStatus = "pending"
    progress: int = 0
    total: int = 0
    current: str = ""
    message: str = ""
    result: dict[str, Any] | None = None
    error: str | None = None
    _cancel: threading.Event = field(default_factory=threading.Event, repr=False)

    def cancel(self) -> None:
        self._cancel.set()
        if self.status == "running":
            self.status = "cancelled"

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "status": self.status,
            "progress": self.progress,
            "total": self.total,
            "current": self.current,
            "message": self.message,
            "cancelled": self.cancelled,
            "error": self.error,
            "result": self.result,
        }


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._llm_cancel = threading.Event()
        self._active_llm_job: str | None = None

    def create(self, job_type: JobType) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], type=job_type)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> bool:
        job = self.get(job_id)
        if not job:
            return False
        job.cancel()
        return True

    def cancel_all(self) -> int:
        n = 0
        with self._lock:
            for job in self._jobs.values():
                if job.status in ("pending", "running"):
                    job.cancel()
                    n += 1
        self.cancel_llm()
        return n

    def set_llm_job(self, job_id: str | None) -> None:
        """Track active LLM job; clear cancel only when a new job starts."""
        self._active_llm_job = job_id
        if job_id:
            self._llm_cancel.clear()

    def cancel_llm(self) -> None:
        self._llm_cancel.set()
        if self._active_llm_job:
            job = self.get(self._active_llm_job)
            if job:
                job.cancel()

    def reset_llm_cancel(self) -> None:
        self._llm_cancel.clear()

    @property
    def llm_cancelled(self) -> bool:
        return self._llm_cancel.is_set()

    def clear_finished(self) -> None:
        with self._lock:
            self._jobs = {
                k: v
                for k, v in self._jobs.items()
                if v.status in ("pending", "running")
            }


JOBS = JobRegistry()
