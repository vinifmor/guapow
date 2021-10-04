import os
import shutil

from guapow.common import system


def is_available() -> bool:
    return bool(shutil.which('systemd-notify')) and os.getenv('NOTIFY_SOCKET')


async def notify_ready() -> bool:
    code, _ = await system.async_syscall("systemd-notify --ready", return_output=False)
    return code == 0

