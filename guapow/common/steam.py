import os.path
import re
from typing import Optional, Tuple

RE_STEAM_CMD = re.compile(r'^.+\s+SteamLaunch\s+AppId\s*=\s*\d+\s+--\s+(.+)')
RE_PROTON_CMD = re.compile(r'^.+/proton\s+waitforexitandrun\s+(/.+)$')
RE_EXE_NAME = re.compile(r'^(.+\.\w+)(\s+.+)?$')


def get_exe_name(file_path: str) -> Optional[str]:
    exe_name = RE_EXE_NAME.findall(os.path.basename(file_path))
    return exe_name[0][0].strip() if exe_name else None


def get_proton_exec_name_and_paths(cmd: str) -> Optional[Tuple[Optional[str], str, str]]:
    if cmd:
        result = RE_PROTON_CMD.findall(cmd)
        if result:
            return get_exe_name(result[0]), 'Z:{}'.format(result[0].replace('/', '\\')), result[0]


def get_steam_runtime_command(cmd: str) -> Optional[str]:
    if cmd:
        result = RE_STEAM_CMD.findall(cmd)
        if result:
            return result[0].strip()
