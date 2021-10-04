import asyncio
import os
import subprocess
import traceback
from io import StringIO
from multiprocessing import Manager, Process
from multiprocessing.managers import DictProxy
from re import Pattern
from typing import Optional, Tuple, Dict, List, Set, Callable, TypeVar, Collection

BAD_USER_ENV_VARS = {'LD_PRELOAD'}
T = TypeVar('T')


def syscall(cmd: str, shell: bool = True, cwd: Optional[str] = None, custom_env: Optional[dict] = None, stdin: bool = False, return_output: bool = True) -> Tuple[int, Optional[str]]:
    params = {
        'args': cmd.split(' ') if not shell else [cmd],
        'stdout': subprocess.PIPE if return_output else subprocess.DEVNULL,
        'stderr': subprocess.STDOUT if return_output else subprocess.DEVNULL,
        'shell': shell
    }

    if not stdin:
        params['stdin'] = subprocess.DEVNULL

    if cwd is not None:
        params['cwd'] = cwd

    if custom_env is not None:
        params['env'] = custom_env

    try:
        p = subprocess.Popen(**params)
    except:
        traceback.print_exc()
        return False, None

    str_output = StringIO('') if return_output else None

    if str_output:
        for stream in p.stdout:
            string = stream.decode()

            if return_output:
                str_output.write(string)

    p.wait()

    if str_output and return_output:
        str_output.seek(0)
        return p.returncode, str_output.read()
    else:
        return p.returncode, None


async def async_syscall(cmd: str, shell: bool = True, cwd: Optional[str] = None, custom_env: Optional[Dict[str, str]] = None, stdin: bool = False, return_output: bool = True, wait: bool = True) -> Tuple[int, Optional[str]]:
    params = {
        'cmd': cmd,
        'stdout': subprocess.PIPE if return_output else subprocess.DEVNULL,
        'stderr': subprocess.STDOUT if return_output else subprocess.DEVNULL,
    }

    if not stdin:
        params['stdin'] = subprocess.DEVNULL

    if cwd is not None:
        params['cwd'] = cwd

    if custom_env is not None:
        params['env'] = custom_env

    try:
        if shell:
            p = await asyncio.create_subprocess_shell(**params)
        else:
            p = await asyncio.create_subprocess_exec(**params)
    except:
        traceback.print_exc()
        return False, None

    output = None

    if return_output:
        string = StringIO()

        try:
            async for stream in p.stdout:
                if stream:
                    string.write(stream.decode())
        except ValueError:
            return 1, None

        string.seek(0)
        output = string.read()

    if wait:
        await p.wait()

    return p.returncode, (output if output is not None else None)


async def match_syscall(cmd: str, match: Callable[[str], Optional[T]]) -> Optional[T]:
    p = await asyncio.create_subprocess_shell(cmd=cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)

    try:
        async for stream in p.stdout:
            if stream:
                res = match(stream.decode())

                if res is not None:
                    return res

    except ValueError:
        return


async def find_process_by_name(name_pattern: Pattern, last_match: bool = False) -> Optional[Tuple[int, str]]:
    def _match(line: str) -> Optional[Tuple[int, str]]:
        line_strip = line.strip()

        if line_strip:
            line_split = line_strip.split('#', 1)

            if len(line_split) > 1:
                name = line_split[1].strip()
                if name_pattern.match(name):
                    try:
                        return int(line_split[0]), name
                    except ValueError:
                        return

    return await match_syscall(cmd=f'ps -Ao "%p#%c" -ww --no-headers --sort={"-" if last_match else ""}pid',
                               match=_match)


async def find_process_by_command(patterns: Set[Pattern], last_match: bool = False) -> Optional[Tuple[int, str]]:
    def _match(line: str) -> Optional[Tuple[int, str]]:
        line_strip = line.strip()

        if line_strip:
            line_split = line_strip.split('#', 1)

            if len(line_split) > 1:
                for p in patterns:
                    cmd = line_split[1].strip()
                    if p.match(cmd):
                        try:
                            return int(line_split[0]), cmd
                        except ValueError:
                            break

    return await match_syscall(cmd=f'ps -Ao "%p#%a" -ww --no-headers --sort={"-" if last_match else ""}pid',
                               match=_match)


async def find_processes_by_command(commands: Set[str], last_match: bool = False) -> Optional[Dict[str, int]]:
    matches = {}

    def _match(line: str) -> Optional[Dict[str, int]]:
        line_strip = line.strip()

        if line_strip:
            line_split = line_strip.split('#', 1)

            if len(line_split) > 1:
                cmd = line_split[1].strip()
                if cmd in commands and cmd not in matches:
                    try:
                        matches[cmd] = int(line_split[0])
                    except ValueError:
                        pass

            if len(matches) == len(commands):
                return matches

    await match_syscall(cmd=f'ps -Ao "%p#%a" -ww --no-headers --sort={"-" if last_match else ""}pid', match=_match)
    return matches if matches else None


