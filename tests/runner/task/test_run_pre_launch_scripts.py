from subprocess import DEVNULL
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, patch, call, AsyncMock, MagicMock

from guapow import __app_name__
from guapow.common.scripts import RunScripts
from guapow.runner.profile import RunnerProfile
from guapow.runner.task import RunPreLaunchScripts, RunnerContext
from tests import RESOURCES_DIR


class RunPreLaunchScriptsTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.profile = RunnerProfile.empty(f'{RESOURCES_DIR}/test')

    def test_is_available__always_return_true(self):
        opt = RunPreLaunchScripts(Mock())
        available, _ = opt.is_available()
        self.assertTrue(available)

    def test_should_run__true_when_there_are_scripts_to_execute_before_the_process(self):
        opt = RunPreLaunchScripts(Mock())
        self.profile.before_scripts.scripts = ['/xpto']
        self.assertTrue(opt.should_run(self.profile))

    def test_should_run__false_when_scripts_settings_is_not_defined(self):
        opt = RunPreLaunchScripts(Mock())
        self.profile.before_scripts = None
        self.assertFalse(opt.should_run(self.profile))

    def test_should_run__false_when_there_are_no_script_to_execute_before_optimizations(self):
        opt = RunPreLaunchScripts(Mock())
        self.profile.before_scripts.scripts = []
        self.assertFalse(opt.should_run(self.profile))

    @patch(f'{__app_name__}.common.scripts.os.getuid', return_value=123)
    async def test_run__must_delegate_to_run_scripts_with_the_data_from_context(self, getuid: Mock):
        context = RunnerContext(processes_initialized=set(), environment_variables={}, logger=Mock(), stopped_processes={})
        opt = RunPreLaunchScripts(context)
        opt._task = MagicMock(run=AsyncMock(return_value={4, 10, 111}))

        self.profile.before_scripts.scripts = ['/a', '/b', '/c']
        self.profile.before_scripts.wait_execution = True
        self.profile.before_scripts.timeout = 1

        user_id, user_env = 123, RunScripts.get_environ()

        await opt.run(self.profile)

        getuid.assert_called_once()
        opt._task.run.assert_awaited_once_with(scripts=[self.profile.before_scripts], user_id=user_id, user_env=user_env)

        self.assertEqual({4, 10, 111}, context.processes_initialized)
