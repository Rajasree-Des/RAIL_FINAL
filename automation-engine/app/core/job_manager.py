"""In-memory job state for run/stop/pause/resume control."""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class JobState:
    run_id: str
    status: str = "pending"
    task: asyncio.Task | None = None
    pause_event: asyncio.Event = field(default_factory=asyncio.Event)
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)
    config: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.pause_event.set()


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, JobState] = {}

    def get(self, run_id: str) -> JobState | None:
        return self._jobs.get(run_id)

    def register(self, run_id: str, config: dict[str, Any]) -> JobState:
        state = JobState(run_id=run_id, config=config, status="pending")
        self._jobs[run_id] = state
        return state

    def set_task(self, run_id: str, task: asyncio.Task) -> None:
        if run_id in self._jobs:
            self._jobs[run_id].task = task
            self._jobs[run_id].status = "running"

    async def wait_if_paused(self, run_id: str) -> bool:
        state = self._jobs.get(run_id)
        if not state:
            return False
        if state.stop_event.is_set():
            return False
        await state.pause_event.wait()
        return not state.stop_event.is_set()

    def pause(self, run_id: str) -> bool:
        state = self._jobs.get(run_id)
        if not state or state.status != "running":
            return False
        state.pause_event.clear()
        state.status = "paused"
        return True

    def resume(self, run_id: str) -> bool:
        state = self._jobs.get(run_id)
        if not state or state.status != "paused":
            return False
        state.pause_event.set()
        state.status = "running"
        return True

    def stop(self, run_id: str) -> bool:
        state = self._jobs.get(run_id)
        if not state:
            return False
        state.stop_event.set()
        state.pause_event.set()
        state.status = "stopped"
        if state.task and not state.task.done():
            state.task.cancel()
        return True

    def update_status(self, run_id: str, status: str) -> None:
        if run_id in self._jobs:
            self._jobs[run_id].status = status

    def cleanup(self, run_id: str) -> None:
        self._jobs.pop(run_id, None)


job_manager = JobManager()
