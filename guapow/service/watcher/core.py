import asyncio
import re
import time
from asyncio import create_task
from logging import Logger
from typing import Dict, Optional, Tuple, Set, Any, Union

from guapow.common import network
from guapow.common.config import OptimizerConfig
from guapow.common.dto import OptimizationRequest
from guapow.service.watcher import mapping, ignored
from guapow.service.watcher.config import ProcessWatcherConfig
from guapow.service.watcher.patterns import RegexMapper, RegexType
from guapow.service.watcher.util import map_processes


class ProcessWatcherContext:

    def __init__(self, user_id: int, user_name: str, user_env: Dict[str, str], logger: Logger,
                 optimized: Dict[int, str], opt_config: OptimizerConfig, watch_config: ProcessWatcherConfig,
                 mapping_file_path: str, machine_id: Optional[str], ignored_file_path: str,
                 ignored_procs: Dict[Union[str, re.Pattern], Set[str]]):
        self.user_id = user_id
        self.user_name = user_name
        self.user_env = user_env
        self.logger = logger
        self.optimized = optimized  # keeps the state of which processes were optimized to avoid sending duplicate requests
        self.opt_config = opt_config
        self.watch_config = watch_config
        self.mapping_file_path = mapping_file_path
        self.machine_id = machine_id
        self.ignored_file_path = ignored_file_path
        self.ignored_procs = ignored_procs


