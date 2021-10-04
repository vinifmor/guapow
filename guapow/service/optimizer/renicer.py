import asyncio
import os
from logging import Logger
from typing import Optional

from guapow.common import system


class Renicer:

    def __init__(self, logger: Logger, watch_interval: float):
        self._log = logger
        self._pid_nice = {}
        self._watching = False
        self._watch_interval = watch_interval

    def get_priority(self, pid: int) -> Optional[int]:
        try:
            return os.getpriority(os.PRIO_PROCESS, pid)
        except:
            pass

    def set_priority(self, pid: int, level: int, request_pid: int) -> bool:
        try:
            os.setpriority(os.PRIO_PROCESS, pid, level)
            self._log.info(f"Process {pid} nice level changed to '{level}' (request={request_pid})")
            return True
        except:
            self._log.error(f"Could not change process {pid} nice level to {level} (request={request_pid})")
            return False

    def add(self, pid: int, nice_level: int, request_pid: int) -> bool:
        if pid not in self._pid_nice:
            self._pid_nice[pid] = nice_level, request_pid
            self._log.info(f"Process {pid} nice level will be monitored (request={request_pid})")
            return True

        self._log.debug(f"Process {pid} nice level is already being monitored (request={request_pid})")
        return False

    def is_watching(self) -> bool:
        return self._watching

    async def _watch(self):
        while True:
            if not self._pid_nice:
                break

            pids = system.read_current_pids()
            dead_pids = set()

            for pid, nice_request in self._pid_nice.items():
                level, request_pid = nice_request[0], nice_request[1]
                if pid not in pids:
                    dead_pids.add(pid)

                current_nice = self.get_priority(pid)

                if current_nice != nice_request[0]:
                    self._log.debug(
                        f"Process {pid} current nice level ({current_nice}) differs from expected ({level}) "
                        f"(request={request_pid})")

                    self.set_priority(pid, level, request_pid)

            if dead_pids:
                for pid in dead_pids:
                    if pid in self._pid_nice:
                        del self._pid_nice[pid]

                self._log.debug(f"Stop monitoring the nice level of processes: {', '.join((str(p) for p in dead_pids))}")

            if not self._pid_nice:
                break

            if self._watch_interval and self._watch_interval > 0:
                await asyncio.sleep(self._watch_interval)

        self._watching = False
        self._log.debug(f"Stopped monitoring nice levels")

    def watch(self) -> bool:
        if not self._watching and self._pid_nice:
            self._watching = True
            asyncio.get_event_loop().create_task(self._watch())
            return True

        return False
