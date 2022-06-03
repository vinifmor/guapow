from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Set, Type, Tuple

from guapow.common.model import ScriptSettings
from guapow.service.optimizer.gpu import GPUState, GPUDriver
from guapow.service.optimizer.post_process.summary import PostProcessSummary
from guapow.service.optimizer.task.model import CPUState


class PostProcessContext:

    def __init__(self, restorable_cpus: Optional[List[CPUState]],
                 restorable_gpus: Optional[Dict[Type[GPUDriver], List[GPUState]]],
                 pids_to_stop: Optional[Set[int]],
                 scripts: Optional[List[ScriptSettings]],
                 user_id: Optional[int],
                 user_env: Optional[dict],
                 restore_compositor: Optional[bool],
                 stopped_processes: Optional[List[Tuple[str, Optional[str]]]],
                 not_stopped_processes: Optional[Set[str]],
                 restore_mouse_cursor: Optional[bool],
                 restore_cpu_energy_policy: Optional[bool]):
        self.restorable_cpus = restorable_cpus
        self.restorable_gpus = restorable_gpus
        self.pids_to_stop = pids_to_stop
        self.scripts = scripts
        self.user_env = user_env
        self.user_id = user_id
        self.restore_compositor = restore_compositor
        self.stopped_processes = stopped_processes
        self.not_stopped_processes = not_stopped_processes
        self.restore_mouse_cursor = restore_mouse_cursor
        self.restore_cpu_energy_policy = restore_cpu_energy_policy

    @classmethod
    def empty(cls):
        return cls(restorable_cpus=None, restorable_gpus=None, pids_to_stop=None,
                   scripts=None, user_env=None, user_id=None, restore_compositor=None,
                   stopped_processes=None, restore_mouse_cursor=None, not_stopped_processes=None,
                   restore_cpu_energy_policy=None)


class PostContextFiller(ABC):

    @abstractmethod
    def fill(self, context: PostProcessContext, summary: PostProcessSummary):
        pass


class RestorableCPUGovernorsFiller(PostContextFiller):

    def fill(self, context: PostProcessContext, summary: PostProcessSummary):
        if not summary.cpus_in_use and summary.previous_cpus_states:
            context.restorable_cpus = summary.previous_cpus_states


class RestorableCPUEnergyPolicyLevelFiller(PostContextFiller):

    def fill(self, context: PostProcessContext, summary: PostProcessSummary):
        context.restore_cpu_energy_policy = not summary.keep_cpu_energy_policy and summary.restore_cpu_energy_policy


class RestorableGPUsFiller(PostContextFiller):

    def fill(self, context: PostProcessContext, summary: PostProcessSummary):
        if summary.previous_gpus_states:
            gpus = summary.previous_gpus_states

            if summary.gpus_in_use:
                gpus_in_use = summary.gpus_in_use

                drivers_to_restore = {*gpus.keys()}
                for driver in drivers_to_restore:
                    ids = gpus_in_use.get(driver)

                    if ids:
                        to_restore = [s for s in gpus[driver] if s.id not in ids]

                        if to_restore:
                            gpus[driver] = to_restore
                        else:
                            del gpus[driver]

            if gpus:
                context.restorable_gpus = gpus


class SortedFinishScriptsFiller(PostContextFiller):

    def fill(self, context: PostProcessContext, summary: PostProcessSummary):
        if summary.post_scripts:
            sorted_scripts = []

            for _, scripts in sorted(summary.post_scripts.items()):  # sorted by optimization timestamp
                sorted_scripts.append(scripts)

            context.scripts = sorted_scripts


class SortedProcessesToRelaunchFiller(PostContextFiller):

    def fill(self, context: PostProcessContext, summary: PostProcessSummary):
        if summary.processes_relaunch_by_time:
            sorted_procs, unique_procs, stopped_names, not_stopped_names = [], set(), set(), set()

            for _, comm_cmd in sorted(summary.processes_relaunch_by_time.items()):  # sorted by optimization timestamp
                for comm, cmd in comm_cmd.items():
                    if not summary.processes_not_relaunch or comm not in summary.processes_not_relaunch:
                        if not cmd:
                            not_stopped_names.add(comm)
                        else:
                            proc = (comm, cmd)

                            if proc not in unique_procs:
                                stopped_names.add(comm)
                                unique_procs.add(proc)
                                sorted_procs.append(proc)

            if sorted_procs:
                context.stopped_processes = sorted_procs

            if not_stopped_names:
                actually_not_stopped = not_stopped_names.difference(stopped_names)

                if actually_not_stopped:
                    context.not_stopped_processes = actually_not_stopped


class PostProcessContextMapper(PostContextFiller):

    __instance: Optional["PostProcessContextMapper"] = None

    def __init__(self, fillers: Optional[List[PostContextFiller]]):
        self._fillers = fillers

    @classmethod
    def instance(cls) -> "PostProcessContextMapper":
        if cls.__instance is None:
            fillers = [sub() for sub in PostContextFiller.__subclasses__() if sub != cls]
            cls.__instance = cls(fillers)

        return cls.__instance

    def fill(self, context: PostProcessContext, summary: PostProcessSummary):
        if self._fillers:
            for filler in self._fillers:
                filler.fill(context, summary)

    def get_fillers(self) -> Optional[List[PostContextFiller]]:
        return [*self._fillers] if self._fillers else None

    def map(self, summary: PostProcessSummary) -> PostProcessContext:
        context = PostProcessContext.empty()

        if summary.user_id is not None:
            context.user_id = summary.user_id

        if summary.user_env:
            context.user_env = summary.user_env

        if summary.pids_to_stop:
            context.pids_to_stop = summary.pids_to_stop

        context.restore_compositor = not summary.keep_compositor_disabled and summary.restore_compositor
        context.restore_mouse_cursor = not summary.keep_mouse_hidden and summary.restore_mouse_cursor

        self.fill(context, summary)
        return context
