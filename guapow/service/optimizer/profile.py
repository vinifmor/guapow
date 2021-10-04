import asyncio
import glob
import os
import time
from logging import Logger
from typing import Optional, Dict, List, Tuple

import aiofiles

from guapow.common.config import OptimizerConfig
from guapow.common.model import FileModel, CustomEnum, ProfileFile, ScriptSettings
from guapow.common.model_util import FileModelFiller
from guapow.common.profile import StopProcessSettings, get_profile_dir


class CPUSchedulingPolicy(CustomEnum):
    RR = os.SCHED_RR, True, True  # round-robin
    FIFO = os.SCHED_FIFO, True, True
    BATCH = os.SCHED_BATCH, False, False
    OTHER = os.SCHED_OTHER, False, False
    IDLE = os.SCHED_IDLE, False, False

    def __init__(self, value: str, priority: bool, root: bool):
        self._value = value
        self._priority = priority
        self._root = root

    def requires_priority(self) -> bool:
        return self._priority

    def requires_root(self) -> bool:
        return self._root

    def value(self):
        return self._value


class IOSchedulingClass(CustomEnum):
    NONE = '0', False
    REALTIME = '1', True
    BEST_EFFORT = '2', True
    IDLE = '3', False

    def __init__(self, value: int, priority: bool):
        self._value = value
        self.priority = priority

    def supports_priority(self) -> bool:
        return self.priority

    def value(self):
        return self._value

    def __str__(self) -> str:
        return self.name.lower()


class ProcessSchedulingSettings(FileModel):
    FILE_MAPPING = {'policy': ('policy', CPUSchedulingPolicy, None),
                    'policy.priority': ('priority', int, None)}

    def __init__(self, policy: Optional[CPUSchedulingPolicy], policy_priority: Optional[int] = None):
        self.policy = policy
        self.priority = policy_priority

    def is_valid(self) -> bool:
        return bool(self.policy)

    def has_valid_priority(self) -> bool:
        if not self.policy.requires_priority():
            return False

        return self.priority is not None and 0 < self.priority < 100

    def get_file_mapping(self) -> Dict[str, Tuple[str, type, Optional[object]]]:
        return self.FILE_MAPPING

    def get_file_root_node_name(self) -> Optional[str]:
        pass


class ProcessNiceSettings(FileModel):

    FILE_MAPPING = {'nice': ('level', int, None),
                    'nice.delay': ('delay', float, None),
                    'nice.watch': ('watch', bool, True)}

    def __init__(self, nice_level: Optional[int], delay: Optional[float], watch: Optional[bool]):
        self.delay = delay
        self.level = nice_level
        self.watch = watch

    def has_valid_level(self) -> bool:
        return self.level is not None and -21 < self.level < 20

    def get_output_name(self) -> str:
        return ""

    def get_file_mapping(self) -> Dict[str, Tuple[str, type, Optional[object]]]:
        return self.FILE_MAPPING

    def get_file_root_node_name(self) -> Optional[str]:
        pass

    def is_valid(self) -> bool:
        return self.has_valid_level()


class ProcessSettings(FileModel):

    MAPPING = {'affinity': ('cpu_affinity', List[int], None)}

    def __init__(self, affinity: Optional[List[int]]):
        self.scheduling = ProcessSchedulingSettings(None, None)
        self.io = IOScheduling(None, None)
        self.nice = ProcessNiceSettings(None, None, None)
        self.cpu_affinity = affinity

    def has_valid_cpu_affinity(self, cpu_count: int) -> bool:
        if cpu_count <= 0:
            return False

        if not self.cpu_affinity:
            return False

        for idx in self.cpu_affinity:
            if idx < 0 or idx >= cpu_count:
                return False

        return True

    def is_valid(self) -> bool:
        if self.cpu_affinity:
            return True

        valid = False
        for v in self.__dict__.values():
            if v is not None and isinstance(v, FileModel):
                if v.is_valid():
                    valid = True

        return valid

    def get_file_mapping(self) -> Dict[str, Tuple[str, type, Optional[object]]]:
        return self.MAPPING

    def get_file_root_node_name(self) -> Optional[str]:
        return 'proc'

    @classmethod
    def empty(cls) -> "ProcessSettings":
        instance = ProcessSettings(None)
        instance.scheduling = None
        instance.nice = None
        instance.io = None
        return instance


