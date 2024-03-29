import asyncio
import os
import re
import subprocess
from typing import Optional
from unittest import TestCase
from unittest.async_case import IsolatedAsyncioTestCase
from unittest.mock import patch, Mock, AsyncMock, MagicMock, PropertyMock

from guapow import __app_name__
from guapow.common import system
from guapow.common.system import find_pids_by_names, find_commands_by_pids, find_processes_by_command, \
    find_process_children, map_processes_by_parent, run_async_process, ProcessTimedOutError
from tests import AsyncIterator, AnyInstance


class FindProcessByNameTest(IsolatedAsyncioTestCase):

    @patch(f'{__app_name__}.common.system.asyncio.create_subprocess_shell', return_value=MagicMock(stdout=AsyncIterator([b' 456 xpto ', b' 123 abc '])))
    async def test__make_exact_comparisson(self, create_subprocess_shell: AsyncMock):
        proc_found = await system.find_process_by_name(re.compile('^abc$'))
        self.assertIsNotNone(proc_found)
        self.assertEqual(123, proc_found[0])
        self.assertEqual('abc', proc_found[1])
        create_subprocess_shell.assert_awaited_once_with(cmd='ps -Ao pid,comm -ww --no-headers --sort=pid', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)

    @patch(f'{__app_name__}.common.system.asyncio.create_subprocess_shell', side_effect=[
        MagicMock(stdout=AsyncIterator([b'456 xpto', b'123 abc'])),
        MagicMock(stdout=AsyncIterator([b'456 xpto', b'123 abc']))])
    async def test__make_regex_comparisson(self, create_subprocess_shell: AsyncMock):
        regex_no_match = re.compile('^.+b$')

        proc1_found = await system.find_process_by_name(regex_no_match)
        self.assertIsNone(proc1_found)

        re_match = re.compile('^.+b.+$')
        proc2_found = await system.find_process_by_name(re_match)
        self.assertEqual(123, proc2_found[0])
        self.assertEqual('abc', proc2_found[1])

        self.assertEqual(2, create_subprocess_shell.await_count)

    @patch(f'{__app_name__}.common.system.asyncio.create_subprocess_shell', return_value=MagicMock(stdout=AsyncIterator([b'123 ac', b'456 ab'])))
    async def test__return_first_last_match_when_last_match_is_false(self, create_subprocess_shell: AsyncMock):
        proc_found = await system.find_process_by_name(re.compile('^a.+$'))
        self.assertIsNotNone(proc_found)
        self.assertEqual(123, proc_found[0])
        self.assertEqual('ac', proc_found[1])
        create_subprocess_shell.assert_awaited_once_with(cmd='ps -Ao pid,comm -ww --no-headers --sort=pid', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)

    @patch(f'{__app_name__}.common.system.asyncio.create_subprocess_shell', return_value=MagicMock(stdout=AsyncIterator([b'456 ab', b'123 ac'])))
    async def test__return_last_match_when_last_match_is_true(self, create_subprocess_shell: AsyncMock):
        proc_found = await system.find_process_by_name(re.compile('^a.+$'), last_match=True)
        self.assertIsNotNone(proc_found)
        self.assertEqual(456, proc_found[0])
        self.assertEqual('ab', proc_found[1])
        create_subprocess_shell.assert_awaited_once_with(cmd='ps -Ao pid,comm -ww --no-headers --sort=-pid', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)


