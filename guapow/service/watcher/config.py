import os
from logging import Logger
from typing import Dict, Tuple, Optional

from guapow import __app_name__
from guapow.common.model import FileModel
from guapow.common.model_util import FileModelFiller
from guapow.common.users import is_root_user


class ProcessWatcherConfig(FileModel):

    FILE_NAME = 'watch.conf'
    FILE_MAPPING = {'interval': ('check_interval', float, None),
                    'regex.cache': ('regex_cache', bool, True),
                    'mapping.cache': ('mapping_cache', bool, True)}

    def __init__(self, regex_cache: Optional[bool], check_interval: Optional[float], mapping_cache: Optional[bool]):
        self.check_interval = check_interval
        self.regex_cache = regex_cache
        self.mapping_cache = mapping_cache

    def get_output_name(self) -> str:
        pass

    def get_file_mapping(self) -> Dict[str, Tuple[str, type, Optional[object]]]:
        return self.FILE_MAPPING

    def is_valid(self) -> bool:
        return all((self.is_check_interval_valid(),
                    self.regex_cache is not None,
                    self.mapping_cache is not None))

    def is_check_interval_valid(self):
        return self.check_interval is not None and self.check_interval > 0

    def setup_valid_properties(self):
        if not self.is_check_interval_valid():
            self.check_interval = 1.0

        if self.regex_cache is None:
            self.regex_cache = True

        if self.mapping_cache is None:
            self.mapping_cache = False

    def get_file_root_node_name(self) -> Optional[str]:
        pass

    @classmethod
    def empty(cls) -> "ProcessWatcherConfig":
        return cls(None, None, None)

    @classmethod
    def default(cls) -> "ProcessWatcherConfig":
        instance = cls.empty()
        instance.setup_valid_properties()
        return instance

    @classmethod
    def get_file_path_by_user(cls, user_id: int, user_name: str, logger: Logger) -> Optional[str]:
        is_root = is_root_user(user_id)

        file_path = f'/etc/{__app_name__}/{cls.FILE_NAME}' if is_root else f'/home/{user_name}/.config/{__app_name__}/{cls.FILE_NAME}'

        if os.path.isfile(file_path):
            logger.info(f"Watcher configuration file '{file_path}' found")
            return file_path
        else:
            logger.warning(f"Watcher configuration file '{file_path}' not found")
            return cls.get_file_path_by_user(0, 'root', logger) if not is_root else None  # tries to retrieve it from root


class ProcessWatcherConfigReader:

    def __init__(self, filler: FileModelFiller, logger: Logger):
        self._filler = filler
        self._log = logger

    def read_valid(self, file_path: Optional[str]) -> Optional[ProcessWatcherConfig]:
        if file_path:
            self._log.debug(f"Trying to read Watcher configuration file '{file_path}'")

            try:
                with open(file_path) as f:
                    config_str = f.read().strip()

            except FileNotFoundError:
                self._log.warning(f"Watcher configuration file '{file_path}' not found. Default settings will be used instead.")
                config_str = None

            instance = ProcessWatcherConfig.empty()

            if config_str:
                self._filler.fill(instance, config_str)

            if not instance.is_valid():
                self._log.warning(f"Invalid or missing settings in Watcher configuration file '{file_path}' (default values of some properties will be used instead)")
                instance.setup_valid_properties()

            return instance
        else:
            self._log.info("Using default Watcher settings")
            return ProcessWatcherConfig.default()
