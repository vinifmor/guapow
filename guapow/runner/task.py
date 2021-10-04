import asyncio
import os
import re
import shutil
from abc import ABC, abstractmethod
from logging import Logger
from typing import Tuple, Optional, List, Set, Type, Dict

from guapow.common import system
from guapow.common.scripts import RunScripts
from guapow.runner.profile import RunnerProfile


class RunnerContext:

    def __init__(self, logger: Logger, processes_initialized: Optional[Set[int]], environment_variables: Optional[dict],
                 stopped_processes: Optional[Dict[str, str]]):
        self.logger = logger
        self.processes_initialized = processes_initialized
        self.environment_variables = environment_variables
        self.stopped_processes = stopped_processes

    def get_process_extra_arguments(self) -> dict:
        args = {}
        if self.environment_variables:
            args['env'] = {**os.environ, **self.environment_variables}

        return args


class RunnerTask(ABC):

    @abstractmethod
    def __init__(self, context: RunnerContext):
        pass

    @abstractmethod
    def is_available(self) -> Tuple[bool, Optional[str]]:
        pass

    @abstractmethod
    def should_run(self, profile: RunnerProfile) -> bool:
        pass

    @abstractmethod
    async def run(self, profile: RunnerProfile):
        pass


class AddDefinedEnvironmentVariables(RunnerTask):

    def __init__(self, context: RunnerContext):
        self.context = context
        self._log = context.logger

    def is_available(self) -> Tuple[bool, Optional[str]]:
        return True, None

    def should_run(self, profile: RunnerProfile) -> bool:
        return bool(profile.environment_variables)

    async def run(self, profile: RunnerProfile):
        vars_added = {}
        for var, val in profile.environment_variables.items():
            if var:
                final_val = str(val) if val is not None else ''
                self.context.environment_variables[var] = final_val
                vars_added[var] = final_val

        if vars_added:
            self._log.info(f"Environment variables added: {', '.join(f'{k} = {v}' for k,v in vars_added.items())}")


class RunPreLaunchScripts(RunnerTask):

    def __init__(self, context: RunnerContext):
        super(RunPreLaunchScripts, self).__init__(context)
        self._context = context
        self._task = RunScripts(name="pre launch", root_allowed=False, logger=context.logger)

    def is_available(self) -> Tuple[bool, Optional[str]]:
        return True, None

    def should_run(self, profile: RunnerProfile) -> bool:
        return bool(profile.before_scripts and profile.before_scripts.scripts)

    async def run(self, profile: RunnerProfile):
        pids = await self._task.run(scripts=[profile.before_scripts], user_id=os.getuid(), user_env={**os.environ})

        if pids:
            self._context.processes_initialized.update(pids)


class StopProcesses(RunnerTask):

    def __init__(self, context: RunnerContext):
        self._log = context.logger
        self._context = context

    def is_available(self) -> Tuple[bool, Optional[str]]:
        return True, None

    def should_run(self, profile: RunnerProfile) -> bool:
        return bool(profile.stop and profile.stop.processes)

    async def run(self, profile: RunnerProfile):
        stopped_processes = {}

        found = await system.find_pids_by_names(profile.stop.processes)
        not_stopped = set()

        if found:
            pid_cmds = await system.find_commands_by_pids({*found.values()})

            if not pid_cmds:
                self._log.warning(f"Could not retrieve commands of: {', '.join((str(p) for p in pid_cmds))}")

            _, kill_output = await system.async_syscall(f"kill -9 {' '.join((str(p) for p in found.values()))}")

            not_killed = re.compile(r'kill\s*:\s*\(?(\d+)\)?.+').findall(kill_output) if kill_output else []

            if not_killed:
                not_killed = {int(pid) for pid in not_killed}

            for comm, pid in found.items():
                if pid in not_killed:
                    not_stopped.add(comm)
                elif pid_cmds:
                    cmd = pid_cmds.get(pid)

                    if cmd:
                        stopped_processes[comm] = cmd

        if stopped_processes:
            self._log.info(f"Processes stopped: {', '.join(stopped_processes)}")

        if not_stopped:
            self._log.warning(f"Fail to stop processes: {', '.join(not_stopped)}")

        if len(stopped_processes) != len(profile.stop.processes):
            not_running = profile.stop.processes.difference(stopped_processes).difference(not_stopped)

            # check if the processes that were not running exist
            existent_not_running = {comm: None for comm in not_running if shutil.which(comm)}  # when the process command is sent to the backend with as 'None', it means it was not stopped. This behavior is essential to properly manage the requirements state.

            if existent_not_running:
                stopped_processes.update(existent_not_running)  # must be added even if not stopped so the optimizer can properly manage what should be relaunched
                self._log.warning(f"Some processes were not running and could not be stopped: {', '.join(existent_not_running)}")

        if stopped_processes:
            self._context.stopped_processes.update(stopped_processes)


class RunnerTaskManager:
    """
    Execute tasks before the process is called
    """

    def __init__(self, context: RunnerContext, actions: Optional[List[RunnerTask]] = None):
        self._context = context
        self._log = context.logger
        self._actions = actions
        self._tasks_order: Dict[Type[RunnerTask], int] = {
            AddDefinedEnvironmentVariables: 0,
            StopProcesses: 1,
            RunPreLaunchScripts: 2
        }

    def _sort(self, task: RunnerTask):
        return self._tasks_order.get(task.__class__, 99)

    def _check_availability(self):
        if self._actions is None:
            actions = []

            for cls in RunnerTask.__subclasses__():
                action = cls(self._context)
                available, warning_msg = action.is_available()

                if available:
                    actions.append(action)
                elif warning_msg:
                    self._log.warning(warning_msg)

            actions.sort(key=self._sort)
            self._actions = actions

    def get_available_tasks(self) -> List[RunnerTask]:
        return [*self._actions]

    async def run(self, profile: RunnerProfile) -> int:
        self._check_availability()

        if self._actions:
            res = await asyncio.gather(*(a.run(profile) for a in self._actions if a.should_run(profile)))
            return len(res)

        return 0
