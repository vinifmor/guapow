import asyncio
import re
import time
from logging import Logger
from typing import Dict, Optional, Tuple

from guapow.common import network
from guapow.common.config import OptimizerConfig
from guapow.common.dto import OptimizationRequest
from guapow.service.watcher import mapping
from guapow.service.watcher.config import ProcessWatcherConfig
from guapow.service.watcher.mapping import RegexMapper
from guapow.service.watcher.util import map_processes


class ProcessWatcherContext:

    def __init__(self, user_id: int, user_name: str, user_env: Dict[str, str], logger: Logger,
                 optimized: Dict[int, str], opt_config: OptimizerConfig, watch_config: ProcessWatcherConfig,
                 mapping_file_path: str, machine_id: Optional[str]):
        self.user_id = user_id
        self.user_name = user_name
        self.user_env = user_env
        self.logger = logger
        self.optimized = optimized  # keeps the state of which processes were optimized to avoid sending duplicate requests
        self.opt_config = opt_config
        self.watch_config = watch_config
        self.mapping_file_path = mapping_file_path
        self.machine_id = machine_id


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
        self._last_file_found_log: Optional[bool] = None  # controls repetitive file found logs

    async def _read_mappings(self) -> Optional[Tuple[Dict[str, str], Optional[Dict[re.Pattern, str]], Optional[Dict[re.Pattern, str]]]]:
        if self._mapping_cached:
            if self._mappings:
                return self._mappings, self._cmd_patterns, self._comm_patterns
        else:
            file_found, mappings = await mapping.read(file_path=self._context.mapping_file_path, logger=self._log, last_file_found_log=self._last_file_found_log)
            self._last_file_found_log = file_found

            pattern_mappings = self._regex_mapper.map(mappings)
            cmd_patterns, comm_patterns = (pattern_mappings[0], pattern_mappings[1]) if pattern_mappings else (None, None)

            if self._context.watch_config.mapping_cache:
                self._mappings, self._cmd_patterns, self._comm_patterns = mappings, cmd_patterns, comm_patterns
                self._mapping_cached = True

            return mappings, cmd_patterns, comm_patterns

    async def check_mappings(self):
        mapping_tuple = await self._read_mappings()

        if not mapping_tuple or not mapping_tuple[0]:
            return

        mappings, cmd_patterns, comm_patterns = mapping_tuple[0], mapping_tuple[1], mapping_tuple[2]
        
        procs = await map_processes()

        if not procs:
            self._log.warning('No processes alive')
            self._context.optimized.clear()
            return

        tasks = []
        for pid, cmd_comm in procs.items():
            previously_optimized_cmd = self._context.optimized.get(pid)

            if previously_optimized_cmd and (previously_optimized_cmd == cmd_comm[0] or previously_optimized_cmd == cmd_comm[1]):
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

        if self._context.optimized:  # removing dead processes from the context
            pids_alive = procs.keys()
            for pid in {*self._context.optimized.keys()}:
                if pid not in pids_alive:
                    del self._context.optimized[pid]

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
