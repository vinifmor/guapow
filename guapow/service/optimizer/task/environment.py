import os
from abc import ABC
from asyncio import Lock
from typing import Optional, Tuple, List

from guapow.common.scripts import RunScripts
from guapow.common.users import is_root_user
from guapow.runner.profile import RunnerProfile
from guapow.runner.task import StopProcesses, RunnerContext
from guapow.service.optimizer import cpu
from guapow.service.optimizer.cpu import GOVERNOR_FILE_PATTERN
from guapow.service.optimizer.gpu import GPUDriver
from guapow.service.optimizer.task.model import Task, OptimizationContext, OptimizedProcess, CPUState
from guapow.service.optimizer.win_compositor import get_window_compositor


class EnvironmentTask(Task, ABC):
    """
    Task not related to the optimized process
    """
    pass


class ChangeCPUFrequencyGovernor(EnvironmentTask):

    def __init__(self, context: OptimizationContext, cpu0_governor_file: Optional[str] = GOVERNOR_FILE_PATTERN.format(0)):
        super(ChangeCPUFrequencyGovernor, self).__init__(context)
        self._cpufreq_man = context.cpufreq_man
        self._cpu0_governor_file = cpu0_governor_file
        self._cpu_count = context.cpu_count

    async def is_available(self) -> Tuple[bool, Optional[str]]:
        if self._cpu_count == 0:
            return False, "No CPU detected"

        if os.path.exists(self._cpu0_governor_file):
            if is_root_user():
                return True, None
            else:
                return False, "It will not be possible to change the CPUs scaling governors: requires root privileges"

        return False, f"It will not be possible to change the CPUs scaling governors: file '{self._cpu0_governor_file}' not found"

    async def should_run(self, process: OptimizedProcess) -> bool:
        return bool(process.profile.cpu and process.profile.cpu.performance)

    def is_allowed_for_self_requests(self) -> bool:
        return True

    async def run(self, process: OptimizedProcess):
        async with self._cpufreq_man.lock():
            current_governors = await self._cpufreq_man.map_current_governors()
            prev_governors = {}

            for gov, cpus in current_governors.items():
                if gov != cpu.GOVERNOR_PERFORMANCE:
                    changed_cpus = await self._cpufreq_man.change_governor(cpu.GOVERNOR_PERFORMANCE, cpus)
                    if changed_cpus:
                        prev_governors[gov] = changed_cpus

            if not process.request.is_self_request:
                if prev_governors:
                    self._cpufreq_man.save_governors(prev_governors)
                    process.previous_cpu_state = CPUState(prev_governors)
                else:
                    saved_governors = self._cpufreq_man.get_saved_governors()

                    if saved_governors:
                        process.previous_cpu_state = CPUState(saved_governors)


class ChangeGPUModeToPerformance(EnvironmentTask):

    def __init__(self, context: OptimizationContext):
        super(ChangeGPUModeToPerformance, self).__init__(context=context)
        self._log = context.logger
        self._gpu_man = context.gpu_man

    def check_gpus_for_every_request(self):
        return not self._gpu_man.is_cache_enabled()

    async def is_available(self) -> Tuple[bool, Optional[str]]:
        if self.check_gpus_for_every_request():
            return True, None

        if await self._list_drivers_with_gpus():
            return True, None
        else:
            return False, "No manageable GPUs found"

    async def _list_drivers_with_gpus(self) -> List[GPUDriver]:
        self._log.debug("Checking available GPUs")
        return [gpu async for gpu, _ in self._gpu_man.map_working_drivers_and_gpus()]

    async def should_run(self, process: OptimizedProcess) -> bool:
        return bool(process.profile.gpu and process.profile.gpu.performance)

    async def run(self, process: OptimizedProcess):
        previous_gpu_states = await self._gpu_man.activate_performance(user_environment=process.request.user_env)

        if previous_gpu_states:
            process.previous_gpus_states = previous_gpu_states


class DisableWindowCompositor(EnvironmentTask):

    def __init__(self, context: OptimizationContext, available: Optional[bool] = None):
        super(DisableWindowCompositor, self).__init__(context=context)
        self._log = context.logger
        self._context = context
        self._available = available
        self._compositor_checked = False
        self._manageable: Optional[bool] = None
        self._lock = Lock()

    async def is_available(self) -> Tuple[bool, Optional[str]]:
        return True, None

    async def should_run(self, process: OptimizedProcess) -> bool:
        request, profile = process.request, process.profile

        if profile.compositor and profile.compositor.off:
            async with self._lock:
                if not self._context.compositor and not self._compositor_checked:
                    compositor = await get_window_compositor(logger=self._log, user_id=request.user_id, user_env=request.user_env)

                    if compositor:
                        self._log.info(f"Window compositor detected: {compositor.get_name()}")
                        self._context.compositor = compositor

                    self._compositor_checked = True

                if self._context.compositor and self._manageable is None:
                    res, msg = self._context.compositor.can_be_managed()
                    self._manageable = res

                    if not self._manageable:
                        log_warn = f'. Reason: {msg}' if msg else ''
                        self._log.warning(f"Compositor {self._context.compositor.get_name()} cannot be managed{log_warn}")

            return bool(self._context.compositor and self._manageable)

        return False

    async def run(self, process: OptimizedProcess):
        async with self._context.compositor.lock():
            context = {}
            enabled = await self._context.compositor.is_enabled(user_id=process.user_id, user_env=process.user_env, context=context)

            if enabled is None:
                self._log.error(f"It will not be possible to disable the window compositor for process '{process.pid}'")
                return

            if not enabled:
                self._log.info("Window compositor is already disabled")
                return

            if await self._context.compositor.disable(user_id=process.user_id, user_env=process.user_env, context=context):
                self._log.info("Window compositor disabled")
                self._context.compositor_disabled_context = context