class FindProcessByCommandTest(IsolatedAsyncioTestCase):

    @patch(f'{__app_name__}.common.system.asyncio.create_subprocess_shell', return_value=MagicMock(stdout=AsyncIterator([b' 456 /bin/xpto ', b' 123 /opt/abc '])))
    async def test__make_exact_comparisson(self, create_subprocess_shell: MagicMock):
        proc_found = await system.find_process_by_command({re.compile('^/opt/abc$')})
        self.assertIsNotNone(proc_found)
        self.assertEqual(123, proc_found[0])
        self.assertEqual('/opt/abc', proc_found[1])
        create_subprocess_shell.assert_awaited_once_with(cmd='ps -Ao pid,args -ww --no-headers --sort=pid', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)

    @patch(f'{__app_name__}.common.system.asyncio.create_subprocess_shell', return_value=MagicMock(stdout=AsyncIterator([b' 456 /bin/xpto ', b' 123 /opt/abc '])))
    async def test__match_for_one_of_the_specified_patterns(self, create_subprocess_shell: AsyncMock):
        proc_found = await system.find_process_by_command({re.compile('^/def$'), re.compile('^/opt/abc$')})
        self.assertIsNotNone(proc_found)
        self.assertEqual(123, proc_found[0])
        self.assertEqual('/opt/abc', proc_found[1])
        create_subprocess_shell.assert_awaited_once()

    @patch(f'{__app_name__}.common.system.asyncio.create_subprocess_shell', side_effect=[
        MagicMock(stdout=AsyncIterator([b' 456 /bin/xpto', b' 123 /abcd -xpto '])),
        MagicMock(stdout=AsyncIterator([b' 456 /bin/xpto', b' 123 /abcd -xpto ']))
    ])
    async def test__make_regex_comparisson(self, create_subprocess_shell: AsyncMock):
        regex_no_match = re.compile('^/.+c$')

        proc1_found = await system.find_process_by_command({regex_no_match})
        self.assertIsNone(proc1_found)

        re_match = re.compile('^/.+c.+$')
        proc2_found = await system.find_process_by_command({re_match})
        self.assertEqual(123, proc2_found[0])
        self.assertEqual('/abcd -xpto', proc2_found[1])

        self.assertEqual(2, create_subprocess_shell.await_count)

    @patch(f'{__app_name__}.common.system.asyncio.create_subprocess_shell', return_value=MagicMock(stdout=AsyncIterator([b'456 /bin/x', b'123 /bin/a'])))
    async def test__return_last_match_when_last_match_is_true(self, create_subprocess_shell: AsyncMock):
        proc_found = await system.find_process_by_command({re.compile('^/bin/.+$')}, last_match=True)
        self.assertIsNotNone(proc_found)
        self.assertEqual(456, proc_found[0])
        self.assertEqual('/bin/x', proc_found[1])
        create_subprocess_shell.assert_awaited_once_with(cmd='ps -Ao pid,args -ww --no-headers --sort=-pid', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)

    @patch(f'{__app_name__}.common.system.asyncio.create_subprocess_shell', return_value=MagicMock(stdout=AsyncIterator([b'123 /bin/a', b'456 /bin/x'])))
    async def test__return_first_match_when_last_match_is_false(self, create_subprocess_shell: AsyncMock):
        proc_found = await system.find_process_by_command({re.compile('^/bin/.+$')}, last_match=False)
        self.assertIsNotNone(proc_found)
        self.assertEqual(123, proc_found[0])
        self.assertEqual('/bin/a', proc_found[1])
        create_subprocess_shell.assert_awaited_once_with(cmd='ps -Ao pid,args -ww --no-headers --sort=pid', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)


class FindChildrenTest(IsolatedAsyncioTestCase):

    @patch(f'{__app_name__}.common.system.async_syscall', return_value=(0, "789 101\n776 12\n"))
    async def test__empty_list_when_no_children_is_found(self, async_syscall: Mock):
        children = await system.find_children({123, 456})
        self.assertEqual([], children)

        async_syscall.assert_called_once_with('ps -Ao ppid,pid -ww --no-headers')

    @patch(f'{__app_name__}.common.system.async_syscall')
    async def test__children_sorted_by_the_deepest_on_the_tree(self, async_syscall: Mock):
        pid_tree = '''
          1 11 
          1 12 
          11 111 
          11 112 
          2 22 
          2 23 
          23 233 
          233 444 
        '''
        async_syscall.return_value = (0, pid_tree)
        children = await system.find_children({1, 2})
        async_syscall.assert_called_once_with('ps -Ao ppid,pid -ww --no-headers')
        self.assertIsNotNone(children)
        self.assertEqual(8, len(children))
        self.assertEqual(444, children[0])
        self.assertEqual({233, 111, 112}, {*children[1:4]})  # same level
        self.assertEqual({11, 12, 22, 23}, {*children[4:]})  # same level


