import asyncio
import os
import time
from asyncio import Task
from typing import Optional, Awaitable, Tuple, Iterable, AsyncGenerator, List

from guapow.common.dto import OptimizationRequest
from guapow.common.profile import get_possible_profile_paths_by_priority, \
    get_default_profile_name
from guapow.service.optimizer.launcher import LauncherMapperManager
from guapow.service.optimizer.profile import OptimizationProfile, OptimizationProfileReader
from guapow.service.optimizer.task.environment import EnvironmentTask
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

    async def _generate_process_tasks(self, source_process: OptimizedProcess) -> \
            AsyncGenerator[Tuple[OptimizedProcess, Iterable[Awaitable]], None]:
        """
        Generates tasks related to the source process or mapped processes.
        """
        if source_process.profile.process:
            proc_tasks = await self._tasks_man.get_available_process_tasks(source_process)

            if proc_tasks:
                any_mapped = False
                async for pid in self._launcher_mapper.map_pids(source_process.request, source_process.profile):
                    if pid is not None and pid != source_process.pid:
                        await self._queue.add_pid(pid)
                        any_mapped = True
                        cloned_process = source_process.clone()
                        cloned_process.pid = pid
                        yield cloned_process, run_tasks(proc_tasks, cloned_process)

                if not any_mapped:
                    yield source_process, run_tasks(proc_tasks, source_process)

    async def _handle_process(self, process: OptimizedProcess, tasks: Optional[Iterable[Awaitable]] = None,
                              env_tasks: Optional[Iterable[Task]] = None):
        if env_tasks:
            self._log.debug(f"Awaiting environment tasks required by process '{process.pid}'")
            await asyncio.gather(*run_tasks(env_tasks, process))

        should_be_watched = process.should_be_watched()

        if should_be_watched:
            self._log.debug(f"Process '{process.pid}' should be watched")
            await self._watcher_man.watch(process)

            if process.pid != process.source_pid:
                await self._queue.remove_pids(process.source_pid)

        if tasks:
            self._log.debug(f"Awaiting process tasks required by the process '{process.pid}'")
            await asyncio.gather(*tasks)

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
                        f"{f' (source pid={process.pid})' if request.pid != process.pid else ''}")

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

            env_tasks: Optional[List[EnvironmentTask]] = None
            if profile:
                env_tasks = await self._tasks_man.get_available_environment_tasks(source_process)

                pids_handled = False
                async for mapped_proc, proc_tasks in self._generate_process_tasks(source_process):
                    await self._handle_process(mapped_proc, proc_tasks, env_tasks)
                    pids_handled = True

                if pids_handled:
                    return

            # only tries to handle the source process in case it wasn't mapped as other processes
            await self._handle_process(source_process, env_tasks=env_tasks)
