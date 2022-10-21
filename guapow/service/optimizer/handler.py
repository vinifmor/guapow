import asyncio
import os
import time
from asyncio import Task
from datetime import timedelta, datetime
from typing import Optional, Iterable, List

from guapow.common.dto import OptimizationRequest
from guapow.common.profile import get_possible_profile_paths_by_priority, \
    get_default_profile_name
from guapow.common.system import map_processes_by_parent, find_process_children
from guapow.service.optimizer.launcher import LauncherMapperManager
from guapow.service.optimizer.profile import OptimizationProfile, OptimizationProfileReader
from guapow.service.optimizer.task.manager import TasksManager, run_tasks
from guapow.service.optimizer.task.model import OptimizationContext, OptimizedProcess
from guapow.service.optimizer.watch import DeadProcessWatcherManager


class OptimizationHandler:

    def __init__(self, context: OptimizationContext, tasks_man: TasksManager, watcher_man: DeadProcessWatcherManager,
                 profile_reader: OptimizationProfileReader):
        super(OptimizationHandler, self)
        self.context = context
        self._queue = context.queue
        self._log = context.logger
        self._tasks_man = tasks_man
        self._watcher_man = watcher_man
        self._profile_reader = profile_reader
        self._launcher_mapper = LauncherMapperManager(check_time=context.launcher_mapping_timeout,
                                                      found_check_time=context.launcher_mapping_found_timeout,
                                                      logger=context.logger)
    @property
    def children_timeout(self):
        return self.context.search_children_timeout

    @property
    def children_found_timeout(self):
        return self.context.search_children_found_timeout

    async def _read_valid_profile(self, name: str, add_settings: Optional[str], user_id: Optional[int], user_name: Optional[str], request: OptimizationRequest) -> Optional[OptimizationProfile]:
        for file_path in get_possible_profile_paths_by_priority(name=name, user_id=user_id, user_name=user_name):
            if file_path:
                try:
                    return await self._profile_reader.read_valid(profile_path=file_path, add_settings=add_settings,
                                                                 handle_not_found=False)
                except FileNotFoundError:
                    self._log.debug(f"Profile file '{file_path}' not found (request={request.pid})")

    async def _load_valid_profile(self, request: OptimizationRequest) -> Optional[OptimizationProfile]:
        profile = None

        if request.profile:
            profile = await self._read_valid_profile(request.profile, request.profile_config, request.user_id, request.user_name, request)

            if profile:
                self._log.info(f"Valid profile '{profile.name}' ({profile.path}) found (request={request.pid})")

        if not profile:
            profile = await self._read_valid_profile(get_default_profile_name(), request.profile_config, request.user_id, request.user_name, request)

            if profile:
                pre_msg = "No existing/valid profile '{}'. ".format(request.profile) if request.profile else "Request has no profile defined. "
                self._log.warning(f"{pre_msg}Profile '{profile.path}' will be used instead (request={request.pid})")

        return profile

    def map_valid_config(self, config: str) -> Optional[OptimizationProfile]:
        if config:
            profile = self._profile_reader.map(profile_str=config)

            if profile and profile.is_valid():
                return profile

        self._log.warning("No optimization settings defined in configuration: {}".format(config.replace('\n', ' ')))

    async def _handle_process(self, process: OptimizedProcess, proc_tasks: Optional[Iterable[Task]] = None,
                              env_tasks: Optional[Iterable[Task]] = None, mapped: bool = False) -> None:

        await self._queue.add_pid(process.pid)

        if env_tasks:
            self._log.debug(f"Awaiting environment tasks required by process '{process.pid}'")
            await asyncio.gather(*run_tasks(env_tasks, process))

        should_be_watched = process.should_be_watched()

        if should_be_watched:
            self._log.debug(f"Process '{process.pid}' should be watched")
            await self._watcher_man.watch(process)

            if mapped:
                await self._queue.remove_pids(process.source_pid)

        if proc_tasks:
            self._log.debug(f"Awaiting process tasks required by the process '{process.pid}'")
            await asyncio.gather(*run_tasks(proc_tasks, process))

        if not should_be_watched:
            self._log.debug(f"Process '{process.pid}' does not require watching")
            related_pids = process.get_pids()

            if related_pids:
                self._log.debug(f"Disassociating process '{process.pid}' related pids "
                                f"({', '.join(str(p) for p in related_pids)}) from the optimization queue")
                await self._queue.remove_pids(*related_pids)

        request = process.request
        exec_time = time.time() - request.created_at
        self._log.debug(f"Optimization request for process '{process.pid}' took {exec_time:.4f} seconds"
                        f"{f' (source_pid={process.pid})' if request.pid != process.pid else ''}")

    async def optimize_children(self, target_parents: Iterable[OptimizedProcess], env_tasks: Iterable[Task],
                                proc_tasks: Iterable[Task]) -> None:
        already_found = set()  # children already found

        # max time period to end the iteration in case a result is found
        latest_found_timestamp: Optional[datetime] = None

        time_init = datetime.now()

        # max time period to search for children
        timeout = time_init + timedelta(seconds=self.children_timeout)

        while datetime.now() < timeout:
            if latest_found_timestamp and datetime.now() >= latest_found_timestamp:
                ppids = ", ".join(sorted(str(p.pid) for p in target_parents))
                self._log.debug(f"Children search timed out earlier (ppids={ppids})")
                return

            ppid_comm_pid = await map_processes_by_parent()

            for parent in target_parents:
                for pid_, comm_, ppid_ in find_process_children(ppid=parent.pid,
                                                                processes_by_parent=ppid_comm_pid,
                                                                already_found=already_found):
                    if self.children_found_timeout >= 0:
                        latest_found_timestamp = datetime.now() + timedelta(seconds=self.children_found_timeout)

                    self._log.info(f"Child process found: {comm_} (pid={pid_}, ppid={ppid_})")
                    child = parent.clone()
                    child.pid = pid_
                    await self._handle_process(child, proc_tasks, env_tasks)

        time_end = datetime.now()
        ppids = ", ".join(sorted(str(p.pid) for p in target_parents))
        self._log.debug(f"Children search timed out in {(time_end - time_init).total_seconds():.2f} (ppids={ppids})")

    async def handle(self, request: OptimizationRequest):
        request.prepare()

        if not os.path.exists(f'/proc/{request.pid}'):
            self._log.warning(f'Process {request.pid} does not exist. No optimization will be applied.')
            await self.context.queue.remove_pids(request.pid)
        else:
            if request.has_full_configuration():
                profile = self.map_valid_config(request.config)
            else:
                profile = await self._load_valid_profile(request)

            if not profile:
                self._log.warning(f"No optimizations available for process '{request.pid}'")

            source_process = OptimizedProcess(request=request, created_at=time.time(), profile=profile)

            env_tasks: Optional[Iterable[Task]] = None
            proc_tasks: Optional[Iterable[Task]] = None
            handled_processes: List[OptimizedProcess] = list()

            if profile:
                env_tasks = await self._tasks_man.get_available_environment_tasks(source_process)

                if source_process.profile.process:
                    proc_tasks = await self._tasks_man.get_available_process_tasks(source_process)

                async for pid in self._launcher_mapper.map_pids(source_process.request, source_process.profile):
                    if pid is not None and pid != source_process.pid:
                        mapped_process = source_process.clone()
                        mapped_process.pid = pid
                        await self._handle_process(mapped_process, proc_tasks, env_tasks, mapped=True)
                        handled_processes.append(mapped_process)

            if not handled_processes:
                # if no other process was handled yet, it means the source process was not mapped as another processes.
                # so it should be optimized
                await self._handle_process(source_process, proc_tasks, env_tasks)
                handled_processes.append(source_process)

            if handled_processes:
                if self.children_timeout <= 0:
                    ppids = ", ".join(sorted(str(p.pid) for p in handled_processes))
                    self._log.debug(f"Not looking for processes children (ppids={ppids})")
                else:
                    await self.optimize_children(handled_processes, proc_tasks, env_tasks)