class FindPidsByNameTest(IsolatedAsyncioTestCase):

    @patch(f'{__app_name__}.common.system.asyncio.create_subprocess_shell', return_value=MagicMock(stdout=AsyncIterator([b' 1 a ', b' 2 b ', b' 3 a ', b' 4 b', b' 5 c '])))
    async def test__must_return_the_first_match_when_last_match_is_not_defined(self, create_subprocess_shell: AsyncMock):
        res = await find_pids_by_names({'a', 'b', 'c', 'd'})

        self.assertEqual({'a': 1, 'b': 2, 'c': 5}, res)

        create_subprocess_shell.assert_awaited_once_with(cmd='ps -Ao pid,comm -ww --no-headers --sort=pid', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)

    @patch(f'{__app_name__}.common.system.asyncio.create_subprocess_shell', return_value=MagicMock(stdout=AsyncIterator([b'5  c', b'4  b', b'3  a', b'2 b', b'1 a'])))
    async def test__must_return_the_last_match_when_last_match_is_true(self, create_subprocess_shell: AsyncMock):
        res = await find_pids_by_names({'a', 'b', 'c'}, last_match=True)

        self.assertEqual({'a': 3, 'b': 4, 'c': 5}, res)

        create_subprocess_shell.assert_awaited_once_with(cmd='ps -Ao pid,comm -ww --no-headers --sort=-pid',
                                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                                         stdin=subprocess.DEVNULL)


class FindCommandsByPidsTest(IsolatedAsyncioTestCase):

    @patch(f'{__app_name__}.common.system.asyncio.create_subprocess_shell', return_value=MagicMock(stdout=AsyncIterator([b' 1 /bin/a ', b'  2 /bin/b  ', b' 3 /bin/c ', b' 4 /bin/d -xpto '])))
    async def test__must_return_commands_by_informed_pids(self, create_subprocess_shell: AsyncMock):
        res = await find_commands_by_pids({2, 4, 7})
        self.assertEqual({2: '/bin/b', 4: '/bin/d -xpto'}, res)

        create_subprocess_shell.assert_awaited_once_with(cmd='ps -Ao pid,args -ww --no-headers',
                                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                                         stdin=subprocess.DEVNULL)


class FindProcessesByCommandTest(IsolatedAsyncioTestCase):

    @patch(f'{__app_name__}.common.system.asyncio.create_subprocess_shell', return_value=MagicMock(stdout=AsyncIterator([b' 1 /bin/a ', b' 2 /bin/b ', b' 3 /bin/a ', b' 4 /bin/c', b' 5 /bin/b ', b' 6 /bin/d'])))
    async def test__must_return_first_matches_when_parameter_not_defined(self, create_subprocess_shell: AsyncMock):
        res = await find_processes_by_command({'/bin/a', '/bin/b', '/bin/d'})
        self.assertEqual({'/bin/a': 1, '/bin/b': 2, '/bin/d': 6}, res)
        create_subprocess_shell.assert_awaited_once_with(cmd='ps -Ao pid,args -ww --no-headers --sort=pid', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)

    @patch(f'{__app_name__}.common.system.asyncio.create_subprocess_shell', return_value=MagicMock(stdout=AsyncIterator([b' 1 /bin/a ', b' 2 /bin/b ', b' 3 /bin/a ', b' 4  /bin/c', b' 5  /bin/b ', b' 6  /bin/d'])))
    async def test__must_return_first_matches_when_parameter_set_to_false(self, create_subprocess_shell: AsyncMock):
        res = await find_processes_by_command({'/bin/a', '/bin/b', '/bin/d'}, last_match=False)
        self.assertEqual({'/bin/a': 1, '/bin/b': 2, '/bin/d': 6}, res)
        create_subprocess_shell.assert_awaited_once_with(cmd='ps -Ao pid,args -ww --no-headers --sort=pid', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)

    @patch(f'{__app_name__}.common.system.asyncio.create_subprocess_shell', return_value=MagicMock(stdout=AsyncIterator([b' 6  /bin/d', b' 5  /bin/b ',  b' 4  /bin/c', b' 3  /bin/a ', b' 2  /bin/b ',  b' 1  /bin/a '])))
    async def test__must_return_last_matches_when_parameter_set_to_true(self, create_subprocess_shell: AsyncMock):
        res = await find_processes_by_command({'/bin/a', '/bin/b', '/bin/d'}, last_match=True)
        self.assertEqual({'/bin/a': 3, '/bin/b': 5, '/bin/d': 6}, res)
        create_subprocess_shell.assert_awaited_once_with(cmd='ps -Ao pid,args -ww --no-headers --sort=-pid', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)


