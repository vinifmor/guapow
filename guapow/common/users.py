import os
import pwd

from typing import Dict, Optional


def map_home_users() -> Dict[str, int]:
    return {p.pw_name: p.pw_uid for p in pwd.getpwall() if (p.pw_name == 'root' or p.pw_dir.startswith('/home/'))}


def map_all_users() -> Dict[str, int]:
    return {p.pw_name: p.pw_uid for p in pwd.getpwall()}


def is_root_user(uid: Optional[int] = None) -> bool:
    return os.getuid() == 0 if uid is None else uid == 0
