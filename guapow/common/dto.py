import os
import time
from datetime import datetime
from typing import Optional, Set, Dict


class OptimizationRequest:

    NOT_LOGGABLE_FIELDS = {'user_env', 'user_id'}

    def __init__(self, pid: Optional[int], command: Optional[str], user_name: Optional[str], profile: Optional[str] = None,
                 created_at: Optional[float] = time.time(), config: Optional[str] = None,
                 profile_config: Optional[str] = None, related_pids: Optional[Set[int]] = None,
                 user_env: Optional[dict] = None, stopped_processes: Optional[Dict[str, Optional[str]]] = None,
                 relaunch_stopped_processes: Optional[bool] = None):
        self.pid = pid
        self.command = command
        self.profile = profile
        self.user_name = user_name
        self.created_at = created_at
        self.config = config
        self.profile_config = profile_config
        self.related_pids = related_pids if related_pids is None or isinstance(related_pids, set) else {*related_pids}  # processes that were initialized with/for the root process
        self.user_env = user_env  # only informed to scripts to be executed at the user level
        self.stopped_processes = stopped_processes
        self.relaunch_stopped_processes = relaunch_stopped_processes
        self.user_id: Optional[int] = None

    def is_valid(self) -> bool:
        return self.pid is not None and self.pid >= 0 and \
               bool(self.command) and \
               bool(self.user_name) and self.user_id is not None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}

    def has_full_configuration(self) -> bool:
        return bool(self.config)

    @property
    def is_self_request(self) -> bool:
        return self.pid is None and self.command is None and self.user_name is None

    @classmethod
    def new_from_config(cls, config: str, **kwargs) -> "OptimizationRequest":
        if kwargs and 'profile_config' in kwargs:
            del kwargs['profile_config']

        return cls(config=config, **kwargs)

    @classmethod
    def new_from_profile(cls, **kwargs) -> "OptimizationRequest":
        if kwargs and 'config' in kwargs:
            del kwargs['config']

        return cls(**kwargs)

    def prepare(self):
        """sets up required/important properties"""

        if self.user_env is None:
            self.user_env = {}

        if 'DISPLAY' not in self.user_env:
            self.user_env['DISPLAY'] = os.getenv('DISPLAY', ':0')

    def __repr__(self) -> str:
        return ', '.join(['{}: {}'.format(k, str(datetime.fromtimestamp(v)) if k == 'created_at' else v) for k, v in self.__dict__.items() if v is not None and k not in self.NOT_LOGGABLE_FIELDS]).replace('\n', ' ')

    def __eq__(self, other):
        if isinstance(other, OptimizationRequest):
            return self.__dict__ == other.__dict__

    @classmethod
    def self_request(cls) -> "OptimizationRequest":
        return cls(pid=None, command=None, user_name=None, created_at=time.time())
