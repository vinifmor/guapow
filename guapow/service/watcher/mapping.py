import os
import re
from logging import Logger
from typing import Optional, Dict, Pattern, Tuple, Set

import aiofiles

from guapow import __app_name__
from guapow.common import steam
from guapow.common.profile import get_default_profile_name
from guapow.common.users import is_root_user
from guapow.common.util import map_only_any_regex, has_any_regex

FILE_NAME = 'watch.map'
RE_PYTHON_REGEX = re.compile(r'^r:(.+)$')


def get_root_file_path() -> str:
    return f'/etc/{__app_name__}/{FILE_NAME}'


def get_user_file_path(user_name: str) -> str:
    return f'/home/{user_name}/.config/{__app_name__}/{FILE_NAME}'


def get_file_path(user_id: int, user_name: str) -> Optional[str]:
    return get_root_file_path() if is_root_user(user_id) else get_user_file_path(user_name)


def get_existing_file_path(user_id: int, user_name: str, logger: Logger) -> Optional[str]:
    file_path = get_file_path(user_id, user_name)
    if os.path.isfile(file_path):
        logger.info(f"Mapping file '{file_path}' found")
        return file_path
    else:
        logger.warning(f"Mapping file '{file_path}' not found")
        return get_existing_file_path(0, 'root', logger) if not is_root_user(user_id) else None


def get_default_file_path(user_id: int, user_name: str, logger: Logger) -> str:
    file_path = get_existing_file_path(user_id, user_name, logger)

    if file_path:
        return file_path

    default_path = get_file_path(user_id, user_name)
    logger.info(f'Considering the default mapping file path for current user: {default_path}')
    return default_path


async def read(file_path: str, logger: Logger, last_file_found_log: Optional[bool]) -> Tuple[bool, Optional[Dict[str, str]]]:
    try:
        async with aiofiles.open(file_path) as f:
            mapping_file_str = (await f.read()).strip()

        if not last_file_found_log:
            logger.error(f"Mapping file '{file_path}' found")

    except FileNotFoundError:
        if last_file_found_log is None or last_file_found_log is True:
            logger.error(f"Mapping file '{file_path}' not found")

        return False, None

    mappings = map_string(mapping_file_str)
    return True, mappings if mappings else None


def map_string(string: str) -> Optional[Dict[str, str]]:
    if string:
        mappings = {}
        for line in string.split('\n'):
            if line:
                line_strip = line.strip()

                if line_strip:
                    line_no_comment = [w.strip() for w in line_strip.split('#', 1)]

                    if not line_no_comment or not line_no_comment[0]:
                        continue

                    try:
                        div_idx = line_no_comment[0].rindex('=')
                        pattern = line_no_comment[0][0:div_idx].strip()
                        profile = line_no_comment[0][div_idx + 1:].strip()
                    except ValueError:
                        pattern = line_no_comment[0].strip()
                        profile = None

                    if pattern and not profile:
                        mappings[pattern] = get_default_profile_name()
                    else:
                        mappings[pattern] = profile

        if mappings:
            return mappings


class RegexMapper:

    RE_TYPE_CMD, RE_TYPE_COMM = 0, 1

    BUILTIN_RE = {'__steam__': (steam.RE_STEAM_CMD, RE_TYPE_CMD)}

    def __init__(self, cache: bool, logger: Logger):
        self._pattern_cache: Optional[dict] = None
        self._no_pattern_cache: Optional[Set] = None

        if cache:
            self._pattern_cache, self._no_pattern_cache = {}, set()

        self._log = logger

    def get_cached_pattern(self, str_pattern: str) -> Optional[re.Pattern]:
        if self._pattern_cache is not None:
            return self._pattern_cache.get(str_pattern)

    def is_no_pattern_string_cached(self, string: str) -> bool:
        return string in self._no_pattern_cache if self._no_pattern_cache is not None else False

    def map(self, mapping: Dict[str, str]) -> Optional[Tuple[Dict[Pattern, str], Dict[Pattern, str]]]:
        """
        return: a tuple with two dictionaries: first with cmd patterns and second with comm patterns.
        """
        if mapping:
            cmd, comm = {}, {}

            for string, prof in mapping.items():
                builtin_pattern = self.BUILTIN_RE.get(string)

                if builtin_pattern:
                    if builtin_pattern[1] == self.RE_TYPE_CMD:
                        cmd[builtin_pattern[0]] = prof
                    elif builtin_pattern[1] == self.RE_TYPE_COMM:
                        comm[builtin_pattern[0]] = prof
                    else:
                        self._log.error(f"Unknown type of built-in pattern '{string}'. It will be ignored.")

                    continue

                if self.is_no_pattern_string_cached(string):
                    continue

                pattern = self.get_cached_pattern(string)
                cached = bool(pattern)

                if not cached:
                    python_regex = RE_PYTHON_REGEX.findall(string)

                    if python_regex:
                        try:
                            pattern = re.compile('^{}$'.format(python_regex[0]))
                        except re.error:
                            self._log.warning(f'Invalid Python regex mapping: {string}')
                            continue

                    elif has_any_regex(string):
                        pattern = map_only_any_regex(string)
                    else:
                        pattern = None

                if pattern:
                    if pattern.pattern[1] == '/':
                        cmd[pattern] = prof
                    else:
                        comm[pattern] = prof

                    if not cached and self._pattern_cache is not None:
                        self._pattern_cache[string] = pattern

                elif self._no_pattern_cache is not None:
                    self._no_pattern_cache.add(string)

            return cmd, comm
