import os
from logging import Logger
from typing import Optional, Dict, Tuple

import aiofiles

from guapow import __app_name__
from guapow.common.profile import get_default_profile_name
from guapow.common.users import is_root_user

FILE_NAME = 'watch.map'


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
