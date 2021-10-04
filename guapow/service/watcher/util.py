import asyncio
from typing import Dict, Tuple

from guapow.common.system import async_syscall


async def _map_processes_by_attribute(attr: str) -> Dict[int, str]:
    code, output = await async_syscall(f'ps -Ao "%p#%{attr}" -ww --no-headers')

    if code == 0:
        procs = {}
        for line in output.split('\n'):
            line_strip = line.strip()
            if line_strip:
                line_split = line_strip.split('#', 1)

                if len(line_split) > 1:
                    try:
                        procs[int(line_split[0])] = line_split[1].strip()
                    except ValueError:
                        continue

        return procs


async def map_processes() -> Dict[int, Tuple[str, str]]:
    pid_comm, pid_cmd = await asyncio.gather(_map_processes_by_attribute('c'), _map_processes_by_attribute('a'))

    if pid_comm and pid_cmd:
        res = {}
        for pid in {*pid_comm, *pid_cmd}:
            comm = pid_comm.get(pid)
            cmd = pid_cmd.get(pid)

            if comm and cmd:
                res[pid] = cmd, comm

        return res if res else None
