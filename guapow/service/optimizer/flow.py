from asyncio import Lock
from logging import Logger
from typing import Set, Optional


class OptimizationQueue:
    """
    Responsible to properly control what is being processed
    """

    def __init__(self, queued_pids: Set[int], logger: Optional[Logger] = None):
        self._queued_pids = queued_pids
        self._lock_queued_pids = Lock()
        self._logger = logger

    def _log(self, msg: str):
        if self._logger:
            self._logger.debug(msg)

    async def add_pid(self, pid: int) -> bool:
        if pid is not None:
            async with self._lock_queued_pids:
                if pid not in self._queued_pids:
                    self._log(f"Adding pid {pid} to the optimization queue")
                    self._queued_pids.add(pid)
                    return True

        return False

    async def remove_pids(self, *pids: int):
        if pids is not None:
            async with self._lock_queued_pids:
                for pid in pids:
                    if pid is not None:
                        self._log(f"Removing pid {pid} from the optimization queue")
                        self._queued_pids.discard(pid)

    def get_view(self) -> Optional[Set[int]]:
        if self._queued_pids is not None:
            return {*self._queued_pids}

    @classmethod
    def empty(cls) -> "OptimizationQueue":
        return OptimizationQueue(set())
