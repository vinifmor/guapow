import asyncio
from typing import Optional, List, Awaitable, Type, Dict

from guapow.service.optimizer.task.environment import EnvironmentTask, DisableWindowCompositor, \
    ChangeCPUFrequencyGovernor, ChangeGPUModeToPerformance, HideMouseCursor, StopProcessesAfterLaunch, \
    RunPostLaunchScripts, ChangeCPUEnergyPolicyLevel
from guapow.service.optimizer.task.model import OptimizationContext, Task, OptimizedProcess
from guapow.service.optimizer.task.process import ProcessTask, ReniceProcess, ChangeCPUAffinity, \
    ChangeCPUScalingPolicy, ChangeProcessIOClass


def run_tasks(tasks: List[Task], process: OptimizedProcess) -> Optional[List[Awaitable]]:
    if tasks:
        return [t.run(process) for t in tasks]


class TasksManager:

    def __init__(self, context: OptimizationContext):
        self._context = context
        self._log = context.logger
        self._proc_tasks: Optional[List[ProcessTask]] = None
        self._env_tasks: Optional[List[EnvironmentTask]] = None
        self._env_order: Dict[Type[EnvironmentTask, int]] = {
            StopProcessesAfterLaunch: 0,
            RunPostLaunchScripts: 1,
            DisableWindowCompositor: 2,
            HideMouseCursor: 3,
            ChangeCPUFrequencyGovernor: 4,
            ChangeCPUEnergyPolicyLevel: 5,
            ChangeGPUModeToPerformance: 6
        }
        self._proc_order: Dict[Type[ProcessTask, int]] = {
            ReniceProcess: 0,
            ChangeCPUAffinity: 1,
            ChangeCPUScalingPolicy: 2,
            ChangeProcessIOClass: 3
        }

    def _sort_proc(self, o: ProcessTask) -> int:
        return self._proc_order.get(o.__class__, 999)

    def _sort_env(self, o: EnvironmentTask) -> int:
        return self._env_order.get(o.__class__, 999)

    async def check_availability(self):
        self._log.debug("Checking available tasks")

        proc_opts, env_opts = [], []

        for root_cls in (EnvironmentTask, ProcessTask):
            for opt_cls in root_cls.__subclasses__():
                task = opt_cls(self._context)
                available, warning_msg = await task.is_available()

                if available:
                    if root_cls == EnvironmentTask:
                        env_opts.append(task)
                    else:
                        proc_opts.append(task)
                else:
                    self._log.warning(warning_msg)

        self._proc_tasks = proc_opts
        self._env_tasks = env_opts

        if self._proc_tasks:
            self._log.debug(f"Process tasks available ({len(self._proc_tasks)}): {', '.join([t.__class__.__name__ for t in self._proc_tasks])}")
            self._proc_tasks.sort(key=self._sort_proc)

        if self._env_tasks:
            self._log.debug(f"Environment tasks available ({len(self._env_tasks)}): {', '.join([t.__class__.__name__ for t in self._env_tasks])}")
            self._env_tasks.sort(key=self._sort_env)

    async def get_available_process_tasks(self, process: OptimizedProcess) -> Optional[List[ProcessTask]]:
        if self._proc_tasks:
            return await self._list_runnable_tasks(process, self._proc_tasks)

    async def get_available_environment_tasks(self, process: OptimizedProcess) -> Optional[List[EnvironmentTask]]:
        if self._env_tasks:
            return await self._list_runnable_tasks(process, self._env_tasks)

    async def _list_runnable_tasks(self, process: OptimizedProcess, tasks: List[Task]) -> Optional[List[Task]]:
        to_verify = [t for t in tasks if t.is_allowed_for_self_requests()] if process.request.is_self_request else tasks

        if to_verify:
            async_tasks = [self._should_run(task, process) for task in to_verify]

            if async_tasks:
                return [t for t in await asyncio.gather(*async_tasks) if t]

    async def _should_run(self, task: Task, process: OptimizedProcess) -> Optional[Task]:
        if await task.should_run(process):
            return task
