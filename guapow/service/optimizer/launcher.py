import asyncio
import re
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from logging import Logger
from typing import Dict, Optional, Tuple, List, Generator

import aiofiles

from guapow import __app_name__
from guapow.common import util, system, steam
from guapow.common.dto import OptimizationRequest
from guapow.common.model import CustomEnum
from guapow.common.steam import get_exe_name
from guapow.common.users import is_root_user
from guapow.service.optimizer.profile import OptimizationProfile

DELIMITER = '%'


class LauncherSearchMode(CustomEnum):
    NAME = 'n'
    COMMAND = 'c'

    @classmethod
    def map_string(cls, string: str) -> "LauncherSearchMode":
        return LauncherSearchMode.COMMAND if string.startswith('/') else LauncherSearchMode.NAME


def gen_possible_launchers_file_paths(user_id: int, user_name: str) -> Generator[str, None, None]:
    if not is_root_user(user_id):
        yield f'/home/{user_name}/.config/{__app_name__}/launchers'

    yield f'/etc/{__app_name__}/launchers'


def map_target(string: str, mapping: str, logger: Logger) -> Optional[Tuple[str, LauncherSearchMode]]:
    string_split = string.split(DELIMITER, 1)

    if len(string_split) > 1:
        mode_str = string_split[0].strip()
        mode = LauncherSearchMode.from_value(mode_str.lower())

        if not mode:
            mode = LauncherSearchMode.map_string(string)
            logger.warning(f"Invalid launcher target '{mode_str}' for mapping: {mapping}. Default type '{mode.value}' will be considered")

        return string_split[1].strip(), mode
    else:
        return string, LauncherSearchMode.map_string(string)


def map_launchers_dict(launchers: dict, logger: Logger) -> Optional[Dict[str, Tuple[str, LauncherSearchMode]]]:
    if launchers:
        res = {}
        for launcher, target in launchers.items():
            launcher_strip = launcher.strip()

            if not launcher_strip:
                continue

            target_strip = target.strip()

            if not target_strip:
                continue

            res[launcher_strip] = map_target(target_strip, f'{launcher}{DELIMITER}{target}', logger)

        return res if res else None


async def map_launchers_file(wrapper_file: str, logger: Logger) -> Optional[Dict[str, Tuple[str, LauncherSearchMode]]]:
    wrappers = {}

    async with aiofiles.open(wrapper_file) as f:
        async for line in f:
            line_strip = line.strip()

            if line_strip and not line_strip.startswith('#'):
                line_split = line_strip.split('#', 1)[0].split('=', 1)

                if len(line_split) == 2:
                    key = line_split[0].strip()

                    if key:
                        val = line_split[1].strip()

                        if val:
                            wrappers[key] = map_target(val, line_strip, logger)

    return wrappers


class LauncherMapper(ABC):

    def __init__(self, check_time: float, logger: Logger):
        self._log = logger
        self._check_time = check_time

    @abstractmethod
    async def map_pid(self, request: OptimizationRequest, profile: OptimizationProfile) -> Optional[int]:
        pass


class ExplicitLauncherMapper(LauncherMapper):
    """
    For mappings declared in the 'launchers' file
    """

    def __init__(self, wait_time: float, logger: Logger):
        super(ExplicitLauncherMapper, self).__init__(check_time=wait_time, logger=logger)

    async def _find_wrapped_process(self, wrapped_target: Tuple[str, LauncherSearchMode], launcher: str) -> Optional[int]:
        wrapped_name, search_mode = wrapped_target[0], wrapped_target[1]
        wrapped_regex = util.map_any_regex(wrapped_name)
        wrapped_regexes = {wrapped_regex}
        self._log.debug(f"Looking for mapped process with {search_mode.name.lower()} '{wrapped_name}' (launcher={launcher})")

        time_init = datetime.now()
        time_limit = time_init + timedelta(seconds=self._check_time)

        while datetime.now() < time_limit:
            if search_mode == LauncherSearchMode.COMMAND:
                wrapped_proc = await system.find_process_by_command(wrapped_regexes, last_match=True)
            else:
                wrapped_proc = await system.find_process_by_name(wrapped_regex, last_match=True)

            if wrapped_proc is not None:
                find_time = (datetime.now() - time_init).total_seconds()
                pid_found, name_found = wrapped_proc[0], wrapped_proc[1]
                self._log.info(f"Mapped process '{name_found}' ({pid_found}) found in {find_time:.2f} seconds")
                return pid_found
            else:
                await asyncio.sleep(0.001)

        find_time = (datetime.now() - time_init).total_seconds()
        self._log.warning(f"Could not find process with {search_mode.name.lower()} '{wrapped_name}' (launcher={launcher}). Timed out in {find_time:.2f} seconds")

    async def map_pid(self, request: OptimizationRequest, profile: OptimizationProfile) -> Optional[int]:
        if profile.launcher and profile.launcher.skip_mapping:
            self._log.info(f"Skipping launcher mapping for {profile.get_log_str()} (pid: {request.pid})")
            return

        if profile.launcher and profile.launcher.mapping:
            self._log.debug(f"Checking mapped launchers for {profile.get_log_str()} (pid: {request.pid})")
            launchers = map_launchers_dict(launchers=profile.launcher.mapping, logger=self._log)
        else:
            launchers = None

            for file_path in gen_possible_launchers_file_paths(request.user_id, request.user_name):
                try:
                    self._log.debug(f"Checking mapped launchers on '{file_path}' (request: {request.pid})")
                    launchers = await map_launchers_file(file_path, self._log)
                    break
                except FileNotFoundError:
                    self._log.debug(f"Launchers file '{file_path}' not found (request: {request.pid})")

        if launchers:
            file_name = request.command.split('/')[-1].strip()

            wrapped_target = launchers.get(file_name)

            if not wrapped_target:  # if there is no exact match, check any name with regex
                for name, real_name in launchers.items():
                    if '*' in name:
                        if util.map_any_regex(name).match(file_name):
                            wrapped_target = real_name
                            break

            if wrapped_target:
                return await self._find_wrapped_process(wrapped_target, file_name)

        else:
            self._log.debug("No valid launchers mapped found")


