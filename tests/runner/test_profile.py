from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import Mock, patch, call

from guapow import __app_name__
from guapow.common.model_util import FileModelFiller
from guapow.runner.profile import RunnerProfileReader, RunnerProfile
from tests import RESOURCES_DIR


class RunnerProfileTest(TestCase):

    def test_set_path__non_empty_path(self):
        exp_path = f'{RESOURCES_DIR}/test .123.profile'
        instance = RunnerProfile(exp_path, None)
        self.assertEqual(exp_path, instance.path)
        self.assertEqual('test .123', instance.name)


class RunnerProfileReaderTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.reader = RunnerProfileReader(FileModelFiller(Mock()), Mock())

    def test_map_valid_config__return_a_valid_config(self):
        profile = self.reader.map_valid_config('scripts.before=/xpto\nscripts.before=/abc\nscripts.before.wait=1\nscript.before.root=1\nscripts.before.timeout=5')
        self.assertIsNotNone(profile)
        self.assertIsNotNone(profile.before_scripts)
        self.assertEqual(['/xpto', '/abc'], profile.before_scripts.scripts)
        self.assertEqual(True, profile.before_scripts.wait_execution)
        self.assertEqual(5, profile.before_scripts.timeout)
        self.assertEqual(False, profile.before_scripts.run_as_root)  # must always be false, even when defined as 'true' in the file

    def test_map_valid_config__return_none_when_invalid_config(self):
        profile = self.reader.map_valid_config('cpu.performance=1')
        self.assertIsNone(profile)

    def test_map_valid_config__with_simple_process_to_stop_properties_defined(self):
        profile = self.reader.map_valid_config('stop.before=abc\nstop.before.relaunch')
        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_valid())
        self.assertIsNotNone(profile.stop)

        self.assertEqual({'abc'}, profile.stop.processes)
        self.assertTrue(profile.stop.relaunch)

    @patch(f'{__app_name__}.runner.profile.get_profile_dir', return_value=RESOURCES_DIR)
    async def test_read_valid__return_only_valid_environment_variables(self, get_profile_dir: Mock):
        user = 'test'

        profile = await self.reader.read_valid(user_id=1, user_name=user, profile='only_runner_env_vars')
        get_profile_dir.assert_called_once_with(1, user)

        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_valid())
        self.assertIsNone(profile.before_scripts)

        self.assertIsNotNone(profile.environment_variables)
        self.assertEqual({'VAR1': 'abc',
                          'VAR2': 'XXX',
                          'VAR3': '0',
                          'VAR4': None,
                          'VAR5': 'abc',
                          'VAR6': None,
                          'VAR_7': None}, profile.environment_variables)

    @patch(f'{__app_name__}.runner.profile.get_profile_dir', return_value=RESOURCES_DIR)
    async def test_read_valid__return_only_valid_script_settings(self, get_profile_dir: Mock):
        user = 'test'

        profile = await self.reader.read_valid(user_id=1, user_name=user, profile='only_before_scripts')
        get_profile_dir.assert_called_once_with(1, user)

        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_valid())

        self.assertIsNotNone(profile.before_scripts)
        self.assertIsNotNone(profile.before_scripts.scripts)
        self.assertFalse(profile.before_scripts.run_as_root)
        self.assertEqual(['/xpto', '/abc'], profile.before_scripts.scripts)
        self.assertEqual(False, profile.before_scripts.run_as_root)  # must always be false, even when defined as 'true' in the file

    @patch(f'{__app_name__}.runner.profile.get_profile_dir', return_value=RESOURCES_DIR)
    async def test_read_valid__return_only_valid_stop_process_settings(self, get_profile_dir: Mock):
        user = 'test'

        profile = await self.reader.read_valid(user_id=1, user_name=user, profile='only_stop_procs')
        get_profile_dir.assert_called_once_with(1, user)

        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_valid())

        self.assertIsNotNone(profile.stop)
        self.assertIsNotNone(profile.stop.processes)
        self.assertEqual({'abc', 'def', 'fgh'}, profile.stop.processes)
        self.assertIsNone(profile.stop.relaunch)

    @patch(f'{__app_name__}.runner.profile.get_profile_dir', return_value=RESOURCES_DIR)
    async def test_read_valid__return_stop_process_settings_with_relaunch_defined(self, get_profile_dir: Mock):
        user = 'test'

        profile = await self.reader.read_valid(user_id=1, user_name=user, profile='only_stop_procs_relaunch')
        get_profile_dir.assert_called_once_with(1, user)

        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_valid())

        self.assertIsNotNone(profile.stop)
        self.assertIsNotNone(profile.stop.processes)
        self.assertEqual({'abc', 'def'}, profile.stop.processes)
        self.assertTrue(profile.stop.relaunch)

    @patch(f'{__app_name__}.runner.profile.get_profile_dir', return_value=RESOURCES_DIR)
    async def test_read_available__return_a_valid_profile_defined(self, get_profile_dir: Mock):
        profile = await self.reader.read_available(user_id=1, user_name='test', profile='only_before_scripts')
        get_profile_dir.assert_called_once_with(1, 'test')
        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_valid())

    @patch(f'{__app_name__}.runner.profile.get_profile_dir', return_value=RESOURCES_DIR)
    async def test_read_available__return_a_valid_profile_defined_with_additional_settings(self, get_profile_dir: Mock):
        user = 'test'
        profile = await self.reader.read_available(user_id=1, user_name=user, profile='only_before_scripts', add_settings='scripts.before=/myscript')
        get_profile_dir.assert_called_once_with(1, user)
        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_valid())

        self.assertIsNotNone(profile.before_scripts)
        self.assertIsNotNone(profile.before_scripts.scripts)
        self.assertEqual(['/xpto', '/abc', '/myscript'], profile.before_scripts.scripts)

    @patch(f'{__app_name__}.runner.profile.get_profile_dir', return_value=RESOURCES_DIR)
    @patch(f'{__app_name__}.runner.profile.get_default_profile_name', return_value='only_before_scripts')
    async def test_read_available__return_default_profile_when_defined_do_not_exist(self, get_default_profile_name: Mock, get_profile_dir: Mock):
        user = 'test'
        profile = await self.reader.read_available(user_id=1, user_name=user, profile='no_runner_profile')
        get_default_profile_name.assert_called_once()
        get_profile_dir.assert_has_calls((call(1, user), call(1, user)))
        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_valid())

    @patch(f'{__app_name__}.runner.profile.get_profile_dir', return_value=RESOURCES_DIR)
    @patch(f'{__app_name__}.runner.profile.get_default_profile_name', return_value='only_compositor')
    async def test_read_available__return_default_profile_with_additional_settings_when_profile_is_not_defined(self, get_default_profile_name: Mock, get_profile_dir: Mock):
        user = 'test'
        profile = await self.reader.read_available(user_id=1, user_name=user, profile=None, add_settings='stop.before=xpto-bin,abc')
        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_valid())

        self.assertIsNotNone(profile.stop)
        self.assertIn('xpto-bin', profile.stop.processes)
        self.assertIn('abc', profile.stop.processes)

        get_default_profile_name.assert_called_once()
        get_profile_dir.assert_called_once_with(1, user)

    @patch(f'{__app_name__}.runner.profile.get_profile_dir', return_value=RESOURCES_DIR)
    @patch(f'{__app_name__}.runner.profile.get_default_profile_name', return_value='no_default_runner_profile')
    async def test_read_available__none_when_profile_and_default_profile_do_not_exist(self, get_default_profile_name: Mock, get_profile_dir: Mock):
        user = 'test'
        profile = await self.reader.read_available(user_id=1, user_name=user, profile='no_runner_profile')
        get_default_profile_name.assert_called_once()
        get_profile_dir.assert_has_calls((call(1, user), call(1, user)))
        self.assertIsNone(profile)
