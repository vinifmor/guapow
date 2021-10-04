from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch, AsyncMock, call

from guapow import __app_name__
from guapow.service.watcher import util


class MapProcessesTest(IsolatedAsyncioTestCase):

    @patch(f'{__app_name__}.service.watcher.util.async_syscall', side_effect=[(0, " 1 # a \n 2 # b \n"), (0, "1#/bin/a\n 2 # /bin/b -c \n")])
    async def test__must_return_a_dict_with_pids_as_keys_and_tuples_as_values_with_the_cmd_and_comm(self, async_syscall: AsyncMock):
        procs = await util.map_processes()
        async_syscall.assert_has_awaits([call('ps -Ao "%p#%c" -ww --no-headers'),
                                        call('ps -Ao "%p#%a" -ww --no-headers')], any_order=True)

        self.assertIsInstance(procs, dict)
        self.assertEqual({1: ('/bin/a', 'a'), 2: ('/bin/b -c', 'b')}, procs)

    @patch(f'{__app_name__}.service.watcher.util.async_syscall', side_effect=[(0, "1#a\n3#c\n"), (0, "\n 2#/bin/b -c \n3#/bin/c\n")])
    async def test__must_not_return_processes_with_comm_or_cmd_missing(self, async_syscall: AsyncMock):
        procs = await util.map_processes()
        self.assertEqual(2, async_syscall.await_count)

        self.assertIsInstance(procs, dict)
        self.assertEqual({3: ('/bin/c', 'c')}, procs)

    @patch(f'{__app_name__}.service.watcher.util.async_syscall', return_value=(1, ""))
    async def test__must_return_none_when_the_syscall_fails(self, async_syscall: AsyncMock):
        procs = await util.map_processes()
        self.assertEqual(2, async_syscall.await_count)
        self.assertIsNone(procs)
