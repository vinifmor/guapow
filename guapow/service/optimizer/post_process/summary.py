from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Set, Type, Tuple

from guapow.common.model import ScriptSettings
from guapow.service.optimizer.gpu import GPUState, GPUDriver
from guapow.service.optimizer.task.model import CPUState, OptimizedProcess, OptimizationContext


class PostProcessSummary:

    def __init__(self, pids_alive: Optional[Set[int]], user_id: Optional[int], user_env: Optional[Dict[str, str]], restore_compositor: Optional[bool],
                 previous_cpu_states: Optional[List[CPUState]], previous_gpus_states: Optional[Dict[Type[GPUDriver], List[GPUState]]],
                 pids_to_stop: Optional[Set[int]], processes_relaunch_by_time: Optional[Dict[float, Dict[str, str]]],
                 post_scripts: Optional[Dict[float, ScriptSettings]], keep_compositor_disabled: Optional[bool], cpus_in_use: Optional[bool],
                 gpus_in_use: Optional[Dict[Type[GPUDriver], Set[int]]], processes_not_relaunch: Optional[Set[str]],
                 processes_to_relaunch: Optional[Dict[str, str]], dead_pids: Optional[Set[Tuple[int, int]]], restore_mouse_cursor: Optional[bool],
                 keep_mouse_hidden: Optional[bool], keep_cpu_energy_policy: Optional[bool],
                 restore_cpu_energy_policy: Optional[bool]):
        self.pids_alive = pids_alive
        self.user_id = user_id
        self.user_env = user_env
        self.previous_cpus_states = previous_cpu_states
        self.previous_gpus_states = previous_gpus_states
        self.pids_to_stop = pids_to_stop
        self.processes_relaunch_by_time = processes_relaunch_by_time
        self.post_scripts = post_scripts
        self.keep_compositor_disabled = keep_compositor_disabled
        self.restore_compositor = restore_compositor
        self.cpus_in_use = cpus_in_use
        self.gpus_in_use = gpus_in_use
        self.processes_not_relaunch = processes_not_relaunch
        self.processes_to_relaunch = processes_to_relaunch
        self.dead_pids = dead_pids
        self.restore_mouse_cursor = restore_mouse_cursor
        self.keep_mouse_hidden = keep_mouse_hidden
        self.keep_cpu_energy_policy = keep_cpu_energy_policy
        self.restore_cpu_energy_policy = restore_cpu_energy_policy

    @classmethod
    def empyt(cls) -> "PostProcessSummary":
        return cls(pids_alive=None, user_id=None, user_env=None, restore_compositor=None, previous_cpu_states=None,
                   cpus_in_use=None, previous_gpus_states=None, pids_to_stop=None, processes_relaunch_by_time=None,
                   post_scripts=None, gpus_in_use=None, keep_compositor_disabled=None, processes_not_relaunch=None,
                   processes_to_relaunch=None, dead_pids=None, keep_mouse_hidden=None, restore_mouse_cursor=None,
                   keep_cpu_energy_policy=None, restore_cpu_energy_policy=None)


class PostProcessSummarizer(ABC):

    @abstractmethod
    async def fill(self, summary: PostProcessSummary, process: OptimizedProcess, main_context: OptimizationContext):
        pass


class UserEnvironmentSummarizer(PostProcessSummarizer):

    async def fill(self, summary: PostProcessSummary, process: OptimizedProcess, main_context: OptimizationContext):
        if not process.alive and process.user_env:
            if summary.user_env is None:
                summary.user_env = {}

            summary.user_env.update(process.user_env)


class UserIdSummarizer(PostProcessSummarizer):

    async def fill(self, summary: PostProcessSummary, process: OptimizedProcess, main_context: OptimizationContext):
        if not process.alive and process.user_id is not None:
            summary.user_id = process.user_id


class ProcessesToStopSummarizer(PostProcessSummarizer):

    async def fill(self, summary: PostProcessSummary, process: OptimizedProcess, main_context: OptimizationContext):
        if not process.alive and process.related_pids and summary.pids_alive:
            if summary.pids_to_stop is None:
                summary.pids_to_stop = set()

            summary.pids_to_stop.update({pid for pid in process.related_pids if pid in summary.pids_alive})


class MouseCursorStateSummarizer(PostProcessSummarizer):

    async def fill(self, summary: PostProcessSummary, process: OptimizedProcess, main_context: OptimizationContext):
        if process.requires_mouse_hidden:
            if process.alive:
                summary.keep_mouse_hidden = True
            elif await main_context.is_mouse_cursor_hidden():  # if the mouse cursor was hidden by the Optimizer
                summary.restore_mouse_cursor = True


class CompositorStateSummarizer(PostProcessSummarizer):

    async def fill(self, summary: PostProcessSummary, process: OptimizedProcess, main_context: OptimizationContext):
        if process.requires_compositor_disabled:
            if process.alive:
                summary.keep_compositor_disabled = True
            elif main_context.compositor_disabled_context is not None:
                summary.restore_compositor = True


class CPUGovernorStateSummarizer(PostProcessSummarizer):

    async def fill(self, summary: PostProcessSummary, process: OptimizedProcess, main_context: OptimizationContext):
        if process.previous_cpu_state:
            if process.alive:
                summary.cpus_in_use = True
            else:
                if summary.previous_cpus_states is None:
                    summary.previous_cpus_states = []

                summary.previous_cpus_states.append(process.previous_cpu_state)


