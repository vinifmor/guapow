import asyncio
import re
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from logging import Logger
from typing import Dict, Optional, Tuple, Generator, AsyncGenerator, Pattern, Set, List

import aiofiles

from guapow import __app_name__
from guapow.common import util
from guapow.common.dto import OptimizationRequest
from guapow.common.model import CustomEnum
from guapow.common.system import async_syscall, map_processes_by_parent, find_process_children
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
    """
    Responsible for mapping the real processes to be optimized since a source process.
    """

    def __init__(self, check_time: float, found_check_time: float, logger: Logger):
        """
        Args:
            check_time: the maximum amount of time the mapper should be looking for a match (seconds)
            found_check_time:
                the maximum amount of time the mapper should be still looking for matches after some already found
                (seconds)
            logger:
        """
        self._log = logger
        self._check_time = check_time
        self._found_check_time = found_check_time

    @abstractmethod
    async def map_pids(self, request: OptimizationRequest, profile: OptimizationProfile) -> AsyncGenerator[int, None]:
        pass


class ExplicitLauncherMapper(LauncherMapper):
    """
    For mappings declared in the 'launchers' file
    """

    def __init__(self, check_time: float, found_check_time: float, logger: Logger,
                 iteration_sleep_time: float = 0.1):
        super(ExplicitLauncherMapper, self).__init__(check_time=check_time,
                                                     found_check_time=found_check_time,
                                                     logger=logger)
        self._iteration_sleep_time = iteration_sleep_time

    @staticmethod
    async def map_process_by_pid(mode: LauncherSearchMode, ignore: Set[int]) -> Optional[Dict[int, str]]:
        if mode:
            mode_str = "a" if mode == LauncherSearchMode.COMMAND else "c"
            exitcode, output = await async_syscall(f'ps -Ao "%p#%{mode_str}" -ww --no-headers')

            if exitcode == 0 and output:
                pid_comm = dict()

                for line in output.split("\n"):
                    line_strip = line.strip()

                    if line_strip:
                        line_split = line_strip.split('#', 1)

                        if len(line_split) > 1:
                            try:
                                pid = int(line_split[0])
                            except ValueError:
                                continue

                            if pid in ignore:
                                continue

                            pid_comm[pid] = line_split[1].strip()

                return pid_comm

    async def find_wrapped_process(self, wrapped_target: Tuple[str, LauncherSearchMode], launcher: str,
                                   source_pid: int) -> AsyncGenerator[int, None]:
        wrapped_name, search_mode = wrapped_target[0].strip(), wrapped_target[1]
        wrapped_regex = util.map_any_regex(wrapped_name)
        self._log.debug(f"Looking for mapped process with {search_mode.name.lower()} '{wrapped_name}' "
                        f"(launcher={launcher})")

        latest_found_timeout = None
        found = set()
        time_init = datetime.now()
        timeout = time_init + timedelta(seconds=self._check_time)
        while datetime.now() < timeout:
            if latest_found_timeout and datetime.now() >= latest_found_timeout:
                self._log.debug(f"Launcher mapping search timed out earlier (source_pid={source_pid})")
                return

            pid_process = await self.map_process_by_pid(search_mode, ignore=found)

            if pid_process:
                for pid, command in pid_process.items():
                    if wrapped_regex.match(command):
                        if self._found_check_time >= 0:
                            latest_found_timeout = datetime.now() + timedelta(seconds=self._found_check_time)

                        self._log.info(f"Mapped process '{command}' ({pid}) found")
                        yield pid
                        found.add(pid)

            if self._iteration_sleep_time > 0:
                await asyncio.sleep(self._iteration_sleep_time)

        if not found:
            timeout_secs = (datetime.now() - time_init).total_seconds()
            self._log.warning(f"Could not find process with {search_mode.name.lower()} '{wrapped_name}' "
                              f"(launcher={launcher}, source_pid={source_pid}). "
                              f"Timed out in {timeout_secs:.2f} seconds")

    async def map_pids(self, request: OptimizationRequest, profile: OptimizationProfile) -> AsyncGenerator[int, None]:
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
                async for pid in self.find_wrapped_process(wrapped_target, file_name, request.pid):
                    yield pid

        else:
            self._log.debug("No valid launchers mapped found")


