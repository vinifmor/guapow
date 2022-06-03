import os
from logging import Logger
from typing import Optional, Tuple, Dict, Set

import aiofiles

from guapow import __app_name__
from guapow.common import log
from guapow.common.model import FileModel, RootFileModel
from guapow.common.model_util import FileModelFiller
from guapow.common.users import is_root_user

HTTP_SERVER_PORT = 'GUAPOW_OPT_PORT'


def get_root_optimizer_config_path():
    return f'/etc/{__app_name__}/opt.conf'


def get_user_optimizer_config_path(user_name: str):
    return f'/home/{user_name}/.config/{__app_name__}/opt.conf'


def get_optimizer_config_path_by_user_priority(current_user_id: int, current_user_name: str, logger: Logger) -> Optional[str]:
    is_root = is_root_user(current_user_id)
    file_path = get_root_optimizer_config_path() if is_root else get_user_optimizer_config_path(current_user_name)

    if os.path.isfile(file_path):
        logger.info(f"Optimizer configuration file '{file_path}' found")
        return file_path
    else:
        logger.warning(f"Optimizer configuration file '{file_path}' not found")
        return get_optimizer_config_path_by_user_priority(0, 'root', logger) if not is_root else None  # tries to retrieve it from root


class RequestSettings(FileModel):

    FILE_MAPPING = {'allowed_users': ('allowed_users', Set[str], None),
                    'encrypted': ('encrypted', bool, True)}

    def __init__(self, encrypted: Optional[bool], allowed_users: Optional[Set[str]]):
        self.encrypted = encrypted
        self.allowed_users = allowed_users

    def get_file_mapping(self) -> Dict[str, Tuple[str, type, Optional[object]]]:
        return self.FILE_MAPPING

    def get_file_root_node_name(self) -> Optional[str]:
        return 'request'

    def is_valid(self) -> bool:
        return self.encrypted is not None

    def setup_valid_properties(self):
        if self.encrypted is None:
            self.encrypted = True

    @classmethod
    def empty(cls) -> Optional["RequestSettings"]:
        return cls(None, None)

    @classmethod
    def default(cls) -> Optional["RequestSettings"]:
        instance = cls.empty()
        instance.setup_valid_properties()
        return instance