class CPUSettings(FileModel):
    FILE_MAPPING = {'performance': ('performance', bool, True)}

    def __init__(self, performance: Optional[bool]):
        self.performance = performance

    def is_valid(self) -> bool:
        return self.performance is not None

    def get_file_mapping(self) -> Dict[str, Tuple[str, type, Optional[object]]]:
        return self.FILE_MAPPING

    def get_file_root_node_name(self) -> Optional[str]:
        return 'cpu'


class IOScheduling(FileModel):

    FILE_MAPPING = {'class': ('ioclass', IOSchedulingClass, None), 'nice': ('nice_level', int, None)}

    def __init__(self, ioclass: Optional[IOSchedulingClass], nice_level: Optional[int]):
        self.ioclass = ioclass
        self.nice_level = nice_level

    def is_valid(self) -> bool:
        return bool(self.ioclass)

    def has_valid_priority(self) -> bool:
        return self.nice_level is not None and 0 <= self.nice_level < 8

    def get_file_mapping(self) -> Dict[str, Tuple[str, type, Optional[object]]]:
        return self.FILE_MAPPING

    def get_file_root_node_name(self) -> Optional[str]:
        return 'io'


class GPUSettings(FileModel):

    FILE_MAPPING = {'performance': ('performance', bool, True)}

    def __init__(self, performance: Optional[bool]):
        self.performance = performance

    def is_valid(self) -> bool:
        return self.performance is not None

    def get_file_mapping(self) -> Dict[str, Tuple[str, type, Optional[object]]]:
        return self.FILE_MAPPING

    def get_file_root_node_name(self) -> Optional[str]:
        return 'gpu'


class CompositorSettings(FileModel):

    FILE_MAPPING = {'off': ('off', bool, True)}

    def __init__(self, off: Optional[bool]):
        self.off = off

    def is_valid(self) -> bool:
        return self.off is True

    def get_file_mapping(self) -> Dict[str, Tuple[str, type, Optional[object]]]:
        return self.FILE_MAPPING

    def get_file_root_node_name(self) -> Optional[str]:
        return 'compositor'


class LauncherSettings(FileModel):
    FILE_MAPPING = {'launcher': ('mapping', dict, None),
                    'launcher.skip_mapping': ('skip_mapping', bool, True)}

    def __init__(self, mapping: Optional[dict], skip_mapping: Optional[bool]):
        self.mapping = mapping
        self.skip_mapping = skip_mapping

    def is_valid(self) -> bool:
        return bool(self.mapping) or self.skip_mapping is not None

    def get_file_mapping(self) -> Dict[str, Tuple[str, type, Optional[object]]]:
        return self.FILE_MAPPING

    def get_file_root_node_name(self) -> Optional[str]:
        pass


class OptimizationProfile(ProfileFile):

    MAPPING = {'mouse.hidden': ('hide_mouse', bool, True), 'steam': ('steam', bool, True)}

    def __init__(self, path: Optional[str], cpu: Optional[CPUSettings], steam: Optional[bool],
                 gpu: Optional[GPUSettings], process: Optional[ProcessSettings], compositor: Optional[CompositorSettings],
                 launcher: Optional[LauncherSettings], hide_mouse: Optional[bool]):
        super(OptimizationProfile, self).__init__(path)
        self.cpu = cpu
        self.steam = steam
        self.gpu = gpu
        self.process = process
        self.after_scripts = ScriptSettings('scripts.after')
        self.finish_scripts = ScriptSettings('scripts.finish')
        self.compositor = compositor
        self.launcher = launcher
        self.hide_mouse = hide_mouse
        self.stop_after = StopProcessSettings('stop.after', None)  # processes to stop after the process to be optimized launches

    def get_file_mapping(self) -> Dict[str, Tuple[str, type, Optional[object]]]:
        return self.MAPPING

    def get_output_name(self) -> str:
        return 'profile'

    def from_config(self) -> bool:
        return not self.path

    def get_log_str(self) -> str:
        return "informed configuration" if self.from_config() else f"profile '{self.name}'"

    def is_valid(self) -> bool:
        if super(OptimizationProfile, self).is_valid():
            return True

        return any([self.hide_mouse is not None,
                    self.steam is not None])

    @classmethod
    def empty(cls, path: Optional[str] = None) -> "OptimizationProfile":
        instance = cls(path=path, cpu=None, gpu=None, steam=None, process=None, compositor=None, launcher=None, hide_mouse=None)
        instance.finish_scripts = None
        instance.after_scripts = None
        instance.stop_after = None
        return instance

    @classmethod
    def raw(cls, path: Optional[str] = None) -> "OptimizationProfile":
        return cls(path=path,
                   cpu=CPUSettings(None),
                   steam=None,
                   process=ProcessSettings(None),
                   gpu=GPUSettings(None),
                   compositor=CompositorSettings(None),
                   launcher=LauncherSettings(None, None),
                   hide_mouse=None)

    @classmethod
    def from_optimizer_config(cls, config: OptimizerConfig) -> Optional["OptimizationProfile"]:
        if config and config.cpu_performance:
            profile = cls.empty(None)

            if config.cpu_performance:
                profile.cpu = CPUSettings(True)

            return profile


