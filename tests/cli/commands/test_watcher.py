import os
import re
import shutil
from typing import Dict
from unittest import TestCase
from unittest.mock import Mock, patch, call

from guapow import __app_name__
from guapow.cli.commands import InstallWatcher, UninstallWatcher, WATCHER_SERVICE_FILE
from tests import RESOURCES_DIR, AnyInstance

MOCKED_SYSTEMD_DIR = f'{RESOURCES_DIR}/mock_systemd'


def remover_mocked_systemd_dir():
    if os.path.exists(MOCKED_SYSTEMD_DIR):
        shutil.rmtree(MOCKED_SYSTEMD_DIR)


class InstallWatcherTest(TestCase):

    def setUp(self):
        remover_mocked_systemd_dir()
        self.cmd = InstallWatcher(Mock())

    def tearDown(self):
        remover_mocked_systemd_dir()

    @classmethod
    def tearDownClass(cls):
        remover_mocked_systemd_dir()

    def test_get_command__must_be_equal_to_install_watcher(self):
        self.assertEqual('install-watcher', self.cmd.get_command())

    @patch(f'{__app_name__}.cli.commands.service.system.syscall',
           side_effect=[(0, ' loaded (/file.service; disabled; xpto)'),
                        (0, '')])
    @patch(f'{__app_name__}.cli.commands.service.get_systemd_user_service_dir', return_value=MOCKED_SYSTEMD_DIR)
    @patch(f'{__app_name__}.cli.commands.service.shutil.which', side_effect=['sysctl', f'/bin/test/{__app_name__}-watch'])
    @patch(f'{__app_name__}.cli.commands.service.is_root_user', return_value=False)
    def test_run__must_be_able_to_install_at_user_level(self, is_root: Mock, which: Mock, get_systemd_user_service_dir: Mock, syscall: Mock):
        self.assertTrue(self.cmd.run(Mock()))

        exp_service_file = f'{MOCKED_SYSTEMD_DIR}/{WATCHER_SERVICE_FILE}'
        self.assertTrue(os.path.exists(exp_service_file))

        with open(exp_service_file) as f:
            service_definition = f.read()

        service_cmd = re.compile(f'ExecStart=(.+)\n').findall(service_definition)
        self.assertEqual([f'/bin/test/{__app_name__}-watch'], service_cmd)

        is_root.assert_called_once()
        which.assert_has_calls([call('systemctl'), call(f'{__app_name__}-watch')])
        get_systemd_user_service_dir.assert_called_once()

        syscall.assert_has_calls([call(f'systemctl status --user {WATCHER_SERVICE_FILE}', custom_env=AnyInstance(Dict)),
                                  call(f'systemctl enable --user --now {WATCHER_SERVICE_FILE}', custom_env=AnyInstance(Dict))])

        for mock_call in syscall.call_args.call_list():
            self.assertGreater(len(mock_call.kwargs['custom_env']), 1)
            self.assertEqual('en_US.UTF-8', mock_call.kwargs['custom_env'].get('LANG'))


class UninstallWatcherTest(TestCase):

    def setUp(self):
        self.cmd = UninstallWatcher(Mock())

    def test_get_command__must_be_equal_to_install_watcher(self):
        self.assertEqual('uninstall-watcher', self.cmd.get_command())

    @patch(f'{__app_name__}.cli.commands.service.os.remove')
    @patch(f'{__app_name__}.cli.commands.service.os.path.exists', return_value=True)
    @patch(f'{__app_name__}.cli.commands.service.system.syscall', side_effect=[(0, ' loaded (/file.service; enabled; )'),
                                                                               (0, '')])
    @patch(f'{__app_name__}.cli.commands.service.shutil.which', return_value='/bin')
    @patch(f'{__app_name__}.cli.commands.service.is_root_user', return_value=False)
    def test_run__must_be_able_to_uninstall_at_user_level(self, is_root: Mock, which: Mock, syscall: Mock, exists: Mock, remove: Mock):
        self.assertTrue(self.cmd.run(Mock()))
        is_root.assert_called_once()
        which.assert_called_once_with('systemctl')
        syscall.assert_has_calls([call(f'systemctl status --user {WATCHER_SERVICE_FILE}', custom_env=AnyInstance(Dict)),
                                  call(f'systemctl disable --user --now {WATCHER_SERVICE_FILE}', custom_env=AnyInstance(Dict))])
        exists.assert_called_once_with('/file.service')
        remove.assert_called_once_with('/file.service')

        for mock_call in syscall.call_args.call_list():
            self.assertGreater(len(mock_call.kwargs['custom_env']), 1)
            self.assertEqual('en_US.UTF-8', mock_call.kwargs['custom_env'].get('LANG'))
