import asyncio
import multiprocessing
import os.path
import traceback
from asyncio import Lock
from logging import Logger
from typing import Optional, Set, Dict, Tuple

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


class CPUEnergyPolicyManager:

    LEVEL_PERFORMANCE = 0

    def __init__(self, cpu_count: int, logger: Logger,
                 file_pattern: str = '/sys/devices/system/cpu/cpu{idx}/power/energy_perf_bias'):
        self._cpus = cpu_count
        self._log = logger
        self._lock = Lock()
        self._state_cache: Dict[int, int] = dict()
        self._file_pattern = file_pattern

    def lock(self) -> Lock:
        return self._lock

    def can_work(self) -> Tuple[bool, Optional[str]]:
        if not self._cpus or self._cpus < 0:
            return False, 'It will not be possible to change the CPU energy policy level: no CPU detected'

        file_path = self._file_pattern.format(idx='0')
        if not os.path.exists(file_path):
            return False, f"It will not be possible to change the CPU energy policy level: " \
                          f"file '{file_path}' not found"

        return True, None

    async def _read_cpu_state(self, idx: int) -> Optional[int]:
        file_path = self._file_pattern.format(idx=idx)
        cpu_state = None

        try:
            async with aiofiles.open(file_path) as f:
                cpu_state = await f.read()
        except:
            err_stack = traceback.format_exc().replace('\n', ' ')
            self._log.error(f"[{self.__class__.__name__}] Could not read file '{file_path}': {err_stack}")

        if cpu_state is not None:
            try:
                return int(cpu_state)
            except ValueError:
                self._log.error(f"[{self.__class__.__name__}] Could not cast CPU energy policy level ({cpu_state}) "
                                f"to int. File: {file_path}")

    async def _write_cpu_state(self, idx: int, state: int) -> bool:
        file_path = self._file_pattern.format(idx=idx)

        try:
            async with aiofiles.open(file_path, 'w+') as f:
                await f.write(str(state))

            return True
        except:
            err_stack = traceback.format_exc().replace('\n', ' ')
            self._log.error(f"[{self.__class__.__name__}] Could not write '{state}' to file '{file_path}': {err_stack}")
            return False

    async def _fill_cpu_state_change(self, idx: int, state: int, output: Dict[int, bool]):
        output[idx] = await self._write_cpu_state(idx, state)

    async def _fill_cpu_state(self, idx: int, output: Dict[int, int]):
        cpu_state = await self._read_cpu_state(idx)

        if isinstance(cpu_state, int):
            output[idx] = cpu_state

    async def map_current_state(self) -> Optional[Dict[int, int]]:
        if self._cpus > 0:
            res = {}
            await asyncio.gather(*[self._fill_cpu_state(idx, res) for idx in range(self._cpus)])
            return res if res else None

    async def change_states(self, cpu_states: Dict[int, int]) -> Dict[int, bool]:
        if self._cpus > 0 and cpu_states:
            res = {}
            await asyncio.gather(*[self._fill_cpu_state_change(idx, state, res) for idx, state in cpu_states.items()])
            return res

    def save_state(self, cpu_states: Dict[int, int]):
        if cpu_states:
            for idx, state in cpu_states.items():
                if idx not in self._state_cache:
                    self._state_cache[idx] = state

    @property
    def saved_state(self) -> Dict[int, int]:
        return {**self._state_cache}

    def clear_state(self, *keys: int):
        if keys:
            for k in keys:
                if k in self._state_cache:
                    del self._state_cache[k]
        else:
            self._state_cache.clear()