class CPUEnergyPolicyLevelSummarizer(PostProcessSummarizer):

    async def fill(self, summary: PostProcessSummary, process: OptimizedProcess, main_context: OptimizationContext):
        if process.cpu_energy_policy_changed:
            if process.alive:
                summary.keep_cpu_energy_policy = True
            else:
                summary.restore_cpu_energy_policy = True


class GPUStateSummarizer(PostProcessSummarizer):

    async def fill(self, summary: PostProcessSummary, process: OptimizedProcess, main_context: OptimizationContext):
        if process.previous_gpus_states:
            if process.alive:
                if summary.gpus_in_use is None:
                    summary.gpus_in_use = {}

                for driver, states in process.previous_gpus_states.items():
                    ids = summary.gpus_in_use.get(driver, set())
                    ids.update({s.id for s in states})
                    summary.gpus_in_use[driver] = ids
            else:
                if summary.previous_gpus_states is None:
                    summary.previous_gpus_states = {}

                for driver, gpus_states in process.previous_gpus_states.items():
                    states = summary.previous_gpus_states.get(driver, [])
                    summary.previous_gpus_states[driver] = states
                    states.extend(gpus_states)


class ProcessesToRelaunchSummarizer(PostProcessSummarizer):

    def _fill(self, summary: PostProcessSummary, process: OptimizedProcess, processes: Dict[str, Optional[str]], relaunch: Optional[bool]):
        if process.alive:
            if summary.processes_not_relaunch is None:
                summary.processes_not_relaunch = set()

            summary.processes_not_relaunch.update(processes)
        else:
            if summary.processes_relaunch_by_time is None:
                summary.processes_relaunch_by_time = {}

            if relaunch:
                if summary.processes_to_relaunch:  # to always get the appropriate command (the clients might not have been able to inform the command, because the process was dead)
                    summary.processes_relaunch_by_time[process.created_at] = {comm: summary.processes_to_relaunch.get(comm, cmd) for comm, cmd in processes.items()}
                else:
                    summary.processes_relaunch_by_time[process.created_at] = processes
            elif summary.processes_to_relaunch:
                summary.processes_relaunch_by_time[process.created_at] = {comm: cmd for comm, cmd in processes.items() if
                                                                          comm in summary.processes_to_relaunch}

    async def fill(self, summary: PostProcessSummary, process: OptimizedProcess, main_context: OptimizationContext):
        if process.stopped_processes:
            self._fill(summary, process, process.stopped_processes, process.relaunch_stopped_processes)

        if process.stopped_after_launch:
            self._fill(summary, process, process.stopped_after_launch, process.relaunch_stopped_after_launch)


class FinishScriptsSummarizer(PostProcessSummarizer):

    async def fill(self, summary: PostProcessSummary, process: OptimizedProcess, main_context: OptimizationContext):
        if not process.alive and process.post_scripts:
            if summary.post_scripts is None:
                summary.post_scripts = {}

            summary.post_scripts[process.created_at] = process.post_scripts


class GeneralPostProcessSummarizer(PostProcessSummarizer):

    ANALYSER_ORDER: Dict[Type[PostProcessSummarizer], int] = {
        UserIdSummarizer: 0,
        UserEnvironmentSummarizer: 1,
        ProcessesToStopSummarizer: 2,
        CompositorStateSummarizer: 3,
        FinishScriptsSummarizer: 4,
        CPUGovernorStateSummarizer: 5,
        CPUEnergyPolicyLevelSummarizer: 6,
        GPUStateSummarizer: 7,
        ProcessesToRelaunchSummarizer: 8
    }

    __instance = None

    def __init__(self, fillers: Optional[List[PostProcessSummarizer]]):
        self._fillers = fillers

    @classmethod
    def sort_filler(cls, filler: PostProcessSummarizer) -> int:
        return cls.ANALYSER_ORDER.get(filler.__class__, 99)

    def get_fillers(self) -> Optional[List[PostProcessSummarizer]]:
        return [*self._fillers] if self._fillers else None

    @classmethod
    def instance(cls) -> "GeneralPostProcessSummarizer":
        if cls.__instance is None:
            fillers = [sub() for sub in PostProcessSummarizer.__subclasses__() if sub != cls]
            fillers.sort(key=cls.sort_filler)
            cls.__instance = cls(fillers)

        return cls.__instance

    async def fill(self, summary: PostProcessSummary, process: OptimizedProcess, main_context: OptimizationContext):
        if self._fillers:
            for analyser in self._fillers:
                await analyser.fill(summary, process, main_context)

    async def summarize(self, processes: List[OptimizedProcess], pids_alive: Set[int], processes_to_relaunch: Optional[Dict[str, Optional[str]]], context: OptimizationContext) -> PostProcessSummary:
        summary = PostProcessSummary.empyt()
        summary.processes_to_relaunch = processes_to_relaunch
        summary.pids_alive = pids_alive

        if processes:
            for idx, process in enumerate(processes):
                if not pids_alive or process.pid not in summary.pids_alive:
                    process.alive = False

                    if summary.dead_pids is None:
                        summary.dead_pids = set()

                    summary.dead_pids.add((idx, process.pid))

                await self.fill(summary, process, context)

        return summary
