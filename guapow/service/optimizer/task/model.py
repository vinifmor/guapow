from abc import ABC, abstractmethod
from logging import Logger
from typing import Optional, Tuple, Dict, Set, Type

from guapow.common.dto import OptimizationRequest
from guapow.common.model import ScriptSettings
from guapow.service.optimizer.cpu import CPUFrequencyManager, CPUEnergyPolicyManager
from guapow.service.optimizer.flow import OptimizationQueue
from guapow.service.optimizer.gpu import GPUManager, GPUDriver, GPUState
from guapow.service.optimizer.mouse import MouseCursorManager
from guapow.service.optimizer.profile import OptimizationProfile
from guapow.service.optimizer.win_compositor import WindowCompositor


class OptimizationContext:

    def __init__(self, gpu_man: Optional[GPUManager], logger: Optional[Logger],
                 cpufreq_man: Optional[CPUFrequencyManager], cpuenergy_man: Optional[CPUEnergyPolicyManager],
                 mouse_man: Optional[MouseCursorManager], queue: Optional[OptimizationQueue], cpu_count: int,
                 launcher_mapping_timeout: float, renicer_interval: float,
                 compositor: Optional[WindowCompositor] = None,  allow_root_scripts: bool = False,
                 compositor_disabled_context: Optional[dict] = None):

        self.queue = queue
        self.gpu_man = gpu_man
        self.logger = logger
        self.cpufreq_man = cpufreq_man
        self.cpuenergy_man = cpuenergy_man
        self.mouse_man = mouse_man
        self.cpu_count = cpu_count
        self.compositor = compositor
        self.allow_root_scripts = allow_root_scripts
        self.launcher_mapping_timeout = launcher_mapping_timeout
        self.compositor_disabled_context = compositor_disabled_context  # if the compositor was disabled by the Optimizer
        self.renicer_interval = renicer_interval

    @classmethod
    def empty(cls) -> "OptimizationContext":
        return cls(gpu_man=None, mouse_man=None, logger=None, cpufreq_man=None, queue=None,
                   cpu_count=0, launcher_mapping_timeout=0, renicer_interval=0, cpuenergy_man=None)

    async def is_mouse_cursor_hidden(self) -> Optional[bool]:
        return await self.mouse_man.is_cursor_hidden() if self.mouse_man else None


class CPUState:

    def __init__(self, governors: Dict[str, Set[int]]):
        self.governors = governors

    def __repr__(self):
        return f'{self.__class__.__name__} {self.__dict__}'

    def __eq__(self, other):
        if isinstance(other, CPUState):
            return self.governors == other.governors

        return False

    def __hash__(self):
        return hash(self.governors)


class OptimizedProcess:

    def __init__(self, request: OptimizationRequest, created_at: float, profile: Optional[OptimizationProfile] = None,
                 previous_gpus_states: Optional[Dict[Type[GPUDriver], Set[GPUState]]] = None,
                 previous_cpu_state: Optional[CPUState] = None, stopped_after_launch: Optional[Dict[str, str]] = None,
                 cpu_energy_policy_changed: bool = False):
        self.created_at = created_at
        self.request = request
        self.profile = profile
        self.previous_gpus_states = previous_gpus_states
        self.previous_cpu_state = previous_cpu_state
        self.stopped_after_launch = stopped_after_launch
        self.alive = True
        self.related_pids = {*self.request.related_pids} if self.request and self.request.related_pids else set()
        self.pid = request.pid if self.request else None
        self.cpu_energy_policy_changed = cpu_energy_policy_changed

    def should_be_watched(self) -> bool:
        return bool(self.pid is not None and any([self.related_pids,
                                                  self.previous_cpu_state,
                                                  self.previous_gpus_states,
                                                  self.post_scripts,
                                                  self.requires_compositor_disabled,
                                                  self.stopped_processes,
                                                  self.requires_mouse_hidden,
                                                  self.stopped_after_launch,
                                                  self.cpu_energy_policy_changed]))

    @property
    def source_pid(self) -> Optional[int]:
        return self.request.pid if self.request else None

    @property
    def user_env(self) -> Optional[Dict[str, str]]:
        return self.request.user_env if self.request else None

    @property
    def user_id(self) -> Optional[int]:
        return self.request.user_id if self.request else None

    @property
    def post_scripts(self) -> Optional[ScriptSettings]:
        return self.profile.finish_scripts if self.profile else None

    @property
    def stopped_processes(self) -> Optional[Dict[str, Optional[str]]]:
        return self.request.stopped_processes if self.request else None

    @property
    def relaunch_stopped_processes(self) -> Optional[bool]:
        return self.request.relaunch_stopped_processes if self.request else None

    @property
    def requires_mouse_hidden(self) -> bool:
        return bool(self.profile and self.profile.hide_mouse)

    @property
    def requires_compositor_disabled(self) -> bool:
        return bool(self.profile and self.profile.compositor and self.profile.compositor.off)

    @property
    def relaunch_stopped_after_launch(self) -> bool:
        return bool(self.profile.stop_after.relaunch) if self.profile and self.profile.stop_after else False

    def get_display(self) -> str:
        return self.request.user_env.get('DISPLAY', ':0') if self.request and self.request.user_env else ':0'

    def get_pids(self) -> Optional[Set[int]]:
        if self.request:
            pids = set()

            if self.pid is not None:
                pids.add(self.pid)

            if self.request.pid is not None:
                pids.add(self.request.pid)

            return pids

    def __eq__(self, other):
        if not isinstance(other, OptimizedProcess):
            return False

        for p, v in self.__dict__.items():
            if v != getattr(other, p):
                return False

        return True

    def __hash__(self):
        hash_sum = 0

        for _, v in sorted(self.__dict__.items()):
            hash_sum += hash(v)

        return hash_sum

    def __repr__(self):
        return f'{self.__class__.__name__} {self.__dict__}'


class Task(ABC):

    @abstractmethod
    def __init__(self, context: OptimizationContext):
        pass

    @abstractmethod
    async def is_available(self) -> Tuple[bool, Optional[str]]:
        pass

    def is_allowed_for_self_requests(self) -> bool:
        return False

    @abstractmethod
    async def should_run(self, process: OptimizedProcess) -> bool:
        pass

    @abstractmethod
    async def run(self, process: OptimizedProcess):
        pass