class SteamLauncherMapper(LauncherMapper):

    def __init__(self, wait_time: float, logger: Logger):
        super(SteamLauncherMapper, self).__init__(check_time=wait_time, logger=logger)

    async def map_pid(self, request: OptimizationRequest, profile: OptimizationProfile) -> Optional[int]:
        if profile.steam:
            steam_cmd = steam.get_steam_runtime_command(request.command)

            if not steam_cmd:
                self._log.warning(f'Command not from Steam: {request.command} (pid: {request.pid})')
                return

            self._log.debug(f'Steam command detected (pid: {request.pid}): {request.command}')

            proton_name_and_paths = steam.get_proton_exec_name_and_paths(steam_cmd)

            if proton_name_and_paths:
                cmd_patterns = {re.compile(r'^{}$'.format(re.escape(cmd))) for cmd in proton_name_and_paths[1:]}
            else:
                cmd_patterns = {re.compile(r'(/bin/\w+\s+)?{}'.format(re.escape(steam_cmd)))}  # native games

            cmd_logs = ', '.join(p.pattern for p in cmd_patterns)
            self._log.debug(f'Looking for a Steam process matching one of the command patterns (pid: {request.pid}): {cmd_logs}')

            time_init = datetime.now()
            time_limit = time_init + timedelta(seconds=self._check_time)
            while datetime.now() < time_limit:
                proc_found = await system.find_process_by_command(cmd_patterns, last_match=True)
                find_time = (datetime.now() - time_init).total_seconds()

                if proc_found is not None:
                    self._log.info(f"Steam process '{proc_found[1]}' ({proc_found[0]}) found in {find_time:.2f} seconds")
                    return proc_found[0]
                else:
                    await asyncio.sleep(0.001)

            find_time = (datetime.now() - time_init).total_seconds()
            self._log.warning(f'Could not find a Steam process matching command patterns (pid: {request.pid}). Search timed out in {find_time:.2f} seconds')

            if proton_name_and_paths:
                proc_name = proton_name_and_paths[0]
            else:
                proc_name = get_exe_name(steam_cmd)

            if not proc_name:
                self._log.warning(f'Name of launched Steam command could not be determined (request={request.pid}). No extra search will be performed.')
            else:
                self._log.debug(f"Trying to find Steam process by name '{proc_name}' (request: {request.pid})")
                ti = time.time()
                proc_found = await system.find_process_by_name(re.compile(r'^{}$'.format(proc_name)), last_match=True)
                tf = time.time()

                if proc_found:
                    self._log.info(f"Steam process named '{proc_found[0]}' ({proc_found[1]}) found in {tf - ti:.2f} seconds")
                    return proc_found[0]
                else:
                    self._log.warning(f'Could not find a Steam process named {proc_name} (request={request.pid})')


class LauncherMapperManager(LauncherMapper):

    def __init__(self, check_time: float, logger: Logger, mappers: Optional[List[LauncherMapper]] = None):
        super(LauncherMapperManager, self).__init__(check_time, logger)

        if mappers:
            self._sub_mappers = mappers
        else:
            self._sub_mappers = [cls(check_time, logger) for cls in LauncherMapper.__subclasses__() if cls != self.__class__]

    async def map_pid(self, request: OptimizationRequest, profile: OptimizationProfile) -> Optional[int]:
        for mapper in self._sub_mappers:
            real_id = await mapper.map_pid(request, profile)

            if real_id:
                return real_id

    def get_sub_mappers(self) -> Optional[List[LauncherMapper]]:
        if self._sub_mappers is not None:
            return [*self._sub_mappers]
