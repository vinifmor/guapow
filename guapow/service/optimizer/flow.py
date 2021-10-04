from asyncio import Lock
from typing import Set, Optional


class OptimizationQueue:
    """
    Responsible to properly control what is being processed
    """

    def __init__(self, queued_pids: Set[int]):
        self._queued_pids = queued_pids
        self._lock_queued_pids = Lock()

    async def add_pid(self, pid: int) -> bool:
        async with self._lock_queued_pids:
            if pid not in self._queued_pids:
                self._queued_pids.add(pid)
                return True

        return False

    async def remove_pids(self, *pids: int):
        if pids is not None:
            async with self._lock_queued_pids:
                for pid in pids:
                    self._queued_pids.discard(pid)

    def get_view(self) -> Optional[Set[int]]:
        if self._queued_pids is not None:
            return {*self._queued_pids}

    @classmethod
    def empty(cls) -> "OptimizationQueue":
        return OptimizationQueue(set())
