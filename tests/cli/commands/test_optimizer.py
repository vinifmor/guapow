import os
import re
import shutil
from unittest import TestCase
from unittest.mock import Mock, patch, call

from guapow import __app_name__
from guapow.cli.commands.optimizer import InstallOptimizer, UninstallOptimizer, OPTIMIZER_SERVICE_FILE
from tests import RESOURCES_DIR

MOCKED_SYSTEMD_DIR = f'{RESOURCES_DIR}/mock_systemd'

EXPECTED_CUSTOM_ENV = dict(os.environ)
EXPECTED_CUSTOM_ENV['LANG'] = 'en_US.UTF-8'


def remover_mocked_systemd_dir():
    if os.path.exists(MOCKED_SYSTEMD_DIR):
        shutil.rmtree(MOCKED_SYSTEMD_DIR)


class InstallOptimizerTest(TestCase):

    def setUp(self):
        remover_mocked_systemd_dir()
        self.cmd = InstallOptimizer(Mock())

    def tearDown(self):
        remover_mocked_systemd_dir()

    @classmethod
    def tearDownClass(cls):
        remover_mocked_systemd_dir()

    def test_get_command__must_be_equal_to_install_optimizer(self):
        self.assertEqual('install-optimizer', self.cmd.get_command())

    @patch(f'{__app_name__}.cli.commands.service.is_root_user', return_value=False)
    def test_run__must_return_false_when_user_is_not_root(self, is_root: Mock):
        self.assertFalse(self.cmd.run(Mock()))
        is_root.assert_called_once()

    @patch(f'{__app_name__}.cli.commands.service.shutil.which', return_value=None)
    @patch(f'{__app_name__}.cli.commands.service.is_root_user', return_value=True)
    def test_run__must_return_false_when_systemctl_is_not_installed(self, is_root: Mock, which: Mock):
        self.assertFalse(self.cmd.run(Mock()))
        is_root.assert_called_once()
        which.assert_called_once_with('systemctl')

    @patch(f'{__app_name__}.cli.commands.service.shutil.which', side_effect=['sysctl', None])
    @patch(f'{__app_name__}.cli.commands.service.is_root_user', return_value=True)
    def test_run__must_return_false_when_service_command_is_not_installed(self, is_root: Mock, which: Mock):
        self.assertFalse(self.cmd.run(Mock()))
        is_root.assert_called_once()
        which.assert_has_calls([call('systemctl'), call(f'{__app_name__}-opt')])

    @patch(f'{__app_name__}.cli.commands.service.system.syscall', return_value=(0, ' loaded (/file.service; enabled; xpto)'))
    @patch(f'{__app_name__}.cli.commands.service.os.path.exists', return_value=True)
    @patch(f'{__app_name__}.cli.commands.service.shutil.which', side_effect=['sysctl', f'/bin/{__app_name__}-opt'])
    @patch(f'{__app_name__}.cli.commands.service.is_root_user', return_value=True)
    def test_run__must_return_true_and_not_call_systemctl_enable_when_already_enabled(self, is_root: Mock, which: Mock, exists: Mock, syscall: Mock):
        self.assertTrue(self.cmd.run(Mock()))
        is_root.assert_called_once()
        which.assert_has_calls([call('systemctl'), call(f'{__app_name__}-opt')])
        exists.assert_called_once_with(f'/usr/lib/systemd/system/{OPTIMIZER_SERVICE_FILE}')

        syscall.assert_called_once_with(f'systemctl status {OPTIMIZER_SERVICE_FILE}', custom_env=EXPECTED_CUSTOM_ENV)

    @patch(f'{__app_name__}.cli.commands.service.system.syscall', side_effect=[(0, ' loaded (/file.service; disabled; xpto)'),
                                                                               (0, '')])
    @patch(f'{__app_name__}.cli.commands.service.os.path.exists', return_value=True)
    @patch(f'{__app_name__}.cli.commands.service.shutil.which', side_effect=['sysctl', f'/bin/{__app_name__}-opt'])
    @patch(f'{__app_name__}.cli.commands.service.is_root_user', return_value=True)
    def test_run__must_return_true_and_call_systemctl_enable_when_not_enabled(self, is_root: Mock, which: Mock, exists: Mock, syscall: Mock):
        self.assertTrue(self.cmd.run(Mock()))
        is_root.assert_called_once()
        which.assert_called()
        exists.assert_called_once_with(f'/usr/lib/systemd/system/{OPTIMIZER_SERVICE_FILE}')

        syscall.assert_has_calls([call(f'systemctl status {OPTIMIZER_SERVICE_FILE}', custom_env=EXPECTED_CUSTOM_ENV),
                                  call(f'systemctl enable --now {OPTIMIZER_SERVICE_FILE}', custom_env=EXPECTED_CUSTOM_ENV)])

    @patch(f'{__app_name__}.cli.commands.service.system.syscall', side_effect=[(0, ' loaded (/file.service; disabled; xpto)'),
                                                                               (0, '')])
    @patch(f'{__app_name__}.cli.commands.service.get_systemd_root_service_dir', return_value=MOCKED_SYSTEMD_DIR)
    @patch(f'{__app_name__}.cli.commands.service.shutil.which', side_effect=['sysctl', f'/bin/test/{__app_name__}-opt'])
    @patch(f'{__app_name__}.cli.commands.service.is_root_user', return_value=True)
    def test_run__must_return_true_after_copying_service_file_and_calling_systemctl_enable(self, is_root: Mock, which: Mock, get_systemd_root_service_dir: Mock, syscall: Mock):
        self.assertTrue(self.cmd.run(Mock()))

        exp_service_file = f'{MOCKED_SYSTEMD_DIR}/{OPTIMIZER_SERVICE_FILE}'
        self.assertTrue(os.path.exists(exp_service_file))

        with open(exp_service_file) as f:
            service_definition = f.read()

        service_cmd = re.compile(f'ExecStart=(.+)\n').findall(service_definition)
        self.assertEqual([f'/bin/test/{__app_name__}-opt'], service_cmd)

        is_root.assert_called_once()
        which.assert_called()
        get_systemd_root_service_dir.assert_called_once()

        syscall.assert_has_calls([call(f'systemctl status {OPTIMIZER_SERVICE_FILE}', custom_env=EXPECTED_CUSTOM_ENV),
                                  call(f'systemctl enable --now {OPTIMIZER_SERVICE_FILE}', custom_env=EXPECTED_CUSTOM_ENV)])


