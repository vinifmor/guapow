import asyncio
import os
import re
import shutil
import traceback
from abc import ABC, abstractmethod
from asyncio import Lock
from copy import deepcopy
from glob import glob
from logging import Logger, ERROR, DEBUG, WARNING, INFO
from re import Pattern
from typing import Optional, Tuple, Set, Dict, List, Type, AsyncIterator, Any

import aiofiles

from guapow.common import system
from guapow.common.model import CustomEnum


class UnknownGPUDriver(Exception):

    def __init__(self, gpu_idx: int):
        self.gpu_idx = gpu_idx


class GPUDriver(ABC):

    @abstractmethod
    def __init__(self, cache: bool, logger: Logger):
        self._logger = logger
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
    async def set_power_mode(self, ids_modes: Dict[str, Any], user_environment: Optional[Dict[str, str]]) \
            -> Dict[str, bool]:
        pass

    @abstractmethod
    async def get_power_mode(self, gpu_ids: Set[str], user_environment: Optional[Dict[str, str]]) \
            -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def can_work(self) -> Tuple[bool, Optional[str]]:
        pass

    @abstractmethod
    def get_default_mode(self) -> Any:
        pass

    @abstractmethod
    def get_performance_mode(self) -> Any:
        pass

    def _log(self, msg: str, level: int = INFO):
        final_msg = f"{self.get_vendor_name()}: {msg}"
        if level == INFO:
            self._logger.info(final_msg)
        elif level == DEBUG:
            self._logger.debug(final_msg)
        elif level == ERROR:
            self._logger.error(final_msg)
        elif level == WARNING:
            self._logger.warning(final_msg)
        else:
            self._logger.info(final_msg)


class NvidiaPowerMode(CustomEnum):
    ON_DEMAND = 0
    PERFORMANCE = 1
    AUTO = 2


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

    async def set_power_mode(self, ids_modes: Dict[str, NvidiaPowerMode],
                             user_environment: Optional[Dict[str, str]] = None) -> Dict[str, bool]:
        params = ' '.join((f'-a [gpu:{i}]/GpuPowerMizerMode={m.value}' for i, m in ids_modes.items()))
        cmd = f'nvidia-settings {params}'

        log_str = {', '.join((f'{i}={ids_modes[i].value}' for i in ids_modes))}
        self._log(f"changing GPUs power mode ({log_str}): {cmd}")
        _, output = await system.async_syscall(cmd, custom_env=self._map_env_vars(user_environment))

        if output:
            changed_gpus = {*self._get_re_set_power().findall(output)}

            if changed_gpus:
                try:
                    return {id_: int(mode) == ids_modes[id_].value for id_, mode in changed_gpus if id_ in ids_modes}
                except ValueError:
                    self._log(f"error while parsing changing modes response: {output}", ERROR)

        err_msg = output.replace('\n', ' ') if output else ''
        self._log(f"could not determine the changing modes response: {err_msg}", ERROR)
        return {i: False for i in ids_modes}

    async def get_power_mode(self, gpu_ids: Set[str], user_environment: Optional[Dict[str, str]] = None) \
            -> Optional[Dict[str, NvidiaPowerMode]]:
        if gpu_ids:
            gpus_query = ' '.join((f'-q [gpu:{id_}]/GpuPowerMizerMode' for id_ in gpu_ids))
            cmd = f"nvidia-settings {gpus_query}"
            code, output = await system.async_syscall(cmd, custom_env=self._map_env_vars(user_environment))

            if code == 0:
                if not output:
                    self._log(f"could not detect GPUs power mode ({cmd}). No output returned", WARNING)
                else:
                    modes = self._get_re_get_power().findall(output)

                    if modes:
                        try:
                            return {id_: NvidiaPowerMode.from_value(int(mode)) for id_, mode in modes if id_ in gpu_ids}
                        except ValueError:
                            self._log(f"error when parsing power modes: {modes}", ERROR)

                    self._log(f"could not detect GPUs power mode ({cmd}). No modes found in output: {output}", ERROR)
            else:
                output_str = '. Output: {}'.format(output.replace('\n', ' ')) if output else ''
                self._log(f"could not detect GPUs power mode ({cmd}){output_str}", ERROR)

    def can_work(self) -> Tuple[bool, Optional[str]]:
        if not shutil.which('nvidia-settings'):
            return False, "'nvidia-settings' is not installed"

        if not shutil.which('nvidia-smi'):
            return False, "'nvidia-smi' is not installed"

        return True, None

    def get_default_mode(self) -> NvidiaPowerMode:
        return NvidiaPowerMode.AUTO

    def get_performance_mode(self) -> NvidiaPowerMode:
        return NvidiaPowerMode.PERFORMANCE


