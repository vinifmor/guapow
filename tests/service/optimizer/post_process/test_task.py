import asyncio
import re
from asyncio import Lock
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import Mock, patch, MagicMock, call, AsyncMock

from guapow import __app_name__
from guapow.common.model import ScriptSettings
from guapow.service.optimizer.post_process.task import PostStopProcesses, PostProcessContext, RunFinishScripts, \
    ReEnableWindowCompositor, \
    PostProcessTaskManager, RestoreCPUGovernor, RestoreGPUState, RelaunchStoppedProcesses, RestoreMouseCursor, \
    RestoreCPUEnergyPolicyLevel
from guapow.service.optimizer.task.model import OptimizationContext
from tests.mocks import WindowCompositorMock


class PostStopProcessesTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.context = OptimizationContext.empty()
        self.context.logger = Mock()

        self.task = PostStopProcesses(self.context)

    def test_should_run__false_when_no_pids_to_stop(self):
        context = PostProcessContext.empty()
        context.pids_to_stop = set()
        self.assertFalse(self.task.should_run(context))

        context.pids_to_stop = None
        self.assertFalse(self.task.should_run(context))

    def test_should_run__true_when_there_are_pids_to_stop(self):
        context = PostProcessContext.empty()
        context.pids_to_stop = {0}
        self.assertTrue(self.task.should_run(context))

    @patch(f'{__app_name__}.service.optimizer.post_process.task.system.find_children', return_value=[])
    @patch(f'{__app_name__}.service.optimizer.post_process.task.system.async_syscall', return_value=(0, None))
    async def test_restore__call_kill_only_for_passed_pids_when_no_children(self, *mocks: Mock):
        async_syscall, find_children = mocks

        context = PostProcessContext.empty()
        context.pids_to_stop = {999, 888}
        await self.task.run(context)
        find_children.assert_called_once_with(context.pids_to_stop)
        async_syscall.assert_called_once()

        call_args = async_syscall.call_args[0][0]
        self.assertTrue(call_args.startswith('kill -9'))
        self.assertIn(' 999', call_args)
        self.assertIn(' 888', call_args)

    @patch(f'{__app_name__}.service.optimizer.post_process.task.system.find_children', return_value=[222, 333, 444])
    @patch(f'{__app_name__}.service.optimizer.post_process.task.system.async_syscall', return_value=(0, None))
    async def test_restore__call_kill_for_passed_pids_and_their_children(self, *mocks: Mock):
        async_syscall, find_children = mocks

        context = PostProcessContext.empty()
        context.pids_to_stop = {999, 888}

        await self.task.run(context)
        find_children.assert_called_once_with(context.pids_to_stop)
        async_syscall.assert_called_once()

        call_args = async_syscall.call_args[0][0]
        self.assertTrue(call_args.startswith('kill -9 222 333 444'))
        self.assertIn(' 999', call_args)
        self.assertIn(' 888', call_args)


class RunFinishScriptsTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.context = OptimizationContext.empty()
        self.context.logger = Mock()

        self.task = RunFinishScripts(self.context)
        self.post_context = PostProcessContext.empty()

    def test_should_run__true_when_scripts_are_defined(self):
        self.post_context.scripts = [ScriptSettings(node_name='', scripts=['/abc'])]
        self.assertTrue(self.task.should_run(self.post_context))

    def test_should_run__false_when_scripts_are_not_defined(self):
        self.post_context.scripts = None
        self.assertFalse(self.task.should_run(self.post_context))

        self.post_context.scripts = []
        self.assertFalse(self.task.should_run(self.post_context))

    def test_should_run__false_when_no_script_settings_have_defined_scripts(self):
        self.post_context.scripts = [ScriptSettings(node_name='', scripts=[])]
        self.assertFalse(self.task.should_run(self.post_context))

    async def test_run__must_delegate_to_run_scripts_with_the_data_from_context(self):
        self.task._task = MagicMock(run=AsyncMock())

        scripts = [ScriptSettings(node_name='', scripts=['/a', '/b'], run_as_root=False),
                   ScriptSettings(node_name='', scripts=['/c'], run_as_root=True)]
        self.post_context.scripts = scripts

        user_id, user_env = 123, {'a': 1}
        self.post_context.user_id, self.post_context.user_env = user_id, user_env

        await self.task.run(self.post_context)

        self.task._task.run.assert_awaited_once_with(scripts=scripts, user_id=user_id, user_env=user_env)


class ReEnableWindowCompositorTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.context = OptimizationContext.empty()
        self.context.logger = Mock()

        self.task = ReEnableWindowCompositor(self.context)
        self.post_context = PostProcessContext.empty()

    def test_should_run__true_when_compositor_is_known_and_restore_compositor_is_true_and_global_disable_context_is_defined(self):
        self.context.compositor = Mock()
        self.context.compositor_disabled_context = Mock()
        self.post_context.restore_compositor = True

        self.assertTrue(self.task.should_run(self.post_context))

    def test_should_run__false_when_compositor_is_unknown_and_restore_compositor_is_true_and_global_disable_context_is_defined(self):
        self.context.compositor = None
        self.context.compositor_disabled_context = Mock()
        self.post_context.restore_compositor = True

        self.assertFalse(self.task.should_run(self.post_context))

    def test_should_run__false_when_compositor_is_known_and_restore_compositor_is_none_and_global_disable_context_is_defined(self):
        self.context.compositor = Mock()
        self.context.compositor_disabled_context = Mock()
        self.post_context.restore_compositor = None

        self.assertFalse(self.task.should_run(self.post_context))

    def test_should_run__false_when_compositor_is_known_and_restore_compositor_is_true_and_global_disable_context_is_none(self):
        self.context.compositor = Mock()
        self.context.compositor_disabled_context = None
        self.post_context.restore_compositor = True

        self.assertFalse(self.task.should_run(self.post_context))

    async def test_run__must_not_call_enable_when_the_current_compositor_state_is_unknown(self):
        compositor = Mock()
        compositor.lock.return_value = Lock()
        self.context.compositor = compositor

        global_context = {'a': 1}
        self.context.compositor_disabled_context = global_context

        compositor.is_enabled = AsyncMock(return_value=None)

        compositor.enable = AsyncMock()

        self.post_context.restore_compositor = True
        await self.task.run(self.post_context)
        self.assertEqual(global_context, self.context.compositor_disabled_context)  # must not be cleaned up

        compositor.is_enabled.assert_called_once_with(user_id=self.post_context.user_id, user_env=self.post_context.user_env, context=global_context)
        compositor.enable.assert_not_called()

    async def test_run__must_not_call_enable_when_the_current_compositor_is_enabled(self):
        compositor = MagicMock()
        compositor.get_lock = lambda: Lock()
        self.context.compositor = compositor

        global_compositor_context = {'a': 1}
        self.context.compositor_disabled_context = global_compositor_context

        compositor.is_enabled = AsyncMock(return_value=True)

        compositor.enable = AsyncMock()

        await self.task.run(self.post_context)
        self.assertIsNone(self.context.compositor_disabled_context)  # must be cleaned up

        compositor.is_enabled.assert_called_once_with(user_id=self.post_context.user_id, user_env=self.post_context.user_env, context=global_compositor_context)
        compositor.enable.assert_not_called()

    async def test_run__must_call_enable_when_the_current_compositor_is_disabled(self):
        compositor = MagicMock()
        compositor.get_lock = lambda: Lock()
        self.context.compositor = compositor

        compositor_context = {'a': 1}
        self.context.compositor_disabled_context = compositor_context

        compositor.is_enabled = AsyncMock(return_value=False)

        compositor.enable = AsyncMock(return_value=True)

        self.post_context.restore_compositor = True
        await self.task.run(self.post_context)
        self.assertIsNone(self.context.compositor_disabled_context)  # must be cleaned up

        compositor.is_enabled.assert_called_once_with(user_id=self.post_context.user_id, user_env=self.post_context.user_env, context=compositor_context)
        compositor.enable.assert_called_once_with(user_id=self.post_context.user_id, user_env=self.post_context.user_env, context=compositor_context)

    async def test_run__must_not_call_enable_twice_for_concurrent_calls(self):
        self.context.compositor = WindowCompositorMock()

        compositor_context = {'a': 1}
        self.context.compositor_disabled_context = compositor_context

        self.post_context.restore_compositor = True
        tasks = [asyncio.get_event_loop().create_task(self.task.run(self.post_context)),
                 asyncio.get_event_loop().create_task(self.task.run(self.post_context))]

        await asyncio.gather(*tasks)

        self.assertEqual(1, self.context.compositor.enable_count)


class RelaunchStoppedProcessesTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.context = OptimizationContext.empty()
        self.context.logger = Mock()

        self.post_context = PostProcessContext.empty()
        self.task = RelaunchStoppedProcesses(self.context)

    def test_get_python_cmd_pattern__returned_pattern_must_be_able_to_find_python_commands(self):
        first_res = self.task.get_python_cmd_pattern().findall('/usr/bin/python /usr/bin/abc')
        self.assertEqual(['/usr/bin/abc'], first_res)

        seconds_res = self.task.get_python_cmd_pattern().findall('/usr/bin/python3 /usr/bin/abc-bin')
        self.assertEqual(['/usr/bin/abc-bin'], seconds_res)

    def test_should_run__false_when_no_user_commands_defined(self):
        self.post_context.stopped_processes = []
        self.assertFalse(self.task.should_run(self.post_context))

    def test_should_run__false_when_user_commands_defined_but_no_user_id(self):
        self.post_context.stopped_processes = []
        self.post_context.user_id = None
        self.assertFalse(self.task.should_run(self.post_context))

    def test_should_run__true_when_user_commands_defined(self):
        self.post_context.stopped_processes = ['/abc']
        self.post_context.user_id = 0
        self.assertTrue(self.task.should_run(self.post_context))

    @patch(f'{__app_name__}.service.optimizer.post_process.task.system.run_async_process')
    @patch(f'{__app_name__}.service.optimizer.post_process.task.system.async_syscall')
    @patch(f'{__app_name__}.service.optimizer.post_process.task.system.find_processes_by_command', return_value=None)
    @patch('os.getuid', return_value=12312)
    async def test_run__must_not_launch_commands_when_not_running_as_root_and_root_request(self, *mocks: Mock):
        getuid, find_processes_by_command, async_syscall, run_async_process = mocks
        self.post_context.stopped_processes = ['/abc']
        self.post_context.user_id = 0

        await self.task.run(self.post_context)

        getuid.assert_called_once()
        find_processes_by_command.assert_not_called()
        async_syscall.assert_not_called()
        run_async_process.assert_not_called()

    @patch(f'{__app_name__}.service.optimizer.post_process.task.run_async_process')
    @patch(f'{__app_name__}.service.optimizer.post_process.task.system.find_processes_by_command', return_value=None)
    @patch('os.getuid', return_value=0)
    async def test_run__must_launch_commands_as_root_when_root_request(self, *mocks: Mock):
        getuid, find_processes_by_command, run_async_process = mocks

        self.post_context.stopped_processes = [('abc', '/abc')]
        self.post_context.user_id = 0

        await self.task.run(self.post_context)

        getuid.assert_called_once()
        find_processes_by_command.assert_called_once()
        run_async_process.assert_called_once_with(cmd="/abc", user_id=None, custom_env=None, wait=False,
                                                  output=False, exception_output=False)

    @patch(f'{__app_name__}.service.optimizer.post_process.task.run_async_process')
    @patch(f'{__app_name__}.service.optimizer.post_process.task.system.find_processes_by_command', return_value=None)
    @patch('os.getuid', return_value=1234)
    async def test_run__must_launch_commands_as_user_when_user_request(self, *mocks: Mock):
        getuid, find_processes_by_command, run_async_process = mocks
        self.post_context.stopped_processes = [('abc', '/abc'), ('def', '/def')]
        self.post_context.user_id = 1234

        await self.task.run(self.post_context)

        getuid.assert_called_once()
        find_processes_by_command.assert_called_once()
        run_async_process.assert_has_calls([call(cmd="/abc", user_id=None, custom_env=None,
                                                 wait=False, output=False, exception_output=False),
                                            call(cmd="/def", user_id=None, custom_env=None,
                                                 wait=False, output=False, exception_output=False)])

    @patch(f'{__app_name__}.service.optimizer.post_process.task.run_async_process')
    @patch(f'{__app_name__}.service.optimizer.post_process.task.system.find_processes_by_command', return_value=None)
    @patch('os.getuid', return_value=0)
    async def test_run__must_launch_commands_when_root_and_user_request(self, *mocks: Mock):
        getuid, find_processes_by_command, run_async_process = mocks
        self.post_context.stopped_processes = [('abc', '/abc'), ('def', '/def')]
        self.post_context.user_id = 1234
        self.post_context.user_env = {'ABC': '123'}

        await self.task.run(self.post_context)

        getuid.assert_called_once()
        find_processes_by_command.assert_called_once()

        expected_calls = [call(cmd=c[1], user_id=self.post_context.user_id, custom_env=self.post_context.user_env,
                               wait=False, output=False, exception_output=False)
                          for c in self.post_context.stopped_processes]
        run_async_process.assert_has_calls(expected_calls)

    @patch(f'{__app_name__}.service.optimizer.post_process.task.run_async_process')
    @patch(f'{__app_name__}.service.optimizer.post_process.task.system.find_processes_by_command', return_value=None)
    @patch('os.getuid', return_value=1234)
    async def test_run__must_launch_python_script_without_python_command_prefix(self, *mocks: Mock):
        """
        otherwise the relaunched process will be named 'python' instead of the original name
        """
        getuid, find_processes_by_command, run_async_process = mocks

        self.post_context.stopped_processes = [('xpto-bin', '/usr/bin/python3 /usr/bin/xpto-bin'),
                                               ('abc', '/usr/bin/python /usr/bin/abc'),
                                               ('def', '/bin/def')]  # no python command
        self.post_context.user_id = 1234

        await self.task.run(self.post_context)

        getuid.assert_called_once()
        find_processes_by_command.assert_called_once()
        expected_calls = [call(cmd=c, user_id=None, custom_env=None, wait=False, output=False, exception_output=False)
                          for c in ("/usr/bin/xpto-bin", "/usr/bin/abc", "/bin/def")]
        run_async_process.assert_has_calls(expected_calls)

    @patch(f'{__app_name__}.service.optimizer.post_process.task.run_async_process')
    @patch(f'{__app_name__}.service.optimizer.post_process.task.system.find_processes_by_command', return_value={'/abc': 5, '/ghi': 8})
    @patch('os.getuid', return_value=1234)
    async def test_run__must_not_launch_commands_already_running(self, *mocks: Mock):
        getuid, find_processes_by_command, run_async_process = mocks
        self.post_context.stopped_processes = [('abc', '/abc'), ('def', '/def'), ('ghi', '/ghi')]
        self.post_context.user_id = 1234

        await self.task.run(self.post_context)

        getuid.assert_called_once()
        find_processes_by_command.assert_called_once_with({'/abc', '/def', '/ghi'})
        run_async_process.assert_called_once_with(cmd="/def", user_id=None, custom_env=None,
                                                  wait=False, output=False, exception_output=False)

    @patch(f'{__app_name__}.service.optimizer.post_process.task.run_async_process')
    @patch(f'{__app_name__}.service.optimizer.post_process.task.system.find_processes_by_command')
    @patch('os.getuid', return_value=1234)
    async def test_run__must_not_launch_commands_any_command_if_all_are_running(self, *mocks: Mock):
        getuid, find_processes_by_command, run_async_process = mocks
        find_processes_by_command.return_value = {'/abc': 5, '/def': 6, '/usr/bin/python3 /usr/bin/ghi': 8}

        self.post_context.stopped_processes = [('abc', '/abc'), ('def', '/def'),
                                               ('ghi', '/usr/bin/python3 /usr/bin/ghi')]
        self.post_context.user_id = 1234

        await self.task.run(self.post_context)

        getuid.assert_called_once()
        find_processes_by_command.assert_called_once_with({'/abc', '/def', '/usr/bin/python3 /usr/bin/ghi'})
        run_async_process.assert_not_called()