class ProcessWatcher:

    def __init__(self, regex_mapper: RegexMapper, context: ProcessWatcherContext):
        self._context = context
        self._regex_mapper = regex_mapper
        self._log = context.logger

        # cached attributes
        self._mapping_cached = False
        self._mappings: Optional[Dict[str, str]] = None
        self._cmd_patterns: Optional[Dict[re.Pattern, str]] = None
        self._comm_patterns: Optional[Dict[re.Pattern, str]] = None

        self._last_mapping_file_found: Optional[bool] = None  # controls repetitive file found logs
        self._last_ignored_file_found: Optional[bool] = None  # controls repetitive file found logs

        self._ignored_cached = False
        self._ignored_exact_strs: Optional[Set[str]] = None
        self._ignored_cmd_patterns: Optional[Set[re.Pattern]] = None
        self._ignored_comm_patterns: Optional[Set[re.Pattern]] = None

    async def _read_ignored(self) -> Optional[Tuple[Set[str], Optional[Set[re.Pattern]], Optional[Set[re.Pattern]]]]:
        """
        return a tuple with command patterns (cmd) and name patterns (comm)
        """
        if self._ignored_cached:
            if self._ignored_exact_strs:
                return self._ignored_exact_strs, self._ignored_cmd_patterns, self._ignored_comm_patterns
        else:
            file_found, ignored_strs = await ignored.read(file_path=self._context.ignored_file_path, logger=self._log,
                                                          last_file_found_log=self._last_ignored_file_found)
            self._last_ignored_file_found = file_found

            if not self._ignored_cached and self._context.watch_config.ignored_cache:
                self._log.debug("Caching ignored patterns to memory")
                self._ignored_cached = True  # pre-saving the caching state (if enabled)

            if ignored_strs:
                if self._context.watch_config.ignored_cache:  # caching to memory (if enabled)
                    self._ignored_exact_strs = ignored_strs

                patterns = self._regex_mapper.map_collection(ignored_strs)

                cmd_patterns, comm_patterns = None, None

                if patterns:
                    cmd_patterns, comm_patterns = patterns.get(RegexType.CMD), patterns.get(RegexType.COMM)

                    if self._context.watch_config.ignored_cache:  # caching to memory (if enabled)
                        self._ignored_cmd_patterns = cmd_patterns
                        self._ignored_comm_patterns = comm_patterns

                return ignored_strs, cmd_patterns, comm_patterns

    async def _read_mappings(self) -> Optional[Tuple[Dict[str, str], Optional[Dict[re.Pattern, str]], Optional[Dict[re.Pattern, str]]]]:
        if self._mapping_cached:
            if self._mappings:
                return self._mappings, self._cmd_patterns, self._comm_patterns
        else:
            file_found, mappings = await mapping.read(file_path=self._context.mapping_file_path, logger=self._log, last_file_found_log=self._last_mapping_file_found)
            self._last_mapping_file_found = file_found

            pattern_mappings = self._regex_mapper.map_for_profiles(mappings)
            cmd_patterns, comm_patterns = (pattern_mappings[0], pattern_mappings[1]) if pattern_mappings else (None, None)

            if self._context.watch_config.mapping_cache:
                self._mappings, self._cmd_patterns, self._comm_patterns = mappings, cmd_patterns, comm_patterns
                self._mapping_cached = True

            return mappings, cmd_patterns, comm_patterns

    def _map_ignored_id(self, pid: int, comm: str) -> str:
        return f'{pid}:{comm}'

    def _is_ignored(self, ignored_id: str) -> bool:
        if self._context.ignored_procs:
            for ignored_ids in self._context.ignored_procs.values():
                if ignored_id in ignored_ids:
                    return True

        return False

    def _clean_old_ignore_patterns(self, ignored_exact: Set[str], current_cmd_patterns: Optional[Set[re.Pattern]],
                                   current_comm_patterns: Optional[Set[re.Pattern]]):
        if self._context.ignored_procs:
            all_patterns = (ignored_exact, current_cmd_patterns, current_comm_patterns)
            to_remove = set()
            for pattern in self._context.ignored_procs:
                found = False
                for patterns in all_patterns:
                    if patterns and pattern in patterns:
                        found = True
                        break

                if not found:
                    to_remove.add(pattern)

            if to_remove:
                self._log.debug(f"Cleaning old ignored patterns from context: {', '.join(str(p) for p in to_remove)}")
                for pattern in to_remove:
                    del self._context.ignored_procs[pattern]

    def _matches_ignored(self, cmd_com: Tuple[str, str], ignored_exact: Set[str],
                         cmd_patterns: Optional[Set[re.Pattern]], comm_patterns: Optional[Set[re.Pattern]],
                         ignored_id: str) -> bool:

        if ignored_exact or cmd_patterns or comm_patterns:
            for idx, cmd in enumerate(cmd_com):  # 0: cmd, 1: comm
                matched_pattern = None
                if ignored_exact and cmd in ignored_exact:  # exact matches have higher priority than patterns
                    matched_pattern = cmd
                else:
                    regex_ignored = cmd_patterns if idx == 0 else comm_patterns

                    if regex_ignored:
                        for pattern in regex_ignored:
                            if pattern.match(cmd):
                                matched_pattern = pattern
                                break

                if matched_pattern:
                    ignored_ids = self._context.ignored_procs.get(matched_pattern)

                    if ignored_ids is None:
                        ignored_ids = set()
                        self._context.ignored_procs[matched_pattern] = ignored_ids

                    ignored_ids.add(ignored_id)
                    return True

        return False

    async def check_mappings(self):
        mapping_tuple = await self._read_mappings()

        if not mapping_tuple or not mapping_tuple[0]:
            return

        mappings, cmd_patterns, comm_patterns = mapping_tuple[0], mapping_tuple[1], mapping_tuple[2]

        task_map_procs, task_ignored = create_task(map_processes()), create_task(self._read_ignored())

        procs = await task_map_procs

        if not procs:
            self._log.warning('No processes alive')
            self._context.optimized.clear()
            return

        ignored_exact, ignored_cmd, ignored_comm = None, None, None
        ignored_patterns = await task_ignored

        if ignored_patterns:
            ignored_exact, ignored_cmd, ignored_comm = ignored_patterns

        self._clean_old_ignore_patterns(ignored_exact, ignored_cmd, ignored_comm)

        tasks = []
        for pid, cmd_comm in procs.items():
            ignored_id = self._map_ignored_id(pid, cmd_comm[1])

            if self._is_ignored(ignored_id):
                continue

            previously_optimized_cmd = self._context.optimized.get(pid)

            if previously_optimized_cmd and (previously_optimized_cmd == cmd_comm[0] or previously_optimized_cmd == cmd_comm[1]):
                continue

            if self._matches_ignored(cmd_comm, ignored_exact, ignored_cmd, ignored_comm, ignored_id):
                self._log.info(f"Ignoring process (pid: {pid}, name: {cmd_comm[1]})")
                continue

            for idx, cmd in enumerate(cmd_comm):  # 0: cmd, 1: comm
                profile = mappings.get(cmd)  # exact matches have higher priority than patterns
                if profile:
                    tasks.append(self.send_request(pid, cmd_comm[0], cmd, profile))
                    break  # 'cmd' has higher priority than 'comm'
                else:
                    regex_mapping = cmd_patterns if idx == 0 else comm_patterns

                    if regex_mapping:
                        matches = dict()
                        for pattern, patter_profile in regex_mapping.items():
                            if pattern.match(cmd):
                                matches[pattern.pattern] = patter_profile

                        if matches:
                            match_profile = matches[max(matches.keys())]  # retrieves the more specific match by length
                            tasks.append(self.send_request(pid, cmd_comm[0], cmd, match_profile))
                            break

        if tasks:
            await asyncio.gather(*tasks)

        self._clean_dead_processes_from_context(procs)

    def _clean_dead_processes_from_context(self, current_processes: Dict[int, Any]):
        if self._context.optimized:
            pids_alive = current_processes.keys()
            for pid in {*self._context.optimized.keys()}:
                if pid not in pids_alive:
                    del self._context.optimized[pid]

        if self._context.ignored_procs:
            pids_alive = current_processes.keys()
            patterns_to_remove = set()
            for pattern, ignored_ids in self._context.ignored_procs.items():
                to_remove = set()
                for id_ in ignored_ids:
                    if int(id_.split(':')[0]) not in pids_alive:
                        to_remove.add(id_)

                if to_remove:
                    self._log.debug(f"Removing dead pids from ignored context: {', '.join(f'{p}' for p in to_remove)}")
                    ignored_ids.difference_update(to_remove)

                    if not ignored_ids:
                        patterns_to_remove.add(pattern)

            if patterns_to_remove:
                for pattern in patterns_to_remove:
                    del self._context.ignored_procs[pattern]

    async def send_request(self, pid: int, command: str, match: str, profile: str):
        request = OptimizationRequest(pid=pid, command=command, created_at=time.time(),
                                      user_name=self._context.user_name, user_env=self._context.user_env,
                                      profile=profile)
        request.created_at = time.time()
        await network.send(request, self._context.opt_config, self._context.machine_id, self._log)
        self._context.optimized[pid] = match

    async def watch(self):
        while True:
            await self.check_mappings()
            await asyncio.sleep(self._context.watch_config.check_interval)