class AMDGPUDriver(GPUDriver):

    PERFORMANCE_FILE = "power_dpm_force_performance_level"
    PROFILE_FILE = "pp_power_profile_mode"
    VENDOR = "AMD"

    def __init__(self, cache: bool, logger: Logger, gpus_path: str = "/sys/class/drm/card{id}/device"):
        super(AMDGPUDriver, self).__init__(cache, logger)
        self._gpus_path = gpus_path
        self._re_power_mode: Optional[Pattern] = None
        self._re_extract_id: Optional[Pattern] = None

    @classmethod
    def get_vendor_name(cls) -> str:
        return cls.VENDOR

    def can_work(self) -> Tuple[bool, Optional[str]]:
        return True, None

    @property
    def re_power_mode(self) -> Pattern:
        if not self._re_power_mode:
            self._re_power_mode = re.compile(r'^\w+\*:?$')

        return self._re_power_mode

    @property
    def re_extract_id(self) -> Pattern:
        if not self._re_extract_id:
            self._re_extract_id = re.compile(self._gpus_path.replace('{id}', r'(\d+)'))

        return self._re_extract_id

    def extract_gpu_id(self, gpu_path: str) -> Optional[int]:
        try:
            return self.re_extract_id.findall(gpu_path)[0]
        except IndexError:
            self._log(f"Could not extract GPU id from path: {gpu_path}", ERROR)

    async def get_gpus(self) -> Optional[Set[str]]:
        required_files = {self.PERFORMANCE_FILE: set(), self.PROFILE_FILE: set()}

        for gpu_file_path in glob(f"{self._gpus_path.format(id='*')}/*"):
            gpu_file = os.path.basename(gpu_file_path)
            if gpu_file in required_files:
                if not os.access(gpu_file_path, mode=os.W_OK):
                    id_ = self.extract_gpu_id(gpu_file_path)
                    self._log(f"Writing is not allowed for file '{gpu_file_path}. It will not be possible to set "
                              f"the GPU ({id_}) to performance mode", WARNING)
                else:
                    required_files[gpu_file].add(os.path.dirname(gpu_file_path))

        all_gpu_dirs = {gpu_dir for paths in required_files.values() for gpu_dir in paths}

        if all_gpu_dirs:
            gpus = set()
            for gpu_dir in all_gpu_dirs:
                missing_files = set()
                for file, gpu_file_dirs in required_files.items():
                    if gpu_dir not in gpu_file_dirs:
                        missing_files.add(file)

                if missing_files:
                    self._log(f"not all required files are accessible for mounted GPU in '{gpu_dir}' "
                              f"(missing: {', '.join(sorted(missing_files))})", WARNING)
                else:
                    self._log(f"all required files are accessible for GPU mounted in '{gpu_dir}'", DEBUG)
                    gpu_id = self.extract_gpu_id(gpu_dir)

                    if gpu_id is not None:
                        gpus.add(gpu_id)

            return gpus if gpus else None
        else:
            self._log("no mounted GPU directories", DEBUG)

    async def _read_file(self, file_path: str) -> Optional[str]:
        try:
            async with aiofiles.open(file_path) as f:
                return await f.read()
        except:
            err_stack = traceback.format_exc().replace('\n', ' ')
            self._log(f"Could not read file '{file_path}': {err_stack}", ERROR)

    def _map_power_profile_output(self, output: str, file_path: str) -> Optional[str]:
        if output is not None:
            for raw_line in output.split('\n'):
                if raw_line.startswith(' '):
                    line = raw_line.strip().split(' ')

                    if len(line) > 1 and line[0].isdigit() and self.re_power_mode.match(line[-1]):
                        return line[0].strip()

            content_log = output.replace('\n', ' ')
            self._log(f"could not map power profile from {file_path}. Content: {content_log}", WARNING)

    async def _fill_power_mode(self, gpu_id: str, gpu_modes: Dict[str, str]):
        gpu_dir = self._gpus_path.format(id=gpu_id)
        performance_level_file = f"{gpu_dir}/{self.PERFORMANCE_FILE}"
        performance_level = (await self._read_file(performance_level_file)).strip()
        self._log(f"GPU file ({performance_level_file}): {performance_level}", DEBUG)

        if not performance_level:
            return

        power_profile_file = f"{gpu_dir}/{self.PROFILE_FILE}"
        power_profile = self._map_power_profile_output(await self._read_file(power_profile_file), power_profile_file)
        self._log(f"GPU file ({power_profile_file}): {power_profile}", DEBUG)

        if not power_profile:
            return

        gpu_modes[gpu_id] = f"{performance_level}:{power_profile}"

    async def get_power_mode(self, gpu_ids: Set[str], user_environment: Optional[Dict[str, str]] = None) \
            -> Optional[Dict[str, str]]:
        if gpu_ids:
            res = {}
            await asyncio.gather(*tuple(self._fill_power_mode(id_, res) for id_ in gpu_ids))
            return res if res else None

    async def _write_to_file(self, file_path: str, content: str) -> bool:
        try:
            async with aiofiles.open(file_path, 'w+') as f:
                await f.write(content)
            return True
        except:
            err_stack = traceback.format_exc().replace('\n', ' ')
            self._log(f"could not write '{content}' to file '{file_path}': {err_stack}", ERROR)
            return False

    async def _fill_write_result(self, file_path: str, content: str, id_: str, output: Dict[str, List[bool]]):
        output[id_].append(await self._write_to_file(file_path, content))

    async def set_power_mode(self, ids_modes: Dict[str, str],
                             user_environment: Optional[Dict[str, str]] = None) -> Dict[str, bool]:
        res = {}
        if ids_modes:
            coros, writes = [], dict()
            for id_, mode_str in ids_modes.items():
                mode = mode_str.split(':')

                if len(mode) == 2:
                    gpu_dir = self._gpus_path.format(id=id_)
                    self._log(f"changing GPU ({id_}) operation mode (performance: {mode[0]}, profile: {mode[1]})")
                    writes[id_] = list()
                    coros.append(self._fill_write_result(f'{gpu_dir}/{self.PERFORMANCE_FILE}', mode[0], id_, writes))
                    coros.append(self._fill_write_result(f'{gpu_dir}/{self.PROFILE_FILE}', mode[1], id_, writes))
                else:
                    self._log(f"could not change GPU ({id_}) operation mode: unexpected mode format '{mode_str}' "
                              f"(expected: 'performance_level:power_profile'", ERROR)

            await asyncio.gather(*coros)

            for id_ in ids_modes:
                gpu_writes = writes.get(id_)
                res[id_] = gpu_writes and all(gpu_writes)

        return res

    def get_default_mode(self) -> str:
        return 'auto:3'

    def get_performance_mode(self) -> str:
        return 'manual:5'


