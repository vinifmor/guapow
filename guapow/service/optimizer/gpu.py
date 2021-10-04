import asyncio
import os
import re
import shutil
import traceback
from abc import ABC, abstractmethod
from asyncio import Lock
from copy import deepcopy
from glob import glob
from logging import Logger
from re import Pattern
from typing import Optional, Tuple, Set, Dict, List, Type, AsyncIterator

import aiofiles

from guapow.common import system
from guapow.common.model import CustomEnum


class GPUPowerMode(CustomEnum):
    ON_DEMAND = 0
    PERFORMANCE = 1
    AUTO = 2


class UnknownGPUDriver(Exception):

    def __init__(self, gpu_idx: int):
        self.gpu_idx = gpu_idx


class GPUDriver(ABC):

    @abstractmethod
    def __init__(self, cache: bool, logger: Logger):
        self._log = logger
        self._lock = Lock()
        self._cache_lock = Lock() if cache else None
        self._gpus: Optional[Set[str]] = None
        self._cached = False

    def lock(self) -> Lock:
        return self._lock

    async def get_cached_gpus(self) -> Optional[Set[str]]:
        if self._cache_lock is None:
            return await self.get_gpus()

        async with self._cache_lock:
            if not self._cached:
                self._gpus = await self.get_gpus()
                self._cached = True

        return self._gpus

    @abstractmethod
    async def get_gpus(self) -> Optional[Set[str]]:
        pass

    @classmethod
    @abstractmethod
    def get_vendor_name(cls) -> str:
        pass

    @abstractmethod
    async def set_power_mode(self, ids_modes: Dict[str, GPUPowerMode], user_environment: Optional[Dict[str, str]]) -> Dict[str, bool]:
        pass

    @abstractmethod
    async def get_power_mode(self, gpu_ids: Set[str], user_environment: Optional[Dict[str, str]]) -> Optional[Dict[str, GPUPowerMode]]:
        pass

    @abstractmethod
    def can_work(self) -> Tuple[bool, Optional[str]]:
        pass


class NvidiaGPUDriver(GPUDriver):

    def __init__(self, cache: bool, logger: Logger):
        super(NvidiaGPUDriver, self).__init__(cache, logger)
        self._re_set_power: Optional[Pattern] = None
        self._re_get_power: Optional[Pattern] = None

    def _get_re_set_power(self) -> Pattern:
        if self._re_set_power is None:
            self._re_set_power = re.compile(r'\[gpu:(\d+)].+(\d)\.?')

        return self._re_set_power

    def _get_re_get_power(self) -> Pattern:
        if self._re_get_power is None:
            self._re_get_power = re.compile(r"Attribute\s+.+\[gpu:(\d+)].+:\s+(\d)")

        return self._re_get_power

    @classmethod
    def get_vendor_name(cls) -> str:
        return 'Nvidia'

    async def get_gpus(self) -> Optional[Set[str]]:
        exitcode, output = await system.async_syscall('nvidia-smi --query-gpu=index --format=csv,noheader')

        gpus = set()
        if exitcode == 0:
            for line in output.split('\n'):
                if line:
                    gpu_idx = line.strip()
                    if gpu_idx:
                        gpus.add(gpu_idx)

        return gpus

    def _map_env_vars(self, vars: Optional[Dict[str, str]]) -> Dict[str, str]:
        env = vars if vars is not None else {}
        env['LANG'] = 'en_US.UTF-8'
        return env

    async def set_power_mode(self, ids_modes: Dict[str, GPUPowerMode], user_environment: Optional[Dict[str, str]] = None) -> Dict[str, bool]:
        params = ' '.join((f'-a [gpu:{i}]/GpuPowerMizerMode={m.value}' for i, m in ids_modes.items()))
        cmd = f'nvidia-settings {params}'

        self._log.info(f"Changing {self.get_vendor_name()} GPUs power mode ({', '.join((f'{i}={ids_modes[i].value}' for i in ids_modes))}): {cmd}")
        _, output = await system.async_syscall(cmd, custom_env=self._map_env_vars(user_environment))

        if output:
            changed_gpus = {*self._get_re_set_power().findall(output)}

            if changed_gpus:
                try:
                    return {id_: int(mode) == ids_modes[id_].value for id_, mode in changed_gpus if id_ in ids_modes}
                except ValueError:
                    self._log.error(f"[{self.__class__.__name__}] Error while parsing changing modes response: {output}")

        err_msg = output.replace('\n', ' ') if output else ''
        self._log.error(f"[{self.__class__.__name__}] Could not determine the changing modes response: {err_msg}")
        return {i: False for i in ids_modes}

    async def get_power_mode(self, gpu_ids: Set[str], user_environment: Optional[Dict[str, str]] = None) -> Optional[Dict[str, GPUPowerMode]]:
        if gpu_ids:
            gpus_query = ' '.join((f'-q [gpu:{id_}]/GpuPowerMizerMode' for id_ in gpu_ids))
            cmd = f"nvidia-settings {gpus_query}"
            code, output = await system.async_syscall(cmd, custom_env=self._map_env_vars(user_environment))

            if code == 0:
                if not output:
                    self._log.warning(f"Could not detect {self.get_vendor_name()} GPUs power mode ({cmd}). No output returned")
                else:
                    modes = self._get_re_get_power().findall(output)

                    if modes:
                        try:
                            return {id_: GPUPowerMode.from_value(int(mode)) for id_, mode in modes if id_ in gpu_ids}
                        except ValueError:
                            self._log.error(f"[{self.__class__.__name__}] Error when parsing power modes: {modes}")

                    self._log.error("Could not detect {} GPUs power mode ({}). No modes found in output: {}".format(self.get_vendor_name(), cmd, output))
            else:
                output_str = '. Output: {}'.format(output.replace('\n', ' ')) if output else ''
                self._log.error(f"Could not detect {self.get_vendor_name()} GPUs power mode ({cmd}){output_str}")

    def can_work(self) -> Tuple[bool, Optional[str]]:
        if not shutil.which('nvidia-settings'):
            return False, "'nvidia-settings' is not installed"

        if not shutil.which('nvidia-smi'):
            return False, "'nvidia-smi' is not installed"

        return True, None


