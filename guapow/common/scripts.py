import os
from logging import Logger
from typing import Optional, List, Dict, Set

from guapow.common.model import ScriptSettings
from guapow.common.system import run_async_process, ProcessTimedOutError
from guapow.common.users import is_root_user


class RunScripts:

    def __init__(self, name: str, root_allowed: bool, logger: Logger):
        self._name = name
        self._log = logger
        self.root_allowed = root_allowed

    @staticmethod
    def get_environ(env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        final_env = env if env else dict(os.environ)

        if 'DISPLAY' not in final_env:
            final_env['DISPLAY'] = ':0'

        return final_env

    async def _execute_scripts(self, settings: ScriptSettings, user_id: Optional[int] = None,
                               user_env: Optional[Dict[str, str]] = None) -> Set[int]:
        pids = set()
        env = self.get_environ(user_env)

        valid_timeout = settings.has_valid_timeout()

        if not valid_timeout and settings.timeout is not None:
            self._log.warning(f"Invalid {self._name} scripts timeout defined: {settings.timeout}. "
                              f"No script will be awaited")

        should_wait = settings.wait_execution or valid_timeout

        for cmd in settings.scripts:
            self._log.info(f"{'Waiting' if should_wait else 'Starting'} {self._name} script: {cmd}")
            try:
                pid, _, output = await run_async_process(cmd=cmd, user_id=user_id, custom_env=env,
                                                         wait=settings.wait_execution, timeout=settings.timeout,
                                                         output=False)

                if pid is not None:
                    pids.add(pid)
                    if should_wait:
                        self._log.info(f"{self._name.capitalize()} script finished: {cmd} (pid={pid})")
                else:
                    err_output = f": {output}" if output else ""
                    self._log.error(f"Unexpected error when running {self._name} script '{cmd}'{err_output}")
            except ProcessTimedOutError as e:
                self._log.warning(f"{self._name.capitalize()} script '{cmd}' timed out (pid={e.pid})")

        return pids

    async def run(self, scripts: List[ScriptSettings], user_id: Optional[int],
                  user_env: Optional[Dict[str, str]]) -> Set[int]:
        current_user_id = os.getuid()
        root_user = is_root_user(current_user_id)

        pids = set()

        for settings in scripts:
            if root_user:
                if not settings.run_as_root and user_id is not None and not is_root_user(user_id):
                    pids.update(await self._execute_scripts(settings, user_id, user_env))
                elif self.root_allowed:
                    pids.update(await self._execute_scripts(settings))
                else:
                    self._log.warning(f"{self._name.capitalize()} scripts {settings.scripts} are not allowed "
                                      f"to run at the root level")
            elif settings.run_as_root:
                self._log.warning(f"Cannot execute {self._name} scripts {settings.scripts} as root user")
            elif user_id is None:
                pids.update(await self._execute_scripts(settings))
            elif current_user_id == user_id:
                pids.update(await self._execute_scripts(settings, user_env=user_env))
            else:
                self._log.warning(f"Cannot execute {self._name} scripts {settings.scripts} as user {user_id}")

        return pids