class GPUState:

    def __init__(self, id_: str, driver_class: Type, power_mode: Any):
        self.id = id_
        self.driver_class = driver_class
        self.power_mode = power_mode

    def __eq__(self, other):
        if isinstance(other, GPUState):
            return self.driver_class == other.driver_class and self.id == other.id

    def __hash__(self):
        return hash(self.driver_class) + hash(self.id)

    def __repr__(self):
        attrs = self.__dict__.items()
        attr_str = ', '.join(f'{p}={v.__name__ if isinstance(v, type) else v}' for p, v in sorted(attrs) if v)
        return f'{self.__class__.__name__} ({attr_str})'


class GPUManager:

    LOG_CACHE_KEY__WORK = 0
    LOG_CACHE_KEY__AVAILABLE = 1

    def __init__(self, logger: Logger, drivers: Optional[Tuple[GPUDriver]] = None, cache_gpus: bool = False):
        self._log = logger
        self._drivers = drivers
        self._drivers_lock = Lock()
        self._cache_gpus = cache_gpus
        self._gpu_state_cache: Dict[Type[GPUDriver], Dict[str, Any]] = {}
        self._gpu_state_cache_lock = Lock()
        self._log_cache: Dict[Type[GPUDriver], Dict[int, object]] = {}  # to avoid repetitive logs
        self._working_drivers_cache: Optional[Tuple[GPUDriver]] = None  # only when 'cache_gpus'
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
                self._log.warning(f"{driver.get_vendor_name()} GPUs cannot be managed: "
                                  f"{reason if reason else 'unknown reason'}")
                driver_cache[self.LOG_CACHE_KEY__WORK] = True

        return can_work

    async def _get_driver_gpus(self, driver: GPUDriver) -> Optional[Set[str]]:
        gpus = await driver.get_cached_gpus()

        driver_cache = self._get_driver_log_cache(driver.__class__)

        cached_gpus = driver_cache.get(self.LOG_CACHE_KEY__AVAILABLE)

        if gpus != cached_gpus:
            gpu_ids = f" (ids={', '.join((str(i) for i in sorted(gpus)))})" if gpus else ''
            self._log.debug(f'[{driver.get_vendor_name()}] GPUs available: {len(gpus)}{gpu_ids}')
            driver_cache[self.LOG_CACHE_KEY__AVAILABLE] = gpus

        return gpus

    async def _map_driver_if_gpus(self, driver: GPUDriver) -> Optional[Tuple[GPUDriver, Optional[Set[str]]]]:
        if await self._can_driver_work(driver):
            gpus = await self._get_driver_gpus(driver)

            if gpus:
                return driver, gpus

    async def _map_drivers_and_gpus(self) -> AsyncIterator[Tuple[GPUDriver, Set[str]]]:
        for task in asyncio.as_completed(tuple(self._map_driver_if_gpus(driver) for driver in self._drivers)):
            driver_gpus = await task

            if driver_gpus:
                yield driver_gpus

    async def map_working_drivers_and_gpus(self) -> AsyncIterator[Tuple[GPUDriver, Set[str]]]:
        async with self._drivers_lock:
            if self._drivers is None:
                driver_types = GPUDriver.__subclasses__()
                self._drivers = tuple(cls(self._cache_gpus, self._log) for cls in driver_types if cls != self.__class__)

        if self._drivers:
            if self._cache_gpus:
                async with self._working_drivers_cache_lock:
                    if self._working_drivers_cache is not None:
                        for driver in self._working_drivers_cache:
                            yield driver, await self._get_driver_gpus(driver)
                    else:
                        working_drivers = []

                        async for driver, gpus in self._map_drivers_and_gpus():
                            yield driver, gpus
                            working_drivers.append(driver)

                        self._working_drivers_cache = tuple(working_drivers)
            else:
                async for driver, gpus in self._map_drivers_and_gpus():
                    yield driver, gpus
        else:
            self._log.error("No GPU driver instances available")

    async def activate_performance(self, user_environment: Optional[Dict[str, str]] = None,
                                   target_gpu_ids: Optional[Set[str]] = None) \
            -> Optional[Dict[Type[GPUDriver], Set[GPUState]]]:
        """

        Args:
            user_environment: user environment variables
            target_gpu_ids: the target GPU ids to enter in performance mode. If None, all available GPUs will be considered.

        Returns: the GPUs previous states

        """

        res = {}
        async for driver, gpus in self.map_working_drivers_and_gpus():
            if not gpus:
                continue

            target_gpus = gpus.intersection(target_gpu_ids) if target_gpu_ids else gpus

            if not target_gpus:
                self._log.debug(f"[{driver.get_vendor_name()}] No valid target GPUs available "
                                f"for performance mode (valid: {', '.join(sorted(gpus))})")
                continue

            async with driver.lock():
                if target_gpu_ids and gpus != target_gpu_ids:
                    self._log.debug(f"[{driver.get_vendor_name()}] Target GPU ids for performance mode: "
                                    f"{', '.join(sorted(target_gpus))}")

                gpu_modes = await driver.get_power_mode(target_gpus, user_environment)
                if gpu_modes:
                    performance_mode = driver.get_performance_mode()
                    async with self._gpu_state_cache_lock:
                        cached_states = self._gpu_state_cache.get(driver.__class__, {})
                        self._gpu_state_cache[driver.__class__] = cached_states

                        driver_res, not_in_performance = set(), set()
                        for gpu, mode in gpu_modes.items():
                            if performance_mode != mode:
                                cached_states[gpu] = mode
                                driver_res.add(GPUState(gpu, driver.__class__, mode))
                                not_in_performance.add(gpu)
                            else:
                                old_state = cached_states.get(gpu)

                                if old_state:
                                    driver_res.add(GPUState(gpu, driver.__class__, old_state))

                    if not_in_performance:
                        gpus_changed = await driver.set_power_mode({g: performance_mode for g in not_in_performance},
                                                                   user_environment)

                        not_changed = {gpu for gpu, changed in gpus_changed.items() if not changed}

                        if not_changed:
                            self._log.error(f"[{driver.get_vendor_name()}] could not change power mode of GPUs: "
                                            f"{', '.join(sorted(not_changed))}")

                    res[driver.__class__] = driver_res

        return res

    def get_drivers(self) -> Optional[Tuple[GPUDriver]]:
        return tuple(self._drivers) if self._drivers is not None else None

    def get_cached_working_drivers(self) -> Optional[Tuple[GPUDriver]]:
        if self._working_drivers_cache:
            return tuple(self._working_drivers_cache)

    def get_gpu_state_cache_view(self) -> Dict[Type[GPUDriver], Dict[str, Any]]:
        return deepcopy(self._gpu_state_cache)


def get_driver_by_vendor(vendor: str) -> Optional[Type[GPUDriver]]:
    if vendor:
        vendor_norm = vendor.strip().lower()

        for cls_ in GPUDriver.__subclasses__():
            if cls_ != GPUManager and cls_.get_vendor_name().strip().lower() == vendor_norm:
                return cls_
