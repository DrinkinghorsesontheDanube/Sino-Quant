"""Minimal in-process background job registry for web-triggered backtests.

One job at a time (a module lock rejects concurrent submissions); each job
runs on a daemon thread and records progress so the frontend can poll.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Callable

_lock = threading.Lock()
_jobs: dict[str, "Job"] = {}


@dataclass
class Job:
    job_id: str
    kind: str
    status: str = "running"          # running | succeeded | failed
    error: str | None = None
    result: dict | None = None
    _done: threading.Event = field(default_factory=threading.Event, repr=False)

    def public(self) -> dict:
        return {
            "job_id": self.job_id,
            "kind": self.kind,
            "status": self.status,
            "error": self.error,
            "result": self.result,
        }


def submit(kind: str, work: Callable[[], dict]) -> Job:
    """Register a job and run ``work`` on a daemon thread immediately."""
    job = Job(job_id=uuid.uuid4().hex[:12], kind=kind)
    with _lock:
        running = [j for j in _jobs.values() if j.status == "running"]
        if running:
            raise RuntimeError("another backtest is already running; try again shortly")
        _jobs[job.job_id] = job

    def _execute() -> None:
        try:
            job.result = work()
            job.status = "succeeded"
        except Exception as exc:  # surface the failure to the poller
            job.status = "failed"
            job.error = f"{type(exc).__name__}: {exc}"
        finally:
            job._done.set()

    threading.Thread(target=_execute, name=f"job-{job.job_id}", daemon=True).start()
    return job


def get(job_id: str) -> Job | None:
    return _jobs.get(job_id)
