import os
import re
from logging import Logger
from typing import Optional


class InvalidConfigurationException(Exception):
    pass


def map_config_str(string: str) -> str:
    if string:
        pattern = re.compile(r'([a-zA-Z.\-_]+)\s*(=(\s*([a-zA-Z.\-_,\d:/%*]+))?)?')
        return '\n'.join(f"{prop[0]}{f'={prop[3]}' if prop[3] else ''}" for prop in pattern.findall(string) if not prop[1] or prop[2])


def read_valid_full_config(logger: Logger) -> Optional[str]:
    config_str = os.getenv('GUAPOW_CONFIG')

    if config_str:
        config_str = config_str.strip()

        if config_str:
            valid_config_str = map_config_str(config_str)

            if valid_config_str:
                return valid_config_str
            else:
                logger.error(f"Invalid 'GUAPOW_CONFIG': {config_str}")
                raise InvalidConfigurationException()


def read_additional_profile_config(logger: Logger) -> Optional[str]:
    config_str = os.getenv('GUAPOW_PROFILE_ADD')

    if config_str:
        config_str.strip()

        if config_str:
            valid_config_str = map_config_str(config_str)

            if valid_config_str:
                return valid_config_str
            else:
                logger.warning(f"Invalid 'GUAPOW_PROFILE_ADD': {config_str}")


def is_log_enabled() -> bool:
    try:
        return bool(int(os.getenv('GUAPOW_LOG', 0)))
    except ValueError:
        return False


def is_file_log() -> bool:
    try:
        return bool(int(os.getenv('GUAPOW_LOG_FILE', 0)))
    except ValueError:
        return False
