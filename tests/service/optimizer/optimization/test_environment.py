import os
import re
import sys
import traceback
from asyncio import Future
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, patch, MagicMock, AsyncMock, PropertyMock

from guapow import __app_name__
from guapow.common.dto import OptimizationRequest
from guapow.common.model import ScriptSettings
from guapow.common.profile import StopProcessSettings
from guapow.service.optimizer.cpu import CPUFrequencyManager
from guapow.service.optimizer.profile import OptimizationProfile, CPUSettings, GPUSettings, CompositorSettings
from guapow.service.optimizer.task.environment import ChangeCPUFrequencyGovernor, ChangeGPUModeToPerformance, \
    DisableWindowCompositor, HideMouseCursor, StopProcessesAfterLaunch, RunPostLaunchScripts
from guapow.service.optimizer.task.model import OptimizationContext, OptimizedProcess, CPUState
from tests import RESOURCES_DIR, AsyncIterator


class ChangeCPUFrequencyGovernorTest(IsolatedAsyncioTestCase):

    TEMP_GOV_FILE_PATTERN = f"{RESOURCES_DIR}/test_cpu{'{}'}_scaling_gov.txt"

    def setUp(self):
        self.context = OptimizationContext.empty()
        self.context.cpu_count = 1
        self.request = OptimizationRequest(pid=123, command='abc', profile='user', user_name='user')
        self.profile = OptimizationProfile.empty('test')
        self.profile.cpu = CPUSettings(performance=None)
        self.process= OptimizedProcess(request=self.request, profile=self.profile, created_at=1)

    def tearDown(self):
        for idx in range(2):
            self.remove_file(self.TEMP_GOV_FILE_PATTERN.format(idx))

    def remove_file(self, file_path: str):
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                sys.stderr.write(f"Could not remove test file '{file_path}'\n")
                traceback.print_exc()

    async def test_is_available__false_when_not_cpu_is_available(self):
        self.context.cpu_count = 0
        task = ChangeCPUFrequencyGovernor(self.context, cpu0_governor_file='')
        available, msg = await task.is_available()
        self.assertFalse(available)
        self.assertIsNotNone(msg)

    @patch(f'{__app_name__}.service.optimizer.task.environment.is_root_user', return_value=True)
    async def test_is_available__true_when_scaling_governor_file_exists_and_user_is_root(self, is_root_user: Mock):
        cpu0_gov_file = f'{RESOURCES_DIR}/cpu0_scaling_gov.txt'
        task = ChangeCPUFrequencyGovernor(self.context, cpu0_governor_file=cpu0_gov_file)
        available, msg = await task.is_available()
        self.assertTrue(available)
        self.assertIsNone(msg)
        is_root_user.assert_called_once()

    @patch(f'{__app_name__}.service.optimizer.task.environment.is_root_user', return_value=False)
    async def test_is_available__false_when_scaling_governor_file_exists_and_user_is_not_root(self, is_root_user: Mock):
        cpu0_gov_file = f'{RESOURCES_DIR}/cpu0_scaling_gov.txt'
        task = ChangeCPUFrequencyGovernor(self.context, cpu0_governor_file=cpu0_gov_file)
        available, msg = await task.is_available()
        self.assertFalse(available)
        self.assertIsNotNone(msg)
        is_root_user.assert_called_once()

    async def test_is_available__false_when_scaling_governor_file_does_not_exist(self):
        cpu0_gov_file = f'{RESOURCES_DIR}/xpto975521718920.txt'
        opt = ChangeCPUFrequencyGovernor(self.context, cpu0_governor_file=cpu0_gov_file)
        available, msg = await opt.is_available()
        self.assertFalse(available)
        self.assertIsNotNone(msg)

    def test_is_allowed_for_self_requests__must_return_true(self):
        self.assertTrue(ChangeCPUFrequencyGovernor(self.context, cpu0_governor_file='').is_allowed_for_self_requests())

    async def test_should_run__true_when_when_cpu_profile_set_to_performance(self):
        opt = ChangeCPUFrequencyGovernor(self.context, cpu0_governor_file='')
        self.profile.cpu.performance = True
        self.assertTrue(await opt.should_run(self.process))

    async def test_should_run__false_when_when_cpu_profile_is_not_defined(self):
        opt = ChangeCPUFrequencyGovernor(self.context, cpu0_governor_file='')
        self.profile.cpu = None
        self.assertFalse(await opt.should_run(self.process))

    async def test_should_run__false_when_when_cpu_profile_not_set_to_performance(self):
        opt = ChangeCPUFrequencyGovernor(self.context, cpu0_governor_file='')
        self.profile.cpu.performance = False
        self.assertFalse(await opt.should_run(self.process))

    async def test_run__should_not_change_governors_when_performance_is_already_set_first_execution(self):
        gov_file_pattern = f"{RESOURCES_DIR}/cpu{'{}'}_scaling_gov.txt"
        cpufreq_man = CPUFrequencyManager(logger=Mock(), cpu_count=self.context.cpu_count, governor_file_pattern=gov_file_pattern)
        self.context.cpufreq_man = cpufreq_man

        cpu0_gov_path = gov_file_pattern.format(0)

        with open(cpu0_gov_path) as f:
            prev_gov = f.read()

        self.assertEqual('performance', prev_gov)

        proc = OptimizedProcess(self.request, 632863771, self.profile)
        opt = ChangeCPUFrequencyGovernor(self.context, cpu0_governor_file=cpu0_gov_path)
        await opt.run(proc)
        self.assertIsNone(proc.previous_cpu_state)

        with open(cpu0_gov_path) as f:
            current_gov = f.read()

        self.assertEqual('performance', current_gov)
        self.assertIsNone(self.context.cpufreq_man.get_saved_governors())

    async def test_run__should_change_governors_when_performance_is_not_set_first_execution(self):
        self.context.cpu_count = 2

        cpufreq_man = CPUFrequencyManager(logger=Mock(), cpu_count=self.context.cpu_count,
                                          governor_file_pattern=self.TEMP_GOV_FILE_PATTERN)
        self.context.cpufreq_man = cpufreq_man

        for idx in range(self.context.cpu_count):
            cpu_gov_file = self.TEMP_GOV_FILE_PATTERN.format(idx)
            try:
                with open(cpu_gov_file, 'w+') as f:
                    f.write('schedutil')
            except:
                traceback.print_exc()
                self.fail(f"Could not create file '{cpu_gov_file}'")

        proc = OptimizedProcess(self.request, 12321312, self.profile)
        opt = ChangeCPUFrequencyGovernor(self.context, cpu0_governor_file=self.TEMP_GOV_FILE_PATTERN.format(0))
        await opt.run(proc)

        self.assertIsNotNone(proc.previous_cpu_state)

        expected_state = {'schedutil': {0, 1}}
        self.assertEqual(CPUState(expected_state), proc.previous_cpu_state)
        self.assertEqual(expected_state, cpufreq_man.get_saved_governors())

        for idx in range(self.context.cpu_count):
            cpu_file = self.TEMP_GOV_FILE_PATTERN.format(idx)

            with open(cpu_file) as f:
                current_gov = f.read()

            self.assertEqual('performance', current_gov)

    async def test_run__must_not_save_governors_states_when_self_request(self):
        self.context.cpu_count = 2

        cpufreq_man = CPUFrequencyManager(logger=Mock(), cpu_count=self.context.cpu_count,
                                          governor_file_pattern=self.TEMP_GOV_FILE_PATTERN)
        self.context.cpufreq_man = cpufreq_man

        for idx in range(self.context.cpu_count):
            cpu_gov_file = self.TEMP_GOV_FILE_PATTERN.format(idx)
            try:
                with open(cpu_gov_file, 'w+') as f:
                    f.write('schedutil')
            except:
                traceback.print_exc()
                self.fail(f"Could not create file '{cpu_gov_file}'")

        proc = OptimizedProcess(OptimizationRequest.self_request(), 12321312, self.profile)
        opt = ChangeCPUFrequencyGovernor(self.context, cpu0_governor_file=self.TEMP_GOV_FILE_PATTERN.format(0))
        await opt.run(proc)

        self.assertIsNone(proc.previous_cpu_state)
        self.assertIsNone(cpufreq_man.get_saved_governors())

        for idx in range(self.context.cpu_count):
            cpu_file = self.TEMP_GOV_FILE_PATTERN.format(idx)

            with open(cpu_file) as f:
                current_gov = f.read()

            self.assertEqual('performance', current_gov)

    async def test_run__should_not_change_governors_when_performance_is_already_set_second_execution(self):
        self.context.cpu_count = 2
        previous_state = {'schedutil': {0, 1}}

        cpufreq_man = CPUFrequencyManager(logger=Mock(), cpu_count=self.context.cpu_count,
                                          governor_file_pattern=self.TEMP_GOV_FILE_PATTERN)

        cpufreq_man._cached_governors.update({c: g for g, cpus in previous_state.items() for c in cpus})  # simulating previously saved state

        self.context.cpufreq_man = cpufreq_man

        for idx in range(self.context.cpu_count):
            cpu_gov_file = self.TEMP_GOV_FILE_PATTERN.format(idx)
            try:
                with open(cpu_gov_file, 'w+') as f:
                    f.write('performance')
            except:
                traceback.print_exc()
                self.fail(f"Could not create file '{cpu_gov_file}'")

        proc = OptimizedProcess(self.request, 632876321, self.profile)
        opt = ChangeCPUFrequencyGovernor(self.context, cpu0_governor_file=self.TEMP_GOV_FILE_PATTERN.format(0))
        await opt.run(proc)

        self.assertIsNotNone(proc.previous_cpu_state)

        self.assertEqual(CPUState(previous_state), proc.previous_cpu_state)
        self.assertEqual(previous_state, cpufreq_man.get_saved_governors())

        for idx in range(self.context.cpu_count):
            cpu_file = self.TEMP_GOV_FILE_PATTERN.format(idx)

            with open(cpu_file) as f:
                current_gov = f.read()

            self.assertEqual('performance', current_gov)


class ChangeGPUModeToPerformanceTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.gpu_man = Mock()

        self.context = OptimizationContext.empty()
        self.context.gpu_man = self.gpu_man
        self.context.logger = Mock()

        self.request = OptimizationRequest(pid=123, command='abc', profile='user', user_name='user')
        self.profile = OptimizationProfile.empty('test')
        self.profile.gpu = GPUSettings(None)
        self.task = ChangeGPUModeToPerformance(self.context)
        self.process = OptimizedProcess(request=self.request, profile=self.profile, created_at=1)

    async def test_is_available__true_when_gpu_manager_returns_working_drivers_with_gpus(self):
        self.gpu_man.map_working_drivers_and_gpus.return_value = AsyncIterator([(Mock(), {'1'})])

        self.assertTrue(await self.task.is_available())

        self.gpu_man.map_working_drivers_and_gpus.assert_called_once()

    async def test_is_available__true_when_gpu_cache_is_off(self):
        self.gpu_man.is_cache_enabled.return_value = False
        self.assertTrue(await self.task.is_available())  # first call
        self.assertTrue(await self.task.is_available())  # second call (ensuring 'is_cache_enabled' is always called)
        self.assertEqual(2, self.gpu_man.is_cache_enabled.call_count)

    async def test_should_run__true_when_gpu_profile_performance_is_true(self):
        self.profile.gpu.performance = True
        self.assertTrue(await self.task.should_run(self.process))

    async def test_should_run__false_when_no_gpu_profile_is_defined(self):
        self.profile.gpu = None
        self.assertFalse(await self.task.should_run(self.process))

    async def test_should_run__false_when_gpu_profile_performance_is_false(self):
        self.profile.gpu.performance = False
        self.assertFalse(await self.task.should_run(self.process))


class DisableWindowCompositorTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.context = OptimizationContext.empty()
        self.context.logger = Mock()

        self.request = OptimizationRequest(pid=123, command='abc', profile='user', user_name='user', user_env={})
        self.request.user_id = 1234

        self.profile = OptimizationProfile.empty('test')
        self.process = OptimizedProcess(self.request, 1236168, self.profile)
        self.task = DisableWindowCompositor(self.context)

    async def test_is_available__always_return_true(self):
        available, output = await self.task.is_available()
        self.assertTrue(available)
        self.assertIsNone(output)

    async def test_should_run__false_when_compositor_settings_is_none(self):
        self.context.compositor = Mock()
        self.profile.compositor = None
        self.assertFalse(await self.task.should_run(self.process))

    async def test_should_run__false_when_compositor_disabled_is_false(self):
        self.context.compositor = Mock()
        self.profile.compositor = CompositorSettings(off=False)
        self.assertFalse(await self.task.should_run(self.process))

    @patch(f'{__app_name__}.service.optimizer.task.environment.get_window_compositor', return_value=None)
    async def test_should_run__false_when_compositor_is_not_set_and_could_not_be_determined(self, get_window_compositor: Mock):
        self.context.compositor = None
        self.profile.compositor = CompositorSettings(off=True)
        self.assertFalse(await self.task.should_run(self.process))
        get_window_compositor.assert_called_once()

    @patch(f'{__app_name__}.service.optimizer.task.environment.get_window_compositor', return_value=MagicMock(can_be_managed=MagicMock(return_value=(True, None))))
    async def test_should_run__true_when_compositor_is_not_set_and_could_be_determined_and_can_be_managed(self, get_window_compositor: Mock):
        self.context.compositor = None
        self.profile.compositor = CompositorSettings(off=True)
        self.assertTrue(await self.task.should_run(self.process))
        self.assertIsNotNone(self.context.compositor)
        get_window_compositor.assert_called_once()

    @patch(f'{__app_name__}.service.optimizer.task.environment.get_window_compositor', return_value=MagicMock(can_be_managed=MagicMock(return_value=(False, None))))
    async def test_should_run__false_when_compositor_is_not_set_and_could_be_determined_but_cannot_be_managed(self, get_window_compositor: Mock):
        self.context.compositor = None
        self.profile.compositor = CompositorSettings(off=True)
        self.assertFalse(await self.task.should_run(self.process))
        get_window_compositor.assert_called_once()

    async def test_should_run__true_when_compositor_is_already_defined_and_manageable_and_profile_requires_it_disabled(self):
        self.context.compositor = MagicMock(can_be_managed=MagicMock(return_value=(True, None)))
        self.profile.compositor = CompositorSettings(off=True)
        self.assertTrue(await self.task.should_run(self.process))

    async def test_should_run__false_when_compositor_is_already_defined_but_not_manageable_and_profile_requires_it_disabled(self):
        can_be_managed = MagicMock(return_value=(False, 'error'))
        self.context.compositor = MagicMock(can_be_managed=can_be_managed)
        self.profile.compositor = CompositorSettings(off=True)
        self.assertFalse(await self.task.should_run(self.process))
        self.assertFalse(await self.task.should_run(self.process))  # second call

        can_be_managed.assert_called_once()  # should only be called by the first 'should_run' call

    async def test_run__not_set_global_compositor_disabled_context_when_could_not_get_compositor_state(self):
        self.assertIsNone(self.context.compositor_disabled_context)

        compositor = MagicMock()
        self.context.compositor = compositor

        compositor.is_enabled = MagicMock(return_value=Future())
        compositor.is_enabled.return_value.set_result(None)

        await self.task.run(self.process)
        self.assertIsNone(self.context.compositor_disabled_context)

        compositor.is_enabled.assert_called_with(user_id=self.request.user_id, user_env=self.request.user_env, context={})

    async def test_run__not_set_global_compositor_disabled_context_when_could_not_change_compositor_state(self):
        self.assertIsNone(self.context.compositor_disabled_context)

        compositor = MagicMock()
        self.context.compositor = compositor

        compositor.is_enabled = MagicMock(return_value=Future())
        compositor.is_enabled.return_value.set_result(True)

        compositor.disable = MagicMock(return_value=Future())
        compositor.disable.return_value.set_result(False)

        await self.task.run(self.process)
        self.assertIsNone(self.context.compositor_disabled_context)

        compositor.is_enabled.assert_called_with(user_id=self.request.user_id, user_env=self.request.user_env, context={})
        compositor.disable.assert_called_with(user_id=self.request.user_id, user_env=self.request.user_env, context={})

    async def test_run__not_set_global_compositor_disabled_context_for_the_first_execution_if_its_already_disabled(self):
        self.assertIsNone(self.context.compositor_disabled_context)
        compositor = MagicMock()
        self.context.compositor = compositor

        compositor.is_enabled = MagicMock(return_value=Future())
        compositor.is_enabled.return_value.set_result(False)

        compositor.disable = MagicMock()

        await self.task.run(self.process)
        self.assertIsNone(self.context.compositor_disabled_context)

        compositor.is_enabled.assert_called_with(user_id=self.request.user_id, user_env=self.request.user_env, context={})
        compositor.disable.assert_not_called()

    async def test_run__not_change_global_compositor_disabled_context_when_compositor_state_is_disabled_and_global_state_is_already_set(self):
        compositor = MagicMock()
        self.context.compositor = compositor

        previous_disabled_state = {'a': 1}
        self.context.compositor_disabled_context = previous_disabled_state

        compositor.is_enabled = MagicMock(return_value=Future())
        compositor.is_enabled.return_value.set_result(False)
        compositor.disable = MagicMock()

        exp_context = {}

        await self.task.run(self.process)
        self.assertIsNotNone(self.context.compositor_disabled_context)
        self.assertEqual(previous_disabled_state, self.context.compositor_disabled_context)  # ensure there is no change on the global context

        compositor.is_enabled.assert_called_with(user_id=self.request.user_id, user_env=self.request.user_env, context=exp_context)
        compositor.disable.assert_not_called()

    async def test_run__set_global_compositor_disabled_context_when_compositor_is_enabled_and_global_context_is_already_defined(self):
        expected_context = {}
        compositor = MagicMock()
        self.context.compositor = compositor

        previous_disabled_context = {'a': 1}
        self.context.compositor_disabled_context = previous_disabled_context

        compositor.is_enabled = MagicMock(return_value=Future())
        compositor.is_enabled.return_value.set_result(True)

        compositor.disable = MagicMock(return_value=Future())
        compositor.disable.return_value.set_result(True)

        await self.task.run(self.process)
        self.assertIsNotNone(self.context.compositor_disabled_context)
        self.assertNotEqual(previous_disabled_context, self.context.compositor_disabled_context)
        self.assertEqual(expected_context, self.context.compositor_disabled_context)

        compositor.is_enabled.assert_called_with(user_id=self.request.user_id, user_env=self.request.user_env, context=expected_context)
        compositor.disable.assert_called_with(user_id=self.request.user_id, user_env=self.request.user_env, context=expected_context)


