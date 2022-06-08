import asyncio
import re
import traceback
from abc import ABC, abstractmethod
from multiprocessing import Process
from re import Pattern
from typing import List, Optional, Dict, Set, Tuple, Type, Awaitable

from guapow.common import system
from guapow.common.scripts import RunScripts
from guapow.common.users import is_root_user
from guapow.service.optimizer.gpu import GPUState, GPUDriver
from guapow.service.optimizer.post_process.context import PostProcessContext
from guapow.service.optimizer.task.model import OptimizationContext, CPUState


class PostProcessTask(ABC):

    @abstractmethod
    def __init__(self, context: OptimizationContext):
        pass

    @abstractmethod
    def should_run(self, context: PostProcessContext) -> bool:
        pass

    @abstractmethod
    async def run(self, context: PostProcessContext):
        pass


class RestoreGPUState(PostProcessTask):

    def __init__(self, context: OptimizationContext):
        super(RestoreGPUState, self).__init__(context)
        self._gpu_man = context.gpu_man
        self._log = context.logger

    def should_run(self, context: PostProcessContext) -> bool:
        return bool(context.restorable_gpus)

    async def _restore(self, driver: GPUDriver, states: List[GPUState], user_env: Optional[dict]):
        async with driver.lock():
            gpus_states = {}  # hold all states mapped to the same GPU

            for state in states:
                modes = gpus_states.get(state.id, set())
                gpus_states[state.id] = modes
                modes.add(state.power_mode)

            gpus_current_modes = await driver.get_power_mode({*gpus_states.keys()}, user_env)
            gpus_to_restore = {}

            for id_, modes in gpus_states.items():
                # if there is more than one mode mapped to same GPU, a default mode is preferred
                mode = [*modes][0] if len(modes) == 1 else driver.get_default_mode()
                current_mode = gpus_current_modes.get(id_)

                if mode:
                    if mode != current_mode:
                        gpus_to_restore[id_] = mode
                    else:
                        self._log.info(f"It is not necessary to restore {driver.get_vendor_name()} GPU ({id_}) to "
                                       f"'{mode.name.lower()}' mode")
                else:
                    self._log.error(f"Current mode unknown for {driver.get_vendor_name()} GPU '{id_}'")

            if gpus_to_restore:
                self._log.debug(f"Restoring power mode of {driver.get_vendor_name()} GPUS: "
                                f"{', '.join(gpus_to_restore)}")

                gpus_changed = await driver.set_power_mode(gpus_to_restore, user_env)

                if gpus_changed:
                    if not self._log.disabled:
                        not_restored = {gpu for gpu, changed in gpus_changed.items() if not changed}

                        if not_restored:
                            self._log.error(f"Could not restore power mode of {driver.get_vendor_name()}  GPUS: "
                                            f"{', '.join(gpus_changed)}")

                else:
                    self._log.error(f"Could not restore power mode of {driver.get_vendor_name()} GPUs: "
                                    f"{', '.join(gpus_to_restore.keys())}")

    async def run(self, context: PostProcessContext):
        restore_tasks = []
        for driver in self._gpu_man.get_drivers():
            states = context.restorable_gpus.get(driver.__class__)

            if states:
                restore_tasks.append(self._restore(driver, states, context.user_env))

        if restore_tasks:
            await asyncio.gather(*restore_tasks)


