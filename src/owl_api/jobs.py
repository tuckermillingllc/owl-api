"""Simple in-process job store.

Solving a big Monte Carlo case can take tens of seconds to minutes. The iOS
client submits a job, polls for completion, then fetches the result. Keep this
lightweight (in-memory dict) — if we ever need persistence we can swap for
SQLite or Redis without changing the API shape.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Awaitable, Callable

from .models import JobStatus, OptimizeResult


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobStatus] = {}
        self._lock = asyncio.Lock()

    async def create(self) -> str:
        job_id = uuid.uuid4().hex[:12]
        async with self._lock:
            self._jobs[job_id] = JobStatus(job_id=job_id, state="queued")
        return job_id

    async def get(self, job_id: str) -> JobStatus | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def run(
        self,
        job_id: str,
        runner: Callable[[], Awaitable[OptimizeResult]],
    ) -> None:
        """Background task — updates JobStatus as it progresses."""
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.state = "running"
            job.message = "solving"

        try:
            result = await runner()
            async with self._lock:
                job = self._jobs[job_id]
                job.state = "done"
                job.progress = 1.0
                job.result = result
        except Exception as e:  # noqa: BLE001
            async with self._lock:
                job = self._jobs[job_id]
                job.state = "failed"
                job.message = f"{type(e).__name__}: {e}"


store = JobStore()
