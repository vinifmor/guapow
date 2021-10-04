from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, patch

from guapow import __app_name__
from guapow.service.optimizer.task.environment import DisableWindowCompositor, ChangeCPUFrequencyGovernor, \
    ChangeGPUModeToPerformance, HideMouseCursor, StopProcessesAfterLaunch, RunPostLaunchScripts
from guapow.service.optimizer.task.manager import TasksManager
from guapow.service.optimizer.task.model import OptimizationContext
from guapow.service.optimizer.task.process import ReniceProcess, ChangeCPUAffinity, ChangeCPUScalingPolicy, \
    ChangeProcessIOClass


class TasksManagerTest(IsolatedAsyncioTestCase):

    @patch(f'{__app_name__}.service.optimizer.task.environment.RunPostLaunchScripts.is_available', return_value=(True, None))
    @patch(f'{__app_name__}.service.optimizer.task.environment.HideMouseCursor.is_available', return_value=(True, None))
    @patch(f'{__app_name__}.service.optimizer.task.environment.ChangeCPUFrequencyGovernor.is_available', return_value=(True, None))
    @patch(f'{__app_name__}.service.optimizer.task.environment.ChangeGPUModeToPerformance.is_available', return_value=(True, None))
    @patch(f'{__app_name__}.service.optimizer.task.environment.DisableWindowCompositor.is_available', return_value=(True, None))
    @patch(f'{__app_name__}.service.optimizer.task.process.ReniceProcess.is_available', return_value=(True, None))
    @patch(f'{__app_name__}.service.optimizer.task.process.ChangeCPUAffinity.is_available', return_value=(True, None))
    @patch(f'{__app_name__}.service.optimizer.task.process.ChangeCPUScalingPolicy.is_available', return_value=(True, None))
    @patch(f'{__app_name__}.service.optimizer.task.process.ChangeProcessIOClass.is_available', return_value=(True, None))
    async def test_check_availability__expected_changes_and_their_order(self, *args: Mock):
        context = OptimizationContext.empty()
        context.logger = Mock()

        man = TasksManager(context)
        await man.check_availability()

        self.assertEqual(6, len(man._env_tasks))
        self.assertEqual(StopProcessesAfterLaunch, man._env_tasks[0].__class__)
        self.assertEqual(RunPostLaunchScripts, man._env_tasks[1].__class__)
        self.assertEqual(DisableWindowCompositor, man._env_tasks[2].__class__)
        self.assertEqual(HideMouseCursor, man._env_tasks[3].__class__)
        self.assertEqual(ChangeCPUFrequencyGovernor, man._env_tasks[4].__class__)
        self.assertEqual(ChangeGPUModeToPerformance, man._env_tasks[5].__class__)

        self.assertEqual(4, len(man._proc_tasks))
        self.assertEqual(ReniceProcess, man._proc_tasks[0].__class__)
        self.assertEqual(ChangeCPUAffinity, man._proc_tasks[1].__class__)
        self.assertEqual(ChangeCPUScalingPolicy, man._proc_tasks[2].__class__)
        self.assertEqual(ChangeProcessIOClass, man._proc_tasks[3].__class__)

        for m in args:
            m.assert_called_once()
