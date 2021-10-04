import asyncio
import os
import re
import shutil
from asyncio import Lock
from io import StringIO
from logging import Logger
from re import Pattern
from typing import Optional, Tuple, Dict

from guapow.common import system
from guapow.common.system import find_process_by_name, async_syscall


class MouseCursorManager:

    def __init__(self, logger: Logger, renicing: bool = True, cursor_hidden: Optional[bool] = None):
        self._log = logger
        self._lock = Lock()
        self._re_process_pattern: Optional[Pattern] = None
        self._process_name = 'unclutter'
        self._cursor_hidden = cursor_hidden
        self._renicing = renicing

    def _gen_custom_env(self, user_env: Optional[Dict[str, str]]):
        env = {**user_env} if user_env else dict(os.environ)

        display = env.get('DISPLAY', '').strip()

        if not display:
            env['DISPLAY'] = ':0'

        return env

    def _get_matching_pattern(self) -> Pattern:
        if self._re_process_pattern is None:
            self._re_process_pattern = re.compile(r'^{}$'.format(self._process_name))

        return self._re_process_pattern

    def can_work(self) -> Tuple[bool, Optional[str]]:
        if not shutil.which(self._process_name):
            return False, f"'{self._process_name}' is not installed. It will not be possible to hide the mouse cursor"

        return True, None

    async def _renice_process(self):
        pids_found = await system.find_pids_by_names(names=(self._process_name,), last_match=True)
        pid = pids_found.get(self._process_name) if pids_found else None
        if pid:
            try:
                os.setpriority(os.PRIO_PROCESS, pid, 1)
                self._log.debug(f"'{self._process_name}' reniced to '1'")
            except Exception as e:
                self._log.warning(f"Could not renice '{self._process_name}'. Exception class: {e.__class__.__name__}")
        else:
            self._log.warning(f"Could not renice '{self._process_name}': process not found")

    async def hide_cursor(self, user_request: bool, user_env: Optional[Dict[str, str]]) -> bool:
        async with self._lock:
            hidden = bool(await find_process_by_name(self._get_matching_pattern()))

            if hidden:
                self._log.warning("Mouse cursor is already hidden")

                if self._cursor_hidden is None:  # it means unclutter was initialized by a different process
                    self._cursor_hidden = False

                return False
            else:
                cmd = 'unclutter --timeout 1 -b'
                self._log.debug(f"Hiding the mouse cursor: {cmd}")
                exitcode, _ = await async_syscall(cmd, custom_env=self._gen_custom_env(user_env), return_output=False)

                if exitcode == 0:
                    self._log.info("Mouse cursor hidden")
                    self._cursor_hidden = user_request

                    if self._renicing:
                        asyncio.get_event_loop().create_task(self._renice_process())

                    return True
                else:
                    self._log.error(f"Could not hide the mouse cursor: {self._process_name} returned an unexpected code ({exitcode})")
                    return False

    async def is_cursor_hidden(self) -> Optional[bool]:
        async with self._lock:
            return self._cursor_hidden

    async def show_cursor(self) -> Optional[bool]:
        async with self._lock:
            if await find_process_by_name(self._get_matching_pattern()):
                exitcode, output = await system.async_syscall(f'killall {self._process_name}')

                if exitcode == 0:
                    self._log.info("Displaying mouse cursor")
                    self._cursor_hidden = None  # resetting initial state
                    return True
                else:
                    msg = StringIO()
                    msg.write(f"Could not display mouse cursor. Not all '{self._process_name}' instances could be killed")

                    if output:
                        msg.write(': {}'.format(' '.join(output.split('\n'))))

                    msg.seek(0)
                    self._log.error(msg.read())
                    return False
            else:
                self._log.info(f"Mouse cursor is already being displayed: '{self._process_name}' is not running")
                self._cursor_hidden = None  # resetting initial state
                return True
