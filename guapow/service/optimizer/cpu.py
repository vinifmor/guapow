import asyncio
import multiprocessing
from asyncio import Lock
from logging import Logger
from typing import Optional, Set, Dict

import aiofiles

GOVERNOR_FILE_PATTERN = '/sys/devices/system/cpu/cpu{}/cpufreq/scaling_governor'
GOVERNOR_PERFORMANCE = 'performance'


def get_cpu_count() -> int:
    try:
        return multiprocessing.cpu_count()
    except:
        return 0


class CPUFrequencyManager:

    def __init__(self, logger: Logger, cpu_count: int, governor_file_pattern: Optional[str] = GOVERNOR_FILE_PATTERN):
        self._cached_governors = {}
        self._log = logger
        self._governor_file_pattern = governor_file_pattern
        self._cpu_count = cpu_count
        self._lock = Lock()

    def lock(self):
        return self._lock

    def save_governors(self, governor_cpus: Dict[str, Set[int]]):
        if self._cached_governors is None:
            self._cached_governors = {}

        for gov, cpus in governor_cpus.items():
            for cpu in cpus:
                self._cached_governors[cpu] = gov

    def get_saved_governors(self) -> Optional[Dict[str, Set[int]]]:
        governors = None
        if self._cached_governors:
            governors = {}
            for cpu, gov in self._cached_governors.items():
                cpus = governors.get(gov, set())
                governors[gov] = cpus
                cpus.add(cpu)

        return governors

    async def map_current_governors(self) -> Dict[str, Set[int]]:
        governors = {}
        if self._cpu_count > 0:
            for cpu in range(self._cpu_count):
                governor_path = self._governor_file_pattern.format(cpu)
                try:
                    async with aiofiles.open(governor_path) as f:
                        gov = await f.read()
                except FileNotFoundError:
                    self._log.warning(f"Could not read governor for CPU '{cpu}'. File '{governor_path}' not found")
                    continue

                gov = gov.strip()
                cpus = governors.get(gov, set())
                cpus.add(cpu)
                governors[gov] = cpus

        return governors

    async def _write_governor(self, idx: int, governor: str) -> bool:
        try:
            async with aiofiles.open(self._governor_file_pattern.format(idx), 'w+') as f:
                await f.write(governor)

            return True
        except OSError:
            return False

    async def _set_governor(self, idx: int, governor: str, changed: Set[int], not_changed: Set[int]):
        if await self._write_governor(idx, governor):
            changed.add(idx)
        else:
            not_changed.add(idx)

    async def change_governor(self, governor: str, cpu_idxs: Optional[Set[int]] = None) -> Set[int]:
        if self._cpu_count == 0:
            return set()

        changed, not_changed = set(), set()

        await asyncio.gather(*(self._set_governor(i, governor, changed, not_changed) for i in (cpu_idxs if cpu_idxs else range(self._cpu_count))))

        if not_changed:
            self._log.warning(f"Could not change CPUs [{','.join((str(i) for i in not_changed))}] frequency governor to '{governor}'")

        if changed:
            self._log.info(f"CPUs [{','.join((str(i) for i in changed))}] frequency governor changed to '{governor}'")

        return changed