class UninstallOptimizerTest(TestCase):

    def setUp(self):
        self.cmd = UninstallOptimizer(Mock())

    def test_get_command__must_be_equal_to_uninstall_optimizer(self):
        self.assertEqual('uninstall-optimizer', self.cmd.get_command())

    @patch(f'{__app_name__}.cli.commands.service.is_root_user', return_value=False)
    def test_run__must_return_false_when_user_is_not_root(self, is_root: Mock):
        self.assertFalse(self.cmd.run(Mock()))
        is_root.assert_called_once()

    @patch(f'{__app_name__}.cli.commands.service.shutil.which', return_value=None)
    @patch(f'{__app_name__}.cli.commands.service.is_root_user', return_value=True)
    def test_run__must_return_false_when_systemctl_is_not_installed(self, is_root: Mock, which: Mock):
        self.assertFalse(self.cmd.run(Mock()))
        is_root.assert_called_once()
        which.assert_called_once_with('systemctl')

    @patch(f'{__app_name__}.cli.commands.service.system.syscall', return_value=(0, ''))
    @patch(f'{__app_name__}.cli.commands.service.shutil.which', return_value='/bin')
    @patch(f'{__app_name__}.cli.commands.service.is_root_user', return_value=True)
    def test_run__must_return_false_when_systemctl_returns_no_status_output(self, is_root: Mock, which: Mock, syscall: Mock):
        self.assertFalse(self.cmd.run(Mock()))
        is_root.assert_called_once()
        which.assert_called_once_with('systemctl')
        syscall.assert_called_once_with(f'systemctl status {OPTIMIZER_SERVICE_FILE}', custom_env=EXPECTED_CUSTOM_ENV)

    @patch(f'{__app_name__}.cli.commands.service.system.syscall', return_value=(1, ' could not be found'))
    @patch(f'{__app_name__}.cli.commands.service.shutil.which', return_value='/bin')
    @patch(f'{__app_name__}.cli.commands.service.is_root_user', return_value=True)
    def test_run__must_return_true_when_systemctl_status_says_service_not_found(self, is_root: Mock, which: Mock, syscall: Mock):
        self.assertTrue(self.cmd.run(Mock()))
        is_root.assert_called_once()
        which.assert_called_once_with('systemctl')
        syscall.assert_called_once_with(f'systemctl status {OPTIMIZER_SERVICE_FILE}', custom_env=EXPECTED_CUSTOM_ENV)

    @patch(f'{__app_name__}.cli.commands.service.system.syscall', return_value=(0, 'xpto'))
    @patch(f'{__app_name__}.cli.commands.service.shutil.which', return_value='/bin')
    @patch(f'{__app_name__}.cli.commands.service.is_root_user', return_value=True)
    def test_run__must_return_false_when_systemctl_status_does_not_match_expected_patterns(self, is_root: Mock, which: Mock, syscall: Mock):
        self.assertFalse(self.cmd.run(Mock()))
        is_root.assert_called_once()
        which.assert_called_once_with('systemctl')
        syscall.assert_called_once_with(f'systemctl status {OPTIMIZER_SERVICE_FILE}', custom_env=EXPECTED_CUSTOM_ENV)

    @patch(f'{__app_name__}.cli.commands.service.os.path.exists', return_value=False)
    @patch(f'{__app_name__}.cli.commands.service.system.syscall', return_value=(0, ' loaded (/file.service; disabled; )'))
    @patch(f'{__app_name__}.cli.commands.service.shutil.which', return_value='/bin')
    @patch(f'{__app_name__}.cli.commands.service.is_root_user', return_value=True)
    def test_run__must_return_true_when_service_already_disabled_and_file_not_in_systemd_dir(self, is_root: Mock, which: Mock, syscall: Mock, exists: Mock):
        self.assertTrue(self.cmd.run(Mock()))
        is_root.assert_called_once()
        which.assert_called_once_with('systemctl')
        syscall.assert_called_once_with(f'systemctl status {OPTIMIZER_SERVICE_FILE}', custom_env=EXPECTED_CUSTOM_ENV)
        exists.assert_called_once_with('/file.service')

    @patch(f'{__app_name__}.cli.commands.service.os.path.exists', return_value=False)
    @patch(f'{__app_name__}.cli.commands.service.system.syscall', side_effect=[(0, ' loaded (/file.service; enabled; )'),
                                                                                       (0, '')])
    @patch(f'{__app_name__}.cli.commands.service.shutil.which', return_value='/bin')
    @patch(f'{__app_name__}.cli.commands.service.is_root_user', return_value=True)
    def test_run__must_return_true_and_call_systemctl_disable_when_service_enabled(self, is_root: Mock, which: Mock, syscall: Mock, exists: Mock):
        self.assertTrue(self.cmd.run(Mock()))
        is_root.assert_called_once()
        which.assert_called_once_with('systemctl')
        syscall.assert_has_calls([call(f'systemctl status {OPTIMIZER_SERVICE_FILE}', custom_env=EXPECTED_CUSTOM_ENV),
                                  call(f'systemctl disable --now {OPTIMIZER_SERVICE_FILE}', custom_env=EXPECTED_CUSTOM_ENV)])
        exists.assert_called_once_with('/file.service')

    @patch(f'{__app_name__}.cli.commands.service.os.remove')
    @patch(f'{__app_name__}.cli.commands.service.os.path.exists', return_value=True)
    @patch(f'{__app_name__}.cli.commands.service.system.syscall', return_value=(0, ' loaded (/file.service; disabled; )'))
    @patch(f'{__app_name__}.cli.commands.service.shutil.which', return_value='/bin')
    @patch(f'{__app_name__}.cli.commands.service.is_root_user', return_value=True)
    def test_run__must_return_true_and_remove_service_file_from_systemd_dir_when_it_exists(self, is_root: Mock, which: Mock, syscall: Mock, exists: Mock, remove: Mock):
        self.assertTrue(self.cmd.run(Mock()))
        is_root.assert_called_once()
        which.assert_called_once_with('systemctl')
        syscall.assert_called_once_with(f'systemctl status {OPTIMIZER_SERVICE_FILE}', custom_env=EXPECTED_CUSTOM_ENV)
        exists.assert_called_once_with('/file.service')
        remove.assert_called_once_with('/file.service')
