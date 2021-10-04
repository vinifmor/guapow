import asyncio
import logging
import logging.handlers
import os
from datetime import datetime
from io import StringIO
from pathlib import Path
from queue import SimpleQueue as Queue

from guapow import __app_name__


class LocalQueueHandler(logging.handlers.QueueHandler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.enqueue(record)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.handleError(record)


class FilePathFilter(logging.Filter):

    def filter(self, record):
        record.module_path = record.pathname.split('site-packages/')[1] if 'site-packages' in record.pathname else str(record.pathname)
        return True


def _setup_logger_as_async(logger: logging.Logger):
    queue = Queue()
    logger.addHandler(LocalQueueHandler(queue))

    handlers = []
    for h in logger.handlers[:]:
        if not isinstance(h, LocalQueueHandler):
            handlers.append(h)
            logger.removeHandler(h)

    listener = logging.handlers.QueueListener(
        queue, *handlers, respect_handler_level=True
    )
    listener.start()


def get_log_format(level: int, service: bool) -> str:
    log_format = StringIO()

    if not service:
        log_format.write('%(asctime)s ')

    if level == logging.DEBUG:
        log_format.write('[%(module_path)s:%(lineno)s] ')

    log_format.write('%(message)s')
    log_format.seek(0)
    return log_format.read()


def new_logger(name: str, service: bool, enabled: bool, write_to_file: bool, threaded: bool = True, level: int = logging.INFO) -> logging.Logger:
    instance = logging.Logger(name, level=level)

    instance.addFilter(FilePathFilter())

    if enabled and write_to_file:
        log_dir = f'{Path.home()}/.local/share/{__app_name__}/log'
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        now = datetime.now()
        handler = logging.FileHandler(f"{log_dir}/{now.strftime('%Y-%m-%d')}-{int(now.timestamp() * 1000000)}.log")
    else:
        handler = logging.StreamHandler()

    handler.setFormatter(logging.Formatter(get_log_format(level, service)))
    instance.addHandler(handler)
    instance.disabled = not enabled

    if threaded:
        _setup_logger_as_async(instance)

    return instance


def get_log_level(var_name: str) -> int:
    try:
        level = os.getenv(var_name, 'INFO').upper().strip()

        if level and hasattr(logging, level):
            return getattr(logging, level)
        else:
            return logging.INFO
    except ValueError:
        return logging.INFO
