import asyncio
import os
import time
from typing import Optional, Awaitable, List

from guapow.common.dto import OptimizationRequest
from guapow.common.profile import get_possible_profile_paths_by_priority, \
    get_default_profile_name
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
        self._launcher_mapper = LauncherMapperManager(check_time=context.launcher_mapping_timeout, logger=context.logger)

    async def _read_valid_profile(self, name: str, add_settings: Optional[str], user_id: Optional[int], user_name: Optional[str], request: OptimizationRequest) -> Optional[OptimizationProfile]:
        for file_path in get_possible_profile_paths_by_priority(name=name, user_id=user_id, user_name=user_name):
            if file_path:
                try:
                    return await self._profile_reader.read_valid(profile_path=file_path, add_settings=add_settings, handle_not_found=False)
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

    async def _start_environment_tasks(self, process: OptimizedProcess) -> Optional[List[Awaitable]]:
        env_tasks = await self._tasks_man.get_available_environment_tasks(process)

        if env_tasks:
            return run_tasks(env_tasks, process)

    async def _start_process_tasks(self, process: OptimizedProcess) -> Optional[List[Awaitable]]:
        if process.profile.process:
            proc_tasks = await self._tasks_man.get_available_process_tasks(process)

            if proc_tasks:
                mapped_pid = await self._launcher_mapper.map_pid(process.request, process.profile)

                if mapped_pid is not None:
                    process.pid = mapped_pid
                    await self._queue.add_pid(mapped_pid)

                return run_tasks(proc_tasks, process)

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

            process = OptimizedProcess(request=request, created_at=time.time(), profile=profile)

            proc_tasks_running = None

            if profile:
                env_tasks_running = await self._start_environment_tasks(process)
                proc_tasks_running = await self._start_process_tasks(process)

                if env_tasks_running:
                    await asyncio.gather(*env_tasks_running)

            should_be_watched = process.should_be_watched()

            if should_be_watched:
                await self._watcher_man.watch(process)

                if process.pid != process.source_pid:
                    await self._queue.remove_pids(process.source_pid)

            if proc_tasks_running:
                await asyncio.gather(*proc_tasks_running)

            if not should_be_watched:
                related_pids = process.get_pids()

                if related_pids:
                    await self._queue.remove_pids(*related_pids)

            exec_time = time.time() - request.created_at
            self._log.debug(f"Optimization request for '{request.pid}' took {exec_time:.4f} seconds"
                            f"{f' (target_pid={process.pid})' if request.pid != process.pid else ''}")
