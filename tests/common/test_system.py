import re
import subprocess
from unittest.async_case import IsolatedAsyncioTestCase
from unittest.mock import patch, Mock, AsyncMock, MagicMock

from guapow import __app_name__
from guapow.common import system
from guapow.common.system import find_pids_by_names, find_commands_by_pids, find_processes_by_command
from tests import AsyncIterator


class FindProcessByNameTest(IsolatedAsyncioTestCase):

    @patch(f'{__app_name__}.common.system.asyncio.create_subprocess_shell', return_value=MagicMock(stdout=AsyncIterator([b' 456 # xpto ', b' 123 # abc '])))
    async def test__make_exact_comparisson(self, create_subprocess_shell: AsyncMock):
        proc_found = await system.find_process_by_name(re.compile('^abc$'))
        self.assertIsNotNone(proc_found)
        self.assertEqual(123, proc_found[0])
        self.assertEqual('abc', proc_found[1])
        create_subprocess_shell.assert_awaited_once_with(cmd='ps -Ao "%p#%c" -ww --no-headers --sort=pid', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)

    @patch(f'{__app_name__}.common.system.asyncio.create_subprocess_shell', side_effect=[
        MagicMock(stdout=AsyncIterator([b'456#xpto', b'123#abc'])),
        MagicMock(stdout=AsyncIterator([b'456#xpto', b'123#abc']))])
    async def test__make_regex_comparisson(self, create_subprocess_shell: AsyncMock):
        regex_no_match = re.compile('^.+b$')

        proc1_found = await system.find_process_by_name(regex_no_match)
        self.assertIsNone(proc1_found)

        re_match = re.compile('^.+b.+$')
        proc2_found = await system.find_process_by_name(re_match)
        self.assertEqual(123, proc2_found[0])
        self.assertEqual('abc', proc2_found[1])

        self.assertEqual(2, create_subprocess_shell.await_count)

    @patch(f'{__app_name__}.common.system.asyncio.create_subprocess_shell', return_value=MagicMock(stdout=AsyncIterator([b'123#ac', b'456#ab'])))
    async def test__return_first_last_match_when_last_match_is_false(self, create_subprocess_shell: AsyncMock):
        proc_found = await system.find_process_by_name(re.compile('^a.+$'))
        self.assertIsNotNone(proc_found)
        self.assertEqual(123, proc_found[0])
        self.assertEqual('ac', proc_found[1])
        create_subprocess_shell.assert_awaited_once_with(cmd='ps -Ao "%p#%c" -ww --no-headers --sort=pid', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)

    @patch(f'{__app_name__}.common.system.asyncio.create_subprocess_shell', return_value=MagicMock(stdout=AsyncIterator([b'456#ab', b'123#ac'])))
    async def test__return_last_match_when_last_match_is_true(self, create_subprocess_shell: AsyncMock):
        proc_found = await system.find_process_by_name(re.compile('^a.+$'), last_match=True)
        self.assertIsNotNone(proc_found)
        self.assertEqual(456, proc_found[0])
        self.assertEqual('ab', proc_found[1])
        create_subprocess_shell.assert_awaited_once_with(cmd='ps -Ao "%p#%c" -ww --no-headers --sort=-pid', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)


