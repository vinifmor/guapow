from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, AsyncMock

from guapow.common.dto import OptimizationRequest
from guapow.common.profile import StopProcessSettings
from guapow.service.optimizer.post_process.summary import GeneralPostProcessSummarizer, UserIdSummarizer, \
    UserEnvironmentSummarizer, ProcessesToStopSummarizer, CompositorStateSummarizer, FinishScriptsSummarizer, \
    CPUStateSummarizer, GPUStateSummarizer, ProcessesToRelaunchSummarizer, MouseCursorStateSummarizer
from guapow.service.optimizer.profile import OptimizationProfile, CompositorSettings
from guapow.service.optimizer.task.model import OptimizedProcess, OptimizationContext


class GeneralPostProcessSummarizerTest(IsolatedAsyncioTestCase):

    def test_instance__must_always_return_the_same_instance(self):
        instance = GeneralPostProcessSummarizer.instance()
        self.assertEqual(instance, GeneralPostProcessSummarizer.instance())

    def test_instance__must_be_filled_with_the_correct_fillers_order(self):
        fillers = GeneralPostProcessSummarizer.instance().get_fillers()
        self.assertIsNotNone(fillers)

        expected_fillers = [UserIdSummarizer, UserEnvironmentSummarizer, ProcessesToStopSummarizer, CompositorStateSummarizer,
                            FinishScriptsSummarizer, CPUStateSummarizer, GPUStateSummarizer, ProcessesToRelaunchSummarizer,
                            MouseCursorStateSummarizer]

        self.assertEqual(len(expected_fillers), len(fillers))

        for idx, cls in enumerate(expected_fillers):
            self.assertEqual(cls, type(fillers[idx]))

    async def test_summarize__mouse_hidden_scenario_01(self):
        """
        'keep_mouse_hidden' must be set to true and 'restore_mouse_cursor' must be set to true when a process (requiring the mouse cursor
        to be hidden) dies, the cursor was hidden by the optimizer and there are other processes alive requiring the mouse cursor hidden.
        """
        context = OptimizationContext.empty()
        context.mouse_man = Mock()
        context.mouse_man.is_cursor_hidden = AsyncMock(return_value=True)

        profile = OptimizationProfile.empty('test')
        profile.hide_mouse = True

        procs = [OptimizedProcess(request=OptimizationRequest(pid=1, command='/bin', user_name='/xpto'), created_at=1, profile=profile),
                 OptimizedProcess(request=OptimizationRequest(pid=2, command='/bin', user_name='/xpto'), created_at=2, profile=profile)]

        pre_context = await GeneralPostProcessSummarizer.instance().summarize(processes=procs, pids_alive={2}, processes_to_relaunch=None, context=context)
        self.assertTrue(pre_context.keep_mouse_hidden)  # because 2 is still alive
        self.assertTrue(pre_context.restore_mouse_cursor)  # because 1 died

    async def test_summarize__mouse_hidden_scenario_02(self):
        """
        'keep_mouse_hidden' must be set to true and 'restore_mouse_cursor' must not be defined when a process (requiring the mouse cursor
        to be hidden) dies, the cursor was not hidden by the Optimizer and there are other processes alive requiring the mouse cursor hidden.
        """
        context = OptimizationContext.empty()
        context.mouse_man = Mock()
        context.mouse_man.is_cursor_hidden = AsyncMock(return_value=False)  # mouse not hidden by the Optimizer

        profile = OptimizationProfile.empty('test')
        profile.hide_mouse = True

        procs = [OptimizedProcess(request=OptimizationRequest(pid=1, command='/bin', user_name='/xpto'), created_at=1, profile=profile),
                 OptimizedProcess(request=OptimizationRequest(pid=2, command='/bin', user_name='/xpto'), created_at=2, profile=profile)]

        pre_context = await GeneralPostProcessSummarizer.instance().summarize(processes=procs, pids_alive={2}, processes_to_relaunch=None, context=context)
        self.assertTrue(pre_context.keep_mouse_hidden)  # because 2 is still alive
        self.assertIsNone(pre_context.restore_mouse_cursor)  # because the cursor was not hidden by the Optimizer (was previously running)

    async def test_summarize__mouse_hidden_scenario_03(self):
        """
            'keep_mouse_hidden' must not be defined and 'restore_mouse_cursor' must be set to true when there are no more
            processes alive requiring the  mouse cursor hidden and the cursor was previously hidden by the Optimizer
        """

        context = OptimizationContext.empty()
        context.mouse_man = Mock()
        context.mouse_man.is_cursor_hidden = AsyncMock(return_value=True)  # mouse hidden by the Optimizer

        profile = OptimizationProfile.empty('test')
        profile.hide_mouse = True

        procs = [OptimizedProcess(request=OptimizationRequest(pid=1, command='/bin', user_name='/xpto'), created_at=1, profile=profile)]

        context_1 = await GeneralPostProcessSummarizer.instance().summarize(processes=procs, pids_alive=set(), processes_to_relaunch=None, context=context)
        self.assertIsNone(context_1.keep_mouse_hidden)  # because there are no other process alive requiring the mouse to be hidden
        self.assertTrue(context_1.restore_mouse_cursor)  # because the Optimizer hid the mouse

    async def test_summarize__mouse_hidden_scenario_04(self):
        """
            'keep_mouse_hidden' must not be defined and 'restore_mouse_cursor' must not be defined when there are no more
            processes requiring the  mouse cursor hidden and the cursor was not hidden by the Optimizer
        """

        context = OptimizationContext.empty()
        context.mouse_man = Mock()
        context.mouse_man.is_cursor_hidden = AsyncMock(return_value=False)  # mouse not hidden by the Optimizer

        profile = OptimizationProfile.empty('test')
        profile.hide_mouse = True

        procs = [OptimizedProcess(request=OptimizationRequest(pid=1, command='/bin', user_name='/xpto'), created_at=1, profile=profile)]

        context_1 = await GeneralPostProcessSummarizer.instance().summarize(processes=procs, pids_alive=set(), processes_to_relaunch=None, context=context)
        self.assertIsNone(context_1.keep_mouse_hidden)  # because there are no other process alive requiring the mouse to be hidden
        self.assertIsNone(context_1.restore_mouse_cursor)  # because the mouse was not hidden by the Optimizer

    async def test_summarize__compositor_disabled_scenario_01(self):
        """
        'keep_compositor_disabled' must be set to true and 'restore_compositor' must be set to true when a process (requiring the compositor disabled)
         dies, the compositor was disabled by the Optimizer and there are other processes alive requiring the compositor disabled
        """
        context = OptimizationContext.empty()
        context.compositor_disabled_context = {'a': 1}  # compositor disabled by the Optimizer

        profile = OptimizationProfile.empty('test')
        profile.compositor = CompositorSettings(off=True)

        procs = [OptimizedProcess(request=OptimizationRequest(pid=1, command='/bin', user_name='/xpto'), created_at=1, profile=profile),
                 OptimizedProcess(request=OptimizationRequest(pid=2, command='/bin', user_name='/xpto'), created_at=2, profile=profile)]

        pre_context = await GeneralPostProcessSummarizer.instance().summarize(processes=procs, pids_alive={2}, processes_to_relaunch=None, context=context)
        self.assertTrue(pre_context.keep_compositor_disabled)  # because 2 is still alive
        self.assertTrue(pre_context.restore_compositor)  # because 1 died

    async def test_summarize__compositor_disabled_scenario_02(self):
        """
        'keep_compositor_disabled' must be set to true and 'restore_compositor' must not be defined when a process (requiring the compositor disabled)
         dies, the compositor was not disabled by the Optimizer and there are other processes alive requiring the compositor disabled
        """
        context = OptimizationContext.empty()
        context.compositor_disabled_context = None  # compositor not disabled by the Optimizer

        profile = OptimizationProfile.empty('test')
        profile.compositor = CompositorSettings(off=True)

        procs = [OptimizedProcess(request=OptimizationRequest(pid=1, command='/bin', user_name='/xpto'), created_at=1, profile=profile),
                 OptimizedProcess(request=OptimizationRequest(pid=2, command='/bin', user_name='/xpto'), created_at=2, profile=profile)]

        pre_context = await GeneralPostProcessSummarizer.instance().summarize(processes=procs, pids_alive={2}, processes_to_relaunch=None, context=context)
        self.assertTrue(pre_context.keep_compositor_disabled)  # because 2 is still alive
        self.assertIsNone(pre_context.restore_compositor)  # because 1 died

    async def test_summarize__compositor_disabled_scenario_03(self):
        """
        'keep_compositor_disabled' must not be defined and 'restore_compositor' must be set to true when there are no more
        processes alive requiring the compositor disabled and the compositor was previously disabled by the Optimizer
        """
        context = OptimizationContext.empty()
        context.compositor_disabled_context = {'a': 1}  # compositor disabled by the Optimizer

        profile = OptimizationProfile.empty('test')
        profile.compositor = CompositorSettings(off=True)

        procs = [OptimizedProcess(request=OptimizationRequest(pid=1, command='/bin', user_name='/xpto'), created_at=1, profile=profile)]

        context_1 = await GeneralPostProcessSummarizer.instance().summarize(processes=procs, pids_alive=set(), processes_to_relaunch=None, context=context)
        self.assertIsNone(context_1.keep_compositor_disabled)  # because there are no other process alive requiring the compositor disabled
        self.assertTrue(context_1.restore_compositor)  # because the Optimizer disabled the compositor

    async def test_summarize__compositor_disabled_scenario_04(self):
        """
        'keep_compositor_disabled' must not be defined and 'restore_compositor' must not be defined when there are no more
        processes alive requiring the compositor disabled and the compositor was not previously disabled by the Optimizer
        """
        context = OptimizationContext.empty()
        context.compositor_disabled_context = None  # compositor not disabled by the Optimizer

        profile = OptimizationProfile.empty('test')
        profile.compositor = CompositorSettings(off=True)

        procs = [OptimizedProcess(request=OptimizationRequest(pid=1, command='/bin', user_name='/xpto'), created_at=1, profile=profile)]

        context_1 = await GeneralPostProcessSummarizer.instance().summarize(processes=procs, pids_alive=set(), processes_to_relaunch=None, context=context)
        self.assertIsNone(context_1.keep_compositor_disabled)  # because there are no other process alive requiring the compositor disabled
        self.assertIsNone(context_1.restore_compositor)  # because the Optimizer did not disable the compositor

    async def test_summarize__must_add_stopped_processes_after_launch_that_should_be_relaunched(self):
        context = OptimizationContext.empty()

        profile = OptimizationProfile.empty('test')
        profile.stop_after = StopProcessSettings(processes={'a', 'b'}, relaunch=True, node_name='')

        procs = [OptimizedProcess(request=OptimizationRequest(pid=1, command='/bin', user_name='/xpto'), created_at=1,
                                  profile=profile)]

        pre_context = await GeneralPostProcessSummarizer.instance().summarize(processes=procs, pids_alive=set(), processes_to_relaunch={'a': None}, context=context)

        self.assertEqual({'a': None}, pre_context.processes_to_relaunch)
