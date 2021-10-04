import asyncio
import os
import shutil
from abc import ABC
from io import StringIO
from typing import Optional, Tuple

from guapow.common.system import async_syscall
from guapow.common.users import is_root_user
from guapow.service.optimizer.renicer import Renicer
from guapow.service.optimizer.task.model import Task, OptimizationContext, OptimizedProcess


class ProcessTask(Task, ABC):
    """
    Task that requires a process to be executed
    """


class ReniceProcess(ProcessTask):

    def __init__(self, context: OptimizationContext):
        super(ReniceProcess, self).__init__(context)
        self._log = context.logger
        self._renicer = Renicer(logger=context.logger, watch_interval=context.renicer_interval)

    async def is_available(self) -> Tuple[bool, Optional[str]]:
        return True, None

    async def should_run(self, process: OptimizedProcess) -> bool:
        request, profile = process.request, process.profile

        if profile.process and profile.process.nice and profile.process.nice.level is not None:
            if profile.process.nice.has_valid_level():
                return True
            else:
                self._log.warning(f"Invalid nice level ({profile.process.nice.level}) defined for {profile.get_log_str()}. "
                                  f"Valid values between -20 and 20. Process ({process.pid}) will not be reniced "
                                  f"(request={process.request.pid})")

        return False

    async def run(self, process: OptimizedProcess):
        profile = process.profile

        if profile.process.nice.delay is not None:
            if profile.process.nice.delay > 0:
                self._log.info(f"Delaying process '{process.pid}' renicing for {profile.process.nice.delay} seconds "
                               f"(request={process.request.pid})")
                await asyncio.sleep(profile.process.nice.delay)
            else:
                self._log.warning(f"Invalid nice delay defined for process '{process.pid}': {profile.process.nice.delay} "
                                  f"(must be higher than zero) (request={process.request.pid})")

        self._renicer.set_priority(process.pid, profile.process.nice.level, process.request.pid)

        if process.profile.process.nice.watch:
            if self._renicer.add(process.pid, profile.process.nice.level, process.request.pid):
                self._renicer.watch()


class ChangeCPUAffinity(ProcessTask):

    def __init__(self, context: OptimizationContext):
        super(ChangeCPUAffinity, self).__init__(context)
        self._log = context.logger
        self._cpu_count = context.cpu_count

    async def is_available(self) -> Tuple[bool, Optional[str]]:
        if self._cpu_count == 0:
            return False, "no CPUs detected. It will not be possible to change CPU affinity"

        return True, None

    async def should_run(self, process: OptimizedProcess) -> bool:
        profile = process.profile

        if profile.process and profile.process.cpu_affinity:
            if profile.process.has_valid_cpu_affinity(self._cpu_count):
                return True
            else:
                self._log.warning(f"Invalid CPU affinity defined ({profile.process.cpu_affinity}) for {profile.get_log_str()}. "
                                  f"It must be a list of integers between '0' and '{self._cpu_count - 1}' (request={process.request.pid})")

        return False

    async def run(self, process: OptimizedProcess):
        profile = process.profile

        try:
            os.sched_setaffinity(process.pid, profile.process.cpu_affinity)
            self._log.info(f"Process '{process.pid}' CPU affinity changed to {profile.process.cpu_affinity} (request={process.request.pid})")
        except:
            self._log.error(f"Could not change process '{process.pid}' CPU affinity to {profile.process.cpu_affinity} (request={process.request.pid})")