class RestoreCPUGovernor(PostProcessTask):

    def __init__(self, context: OptimizationContext):
        self._cpufreq_man = context.cpufreq_man
        self._log = context.logger

    def should_run(self, context: PostProcessContext) -> bool:
        return bool(context.restorable_cpus)

    def _map_governors(self, governors: List[Dict[str, Set[int]]]) -> Tuple[Dict[str, Set[int]], Dict[int, Set[str]]]:
        governor_cpus, cpu_governors = {}, {}

        if governors:
            for govs in governors:
                if govs:  # it is possible that previous governors could not be determined because they were set to 'performance' at that time
                    for gov, cpus in govs.items():
                        gov_cpus = governor_cpus.get(gov, set())
                        gov_cpus.update(cpus)
                        governor_cpus[gov] = gov_cpus

                        for cpu in cpus:
                            govs = cpu_governors.get(cpu, set())
                            govs.add(gov)
                            cpu_governors[cpu] = govs

        return governor_cpus, cpu_governors

    def map_governors(self, cpu_states: List[CPUState]) -> Tuple[Dict[str, Set[int]], Dict[int, Set[str]]]:
        governor_cpus, cpu_governors = self._map_governors([state.governors for state in cpu_states])

        if not governor_cpus:
            governor_cpus, cpu_governors = self._map_governors([self._cpufreq_man.get_saved_governors()])

        return governor_cpus, cpu_governors

    def _remove_duplicates(self, governor_cpus: Dict[str, Set[int]], cpu_governors: Dict[int, Set[str]]):
        """
        if there is a CPU mapped to several governors, remove it from the governors with less CPUs mapped
        """
        sorted_governors_cpus = [g for n, g in sorted([(len(c), g) for g, c in governor_cpus.items()], reverse=True)]

        to_remove = {}  # governor by CPUs to remove
        for cpu, governors in cpu_governors.items():
            if len(governors) > 1:
                pref_gov_idx, pref_gov = None, None
                for gov in governors:
                    gov_prio = sorted_governors_cpus.index(gov)

                    if pref_gov_idx is None or pref_gov_idx > gov_prio:
                        pref_gov_idx = gov_prio
                        pref_gov = gov

                for gov in governors:
                    if gov != pref_gov:
                        gov_cpus = to_remove.get(gov, set())
                        to_remove[gov] = gov_cpus
                        gov_cpus.add(cpu)

        for gov, cpus_to_remove in to_remove.items():
            for cpu in cpus_to_remove:
                governor_cpus[gov].remove(cpu)

    def _cpus_to_str(self, cpus: Set[int]):
        return ','.join((str(c)for c in cpus))

    async def run(self, context: PostProcessContext):
        async with self._cpufreq_man.lock():
            governor_cpus, cpu_governors = self.map_governors(context.restorable_cpus)

            if governor_cpus:
                if len(governor_cpus) == 1:
                    governor = [*governor_cpus][0]
                    cpus = governor_cpus[governor]
                    self._log.debug(f"Restoring CPUs ({self._cpus_to_str(cpus)}) governors to '{governor}'")
                    await self._cpufreq_man.change_governor(governor, cpus)
                else:
                    self._remove_duplicates(governor_cpus, cpu_governors)

                    for governor, cpus in governor_cpus.items():
                        if cpus:
                            self._log.debug(f"Restoring CPUs ({self._cpus_to_str(cpus)}) governors to '{governor}'")
                            await self._cpufreq_man.change_governor(governor, cpus)

            else:
                self._log.warning('Previous CPU governors could be restored because they are unknown')


class PostStopProcesses(PostProcessTask):

    def __init__(self, context: OptimizationContext):
        self._log = context.logger

    def should_run(self, context: PostProcessContext) -> bool:
        return bool(context.pids_to_stop)

    async def run(self, context: PostProcessContext):
        self._log.debug("Finding children of related processes")
        children = await system.find_children({*context.pids_to_stop})

        if children:
            self._log.debug(f"Children of related processes found: {' '.join([str(p) for p in children])}")
        else:
            children = []
            self._log.debug("No children of related processes found")

        all_to_stop = ' '.join((str(p)for p in (*children, *context.pids_to_stop)))
        self._log.info(f'Stopping related processes: {all_to_stop}')

        code, _ = await system.async_syscall(f'kill -9 {all_to_stop}', return_output=False)

        if code != 0:
            self._log.error(f'Not all related processes could be stopped: {all_to_stop}')


class ReEnableWindowCompositor(PostProcessTask):

    def __init__(self, context: OptimizationContext):
        self._log = context.logger
        self._context = context

    def should_run(self, context: PostProcessContext) -> bool:
        return bool(context.restore_compositor and self._context.compositor and self._context.compositor_disabled_context is not None)

    async def run(self, context: PostProcessContext):
        compositor, compositor_context = self._context.compositor, self._context.compositor_disabled_context

        async with compositor.lock():
            enabled = await compositor.is_enabled(user_id=context.user_id, user_env=context.user_env, context=compositor_context)

            if enabled is None:
                self._log.error("Could not re-enable the window compositor. It was not possible to determine its current state")
                return
            elif enabled:
                self._log.info("It was not necessary to enable the window compositor. It is already enabled.")
                self._context.compositor_disabled_context = None  # resetting the global context
            else:
                if await compositor.enable(user_id=context.user_id, user_env=context.user_env, context=compositor_context):
                    self._log.info("Window compositor re-enabled")
                    self._context.compositor_disabled_context = None  # resetting the global context
                else:
                    self._log.error("Could not re-enable the window compositor")


class RunFinishScripts(PostProcessTask):

    def __init__(self, context: OptimizationContext):
        self._context = context
        self._log = context.logger
        self._task = RunScripts('finish', context.allow_root_scripts, self._log)

    def should_run(self, context: PostProcessContext) -> bool:
        if context.scripts:
            for settings in context.scripts:
                if settings.scripts:
                    return True

        return False

    async def run(self, context: PostProcessContext):
        await self._task.run(scripts=context.scripts, user_id=context.user_id, user_env=context.user_env)