async def find_pids_by_names(names: Collection[str], last_match: bool = False) -> Optional[Dict[str, int]]:
    matches: Dict[str, int] = {}

    def _match(line: str) -> Optional[Dict[str, int]]:
        line_strip = line.strip()

        if line_strip:
            line_split = line_strip.split('#', 1)

            if len(line_split) > 1:
                current_name = line_split[1].strip()

                if current_name and current_name not in matches and current_name in names:
                    try:
                        matches[current_name] = int(line_split[0])
                    except ValueError:
                        pass

        if len(matches) == len(names):
            return matches

    await match_syscall(cmd=f'ps -Ao "%p#%c" -ww --no-headers --sort={"-" if last_match else ""}pid', match=_match)
    return matches if matches else None


async def find_commands_by_pids(pids: Set[int]) -> Optional[Dict[int, str]]:
    if pids:
        matches: Dict[int, str] = {}

        def _match(line: str) -> Optional[Dict[int, str]]:
            line_strip = line.strip()

            if line_strip:
                line_split = line_strip.split('#', 1)

                if len(line_split) > 1:
                    try:
                        current_pid = int(line_split[0])
                    except ValueError:
                        return

                    if current_pid in pids:
                        matches[current_pid] = line_split[1].strip()

            if len(matches) == len(pids):
                return matches

        await match_syscall(cmd='ps -Ao "%p#%a" -ww --no-headers', match=_match)
        return matches if matches else None


def read_current_pids() -> Set[int]:
    return {int(pid) for pid in os.listdir('/proc') if pid.isnumeric()}


async def map_pids_by_ppid() -> Optional[Dict[int, Set[int]]]:
    code, output = await async_syscall('ps -Ao "%P#%p" -ww --no-headers')

    if code == 0 and output:
        all_procs = {}
        for line in output.split('\n'):
            if line:
                line_strip = line.strip()

                if line_strip:
                    line_split = line_strip.split('#', 1)

                    if len(line_split) == 2:
                        try:
                            current_ppid, current_pid = int(line_split[0].strip()), int(line_split[1].strip())
                        except ValueError:
                            continue

                        current_children = all_procs.get(current_ppid, set())
                        current_children.add(current_pid)
                        all_procs[current_ppid] = current_children

        return all_procs


async def find_children(ppids: Set[int], ppid_map: Optional[Dict[int, Set[int]]] = None, children: Optional[List[int]] = None) -> Optional[List[int]]:
    pids_by_ppids = ppid_map if ppid_map is not None else (await map_pids_by_ppid())
    children_list = children if children is not None else []

    if pids_by_ppids:
        current_children = set()
        for pid in ppids:
            pid_children = pids_by_ppids.get(pid)

            if pid_children:
                current_children.update((p for p in pid_children if p not in children_list and p not in ppids))

        if current_children:
            await find_children(current_children, pids_by_ppids, children_list)
            children_list.extend(current_children)

    return children_list


def run_user_command(cmd: str, user_id: int, wait: bool, timeout: Optional[float] = None,
                     env: Optional[dict] = None, response: Optional[DictProxy] = None, forbidden_env_vars: Optional[Set[str]] = BAD_USER_ENV_VARS):
    args = {"args": cmd, "shell": True, "stdin": subprocess.DEVNULL,
            "stdout": subprocess.PIPE if wait else subprocess.DEVNULL,
            "stderr": subprocess.STDOUT if wait else subprocess.DEVNULL}

    if env:
        if forbidden_env_vars:
            args['env'] = {k: v for k, v in env.items() if k not in forbidden_env_vars}
        else:
            args['env'] = env

    try:
        os.setpriority(os.PRIO_PROCESS, os.getpid(), 0)  # always launch a command with nice 0
        os.setuid(user_id)

        p = subprocess.Popen(**args)

        if response is not None:
            response['pid'] = p.pid

        if timeout is not None and timeout > 0:
            p.wait(timeout)
        elif wait:
            p.wait()

        if response is not None:
            response['exitcode'] = p.returncode

            string = StringIO()
            for output in p.stdout:
                decoded = output.decode()
                string.write(decoded)

            string.seek(0)
            response['output'] = string.read()

    except Exception as e:
        if response is not None:
            response['exitcode'] = 1
            response['output'] = traceback.format_exc()


async def run_async_user_process(cmd: str, user_id: int, user_env: Optional[dict], forbidden_env_vars: Optional[Set[str]] = BAD_USER_ENV_VARS) -> Tuple[int, Optional[str]]:
    res = new_user_process_response()

    try:
        p = Process(target=run_user_command, kwargs={'cmd': cmd, 'user_id': user_id, 'wait': True, 'timeout': None, 'env': user_env,
                                                     'response': res, 'forbidden_env_vars': forbidden_env_vars})
        p.start()

        while p.is_alive():
            await asyncio.sleep(0.001)

        return res['exitcode'], res['output']
    except:
        error_msg = traceback.format_exc().replace('\n', ' ')
        return 1, error_msg


def new_user_process_response() -> DictProxy:
    proxy_res = Manager().dict()
    proxy_res['exitcode'] = None
    proxy_res['output'] = None
    proxy_res['pid'] = None
    return proxy_res