class ChangeCPUScalingPolicy(ProcessTask):

    def __init__(self, context: OptimizationContext):
        super(ChangeCPUScalingPolicy, self).__init__(context)
        self._log = context.logger
        self._cpu_count = context.cpu_count

    async def is_available(self) -> Tuple[bool, Optional[str]]:
        return True, None

    async def should_run(self, process: OptimizedProcess) -> bool:
        request, profile = process.request, process.profile

        if profile.process and profile.process.scheduling and profile.process.scheduling.policy:
            sched = profile.process.scheduling

            if sched.policy.requires_root() and not is_root_user():
                self._log.warning(f"Not possible to change the scheduling policy for process '{process.pid}' "
                                  f"to '{profile.process.scheduling.policy.name}'. It requires root privileges. (request={process.request.pid})")
                return False
            elif sched.policy.requires_priority() and sched.priority is not None and not sched.has_valid_priority():
                self._log.warning(f"Invalid priority '{sched.priority}' defined for scheduling policy '{sched.policy.name}' "
                                  f"in {profile.get_log_str()} (request={process.request.pid})")
                return False

            return True

        return False

    async def run(self, process: OptimizedProcess):
        profile, scheduling = process.profile, process.profile.process.scheduling

        priority = 0
        if scheduling.policy.requires_priority():
            priority = scheduling.priority

            if scheduling.priority is None:
                priority = 1
                self._log.warning(f"No priority set for policy '{scheduling.policy.name}' in {profile.get_log_str()}. "
                                  f"('{priority}' will be used) (request={process.request.pid})")

        elif scheduling.priority is not None:
            self._log.warning(f"Scheduling policy '{scheduling.policy.name}' does not require priority "
                              f"('{scheduling.priority}' will be ignored) (request={process.request.pid})")

        try:
            os.sched_setscheduler(process.pid, scheduling.policy.value(), os.sched_param(priority))
            self._log.info(f"Process '{process.pid}' scheduling policy changed to '{scheduling.policy.name}'"
                           f"{f' (priority: {priority})' if priority else ''} (request={process.request.pid})")
        except:
            self._log.error(f"Could not change process '{process.pid}' scheduling policy to '{scheduling.policy.name}'"
                            f"{f' (priority: {priority})' if priority else ''} (request={process.request.pid})")


class ChangeProcessIOClass(ProcessTask):

    def __init__(self, context: OptimizationContext):
        super(ChangeProcessIOClass, self).__init__(context)
        self._log = context.logger

    async def is_available(self) -> Tuple[bool, Optional[str]]:
        if shutil.which('ionice'):
            return True, None
        else:
            return False, "'ionice' is not installed. It will not be possible to change a process IO scheduling"

    async def should_run(self, process: OptimizedProcess) -> bool:
        profile = process.profile

        if profile.process.io and profile.process.io.ioclass:
            if profile.process.io.ioclass.supports_priority():

                # if nice_level is None, 0 will be considered
                if profile.process.io.nice_level is None or profile.process.io.has_valid_priority():
                    return True
                else:
                    self._log.warning(f"Invalid IO nice level ({profile.process.io.nice_level}) defined for {profile.get_log_str()}. "
                                      f"It must be a value between 0 and 7. IO class will not be changed (request={process.request.pid})")
                    return False

            return True

        return False

    async def run(self, process: OptimizedProcess):
        io_config = process.profile.process.io

        if io_config.ioclass.supports_priority():
            if io_config.nice_level is None:
                self._log.warning(f"No nice level defined for IO class '{io_config.ioclass.name}' on {process.profile.get_log_str()}. "
                                  f"'0' will be considered (request={process.request.pid})")
                priority = 0
            else:
                priority = io_config.nice_level
        else:
            priority = None

        cmd = StringIO()
        cmd.write(f'ionice -p {process.pid} -c {io_config.ioclass.value()}')

        if priority is not None:
            cmd.write(f' -n {priority}')

        cmd.seek(0)
        cmd_str = cmd.read()

        self._log.info(f"Changing process '{process.pid}' IO class to '{io_config.ioclass.name}'"
                       f"{f' (priority: {priority})'if priority is not None else ''} (request={process.request.pid}): {cmd_str}")

        exitcode, output = await async_syscall(cmd_str)

        if exitcode != 0:
            self._log.error(f"Could not change process '{process.pid}' IO class for {process.profile.get_log_str()} "
                            f"(request={process.request.pid})")

            if output:
                for line in output.split('\n'):
                    self._log.error(line)
