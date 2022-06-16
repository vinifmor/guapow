import os
from logging import Logger
from typing import Optional, Set, Tuple

import aiofiles

from guapow import __app_name__
from guapow.common.users import is_root_user

FILE_NAME = 'watch.ignore'


def get_file_path(user_id: int, user_name: str) -> Optional[str]:
    if is_root_user(user_id):
        return f'/etc/{__app_name__}/{FILE_NAME}'
    else:
        return f'/home/{user_name}/.config/{__app_name__}/{FILE_NAME}'


def get_existing_file_path(user_id: int, user_name: str, logger: Logger) -> Optional[str]:
    file_path = get_file_path(user_id, user_name)
    if os.path.isfile(file_path):
        logger.info(f"Ignored file '{file_path}' found")
        return file_path
    else:
        logger.warning(f"Ignored file '{file_path}' not found")
        return get_existing_file_path(0, 'root', logger) if not is_root_user(user_id) else None


def get_default_file_path(user_id: int, user_name: str, logger: Logger) -> str:
    file_path = get_existing_file_path(user_id, user_name, logger)

    if file_path:
        return file_path

    default_path = get_file_path(user_id, user_name)
    logger.info(f'Considering the default ignored file path for current user: {default_path}')
    return default_path


async def read(file_path: str, logger: Logger, last_file_found_log: Optional[bool]) -> Tuple[bool, Optional[Set[str]]]:
    try:
        async with aiofiles.open(file_path) as f:
            ignored_str = (await f.read()).strip()

        if not last_file_found_log:
            logger.info(f"Ignore file '{file_path}' found")

    except FileNotFoundError:
        if last_file_found_log is None or last_file_found_log is True:
            logger.debug(f"Ignore file '{file_path}' not found")

        return False, None

    ignored = set()

    for string in ignored_str.split('\n'):
        clean_string = string.strip()

        if clean_string:
            sharp_less = clean_string.split('#')
            final_str = sharp_less[0].strip()

            if final_str:
                ignored.add(final_str)

    return True, ignored if ignored else None
