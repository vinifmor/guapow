import os
from logging import Logger
from subprocess import DEVNULL
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch, Mock, call, PropertyMock

from guapow import __app_name__
from guapow.common.config import OptimizerConfig
from guapow.common.dto import OptimizationRequest
from guapow.common.model_util import FileModelFiller
from guapow.common.scripts import RunScripts
from guapow.runner.main import launch_process
from tests import RESOURCES_DIR, AnyInstance


class LaunchProcessTest(IsolatedAsyncioTestCase):

    def tearDown(self):
        if 'GUAPOW_PROFILE' in os.environ:
            del os.environ['GUAPOW_PROFILE']

    @patch(f'{__app_name__}.runner.main.sys')
    @patch('time.time', return_value=1263876386)
    @patch(f'{__app_name__}.runner.main.is_log_enabled', return_value=False)
    @patch('getpass.getuser', return_value="test")
    @patch('os.getuid', return_value=10300)
    @patch(f'{__app_name__}.runner.profile.get_profile_dir', return_value=RESOURCES_DIR)
    @patch(f'{__app_name__}.runner.main.Popen')
    @patch(f'{__app_name__}.common.network.send')
    @patch(f'{__app_name__}.runner.main.read_optimizer_config', return_value=OptimizerConfig.default())
    @patch(f'{__app_name__}.runner.main.read_machine_id', return_value='123')
    async def test__process_must_run_with_environment_variables_defined_on_the_profile(self, read_machine_id: Mock, read_opt_config: Mock,
                                                                                       network_send: Mock, popen: Mock, get_profile_dir: Mock,
                                                                                       getuid: Mock, getuser: Mock, is_log_enabled: Mock,
                                                                                       time_mock: Mock, sys_mock: Mock):
        sys_mock.argv = ['', 'test', 'cmd']
        popen.return_value.pid = 123
        profile = 'runner_env_vars'

        os.environ['GUAPOW_PROFILE'] = profile

        await launch_process()
        is_log_enabled.assert_called()
        getuser.assert_called_once()
        get_profile_dir.assert_called()
        getuid.assert_called_once()
        time_mock.assert_called()

        expected_env = dict(os.environ)
        expected_env['GT_TEST_1'] = 'abc'
        expected_env['GT_TEST_2'] = '0'

        popen.assert_called_once_with(['test', 'cmd'], **{'env': expected_env})

        read_opt_config.assert_called_once_with(user_id=10300, user_name='test', logger=AnyInstance(Logger),
                                                filler=AnyInstance(FileModelFiller), only_properties={'port', 'request.encrypted'})
        read_machine_id.assert_called_once()

        exp_req = OptimizationRequest(profile=profile, pid=123, command='test cmd', user_env=expected_env,
                                      user_name='test', created_at=1263876386)
        network_send.assert_called_once_with(request=exp_req, opt_config=AnyInstance(OptimizerConfig), machine_id='123', logger=AnyInstance(Logger))

    @patch(f'{__app_name__}.runner.main.sys')
    @patch('time.time', return_value=1263876386)
    @patch(f'{__app_name__}.runner.main.is_log_enabled', return_value=False)
    @patch('getpass.getuser', return_value="test")
    @patch('os.getuid', return_value=10300)
    @patch(f'{__app_name__}.runner.profile.get_profile_dir', return_value=RESOURCES_DIR)
    @patch(f'{__app_name__}.runner.main.Popen')
    @patch(f'{__app_name__}.common.network.send')
    @patch(f'{__app_name__}.common.scripts.asyncio.create_subprocess_shell', side_effect=[PropertyMock(pid=444), PropertyMock(pid=555)])
    @patch(f'{__app_name__}.runner.main.read_optimizer_config', return_value=OptimizerConfig.default())
    @patch(f'{__app_name__}.runner.main.read_machine_id', return_value='123')
    async def test__process_must_run_scripts_before_the_process(self, read_machine_id: Mock, read_opt_config: Mock, create_subprocess_shell: Mock,
                                                                network_send: Mock, main_popen: Mock,
                                                                get_profile_dir: Mock, getuid: Mock,
                                                                getuser: Mock, is_log_enabled: Mock,
                                                                time_mock: Mock, sys_mock: Mock):

        sys_mock.argv = ['', 'test', 'cmd']
        main_popen.return_value.pid = 123
        profile = 'only_before_scripts'

        os.environ['GUAPOW_PROFILE'] = profile

        await launch_process()
        is_log_enabled.assert_called()
        getuser.assert_called_once()
        get_profile_dir.assert_called()
        getuid.assert_called()
        time_mock.assert_called()

        create_subprocess_shell.assert_has_calls([
            call(cmd='/xpto', stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL, env=RunScripts.get_environ()),
            call(cmd='/abc', stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL, env=RunScripts.get_environ())
        ])

        main_popen.assert_called_once_with(['test', 'cmd'], **{})
        read_opt_config.assert_called_once()
        read_machine_id.assert_called_once()

        exp_req = OptimizationRequest(profile=profile, pid=123, command='test cmd', user_env=dict(os.environ),
                                      user_name='test', created_at=1263876386, related_pids={444, 555})
        network_send.assert_called_once_with(request=exp_req, opt_config=AnyInstance(OptimizerConfig), machine_id='123', logger=AnyInstance(Logger))

    @patch(f'{__app_name__}.runner.main.sys')
    @patch('time.time', return_value=1263876386)
    @patch(f'{__app_name__}.runner.main.is_log_enabled', return_value=False)
    @patch('getpass.getuser', return_value="test")
    @patch('os.getuid', return_value=10300)
    @patch(f'{__app_name__}.runner.profile.get_profile_dir', return_value=RESOURCES_DIR)
    @patch(f'{__app_name__}.runner.main.Popen')
    @patch(f'{__app_name__}.common.network.send')
    @patch(f'{__app_name__}.runner.task.system.find_commands_by_pids', return_value={1: '/abc', 2: '/def'})
    @patch(f'{__app_name__}.runner.task.system.find_pids_by_names', return_value={'abc': 1, 'def': 2})
    @patch(f'{__app_name__}.runner.task.system.async_syscall', return_value=(0, ''))
    @patch(f'{__app_name__}.runner.main.read_optimizer_config', return_value=OptimizerConfig.default())
    @patch(f'{__app_name__}.runner.main.read_machine_id', return_value='2345678')
    async def test__must_try_to_stop_requested_processes_before_launching_and_request_to_be_relaunched(self,
                                                                                                       read_machine_id: Mock,
                                                                                                       read_opt_config: Mock,
                                                                                                       syscall: Mock,
                                                                                                       find_pids_by_names: Mock,
                                                                                                       find_commands_by_pids: Mock,
                                                                                                       network_send: Mock,
                                                                                                       main_popen: Mock,
                                                                                                       get_profile_dir: Mock,
                                                                                                       getuid: Mock,
                                                                                                       getuser: Mock,
                                                                                                       is_log_enabled: Mock,
                                                                                                       time_mock: Mock,
                                                                                                       sys_mock: Mock):

        sys_mock.argv = ['', 'test', 'cmd']
        main_popen.return_value.pid = 123
        profile = 'only_stop_procs_relaunch'

        os.environ['GUAPOW_PROFILE'] = profile

        await launch_process()
        is_log_enabled.assert_called()
        getuser.assert_called_once()
        get_profile_dir.assert_called()
        getuid.assert_called_once()

        find_pids_by_names.assert_called_once_with({'abc', 'def'})
        find_commands_by_pids.assert_called_once_with({1, 2})

        self.assertTrue(syscall.call_args.args[0].startswith('kill -9 '))
        for cmd in (' 1', ' 2'):
            self.assertIn(cmd, syscall.call_args.args[0])

        time_mock.assert_called()

        main_popen.assert_called_once_with(['test', 'cmd'], **{})
        read_opt_config.assert_called()
        read_machine_id.assert_called_once()

        exp_req = OptimizationRequest(profile=profile, pid=123, command='test cmd', user_env=dict(os.environ),
                                      user_name='test', created_at=1263876386, stopped_processes={'abc': '/abc', 'def': '/def'},
                                      relaunch_stopped_processes=True)
        network_send.assert_called_once_with(request=exp_req, opt_config=AnyInstance(OptimizerConfig), machine_id='2345678', logger=AnyInstance(Logger))

    @patch(f'{__app_name__}.runner.main.sys')
    @patch('time.time', return_value=1263876386)
    @patch(f'{__app_name__}.runner.main.is_log_enabled', return_value=False)
    @patch('getpass.getuser', return_value="test")
    @patch('os.getuid', return_value=10300)
    @patch(f'{__app_name__}.runner.profile.get_profile_dir', return_value=RESOURCES_DIR)
    @patch(f'{__app_name__}.runner.main.Popen')
    @patch(f'{__app_name__}.common.network.send')
    @patch(f'{__app_name__}.runner.task.system.find_commands_by_pids', return_value={1: '/abc', 2: '/def', 3: '/fgh'})
    @patch(f'{__app_name__}.runner.task.system.find_pids_by_names', return_value={'abc': 1, 'def': 2, 'fgh': 3})
    @patch(f'{__app_name__}.runner.task.system.async_syscall', return_value=(0, ''))
    @patch(f'{__app_name__}.runner.main.read_optimizer_config', return_value=OptimizerConfig.default())
    @patch(f'{__app_name__}.runner.main.read_machine_id', return_value='2345678')
    async def test__must_try_to_stop_requested_processes_before_launching(self, read_machine_id: Mock, read_opt_config: Mock,
                                                                          syscall: Mock, find_pids_by_names: Mock,
                                                                          find_commands_by_pids: Mock,
                                                                          network_send: Mock, main_popen: Mock, get_profile_dir: Mock,
                                                                          getuid: Mock, getuser: Mock, is_log_enabled: Mock, time_mock: Mock,
                                                                          sys_mock: Mock):

        sys_mock.argv = ['', 'test', 'cmd']
        main_popen.return_value.pid = 123
        profile = 'only_stop_procs'

        os.environ['GUAPOW_PROFILE'] = profile

        await launch_process()
        is_log_enabled.assert_called()
        getuser.assert_called_once()
        get_profile_dir.assert_called()
        getuid.assert_called_once()
        find_pids_by_names.assert_called_once_with({'abc', 'def', 'fgh'})
        find_commands_by_pids.assert_called_once_with({1, 2, 3})

        self.assertTrue(syscall.call_args.args[0].startswith('kill -9 '))
        for cmd in (' 1', ' 2', ' 3'):
            self.assertIn(cmd, syscall.call_args.args[0])

        time_mock.assert_called()

        main_popen.assert_called_once_with(['test', 'cmd'], **{})
        read_opt_config.assert_called_once()
        read_machine_id.assert_called_once()

        exp_req = OptimizationRequest(profile=profile, pid=123, command='test cmd', user_env=dict(os.environ),
                                      user_name='test', created_at=1263876386, stopped_processes={'abc': '/abc', 'def': '/def', 'fgh': '/fgh'})
        network_send.assert_called_once_with(request=exp_req, opt_config=AnyInstance(OptimizerConfig), machine_id='2345678', logger=AnyInstance(Logger))
