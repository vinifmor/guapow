import asyncio
import getpass
import os
import time

from guapow import __app_name__
from guapow.common.auth import read_machine_id
from guapow.common.config import read_optimizer_config
from guapow.common.log import new_logger, get_log_level
from guapow.common.model_util import FileModelFiller
from guapow.service.watcher import mapping
from guapow.service.watcher.config import ProcessWatcherConfig, ProcessWatcherConfigReader
from guapow.service.watcher.core import ProcessWatcherContext, ProcessWatcher
from guapow.service.watcher.mapping import RegexMapper


def is_log_enabled() -> bool:
    try:
        return bool(int(os.getenv('GUAPOW_WATCH_LOG', 1)))
    except ValueError:
        return True


def is_service() -> bool:
    try:
        return bool(int(os.getenv('GUAPOW_WATCH_SERVICE', 1)))
    except ValueError:
        return True


async def watch():
    ti = time.time()
    service, log_enabled = is_service(), is_log_enabled()
    logger = new_logger(name=f'{__app_name__}-watcher', service=service, enabled=log_enabled,
                        write_to_file=False, level=get_log_level('GUAPOW_WATCH_LOG_LEVEL'))
    user_id, user_name = os.getuid(), getpass.getuser()
    logger.debug(f"Initializing as system user '{user_name}'")

    filler = FileModelFiller(logger)
    watch_config_path = ProcessWatcherConfig.get_file_path_by_user(user_id, user_name, logger)
    watch_config = ProcessWatcherConfigReader(filler, logger).read_valid(watch_config_path)

    if not watch_config:
        exit(1)

    opt_config = await read_optimizer_config(user_id=user_id, user_name=user_name, filler=filler, logger=logger,
                                             only_properties={'port', 'request.encrypted'})

    if not opt_config:
        exit(1)

    machine_id = await read_machine_id() if opt_config.encrypted_requests else None

    user_env = dict(os.environ)

    if 'DISPLAY' not in user_env:
        user_env['DISPLAY'] = ':0'

    context = ProcessWatcherContext(user_id=os.getuid(), user_name=getpass.getuser(), user_env=user_env,
                                    logger=logger, optimized={}, opt_config=opt_config, watch_config=watch_config,
                                    mapping_file_path=mapping.get_default_file_path(user_id, user_name, logger), machine_id=machine_id)

    regex_mapper = RegexMapper(cache=watch_config.regex_cache, logger=logger)
    watcher = ProcessWatcher(regex_mapper, context)
    logger.info(f'Requests encryption: {str(machine_id is not None).lower()}')
    logger.info(f'Regex cache: {str(watch_config.regex_cache).lower()}')
    logger.info(f'Mapping cache: {str(watch_config.mapping_cache).lower()}')
    logger.info(f'Checking processes every {watch_config.check_interval} second(s)')

    tf = time.time()
    logger.debug(f'Initialization took {tf - ti:.4f} seconds')
    await watcher.watch()


def start():
    asyncio.get_event_loop().run_until_complete(watch())


if __name__ == '__main__':
    start()