class AMDGPUDriver(GPUDriver):

    GPUS_PATH = '/sys/bus/pci/drivers/amdgpu'
    PERFORMANCE_FILE = 'power_dpm_force_performance_level'
    PROFILE_FILE = 'pp_compute_power_profile'

    def __init__(self, cache: bool, logger: Logger, gpus_path: str = GPUS_PATH):
        super(AMDGPUDriver, self).__init__(cache, logger)
        self._default_performance_level = {}
        self._default_power_profile = {}
        self._gpus_path = gpus_path

    async def get_gpus(self) -> Optional[Set[str]]:
        gpus = set()
        for gpu_mode_path in glob(f'{self._gpus_path}/*/{self.PERFORMANCE_FILE}'):  # FIXME no async glob at the moment
            if os.access(gpu_mode_path, mode=os.W_OK):  # if writing is allowed
                mode_dir = os.path.dirname(gpu_mode_path)
                power_file = f'{mode_dir}/{self.PROFILE_FILE}'
                if os.access(power_file, mode=os.W_OK):
                    gpus.add(os.path.basename(mode_dir))

        return gpus

    def can_work(self) -> Tuple[bool, Optional[str]]:
        return True, None

    @classmethod
    def get_vendor_name(cls) -> str:
        return 'AMD'

    async def _read_file(self, gpu_id: str, file: str) -> Optional[str]:
        file_path = f'{self._gpus_path}/{gpu_id}/{file}'
        try:
            async with aiofiles.open(file_path) as f:
                return (await f.read()).strip()
        except:
            err_stack = traceback.format_exc().replace('\n', ' ')
            self._log.error(f"[{self.__class__.__name__}] Could not read file '{file}': {err_stack}")

    async def _add_power_mode(self, gpu_id: str, gpu_modes: Dict[str, GPUPowerMode]):
        perf_level = await self._read_file(gpu_id, self.PERFORMANCE_FILE)

        if perf_level is None:
            return

        if perf_level != 'auto' and self._default_performance_level.get(gpu_id) is None:
            self._default_performance_level[gpu_id] = perf_level

        power_profile = await self._read_file(gpu_id, self.PROFILE_FILE)

        if power_profile is None:
            return

        if power_profile != 'set' and self._default_power_profile.get(gpu_id) is None:
            self._default_power_profile[gpu_id] = power_profile

        gpu_modes[gpu_id] = GPUPowerMode.PERFORMANCE if (perf_level == 'auto' and power_profile == 'set') else GPUPowerMode.AUTO

    async def get_power_mode(self, gpu_ids: Set[str], user_environment: Optional[Dict[str, str]] = None) -> Optional[Dict[str, GPUPowerMode]]:
        if gpu_ids:
            res = {}
            await asyncio.gather(*[self._add_power_mode(gpu_id, res) for gpu_id in gpu_ids])
            return res if res else None

    async def _write_to_file(self, content: str, gpu_id: str, file: str) -> bool:
        file_path = f'{self._gpus_path}/{gpu_id}/{file}'

        try:
            async with aiofiles.open(file_path, 'w+') as f:
                await f.write(content)
        except:
            self._log.error(f"[{self.__class__.__name__}] Could not write '{content}' to file '{file_path}'")
            traceback.print_exc()
            return False

        return True

    def map_performance_level(self, mode: GPUPowerMode, gpu_id: Optional[str]) -> Optional[str]:
        if mode == GPUPowerMode.PERFORMANCE:
            return 'auto'
        elif gpu_id is not None and self._default_performance_level:
            return self._default_performance_level.get(gpu_id)

    def map_power_profile(self, mode: GPUPowerMode, gpu_id: Optional[str]) -> Optional[str]:
        if mode == GPUPowerMode.PERFORMANCE:
            return 'set'
        elif gpu_id is not None and self._default_power_profile:
            return self._default_power_profile.get(gpu_id)

    async def _set_power_mode(self, gpu: str, mode: GPUPowerMode, gpu_power: Dict[str, bool]):
        level = self.map_performance_level(mode, gpu)

        if level is not None and await self._write_to_file(level, gpu, self.PERFORMANCE_FILE):
            profile = self.map_power_profile(mode, gpu)

            if profile is not None:
                if await self._write_to_file(profile, gpu, self.PROFILE_FILE):
                    gpu_power[gpu] = True
                    return

        gpu_power[gpu] = False

    async def set_power_mode(self, ids_modes: Dict[str, GPUPowerMode], user_environment: Optional[Dict[str, str]] = None) -> Dict[str, bool]:
        res = {}
        self._log.info(f"Changing {self.get_vendor_name()} GPUs power mode [{', '.join(f'{i}={m.name}' for i, m in sorted(ids_modes.items()))}]")
        await asyncio.gather(*[self._set_power_mode(gpu, mode, res) for gpu, mode in ids_modes.items()])
        return res