class HideMouseCursor(EnvironmentTask):

    def __init__(self, context: OptimizationContext):
        self._context = context
        self._log = context.logger
        self._mouse_man = context.mouse_man

    async def is_available(self) -> Tuple[bool, Optional[str]]:
        return self._mouse_man.can_work()

    async def should_run(self, process: OptimizedProcess) -> bool:
        return bool(process.profile.hide_mouse)

    async def run(self, process: OptimizedProcess):
        await self._mouse_man.hide_cursor(user_request=not process.request.is_self_request, user_env=process.request.user_env)


class StopProcessesAfterLaunch(EnvironmentTask):  # act as a wrapper for 'runner.task.StopProcesses'

    def __init__(self, context: OptimizationContext):
        self._log = context.logger
        self._context = context
        self._task_context = RunnerContext(environment_variables=None, processes_initialized=None,
                                           logger=self._log, stopped_processes=None)
        self._task = StopProcesses(self._task_context)

    async def is_available(self) -> Tuple[bool, Optional[str]]:
        return self._task.is_available()

    async def should_run(self, process: OptimizedProcess) -> bool:
        return process.profile.stop_after and process.profile.stop_after.processes

    async def run(self, process: OptimizedProcess):
        self._task_context.stopped_processes = {}

        fake_profile = RunnerProfile(path=None, environment_variables=None)
        fake_profile.stop = process.profile.stop_after
        await self._task.run(fake_profile)

        if self._task_context.stopped_processes:
            process.stopped_after_launch = self._task_context.stopped_processes


class RunPostLaunchScripts(EnvironmentTask):

    def __init__(self, context: OptimizationContext):
        self._context = context
        self._task = RunScripts(name='post launch', root_allowed=context.allow_root_scripts, logger=context.logger)

    async def is_available(self) -> Tuple[bool, Optional[str]]:
        return True, None

    async def should_run(self, process: OptimizedProcess) -> bool:
        return bool(process.profile.after_scripts and process.profile.after_scripts.scripts)

    async def run(self, process: OptimizedProcess):
        started_pids = await self._task.run(scripts=[process.profile.after_scripts], user_id=process.user_id, user_env=process.user_env)

        if started_pids:
            process.related_pids.update(started_pids)


class ChangeCPUEnergyPolicyLevel(EnvironmentTask):

    def __init__(self, context: OptimizationContext):
        super(ChangeCPUEnergyPolicyLevel, self).__init__(context)
        self._man = context.cpuenergy_man
        self._log = context.logger

    async def is_available(self) -> Tuple[bool, Optional[str]]:
        return self._man.can_work()

    async def should_run(self, process: OptimizedProcess) -> bool:
        return bool(process.profile.cpu and process.profile.cpu.performance)

    def is_allowed_for_self_requests(self) -> bool:
        return True

    async def run(self, process: OptimizedProcess):
        async with self._man.lock():
            current_cpu_states = await self._man.map_current_state()

            if not current_cpu_states:
                self._log.error("Could not determine the current CPUs energy policy level")
                return

            not_in_performance = {i: state for i, state in current_cpu_states.items()
                                  if state != self._man.LEVEL_PERFORMANCE}

            if not not_in_performance:
                process.cpu_energy_policy_changed = bool(self._man.saved_state)
                return

            cpus_changed_state = await self._man.change_states({i: self._man.LEVEL_PERFORMANCE
                                                                for i in not_in_performance})
            cpus_changed, cpus_not_changed = [], []

            for idx, changed in cpus_changed_state.items():
                if changed:
                    cpus_changed.append(idx)
                else:
                    cpus_not_changed.append(idx)

            if cpus_not_changed:
                self._log.error(f"Could not change the energy policy level to full performance "
                                f"({self._man.LEVEL_PERFORMANCE}) for the following CPUs: "
                                f"{', '.join(str(i) for i in sorted(cpus_not_changed))}")

            if cpus_changed:
                cpus_changed.sort()
                self._log.info(f"Energy policy level changed to full performance ({self._man.LEVEL_PERFORMANCE}) "
                               f"for the following CPUs: {', '.join(str(i) for i in sorted(cpus_changed))}")

                if not process.request.is_self_request:
                    state_to_save = {idx: current_cpu_states[idx] for idx in cpus_changed}
                    self._log.debug(f"Previous CPUs energy policy levels state saved: {state_to_save}")
                    self._man.save_state(state_to_save)
                    process.cpu_energy_policy_changed = True
