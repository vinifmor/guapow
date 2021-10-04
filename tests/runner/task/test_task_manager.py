from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, MagicMock, AsyncMock

from guapow.runner.profile import RunnerProfile
from guapow.runner.task import RunnerTaskManager, StopProcesses, RunPreLaunchScripts, \
    AddDefinedEnvironmentVariables


class RunnerTaskManagerTest(IsolatedAsyncioTestCase):

    def test_get_available_tasks(self):
        man = RunnerTaskManager(Mock())
        man._check_availability()
        tasks = man.get_available_tasks()
        self.assertIsNotNone(tasks)
        self.assertIsInstance(tasks[0], AddDefinedEnvironmentVariables)
        self.assertIsInstance(tasks[1], StopProcesses)
        self.assertIsInstance(tasks[2], RunPreLaunchScripts)

    async def test_run__must_run_available_actions_that_should_run_for_a_given_profile(self):
        runner_task = MagicMock()
        runner_task.should_run = MagicMock(return_value=True)
        runner_task.run = AsyncMock(return_value=None)

        man = RunnerTaskManager(Mock(), actions=[runner_task])

        profile = RunnerProfile.empty()
        runned_tasks = await man.run(profile)
        self.assertEqual(1, runned_tasks)

        runner_task.should_run.assert_called_once_with(profile)
        runner_task.run.assert_called_once_with(profile)