class RelaunchStoppedProcesses(PostProcessTask):

    def __init__(self, context: OptimizationContext):
        self._context = context
        self._log = context.logger
        self._re_python_cmd: Optional[Pattern] = None

    def get_python_cmd_pattern(self) -> Pattern:
        if self._re_python_cmd is None:
            self._re_python_cmd = re.compile(r'^/.+/python\d*\s+(/.+)$')

        return self._re_python_cmd

    def should_run(self, context: PostProcessContext) -> bool:
        return bool(context.stopped_processes and context.user_id is not None)

    async def _run_command(self, name: str, cmd: str):
        try:
            await system.async_syscall(cmd, return_output=False, wait=False)
            self._log.info(f"Process '{name}' ({cmd}) relaunched")
        except:
            stack_log = traceback.format_exc().replace('\n', ' ')
            self._log.warning(f"An exception happened when relaunching process '{name}' ({cmd}): {stack_log}")

    def _run_user_command(self, name: str, cmd: str, user_id: int, user_env: Optional[Dict[str, str]] = None):
        try:
            Process(daemon=True, target=system.run_user_command, kwargs={'cmd': cmd, 'user_id': user_id, 'env': user_env, 'wait': False}).start()
            self._log.info(f"Process '{name}' ({cmd}) relaunched (user={user_id})")
        except:
            stack_log = traceback.format_exc().replace('\n', ' ')
            self._log.warning(f"An exception happened when relaunching process '{name}' ({cmd}) [user={user_id}]: {stack_log}")

    async def run(self, context: PostProcessContext):
        self_is_root = is_root_user()
        root_request = is_root_user(context.user_id)

        if not self_is_root and root_request:
            self._log.warning(f"It will not be possible to launch the following root processes: {', '.join((c[0] for c in context.stopped_processes))}")
            return

        running_cmds = await system.find_processes_by_command({p[1] for p in context.stopped_processes})

        for comm_cmd in context.stopped_processes:
            name, cmd = comm_cmd[0], comm_cmd[1]
            if running_cmds and cmd in running_cmds:
                self._log.warning(f"Process '{name}' ({cmd}) is alive. Skipping its relaunching.")
                continue

            python_cmd = self.get_python_cmd_pattern().findall(cmd)

            real_cmd = python_cmd[0] if python_cmd else cmd

            if self_is_root:
                if root_request:
                    await self._run_command(name, real_cmd)
                else:
                    self._run_user_command(name, real_cmd, context.user_id, context.user_env)
            else:
                await self._run_command(name, real_cmd)


class RestoreMouseCursor(PostProcessTask):

    def __init__(self, context: OptimizationContext):
        self._log = context.logger
        self._mouse_man = context.mouse_man

    def should_run(self, context: PostProcessContext) -> bool:
        return bool(context.restore_mouse_cursor)

    async def run(self, context: PostProcessContext):
        await self._mouse_man.show_cursor()


class RestoreCPUEnergyPolicyLevel(PostProcessTask):

    def __init__(self, context: OptimizationContext):
        self._log = context.logger
        self._man = context.cpuenergy_man

    def should_run(self, context: PostProcessContext):
        return context.restore_cpu_energy_policy

    async def run(self, context: PostProcessContext):
        async with self._man.lock():
            saved_state = self._man.saved_state

            if not saved_state:
                self._log.info("No CPU energy policy level saved state to restore")
                return

            self._log.info(f"Restoring CPUs energy policy levels: "
                           f"{', '.join(f'{idx}={state}' for idx, state in sorted(saved_state.items()))}")

            cpus_changed = await self._man.change_states(saved_state)

            if not cpus_changed:
                self._log.error("Could not restore CPUs energy policy levels")
                return

            restored, not_restored = [], []

            for idx, changed in cpus_changed.items():
                if changed:
                    restored.append(idx)
                else:
                    not_restored.append(str(idx))

            if not_restored:
                self._log.warning(f"Could not restore the energy policy levels of the following CPUs: "
                                  f"{', '.join(sorted(not_restored))}")

            if restored:
                self._man.clear_state(*restored)
                self._log.debug(f"Saved CPUs energy policy levels cleared: "
                                f"{', '.join(str(i) for i in sorted(restored))}")


class PostProcessTaskManager:

    __ORDER: Dict[Type[PostProcessTask], int] = {ReEnableWindowCompositor: 0,
                                                 PostStopProcesses: 1,
                                                 RestoreMouseCursor: 2,
                                                 RestoreGPUState: 3,
                                                 RestoreCPUGovernor: 4,
                                                 RestoreCPUEnergyPolicyLevel: 5,
                                                 RelaunchStoppedProcesses: 6,
                                                 RunFinishScripts: 7}

    def __init__(self, context: OptimizationContext, tasks: Optional[List[PostProcessTask]] = None):
        self._tasks = tasks if tasks else [cls(context) for cls in PostProcessTask.__subclasses__() if cls != self.__class__]
        self._tasks.sort(key=self._sort)

    def _sort(self, task: PostProcessTask) -> int:
        return self.__ORDER.get(task.__class__, 100)

    def get_available_tasks(self):
        return [*self._tasks]

    def create_tasks(self, context: PostProcessContext) -> Optional[List[Awaitable]]:
        if self._tasks:
            to_run = [t.run(context) for t in self._tasks if t.should_run(context)]
            if to_run:
                return to_run