class SteamLauncherMapper(LauncherMapper):

    def __init__(self, check_time: float, found_check_time: float, logger: Logger,
                 iteration_sleep_time: float = 0.1):
        super(SteamLauncherMapper, self).__init__(check_time=check_time,
                                                  found_check_time=found_check_time,
                                                  logger=logger)
        self._re_steam_cmd: Optional[Pattern] = None
        self._to_ignore: Optional[Set[str]] = None  # processes that should not be optimized
        self._re_proton_command: Optional[Pattern] = None
        self._iteration_sleep_time = iteration_sleep_time  # used to avoid CPU overloading while looking for targets

    @property
    def re_steam_cmd(self) -> Pattern:
        if not self._re_steam_cmd:
            self._re_steam_cmd = re.compile(r'^.+/(\w+)\s+SteamLaunch\s+.+', re.IGNORECASE)

        return self._re_steam_cmd

    @property
    def re_proton_command(self) -> Pattern:
        if not self._re_proton_command:
            self._re_proton_command = re.compile(r'^.+/proton\s+waitforexitandrun\s+.+$', re.IGNORECASE)

        return self._re_proton_command

    @property
    def to_ignore(self) -> Set[str]:
        if self._to_ignore is None:
            self._to_ignore = {"wineserver", "services.exe", "winedevice.exe", "plugplay.exe", "svchost.exe",
                               "explorer.exe", "rpcss.exe", "tabtip.exe", "wine", "wine64", "wineboot.exe",
                               "cmd.exe", "conhost.exe", "start.exe", "steam-runtime-l", "proton", "gzip",
                               "steam.exe", "python", "python3", "OriginWebHelper", "Origin.exe",
                               "OriginClientSer", "QtWebEngineProc", "EASteamProxy.ex", "ActivationUI.ex",
                               "EALink.exe", "OriginLegacyCLI", "IGOProxy.exe", "IGOProxy64.exe", "igoproxy64.exe",
                               "ldconfig", "UPlayBrowser.exe", "UbisoftGameLaun", "upc.exe", "UplayService.ex",
                               "UplayWebCore.ex", "CrRendererMain", "regsvr32", "CrGpuMain", "CrUtilityMain",
                               "whql:off", "PnkBstrA.exe"}

        return self._to_ignore

    def find_target_in_hierarchy(self, reverse_hierarchy: List[str], root_element_pid: int,
                                 processes_by_parent: Optional[Dict[int, Set[Tuple[int, str]]]] = None,
                                 pid_by_comm: Optional[Dict[str, int]] = None) -> Optional[int]:

        if len(reverse_hierarchy) == 1:
            return root_element_pid

        comm_pid = dict() if pid_by_comm is None else pid_by_comm

        if reverse_hierarchy[-1] not in comm_pid:
            comm_pid[reverse_hierarchy[-1]] = root_element_pid

        for idx, comm in enumerate(reverse_hierarchy):
            pid = comm_pid.get(comm)

            if pid is None:
                parent_id = comm_pid.get(reverse_hierarchy[idx + 1])

                if not parent_id:
                    continue  # the iteration must continue if the parent id is not mapped yet

                parent_children = processes_by_parent.get(parent_id)

                if not parent_children:
                    return   # if the parent has no children, it will not be possible to find the current comm's pid

                try:
                    pid = next(pid_ for pid_, comm_ in sorted(parent_children, reverse=True) if comm_ == comm)
                except StopIteration:
                    return  # the current comm could not be found, so stop the iteration

                comm_pid[comm] = pid

            if idx == 0:  # if current element is the target, return it immediately
                return pid

            # restart the find
            return self.find_target_in_hierarchy(reverse_hierarchy=reverse_hierarchy,
                                                 root_element_pid=root_element_pid,
                                                 processes_by_parent=processes_by_parent,
                                                 pid_by_comm=comm_pid)

    def map_expected_hierarchy(self, request: OptimizationRequest, root_comm: Optional[str] = None) -> List[str]:
        hierarchy = list()

        if "/steamapps/common/SteamLinux" in request.command:
            self._log.debug(f"Steam command comes from container (pid: {request.pid})")
            hierarchy.append("pressure-vessel")
            hierarchy.append("pv-bwrap")
        elif self.re_proton_command.match(request.command):
            hierarchy.append("python3")

        if root_comm:
            hierarchy.append(root_comm)

        return hierarchy

    def extract_root_process_name(self, command: str) -> str:
        root_cmd = self.re_steam_cmd.findall(command)

        if root_cmd:
            return root_cmd[0]

    async def map_pids(self, request: OptimizationRequest, profile: OptimizationProfile) -> AsyncGenerator[int, None]:
        if profile.steam:
            steam_root_comm = self.extract_root_process_name(request.command)

            if not steam_root_comm:
                self._log.warning(f'Command not from Steam: {request.command} (pid: {request.pid})')
            else:
                self._log.debug(f'Steam command detected for request (pid: {request.pid})')
                expected_hierarchy = self.map_expected_hierarchy(request, steam_root_comm)
                timeout = datetime.now() + timedelta(seconds=self._check_time)

                latest_found_timeout = None  # timeout for every time a target is found (to stop faster)
                pid_by_comm = dict()  # to save which processes were previously mapped
                already_found: Set[int] = set()  # processes already yielded
                target_ppid = None  # parent with the target children

                to_ignore = {*expected_hierarchy, *self.to_ignore}  # target children to ignore

                while datetime.now() < timeout:
                    if latest_found_timeout and datetime.now() >= latest_found_timeout:
                        self._log.debug(f"Steam subprocesses search timed out earlier (source_pid={request.pid})")
                        return

                    parent_procs = await map_processes_by_parent()

                    if target_ppid is None:
                        target_ppid = self.find_target_in_hierarchy(reverse_hierarchy=expected_hierarchy,
                                                                    root_element_pid=request.pid,
                                                                    processes_by_parent=parent_procs,
                                                                    pid_by_comm=pid_by_comm)
                        if target_ppid is not None:
                            self._log.debug(f"Target Steam process parent found (pid={target_ppid}, "
                                            f"comm={expected_hierarchy[0]}) (source_pid={request.pid})")

                    if target_ppid is not None:
                        for pid_, comm_, ppid_ in find_process_children(ppid=target_ppid,
                                                                        processes_by_parent=parent_procs,
                                                                        already_found=already_found,
                                                                        comm_to_ignore=to_ignore,
                                                                        recursive=False):
                            if self._found_check_time >= 0:
                                latest_found_timeout = datetime.now() + timedelta(seconds=self._found_check_time)

                            self._log.info(f"Steam child process found: {comm_} (pid={pid_}, ppid={ppid_})")
                            yield pid_

                    if self._iteration_sleep_time > 0:
                        await asyncio.sleep(self._iteration_sleep_time)

                self._log.debug(f"Steam subprocesses search timed out (source_pid={request.pid})")


class LauncherMapperManager(LauncherMapper):
    def __init__(self, check_time: float, found_check_time: float,
                 logger: Logger, mappers: Optional[Tuple[LauncherMapper, ...]] = None):
        super(LauncherMapperManager, self).__init__(check_time, found_check_time, logger)

        if mappers:
            self._sub_mappers = mappers
        else:
            sub_classes = LauncherMapper.__subclasses__()
            self._sub_mappers = tuple(cls(check_time, found_check_time, logger) for cls in sub_classes
                                      if cls != self.__class__)

    async def map_pids(self, request: OptimizationRequest, profile: OptimizationProfile) -> AsyncGenerator[int, None]:
        any_mapper_yield = False
        for mapper in self._sub_mappers:
            if any_mapper_yield:  # if any mapper already returned something, stop the iteration
                return

            async for real_id in mapper.map_pids(request, profile):
                if real_id is not None:
                    any_mapper_yield = True
                    yield real_id

    def get_sub_mappers(self) -> Optional[Tuple[LauncherMapper]]:
        if self._sub_mappers is not None:
            return tuple(self._sub_mappers)