class OptimizationProfileCache:

    def __init__(self, logger: Logger):
        self._cache: Dict[str, OptimizationProfile] = dict()
        self._log = logger

    @staticmethod
    def map_key(path: str, add_settings: Optional[str]) -> str:
        return f"{path}{f'#{add_settings}' if add_settings else ''}"

    def _map_extra_log(self, add_settings: Optional[str]) -> str:
        return f" ({add_settings})" if add_settings else ''

    def get(self, path: str, add_settings: Optional[str] = None) -> Optional[OptimizationProfile]:
        ti = time.time()
        if self._cache:
            instance = self._cache.get(self.map_key(path, add_settings))
            if instance:
                tf = time.time()
                self._log.debug(f"Cached profile '{path}'{self._map_extra_log(add_settings)} found in {tf - ti:.5f} seconds")
                return instance

        self._log.debug(f"No cached profile found for '{path}'{self._map_extra_log(add_settings)}")

    def add(self, path: str,  profile: OptimizationProfile, add_settings: Optional[str]):
        if profile:
            self._log.debug(f"Caching profile '{path}'{self._map_extra_log(add_settings)}")
            self._cache[self.map_key(path, add_settings)] = profile

    @property
    def size(self) -> int:
        return len(self._cache)


class OptimizationProfileReader:

    def __init__(self, model_filler: FileModelFiller, logger: Logger, cache: Optional[OptimizationProfileCache]):
        self._model_filler = model_filler
        self._log = logger
        self._cache = cache

    def map(self, profile_str: str, profile_path: Optional[str] = None, add_settings: Optional[str] = None) -> OptimizationProfile:

        profile = OptimizationProfile.raw()

        self._model_filler.fill_profile(profile=profile, profile_str=profile_str,
                                        profile_path=profile_path, add_settings=add_settings)
        return profile

    async def read(self, profile_path: str, add_settings: Optional[str] = None) -> Optional[OptimizationProfile]:
        ti = time.time()

        async with aiofiles.open(profile_path) as f:
            profile_str = await f.read()

        profile_str = profile_str.strip()

        if not profile_str:
            self._log.warning(f"No properties defined in profile file '{profile_path}'")
            return

        instance = self.map(profile_str=profile_str, profile_path=profile_path, add_settings=add_settings)
        tf = time.time()
        self._log.debug(f"Profile file '{profile_path}' read and mapped in {tf - ti:.5f} seconds")
        return instance

    async def read_valid(self, profile_path: str, add_settings: Optional[str] = None, handle_not_found: bool = True) -> Optional[OptimizationProfile]:
        if self._cache:
            profile = self._cache.get(profile_path, add_settings)

            if profile:
                return profile

        try:
            profile = await self.read(profile_path=profile_path, add_settings=add_settings)
        except FileNotFoundError:
            if handle_not_found:
                profile = None
                self._log.warning(f"Profile file '{profile_path}' not found")
            else:
                raise

        if profile:
            if profile.is_valid():
                if self._cache:
                    self._cache.add(profile_path, profile, add_settings)

                return profile
            else:
                self._log.warning(f"Invalid profile file '{profile_path}'")

    @property
    def cached_profiles(self) -> int:
        return self._cache.size if self._cache else 0


async def cache_profiles(reader: OptimizationProfileReader, logger: Logger):
    profile_paths = set()
    for exp in {f'{d}/*.profile' for d in (get_profile_dir(0, 'root'), get_profile_dir(1, '*'))}:
        profile_paths.update(glob.glob(exp))

    if profile_paths:
        logger.debug(f"{len(profile_paths)} profiles found on disk")
        await asyncio.gather(*(reader.read_valid(path) for path in profile_paths))
        logger.info(f"{reader.cached_profiles} valid profiles cached")
    else:
        logger.info("No profile file found on disk to cache")