class HideMouseCursorTest(IsolatedAsyncioTestCase):

    UNCLUTTER_MATCH_PATTERN = re.compile(r'^unclutter$')

    def setUp(self):
        self.context = OptimizationContext.empty()
        self.context.mouse_man = Mock()
        self.context.logger = Mock()

        self.task = HideMouseCursor(self.context)
        self.profile = OptimizationProfile.empty('test')
        self.process = OptimizedProcess(request=PropertyMock(related_pids=None), profile=self.profile, created_at=1)

    async def test_is_available__must_delegate_to_mouse_manager_can_work(self):
        self.context.mouse_man.can_work = Mock(return_value=(True, None))

        res = await self.task.is_available()
        self.assertTrue(res[0])
        self.assertIsNone(res[1])

        self.context.mouse_man.can_work.assert_called_once()

    async def test_should_run__true_when_hide_mouse_is_set_to_true(self):
        self.profile.hide_mouse = True
        self.assertTrue(await self.task.should_run(self.process))

    async def test_should_run__false_when_hide_mouse_is_not_defined(self):
        self.profile.hide_mouse = None
        self.assertFalse(await self.task.should_run(self.process))

    async def test_is_allowed_for_self_requests__must_return_false(self):
        self.assertFalse(self.task.is_allowed_for_self_requests())

    async def test_run__must_delegate_to_mouse_manager_hide_cursor(self):
        self.context.mouse_man.hide_cursor = AsyncMock(return_value=True)

        req = OptimizationRequest(pid=1, command='/xpto', user_name='test', user_env={'DISPLAY': ':1'})
        proc = OptimizedProcess(request=req, profile=self.profile, created_at=1)
        await self.task.run(proc)

        self.context.mouse_man.hide_cursor.assert_called_once_with(user_request=True, user_env={'DISPLAY': ':1'})

    async def test_run__must_delegate_self_requests_to_mouse_manager_hide_cursor(self):
        self.context.mouse_man.hide_cursor = AsyncMock(return_value=True)

        req = OptimizationRequest.self_request()
        req.user_env = {'DISPLAY': ':1'}
        proc = OptimizedProcess(request=req, profile=self.profile, created_at=1)
        await self.task.run(proc)

        self.context.mouse_man.hide_cursor.assert_called_once_with(user_request=False, user_env={'DISPLAY': ':1'})


class StopProcessesAfterLaunchTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.context = OptimizationContext.empty()
        self.context.logger = Mock()

        self.task = StopProcessesAfterLaunch(self.context)
        self.profile = OptimizationProfile.empty(f'{RESOURCES_DIR}/test.profile')
        self.process = OptimizedProcess(request=PropertyMock(related_pids=None), profile=self.profile, created_at=1)

    async def test_is_available__must_delegate_to_the_inner_implementation(self):
        self.task._task = MagicMock()
        self.task._task.is_available = MagicMock(return_value=False)

        self.assertFalse(await self.task.is_available())
        self.task._task.is_available.assert_called_once()

    async def test_should_run__true_when_stop_after_launch_settings_are_defined(self):
        self.profile.stop_after = StopProcessSettings(node_name='', processes={'abc'}, relaunch=False)
        self.assertTrue(await self.task.should_run(self.process))

    async def test_should_run__false_when_no_process_is_defined(self):
        self.profile.stop_after = StopProcessSettings(node_name='', processes=set(), relaunch=False)
        self.assertFalse(await self.task.should_run(self.process))

    async def test_should_run__false_when_no_settings_are_defined(self):
        self.profile.stop_after = None
        self.assertFalse(await self.task.should_run(self.process))

    @patch(f'{__app_name__}.runner.task.shutil.which', return_value=False)
    @patch(f'{__app_name__}.runner.task.system.async_syscall', return_value=(0, None))
    @patch(f'{__app_name__}.runner.task.system.find_commands_by_pids', return_value={1: '/a', 3: '/c'})
    @patch(f'{__app_name__}.runner.task.system.find_pids_by_names', return_value={'a': 1, 'c': 3})
    async def test_run__must_fill_stopped_processes_on_the_optimized_process(self, find_pids_by_names: Mock, find_commands_by_pids: Mock,  async_syscall: Mock, which: Mock):
        self.profile.stop_after = StopProcessSettings(node_name='', processes={'a', 'b', 'c'}, relaunch=False)

        proc = OptimizedProcess(MagicMock(related_pids=None), created_at=1, profile=self.profile)
        await self.task.run(proc)

        find_pids_by_names.assert_called_once_with({'a', 'b', 'c'})
        find_commands_by_pids.assert_called_once_with({1, 3})

        self.assertTrue(async_syscall.call_args.args[0].startswith('kill -9 '))
        self.assertIn(' 1', async_syscall.call_args.args[0])
        self.assertIn(' 3', async_syscall.call_args.args[0])

        which.assert_called_once_with('b')

        self.assertEqual({'a': '/a', 'c': '/c'}, proc.stopped_after_launch)


class RunPostLaunchScriptsTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.context = OptimizationContext.empty()
        self.context.logger = Mock()
        self.profile = OptimizationProfile.empty('test')
        self.profile.after_scripts = ScriptSettings(node_name='', scripts=[], run_as_root=False, wait_execution=False)
        self.process = OptimizedProcess(request=PropertyMock(related_pids=None), profile=self.profile, created_at=1)
        self.task = RunPostLaunchScripts(self.context)

    async def test_should_run__true_when_profile_defines_post_scripts(self):
        self.profile.after_scripts.scripts = ['/abc']
        self.assertTrue(await self.task.should_run(self.process))

    async def test_should_run__false_when_profile_does_not_define_a_non_empty_post_scripts_list(self):
        self.profile.after_scripts.scripts = None
        self.assertFalse(await self.task.should_run(self.process))

        self.profile.after_scripts.scripts = []
        self.assertFalse(await self.task.should_run(self.process))

        self.profile.after_scripts = None
        self.assertFalse(await self.task.should_run(self.process))

    async def test_run__must_delegate_to_run_scripts_with_the_data_from_context(self):
        self.task._task = MagicMock(run=AsyncMock(return_value={4, 10, 111}))

        self.profile.after_scripts.scripts = ['/a', '/b', '/c']

        user_id, user_env = 123, {'a': 1}

        request = OptimizationRequest(pid=1234, command='/test', user_name='test', user_env=user_env)
        request.user_id = user_id
        request.related_pids = {1}

        proc = OptimizedProcess(request=request, created_at=1, profile=self.profile)

        self.assertEqual({1}, proc.related_pids)  # from request

        await self.task.run(proc)

        self.task._task.run.assert_awaited_once_with(scripts=[self.profile.after_scripts], user_id=user_id, user_env=user_env)
        self.assertEqual({1, 4, 10, 111}, proc.related_pids)  # additional started pids