class OptimizerConfig(RootFileModel):

    DEFAULT_PORT = 5087

    FILE_MAPPING = {'port': ('port', int, None),
                    'compositor': ('compositor', str, None),
                    'scripts.allow_root': ('allow_root_scripts', bool, True),
                    'check.finished.interval': ('check_finished_interval', int, None),
                    'launcher.mapping.timeout': ('launcher_mapping_timeout', float, None),
                    'gpu.cache': ('gpu_cache', bool, True),
                    'gpu.vendor': ('gpu_vendor', str, None),
                    'cpu.performance': ('cpu_performance', bool, True),
                    'profile.cache': ('profile_cache', bool, True),
                    'profile.pre_caching': ('pre_cache_profiles', bool, True),
                    'nice.check.interval': ('renicer_interval', float, None)}

    def __init__(self, port: Optional[int] = None, compositor: Optional[str] = None,
                 allow_root_scripts: Optional[bool] = False,
                 check_finished_interval: Optional[int] = None, launcher_mapping_timeout: Optional[float] = 30,
                 gpu_cache: Optional[bool] = False, cpu_performance: Optional[bool] = None,
                 profile_cache: Optional[bool] = None, pre_cache_profiles: Optional[bool] = None,
                 gpu_vendor: Optional[str] = None, renicer_interval: Optional[float] = None):
        self.port = port
        self.compositor = compositor
        self.allow_root_scripts = allow_root_scripts
        self.check_finished_interval = check_finished_interval
        self.launcher_mapping_timeout = launcher_mapping_timeout
        self.gpu_cache = gpu_cache
        self.gpu_vendor = gpu_vendor
        self.cpu_performance = cpu_performance
        self.request = RequestSettings.default()
        self.profile_cache = profile_cache
        self.pre_cache_profiles = pre_cache_profiles
        self.renicer_interval = renicer_interval

    def get_file_mapping(self) -> Dict[str, Tuple[str, type, Optional[object]]]:
        return self.FILE_MAPPING

    def get_file_root_node_name(self) -> Optional[str]:
        pass

    def is_valid(self) -> bool:
        if super(OptimizerConfig, self).is_valid():
            return True

        return all([self.has_valid_port(),
                    bool(self.compositor),
                    self.allow_root_scripts is not None,
                    self.cpu_performance is not None,
                    self.profile_cache is not None,
                    self.has_valid_check_finished_interval(),
                    self.has_valid_launcher_mapping_timeout(),
                    self.has_valid_renicer_interval()])

    def has_valid_port(self) -> bool:
        return self.port is not None and 0 <= self.port <= 65535

    def has_valid_launcher_mapping_timeout(self) -> bool:
        return self.launcher_mapping_timeout is not None and self.launcher_mapping_timeout >= 0

    def has_valid_check_finished_interval(self) -> bool:
        return self.check_finished_interval is not None and self.check_finished_interval > 0

    def has_valid_renicer_interval(self) -> bool:
        return self.renicer_interval is not None and self.renicer_interval > 0

    def setup_valid_properties(self):
        if self.port is None:
            try:
                self.port = int(os.getenv(HTTP_SERVER_PORT, self.DEFAULT_PORT))
            except ValueError:
                self.port = self.DEFAULT_PORT

        if not self.has_valid_port():
            self.port = self.DEFAULT_PORT

        if not self.has_valid_check_finished_interval():
            self.check_finished_interval = 3

        if not self.has_valid_launcher_mapping_timeout():
            self.launcher_mapping_timeout = 30

        if self.gpu_cache is None:
            self.gpu_cache = False

        if self.profile_cache is None:
            self.profile_cache = False

        if self.pre_cache_profiles is None:
            self.pre_cache_profiles = False

        if not self.has_valid_renicer_interval():
            self.renicer_interval = 5

        if self.request is None:
            self.request = RequestSettings.default()
        elif not self.request.is_valid():
            self.request.setup_valid_properties()

    @property
    def encrypted_requests(self) -> bool:
        return bool(self.request and self.request.encrypted)

    @classmethod
    def read_valid(cls, logger: Logger, model_filler: FileModelFiller, file_path: str, only_properties: Optional[Set[str]] = None) -> "OptimizerConfig":
        instance = cls()

        try:
            with open(file_path) as f:
                config_str = f.read().strip()

            model_filler.fill(instance, config_str, only_properties)
        except FileNotFoundError:
            logger.warning(f"Optimizer configuration file '{file_path}' does not exist. Using default settings.")

        instance.setup_valid_properties()

        if instance.is_valid():
            return instance
        else:
            logger.warning(f"Invalid optimizer configuration file '{file_path}'")

    @staticmethod
    def is_log_enabled() -> bool:
        try:
            return bool(int(os.getenv('GUAPOW_OPT_LOG', '1')))
        except ValueError:
            return True

    @staticmethod
    def get_log_level() -> int:
        return log.get_log_level('GUAPOW_OPT_LOG_LEVEL')

    @staticmethod
    def is_service() -> bool:
        try:
            return bool(int(os.getenv('GUAPOW_OPT_SERVICE', '0')))
        except ValueError:
            return False

    @classmethod
    def empty(cls) -> "OptimizerConfig":
        instance = cls(allow_root_scripts=None, check_finished_interval=None, launcher_mapping_timeout=None,
                       gpu_cache=None)
        instance.request = None
        return instance

    @classmethod
    def default(cls) -> "OptimizerConfig":
        instance = OptimizerConfig()
        instance.setup_valid_properties()
        return instance


class OptimizerConfigReader:

    def __init__(self, model_filler: FileModelFiller, logger: Logger):
        self._model_filler = model_filler
        self._log = logger

    async def read_valid(self, file_path: str, only_properties: Optional[Set[str]] = None) -> Optional[OptimizerConfig]:
        instance = OptimizerConfig()

        try:
            async with aiofiles.open(file_path) as f:
                config_str = (await f.read()).strip()

            self._model_filler.fill(instance, config_str, only_properties)
        except FileNotFoundError:
            self._log.warning(f"Optimizer configuration file '{file_path}' does not exist. Using default settings.")

        instance.setup_valid_properties()

        if instance.is_valid():
            return instance
        else:
            self._log.warning(f"Invalid optimizer configuration file '{file_path}'")


async def read_optimizer_config(user_id: int, user_name: str, filler: FileModelFiller, logger: Logger, only_properties: Optional[Set[str]] = None) -> Optional[OptimizerConfig]:
    opt_config_path = get_optimizer_config_path_by_user_priority(user_id, user_name, logger)

    if opt_config_path:
        return await OptimizerConfigReader(filler, logger).read_valid(file_path=opt_config_path,
                                                                      only_properties=only_properties)

    else:
        logger.warning("Using default Optimizer settings")
        return OptimizerConfig.default()