class RestoreMouseCursorTest(IsolatedAsyncioTestCase):

    UNCLUTTER_MATCH_PATTERN = re.compile(r'^unclutter$')

    def setUp(self):
        self.context = OptimizationContext.empty()
        self.context.mouse_man = Mock()
        self.context.logger = Mock()
        self.task = RestoreMouseCursor(self.context)

    def test_should_run__true_when_restore_mouse_cursor_is_set_to_true(self):
        context = PostProcessContext.empty()
        context.restore_mouse_cursor = True
        self.assertTrue(self.task.should_run(context))

    def test_should_run__false_when_restore_mouse_cursor_is_not_defined(self):
        context = PostProcessContext.empty()
        self.assertFalse(self.task.should_run(context))

    async def test_run__must_delegate_to_mouse_manager_show_cursor(self):
        self.context.mouse_man.show_cursor = AsyncMock(return_value=True)

        await self.task.run(PostProcessContext.empty())

        self.context.mouse_man.show_cursor.assert_called_once()


class RestoreCPUEnergyPolicyLevelTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.context = OptimizationContext.empty()
        self.context.cpuenergy_man = Mock()
        self.context.cpuenergy_man.lock = MagicMock(return_value=Lock())
        self.context.cpuenergy_man.change_states = AsyncMock()
        self.context.cpuenergy_man.clear_state = MagicMock()
        self.context.logger = Mock()
        self.task = RestoreCPUEnergyPolicyLevel(self.context)

    def test_should_run__true_when_restore_cpu_energy_policy_is_set_to_true(self):
        context = PostProcessContext.empty()
        context.restore_cpu_energy_policy = True
        self.assertTrue(self.task.should_run(context))

    def test_should_run__false_when_restore_cpu_energy_policy_is_not_defined(self):
        context = PostProcessContext.empty()
        self.assertFalse(self.task.should_run(context))

    async def test_run__must_not_call_manager_change_state_if_saved_state_is_empty(self):
        self.context.cpuenergy_man.saved_state = dict()

        await self.task.run(PostProcessContext.empty())

        self.context.cpuenergy_man.change_states.assert_not_awaited()
        self.context.cpuenergy_man.clear_state.assert_not_called()

    async def test_run__must_not_call_clear_state_for_cpus_which_energy_policy_restoring_failed(self):
        saved_stated = {0: 3, 1: 2, 2: 5, 3: 6}
        self.context.cpuenergy_man.saved_state = saved_stated
        self.context.cpuenergy_man.change_states.return_value = {0: False, 1: True, 2: False, 3: True}

        await self.task.run(PostProcessContext.empty())

        self.context.cpuenergy_man.change_states.assert_awaited_once_with(saved_stated)
        self.context.cpuenergy_man.clear_state.assert_called_once_with(1, 3)


class PostProcessTaskManagerTest(TestCase):

    def setUp(self):
        self.man = PostProcessTaskManager(Mock())

    def test_get_available_tasks__should_returned_sorted_tasks(self):
        tasks = self.man.get_available_tasks()
        self.assertEqual(8, len(tasks))
        self.assertIsInstance(tasks[0], ReEnableWindowCompositor)
        self.assertIsInstance(tasks[1], PostStopProcesses)
        self.assertIsInstance(tasks[2], RestoreMouseCursor)
        self.assertIsInstance(tasks[3], RestoreGPUState)
        self.assertIsInstance(tasks[4], RestoreCPUGovernor)
        self.assertIsInstance(tasks[5], RestoreCPUEnergyPolicyLevel)
        self.assertIsInstance(tasks[6], RelaunchStoppedProcesses)
        self.assertIsInstance(tasks[7], RunFinishScripts)
