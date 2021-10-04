from typing import Set, Optional
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, patch, call

from guapow import __app_name__
from guapow.runner.profile import RunnerProfile
from guapow.runner.task import StopProcesses, RunnerContext
from tests import RESOURCES_DIR


class WhichMock:

    def __init__(self, existing: Set[str]):
        self._existing = {p: f'/{p}' for p in existing} if existing else None

    def which(self, comm: str) -> Optional[str]:
        return self._existing.get(comm) if comm else None


class StopProcessesTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.context = RunnerContext(logger=Mock(), environment_variables=None, processes_initialized=None, stopped_processes={})
        self.profile = RunnerProfile.empty(f'{RESOURCES_DIR}/test')
        self.task = StopProcesses(self.context)

    def test_is_available__must_always_return_true(self):
        res = self.task.is_available()
        self.assertTrue(res[0])
        self.assertIsNone(res[1])

    def test_should_run__true_when_there_are_processes_to_stop_defined(self):
        self.profile.stop.processes = {'abc'}
        self.assertTrue(self.task.should_run(self.profile))

    def test_should_run__false_when_there_are_no_processes_to_stop_defined(self):
        self.profile.processes_to_stop = {}
        self.assertFalse(self.task.should_run(self.profile))

    @patch(f'{__app_name__}.runner.task.shutil.which')
    @patch(f'{__app_name__}.runner.task.system.async_syscall', return_value=(1, 'kill: (2) could not kill'))
    @patch(f'{__app_name__}.runner.task.system.find_commands_by_pids', return_value={1: '/a', 2: '/b'})
    @patch(f'{__app_name__}.runner.task.system.find_pids_by_names', return_value={'a': 1, 'b': 2})
    async def test_run__must_try_to_kill_process_names_defined_to_be_stopped_and_not_add_the_not_stopped_to_context(self, find_pids_by_names: Mock, find_commands_by_pids: Mock, async_syscall: Mock, which: Mock):
        self.profile.stop.processes = {'a', 'b'}
        await self.task.run(self.profile)

        find_pids_by_names.assert_called_once_with({'a', 'b'})
        find_commands_by_pids.assert_called_once_with({1, 2})

        self.assertTrue(async_syscall.call_args.args[0].startswith('kill -9 '))
        self.assertIn(' 1', async_syscall.call_args.args[0])
        self.assertIn(' 2', async_syscall.call_args.args[0])

        which.assert_not_called()

        self.assertEqual({'a': '/a'}, self.context.stopped_processes)

    @patch(f'{__app_name__}.runner.task.shutil.which', side_effect=WhichMock({'c'}).which)
    @patch(f'{__app_name__}.runner.task.system.async_syscall', return_value=(0, None))
    @patch(f'{__app_name__}.runner.task.system.find_commands_by_pids', return_value={1: '/a'})
    @patch(f'{__app_name__}.runner.task.system.find_pids_by_names', return_value={'a': 1})
    async def test_run__must_still_add_processes_to_be_stopped_to_the_context_that_were_not_running_if_they_exist(self, find_pids_by_names: Mock, find_commands_by_pids: Mock, async_syscall: Mock, which: Mock):
        self.profile.stop.processes = {'a', 'b', 'c'}
        await self.task.run(self.profile)

        find_pids_by_names.assert_called_once_with({'a', 'b', 'c'})
        find_commands_by_pids.assert_called_once_with({1})
        async_syscall.assert_called_once_with('kill -9 1')  # only 'a' was running
        which.assert_has_calls([call('b'), call('c')], any_order=True)

        self.assertEqual(2, len(self.context.stopped_processes))
        self.assertEqual({'a': '/a',
                          'c': None}, self.context.stopped_processes)  # as 'c' process were not running (but exists), it's command is not sent