class GPUState:

    def __init__(self, id_: str, driver_class: Type, power_mode: GPUPowerMode):
        self.id = id_
        self.driver_class = driver_class
        self.power_mode = power_mode

    def __eq__(self, other):
        if isinstance(other, GPUState):
            return self.driver_class == other.driver_class and self.id == other.id

    def __hash__(self):
        return hash(self.driver_class) + hash(self.id)

    def __repr__(self):
        attrs = ', '.join(f'{p}={v.__name__ if isinstance(v, type) else v}' for p, v in sorted(self.__dict__.items()) if v)
        return f'{self.__class__.__name__} ({attrs})'


class GPUManager:

    LOG_CACHE_KEY__WORK = 0
    LOG_CACHE_KEY__AVAILABLE = 1

    def __init__(self, logger: Logger, drivers: Optional[List[GPUDriver]] = None, cache_gpus: bool = False):
        self._log = logger
        self._drivers = drivers
        self._drivers_lock = Lock()
        self._cache_gpus = cache_gpus
        self._gpu_state_cache: Dict[Type[GPUDriver], Dict[str, GPUPowerMode]] = {}
        self._gpu_state_cache_lock = Lock()
        self._log_cache: Dict[Type[GPUDriver], Dict[int, object]] = {}  # to avoid repetitive logs
        self._working_drivers_cache: Optional[List[GPUDriver]] = None  # cached working drivers (only when 'cache_gpus')
        self._working_drivers_cache_lock = Lock()

    def is_cache_enabled(self) -> bool:
        return self._cache_gpus

    def _get_driver_log_cache(self, cls: Type[GPUDriver]) -> Dict[int, object]:
        driver_cache = self._log_cache.get(cls)

        if driver_cache is None:
            driver_cache = {}
            self._log_cache[cls] = driver_cache

        return driver_cache

    async def _can_driver_work(self, driver: GPUDriver) -> bool:
        can_work, reason = driver.can_work()

        driver_cache = self._get_driver_log_cache(driver.__class__)

        if can_work:
            driver_cache[self.LOG_CACHE_KEY__WORK] = False
        else:
            logged = driver_cache.get(self.LOG_CACHE_KEY__WORK)

            if not logged:
                self._log.warning(f"{driver.get_vendor_name()} GPUs cannot be managed: {reason if reason else 'unknown reason'}")
                driver_cache[self.LOG_CACHE_KEY__WORK] = True

        return can_work

    async def _get_driver_gpus(self, driver: GPUDriver) -> Optional[Set[str]]:
        gpus = await driver.get_cached_gpus()

        driver_cache = self._get_driver_log_cache(driver.__class__)

        cached_gpus = driver_cache.get(self.LOG_CACHE_KEY__AVAILABLE)

        if gpus != cached_gpus:
            gpu_ids = f" (ids={', '.join((str(i) for i in sorted(gpus)))})" if gpus else ''
            self._log.debug(f'{driver.get_vendor_name()} GPUs available: {len(gpus)}{gpu_ids}')
            driver_cache[self.LOG_CACHE_KEY__AVAILABLE] = gpus

        return gpus

    async def _map_driver_if_gpus(self, driver: GPUDriver) -> Optional[Tuple[GPUDriver, Optional[Set[str]]]]:
        if await self._can_driver_work(driver):
            gpus = await self._get_driver_gpus(driver)

            if gpus:
                return driver, gpus

    async def _map_drivers_and_gpus(self) -> AsyncIterator[Tuple[GPUDriver, Set[str]]]:
        for task in asyncio.as_completed([self._map_driver_if_gpus(driver) for driver in self._drivers]):
            driver_gpus = await task

            if driver_gpus:
                yield driver_gpus

    async def map_working_drivers_and_gpus(self) -> AsyncIterator[Tuple[GPUDriver, Set[str]]]:
        async with self._drivers_lock:
            if self._drivers is None:
                self._drivers = [cls(self._cache_gpus, self._log) for cls in GPUDriver.__subclasses__() if cls != self.__class__]

        if self._drivers:
            if self._cache_gpus:
                async with self._working_drivers_cache_lock:
                    if self._working_drivers_cache is not None:
                        for driver in self._working_drivers_cache:
                            yield driver, await self._get_driver_gpus(driver)
                    else:
                        self._working_drivers_cache = []

                        async for driver, gpus in self._map_drivers_and_gpus():
                            yield driver, gpus
                            self._working_drivers_cache.append(driver)
            else:
                async for driver, gpus in self._map_drivers_and_gpus():
                    yield driver, gpus

    async def activate_performance(self, user_environment: Optional[Dict[str, str]] = None) -> Optional[Dict[Type[GPUDriver], Set[GPUState]]]:
        res = {}
        async for driver, gpus in self.map_working_drivers_and_gpus():
            async with driver.lock():
                gpu_modes = await driver.get_power_mode(gpus, user_environment)

                if gpu_modes:
                    async with self._gpu_state_cache_lock:
                        cached_states = self._gpu_state_cache.get(driver.__class__, {})
                        self._gpu_state_cache[driver.__class__] = cached_states

                        driver_res, not_in_performance = set(), set()
                        for gpu, mode in gpu_modes.items():
                            if mode != GPUPowerMode.PERFORMANCE:
                                cached_states[gpu] = mode
                                driver_res.add(GPUState(gpu, driver.__class__, mode))
                                not_in_performance.add(gpu)
                            else:
                                old_state = cached_states.get(gpu)

                                if old_state:
                                    driver_res.add(GPUState(gpu, driver.__class__, old_state))

                    if not_in_performance:
                        gpus_changed = await driver.set_power_mode({g: GPUPowerMode.PERFORMANCE for g in not_in_performance}, user_environment)

                        not_changed = {gpu for gpu, changed in gpus_changed.items() if not changed}

                        if not_changed:
                            self._log.error(f"Could not change power mode of {driver.get_vendor_name()} GPUs: {', '.join(sorted(not_changed))}")

                    res[driver.__class__] = driver_res

        return res

    def get_drivers(self) -> Optional[List[GPUDriver]]:
        return [*self._drivers] if self._drivers is not None else None

    def get_cached_working_drivers(self) -> Optional[List[GPUDriver]]:
        if self._working_drivers_cache:
            return [*self._working_drivers_cache]

    def get_gpu_state_cache_view(self) -> Dict[Type[GPUDriver], Dict[str, GPUPowerMode]]:
        return deepcopy(self._gpu_state_cache)


def get_driver_by_vendor(vendor: str) -> Optional[Type[GPUDriver]]:
    if vendor:
        vendor_norm = vendor.strip().lower()

        for cls_ in GPUDriver.__subclasses__():
            if cls_ != GPUManager and cls_.get_vendor_name().strip().lower() == vendor_norm:
                return cls_
