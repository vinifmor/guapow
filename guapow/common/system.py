import asyncio
import os
import subprocess
import traceback
from datetime import datetime, timedelta
from io import StringIO
from re import Pattern
from typing import Optional, Tuple, Dict, List, Set, Callable, TypeVar, Collection, Generator

BAD_USER_ENV_VARS = {'LD_PRELOAD'}
T = TypeVar('T')


class ProcessTimedOutError(Exception):
    def __init__(self, pid: int):
        super(ProcessTimedOutError, self).__init__()
        self.pid = pid


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


async def run_async_process(cmd: str, user_id: Optional[int] = None, custom_env: Optional[dict] = None,
                            forbidden_env_vars: Optional[Set[str]] = BAD_USER_ENV_VARS,
                            wait: bool = True, timeout: Optional[float] = None, output: bool = True,
                            exception_output: bool = True) \
        -> Tuple[Optional[int], Optional[int], Optional[str]]:
    """
    Runs a process using the async API
    Args:
        cmd:
        user_id: if the process should be executed in behalf of a different user
        custom_env: custom environment variables available for the process to be executed
        forbidden_env_vars: environment variables that should not be passed to the process
        wait: if the process should be waited
        timeout: in seconds
        output: if the process output should be read and returned
        exception_output: if the traceback of an unexpected raised exception should be returned as the output
    Returns: a tuple containing the process id, exitcode and output as a String

    """
    args = {"cmd": cmd, "stdin": subprocess.DEVNULL,
            "stdout": subprocess.PIPE if output else subprocess.DEVNULL,
            "stderr": subprocess.STDOUT if output else subprocess.DEVNULL}

    if user_id is not None:
        args["preexec_fn"] = lambda: os.setuid(user_id)

    if custom_env:
        if forbidden_env_vars:
            args['env'] = {k: v for k, v in custom_env.items() if k not in forbidden_env_vars}
        else:
            args['env'] = custom_env

    try:
        p = await asyncio.create_subprocess_shell(**args)
    except Exception:
        return None, 1, (traceback.format_exc().replace('\n', ' ') if exception_output else None)

    if user_id is not None:  # set default niceness in case the process is executed in behalf of another user
        try:
            os.setpriority(os.PRIO_PROCESS, p.pid, 0)  # always launch a command with nice 0
        except Exception:
            pass  # do nothing in case the priority could not be changed

    should_wait = wait or (timeout and timeout > 0)
    try:
        if should_wait:
            if timeout is None or timeout < 0:
                return p.pid, await p.wait(), ((await p.stdout.read()).decode() if output else None)
            elif timeout and timeout > 0:
                timeout_at = datetime.now() + timedelta(seconds=timeout)

                while datetime.now() < timeout_at:
                    if p.returncode is not None:
                        return p.pid, p.returncode, ((await p.stdout.read()).decode() if output else None)

                    await asyncio.sleep(0.0005)

                raise ProcessTimedOutError(p.pid)

        return p.pid, p.returncode, None
    except ProcessTimedOutError:
        raise
    except Exception:
        return p.pid, 1, (traceback.format_exc().replace('\n', ' ') if exception_output else None)


async def map_processes_by_parent() -> Dict[int, Set[Tuple[int, str]]]:
    exitcode, output = await async_syscall(f'ps -Ao "%P#%p#%c" -ww --no-headers')

    if exitcode == 0 and output:
        proc_tree = dict()

        for line in output.split("\n"):
            line_strip = line.strip()

            if line_strip:
                line_split = line_strip.split('#', 2)

                if len(line_split) > 2:
                    ppid, pid, comm, = (e.strip() for e in line_split)
                    try:
                        ppid, pid = int(ppid), int(pid)
                    except ValueError:
                        continue

                    children = proc_tree.get(ppid)

                    if not children:
                        children = set()
                        proc_tree[ppid] = children

                    children.add((pid, comm))

        return proc_tree


def find_process_children(ppid: int, processes_by_parent: Dict[int, Set[Tuple[int, str]]],
                          comm_to_ignore: Optional[Set[str]] = None, already_found: Optional[Set[int]] = None,
                          recursive: bool = True) \
        -> Generator[Tuple[int, str, int], None, None]:
    found = already_found if already_found is not None else set()

    children = processes_by_parent.get(ppid)

    if children:
        for pid, comm in children:
            if (not comm_to_ignore or comm not in comm_to_ignore) and "<defunct>" not in comm:
                if pid not in found:
                    yield pid, comm, ppid
                    found.add(pid)

                if recursive:
                    for pid_, comm_, ppid_ in find_process_children(ppid=pid, processes_by_parent=processes_by_parent,
                                                                    comm_to_ignore=comm_to_ignore, already_found=found):
                        yield pid_, comm_, ppid_