class FindProcessByCommandTest(IsolatedAsyncioTestCase):

    @patch(f'{__app_name__}.common.system.asyncio.create_subprocess_shell', return_value=MagicMock(stdout=AsyncIterator([b' 456 # /bin/xpto ', b' 123 # /opt/abc '])))
    async def test__make_exact_comparisson(self, create_subprocess_shell: MagicMock):
        proc_found = await system.find_process_by_command({re.compile('^/opt/abc$')})
        self.assertIsNotNone(proc_found)
        self.assertEqual(123, proc_found[0])
        self.assertEqual('/opt/abc', proc_found[1])
        create_subprocess_shell.assert_awaited_once_with(cmd='ps -Ao "%p#%a" -ww --no-headers --sort=pid', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)

    @patch(f'{__app_name__}.common.system.asyncio.create_subprocess_shell', return_value=MagicMock(stdout=AsyncIterator([b' 456 # /bin/xpto ', b' 123 # /opt/abc '])))
    async def test__match_for_one_of_the_specified_patterns(self, create_subprocess_shell: AsyncMock):
        proc_found = await system.find_process_by_command({re.compile('^/def$'), re.compile('^/opt/abc$')})
        self.assertIsNotNone(proc_found)
        self.assertEqual(123, proc_found[0])
        self.assertEqual('/opt/abc', proc_found[1])
        create_subprocess_shell.assert_awaited_once()

    @patch(f'{__app_name__}.common.system.asyncio.create_subprocess_shell', side_effect=[
        MagicMock(stdout=AsyncIterator([b' 456 # /bin/xpto', b' 123#/abcd -xpto '])),
        MagicMock(stdout=AsyncIterator([b' 456 # /bin/xpto', b' 123#/abcd -xpto ']))
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

    @patch(f'{__app_name__}.common.system.asyncio.create_subprocess_shell', return_value=MagicMock(stdout=AsyncIterator([b'456#/bin/x', b'123#/bin/a'])))
    async def test__return_last_match_when_last_match_is_true(self, create_subprocess_shell: AsyncMock):
        proc_found = await system.find_process_by_command({re.compile('^/bin/.+$')}, last_match=True)
        self.assertIsNotNone(proc_found)
        self.assertEqual(456, proc_found[0])
        self.assertEqual('/bin/x', proc_found[1])
        create_subprocess_shell.assert_awaited_once_with(cmd='ps -Ao "%p#%a" -ww --no-headers --sort=-pid', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)

    @patch(f'{__app_name__}.common.system.asyncio.create_subprocess_shell', return_value=MagicMock(stdout=AsyncIterator([b'123#/bin/a', b'456#/bin/x'])))
    async def test__return_first_match_when_last_match_is_false(self, create_subprocess_shell: AsyncMock):
        proc_found = await system.find_process_by_command({re.compile('^/bin/.+$')}, last_match=False)
        self.assertIsNotNone(proc_found)
        self.assertEqual(123, proc_found[0])
        self.assertEqual('/bin/a', proc_found[1])
        create_subprocess_shell.assert_awaited_once_with(cmd='ps -Ao "%p#%a" -ww --no-headers --sort=pid', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)


class FindChildrenTest(IsolatedAsyncioTestCase):

    @patch(f'{__app_name__}.common.system.async_syscall', return_value=(0, "789#101\n776#12\n"))
    async def test__empty_list_when_no_children_is_found(self, async_syscall: Mock):
        children = await system.find_children({123, 456})
        self.assertEqual([], children)

        async_syscall.assert_called_once_with('ps -Ao "%P#%p" -ww --no-headers')

    @patch(f'{__app_name__}.common.system.async_syscall')
    async def test__children_sorted_by_the_deepest_on_the_tree(self, async_syscall: Mock):
        pid_tree = '''
          1#  11 
          1#  12 
          11# 111 
          11# 112 
          2#  22 
          2#  23 
          23#  233 
          233#  444 
        '''
        async_syscall.return_value = (0, pid_tree)
        children = await system.find_children({1, 2})
        async_syscall.assert_called_once_with('ps -Ao "%P#%p" -ww --no-headers')
        self.assertIsNotNone(children)
        self.assertEqual(8, len(children))
        self.assertEqual(444, children[0])
        self.assertEqual({233, 111, 112}, {*children[1:4]})  # same level
        self.assertEqual({11, 12, 22, 23}, {*children[4:]})  # same level


class FindPidsByNameTest(IsolatedAsyncioTestCase):

    @patch(f'{__app_name__}.common.system.asyncio.create_subprocess_shell', return_value=MagicMock(stdout=AsyncIterator([b' 1 # a ', b' 2 # b ', b' 3 # a ', b' 4 # b', b' 5 # c '])))
    async def test__must_return_the_first_match_when_last_match_is_not_defined(self, create_subprocess_shell: AsyncMock):
        res = await find_pids_by_names({'a', 'b', 'c', 'd'})

        self.assertEqual({'a': 1, 'b': 2, 'c': 5}, res)

        create_subprocess_shell.assert_awaited_once_with(cmd='ps -Ao "%p#%c" -ww --no-headers --sort=pid', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)

    @patch(f'{__app_name__}.common.system.asyncio.create_subprocess_shell', return_value=MagicMock(stdout=AsyncIterator([b'5#c', b'4#b', b'3#a', b'2#b', b'1#a'])))
    async def test__must_return_the_last_match_when_last_match_is_true(self, create_subprocess_shell: AsyncMock):
        res = await find_pids_by_names({'a', 'b', 'c'}, last_match=True)

        self.assertEqual({'a': 3, 'b': 4, 'c': 5}, res)

        create_subprocess_shell.assert_awaited_once_with(cmd='ps -Ao "%p#%c" -ww --no-headers --sort=-pid',
                                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                                         stdin=subprocess.DEVNULL)


class FindCommandsByPidsTest(IsolatedAsyncioTestCase):

    @patch(f'{__app_name__}.common.system.asyncio.create_subprocess_shell', return_value=MagicMock(stdout=AsyncIterator([b' 1 # /bin/a ', b'  2 # /bin/b  ', b' 3 # /bin/c ', b' 4 # /bin/d -xpto '])))
    async def test__must_return_commands_by_informed_pids(self, create_subprocess_shell: AsyncMock):
        res = await find_commands_by_pids({2, 4, 7})
        self.assertEqual({2: '/bin/b', 4: '/bin/d -xpto'}, res)

        create_subprocess_shell.assert_awaited_once_with(cmd='ps -Ao "%p#%a" -ww --no-headers',
                                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                                         stdin=subprocess.DEVNULL)


class FindProcessesByCommandTest(IsolatedAsyncioTestCase):

    @patch(f'{__app_name__}.common.system.asyncio.create_subprocess_shell', return_value=MagicMock(stdout=AsyncIterator([b' 1 # /bin/a ', b' 2 # /bin/b ', b' 3 # /bin/a ', b' 4 # /bin/c', b' 5 # /bin/b ', b' 6 # /bin/d'])))
    async def test__must_return_first_matches_when_parameter_not_defined(self, create_subprocess_shell: AsyncMock):
        res = await find_processes_by_command({'/bin/a', '/bin/b', '/bin/d'})
        self.assertEqual({'/bin/a': 1, '/bin/b': 2, '/bin/d': 6}, res)
        create_subprocess_shell.assert_awaited_once_with(cmd='ps -Ao "%p#%a" -ww --no-headers --sort=pid', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)

    @patch(f'{__app_name__}.common.system.asyncio.create_subprocess_shell', return_value=MagicMock(stdout=AsyncIterator([b' 1 # /bin/a ', b' 2 # /bin/b ', b' 3 # /bin/a ', b' 4 # /bin/c', b' 5 # /bin/b ', b' 6 # /bin/d'])))
    async def test__must_return_first_matches_when_parameter_set_to_false(self, create_subprocess_shell: AsyncMock):
        res = await find_processes_by_command({'/bin/a', '/bin/b', '/bin/d'}, last_match=False)
        self.assertEqual({'/bin/a': 1, '/bin/b': 2, '/bin/d': 6}, res)
        create_subprocess_shell.assert_awaited_once_with(cmd='ps -Ao "%p#%a" -ww --no-headers --sort=pid', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)

    @patch(f'{__app_name__}.common.system.asyncio.create_subprocess_shell', return_value=MagicMock(stdout=AsyncIterator([b' 6 # /bin/d', b' 5 # /bin/b ',  b' 4 # /bin/c', b' 3 # /bin/a ', b' 2 # /bin/b ',  b' 1 # /bin/a '])))
    async def test__must_return_last_matches_when_parameter_set_to_true(self, create_subprocess_shell: AsyncMock):
        res = await find_processes_by_command({'/bin/a', '/bin/b', '/bin/d'}, last_match=True)
        self.assertEqual({'/bin/a': 3, '/bin/b': 5, '/bin/d': 6}, res)
        create_subprocess_shell.assert_awaited_once_with(cmd='ps -Ao "%p#%a" -ww --no-headers --sort=-pid', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
