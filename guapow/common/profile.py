from typing import Optional, Set, Dict, Tuple

from guapow import __app_name__
from guapow.common.model import FileModel
from guapow.common.users import is_root_user


def get_default_profile_name() -> str:
    return 'default'


def get_root_profile_path(name: str) -> str:
    return f'/etc/{__app_name__}/{name}.profile'


def get_user_profile_path(name: str, user_name: str) -> str:
    return f'/home/{user_name}/.config/{__app_name__}/{name}.profile'


def get_profile_dir(user_id: int, user_name: str) -> str:
    return f'/etc/{__app_name__}' if is_root_user(user_id) else f'/home/{user_name}/.config/{__app_name__}'


def get_possible_profile_paths_by_priority(name: str, user_id: Optional[int], user_name: Optional[str]) -> Tuple[str, Optional[str]]:  # using tuple instead of list to reduce memory usage
    is_root = is_root_user(user_id)

    if not is_root and user_name:
        return get_user_profile_path(name, user_name), get_root_profile_path(name)
    else:
        return get_root_profile_path(name), None


class StopProcessSettings(FileModel):

    def __init__(self, node_name: str, processes: Optional[Set[str]], relaunch: Optional[bool] = None):
        self.processes = processes
        self.relaunch = relaunch
        self._mapping = {f"{node_name}{f'.{p}' if p else ''}": v for p, v in
                         {'': ('processes', Set[str], None), 'relaunch': ('relaunch', bool, True)}.items()}

    def get_file_mapping(self) -> Dict[str, Tuple[str, type, Optional[object]]]:
        return self._mapping

    def is_valid(self) -> bool:
        return bool(self.processes)

    def get_file_root_node_name(self) -> Optional[str]:
        pass