class MapProcessByParentTest(IsolatedAsyncioTestCase):

    @patch(f"{__app_name__}.common.system.async_syscall")
    async def test_map_processes_by_parent(self, async_syscall: AsyncMock):
        async_syscall.return_value = (0, """
        1411    5202 reaper
        5202    5203 pv-bwrap
        5203    5286 pressure-vessel
        5286    7925 python3
        5286    8017 wineserver
        5286    8708 Game.exe
        5286    8747 Game-Win64-Shi
        """)

        proc_map = await map_processes_by_parent()
        async_syscall.assert_awaited_with("ps -Ao ppid,pid,comm -ww --no-headers")
        self.assertEqual(4, len(proc_map))

        expected = {1411: {(5202, "reaper")},
                    5202: {(5203, "pv-bwrap")},
                    5203: {(5286, "pressure-vessel")},
                    5286: {(7925, "python3"), (8017, "wineserver"), (8708, "Game.exe"), (8747, "Game-Win64-Shi")}}
        self.assertEqual(expected, proc_map)


class FindProcessChildrenTest(TestCase):

    def test_it_should_find_children_recursively_by_default(self):
        parent_procs = {
            123: {(456, "reaper")},
            456: {(789, "pv-bwrap")},
            789: {(1011, "abc"), (1012, "def")}
        }

        new_found = {data for data in find_process_children(ppid=456,
                                                            processes_by_parent=parent_procs,
                                                            already_found=set())}
        self.assertEqual({(789, "pv-bwrap", 456),
                          (1011, "abc", 789),
                          (1012, "def", 789)}, new_found)

    def test_it_should_find_children_of_already_found_processes(self):
        parent_procs = {
            123: {(456, "reaper")},
            456: {(789, "pv-bwrap")},
            789: {(1011, "abc"), (1012, "def")}
        }

        already_found = {789}
        new_found = {data for data in find_process_children(ppid=456,
                                                            processes_by_parent=parent_procs,
                                                            already_found=already_found)}
        self.assertEqual({(1011, "abc", 789), (1012, "def", 789)}, new_found)

    def test_it_should_not_find_children_recursively_when_recursive_is_false(self):
        parent_procs = {
            123: {(456, "reaper")},
            456: {(789, "pv-bwrap")},
            789: {(1011, "abc"), (1012, "def")}
        }

        new_found = {data for data in find_process_children(ppid=456,
                                                            processes_by_parent=parent_procs,
                                                            already_found=set(),
                                                            recursive=False)}
        self.assertEqual({(789, "pv-bwrap", 456)}, new_found)


class AsyncProcessMock:

    def __init__(self, pid: Optional[int] = None, returncode: Optional[int] = None, output: Optional[str] = None,
                 wait_time: Optional[float] = None):
        self.pid = pid
        self.returncode = returncode
        self.output = output
        self.wait_time = wait_time
        self.stdout = PropertyMock(read=AsyncMock(return_value=self.output.encode() if output else b''))

    async def wait(self) -> int:
        if self.wait_time and self.wait_time > 0:
            await asyncio.sleep(self.wait_time)

        return self.returncode


