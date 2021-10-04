import asyncio
import datetime
import os
import subprocess
from logging import Logger
from multiprocessing import Process
from typing import Optional, List, Dict, Set

from guapow.common import system
from guapow.common.model import ScriptSettings
from guapow.common.system import run_user_command
from guapow.common.users import is_root_user


class RunScripts:

    def __init__(self, name: str, root_allowed: bool, logger: Logger):
        self._name = name
        self._log = logger
        self.root_allowed = root_allowed

    async def _execute_user_scripts(self, settings: ScriptSettings, user_id: int, user_env: Optional[Dict[str, str]]) -> Set[int]:
        pids = set()

        for cmd in settings.scripts:
            res = system.new_user_process_response()

            self._log.info(f"Running {self._name} script '{cmd}' (user={user_id})")
            p = Process(daemon=True, target=run_user_command, args=(cmd, user_id, settings.wait_execution, settings.timeout, user_env, res))
            p.start()

            if settings.wait_execution or (settings.timeout is not None and settings.timeout > 0):
                self._log.info(f"Waiting {self._name} script '{cmd}' to finish (user={user_id})")

                while p.is_alive():  # to allow other async tasks to execute
                    await asyncio.sleep(0.0005)

                self._log.info(f"{self._name.capitalize()} script '{cmd}' finished (user={user_id})")

            p.join()

            if res['pid'] is not None:
                pids.add(res['pid'])

        return pids

    @staticmethod
    def get_environ(env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        final_env = env if env else dict(os.environ)

        if 'DISPLAY' not in final_env:
            final_env['DISPLAY'] = ':0'

        return final_env

    async def _execute_scripts(self, settings: ScriptSettings, user_env: Optional[Dict[str, str]]) -> Set[int]:
        pids = set()
        env = self.get_environ(user_env)

        for cmd in settings.scripts:
            p = await asyncio.create_subprocess_shell(cmd=cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                                      stderr=subprocess.DEVNULL, env=env)
            pids.add(p.pid)
            self._log.info(f"Started {self._name} script: {cmd} (pid={p.pid})")

            if settings.timeout is not None:
                if not settings.has_valid_timeout():
                    self._log.warning(f"Invalid {self._name} script timeout defined: {settings.timeout}. It will not be awaited")
                    continue

                self._log.info(f"Waiting {self._name} script '{cmd}' to finish (pid={p.pid})")
                timeout = datetime.datetime.now() + datetime.timedelta(seconds=settings.timeout)

                timed_out = True
                while timeout > datetime.datetime.now():
                    if p.returncode is None:
                        await asyncio.sleep(0.001)
                    else:
                        timed_out = False
                        break

                if timed_out:
                    self._log.warning(f"{self._name.capitalize()} script '{cmd}' timed out (pid={p.pid})")

            elif settings.wait_execution:
                self._log.info(f"Waiting {self._name} script '{cmd}' to finish (pid={p.pid})")
                await p.wait()

        return pids

    async def run(self, scripts: List[ScriptSettings], user_id: Optional[int], user_env: Optional[Dict[str, str]]) -> Set[int]:
        current_user_id = os.getuid()
        root_user = is_root_user(current_user_id)

        pids = set()

        for settings in scripts:
            if root_user:
                if not settings.run_as_root and user_id is not None and not is_root_user(user_id):
                    pids.update(await self._execute_user_scripts(settings, user_id, user_env))
                elif self.root_allowed:
                    pids.update(await self._execute_scripts(settings, None))
                else:
                    self._log.warning(f"{self._name.capitalize()} scripts {settings.scripts} are not allowed to run at the root level")
            elif settings.run_as_root:
                self._log.warning(f"Cannot execute {self._name} scripts {settings.scripts} as root user")
            elif user_id is None:
                pids.update(await self._execute_scripts(settings, None))
            elif current_user_id == user_id:
                pids.update(await self._execute_scripts(settings, user_env))
            else:
                self._log.warning(f"Cannot execute {self._name} scripts {settings.scripts} as user {user_id}")

        return pids