class RunAsyncProcessTest(IsolatedAsyncioTestCase):

    @patch(f"{__app_name__}.common.system.asyncio.create_subprocess_shell")
    async def test__raise_exception_when_wait_is_false_and_timeout_is_reached(self, *mocks: Mock):
        create_subprocess_shell = mocks[0]
        create_subprocess_shell.return_value = AsyncProcessMock(pid=888)

        with self.assertRaises(ProcessTimedOutError) as err:
            await run_async_process(cmd="xpto", wait=False, timeout=0.001)
            self.assertEqual(888, err.exception.pid)

        create_subprocess_shell.assert_called_once_with(cmd="xpto", stdin=subprocess.DEVNULL,
                                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    @patch(f"{__app_name__}.common.system.asyncio.create_subprocess_shell")
    async def test__return_output_if_timeout_not_reached_and_returncode_not_none(self, *mocks: Mock):
        create_subprocess_shell = mocks[0]

        create_subprocess_shell.return_value = AsyncProcessMock(pid=888, returncode=0, output="xpto")

        pid, code, output = await run_async_process(cmd="xpto", wait=False, timeout=5)
        self.assertEqual(888, pid)
        self.assertEqual(0, code)
        self.assertEqual("xpto", output)

        create_subprocess_shell.assert_called_once_with(cmd="xpto", stdin=subprocess.DEVNULL,
                                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    @patch(f"{__app_name__}.common.system.asyncio.create_subprocess_shell")
    async def test__return_output_when_output_true_and_wait_true(self, *mocks: Mock):
        create_subprocess_shell = mocks[0]
        create_subprocess_shell.return_value = AsyncProcessMock(pid=888, returncode=0, output="xpto")

        pid, returncode, output = await run_async_process(cmd="xpto", output=True, wait=True)
        self.assertEqual("xpto", output)
        self.assertEqual(0, returncode)
        self.assertEqual(888, pid)

        create_subprocess_shell.assert_called_once_with(cmd="xpto", stdin=subprocess.DEVNULL,
                                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    @patch(f"{__app_name__}.common.system.asyncio.create_subprocess_shell")
    async def test__return_none_as_output_when_output_true_and_wait_false(self, *mocks: Mock):
        create_subprocess_shell = mocks[0]
        create_subprocess_shell.return_value = AsyncProcessMock(pid=888, returncode=0, output="xpto")

        pid, returncode, output = await run_async_process(cmd="xpto", output=True, wait=False)
        self.assertIsNone(output)
        self.assertEqual(0, returncode)
        self.assertEqual(888, pid)

        create_subprocess_shell.assert_called_once_with(cmd="xpto", stdin=subprocess.DEVNULL,
                                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    @patch(f"{__app_name__}.common.system.asyncio.create_subprocess_shell")
    async def test__return_output_none_as_output_when_output_false_and_wait_true(self, *mocks: Mock):
        create_subprocess_shell = mocks[0]
        create_subprocess_shell.return_value = AsyncProcessMock(pid=888, returncode=0, output="xpto")

        pid, returncode, output = await run_async_process(cmd="xpto", output=False, wait=True)
        self.assertIsNone(output)
        self.assertEqual(0, returncode)
        self.assertEqual(888, pid)

        create_subprocess_shell.assert_called_once_with(cmd="xpto", stdin=subprocess.DEVNULL,
                                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @patch(f"{__app_name__}.common.system.asyncio.create_subprocess_shell")
    @patch("os.setpriority")
    @patch("os.setuid")
    async def test__must_call_setui_when_user_id_is_defined_and_set_priority_to_zero(self, *mocks: Mock):
        setuid, setpriority, create_subprocess_shell = mocks
        create_subprocess_shell.return_value = AsyncProcessMock(pid=888, returncode=0, output="xpto")

        custom_env = {"XPTO": 1}
        pid, returncode, output = await run_async_process(cmd="xpto", user_id=1001, custom_env=custom_env,
                                                          output=True, wait=True)
        self.assertEqual("xpto", output)
        self.assertEqual(0, returncode)
        self.assertEqual(888, pid)

        setpriority.assert_called_once_with(os.PRIO_PROCESS, 888, 0)

        expected_lambda_type = type(lambda x: x + 1)
        create_subprocess_shell.assert_called_once_with(cmd="xpto", stdin=subprocess.DEVNULL,
                                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                                        preexec_fn=AnyInstance(expected_lambda_type),
                                                        env=custom_env)
