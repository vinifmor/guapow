import subprocess
from asyncio import Future
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, MagicMock, patch, call

from guapow import __app_name__
from guapow.common.model import ScriptSettings
from guapow.common.scripts import RunScripts


class RunScriptsTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.task = RunScripts(name='test', logger=Mock(), root_allowed=False)

    @patch(f'{__app_name__}.common.scripts.is_root_user', return_value=True)
    @patch('asyncio.create_subprocess_shell', return_value=MagicMock(pid=888))
    async def test_run__must_run_scripts_as_root_when_current_user_is_root_and_root_scripts_are_allowed(self, create_subprocess_shell: Mock, is_root_user: Mock):
        self.task.root_allowed = True

        mocked_proc_wait = MagicMock(return_value=Future())
        mocked_proc_wait.return_value.set_result(None)

        create_subprocess_shell.return_value.wait = mocked_proc_wait

        scripts = [ScriptSettings(node_name='', scripts=['/abc'], run_as_root=True, wait_execution=False)]
        self.assertEqual({888}, await self.task.run(scripts, user_id=0, user_env={}))

        is_root_user.assert_called_once()

        exp_env = self.task.get_environ()
        create_subprocess_shell.assert_called_once_with(cmd='/abc', stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=exp_env)
        mocked_proc_wait.assert_not_called()

    @patch(f'{__app_name__}.common.scripts.is_root_user', return_value=True)
    @patch('asyncio.create_subprocess_shell', return_value=MagicMock())
    async def test_run__must_not_run_scripts_as_root_when_current_user_is_root_and_root_scripts_are_forbidden(self, create_subprocess_shell: Mock, is_root_user: Mock):
        self.task.root_allowed = False

        mocked_proc_wait = MagicMock(return_value=Future())
        mocked_proc_wait.return_value.set_result(None)

        create_subprocess_shell.return_value.wait = mocked_proc_wait

        scripts = [ScriptSettings(node_name='', scripts=['/abc'], run_as_root=True, wait_execution=False)]
        self.assertEqual(set(), await self.task.run(scripts, user_id=0, user_env={}))

        is_root_user.assert_called_once()
        create_subprocess_shell.assert_not_called()
        mocked_proc_wait.assert_not_called()

    @patch(f'{__app_name__}.common.scripts.is_root_user', side_effect=[True, False, False, False])
    @patch(f'{__app_name__}.common.scripts.run_async_process', side_effect=[(5, None, None), (7, None, None), (9, None, None)])
    async def test_run__must_run_scripts_as_another_user_when_current_user_is_root_and_user_is_set(self, *mocks: Mock):
        run_async_process, is_root_user = mocks
        user_id, user_env = 123, {'DISPLAY': ':0'}

        scripts = [ScriptSettings(node_name='', scripts=['/abc', '/def'], run_as_root=False, wait_execution=False),
                   ScriptSettings(node_name='', scripts=['/ghi'], run_as_root=False, wait_execution=False)]
        self.assertEqual({5, 7, 9}, await self.task.run(scripts, user_id=user_id, user_env=user_env))

        self.assertEqual(3, is_root_user.call_count)

        run_async_process.assert_has_calls([
            call(cmd='/abc', user_id=user_id, custom_env=user_env, wait=False, timeout=None, output=False),
            call(cmd='/def', user_id=user_id, custom_env=user_env, wait=False, timeout=None, output=False),
            call(cmd='/ghi', user_id=user_id, custom_env=user_env, wait=False, timeout=None, output=False)
        ])

    @patch(f'{__app_name__}.common.scripts.is_root_user')
    @patch(f'{__app_name__}.common.scripts.run_async_process')
    async def test_run__run_as_another_user_and_wait_timeout_when_current_is_root_and_user_defined(self, *mocks: Mock):
        run_async_process, is_root_user = mocks

        is_root_user.side_effect = [True, False, False, False]
        run_async_process.side_effect = [(5, None, None), (7, None, None), (9, None, None)]

        user_id, user_env = 123, {'DISPLAY': ':0'}

        scripts = [ScriptSettings(node_name='', scripts=['/abc', '/def'], run_as_root=False, timeout=0.001),
                   ScriptSettings(node_name='', scripts=['/ghi'], run_as_root=False, timeout=0.001)]
        self.assertEqual({5, 7, 9}, await self.task.run(scripts, user_id=user_id, user_env=user_env))

        self.assertEqual(3, is_root_user.call_count)

        run_async_process.assert_has_calls([
            call(cmd='/abc', user_id=user_id, custom_env=user_env, wait=False, timeout=0.001, output=False),
            call(cmd='/def', user_id=user_id, custom_env=user_env, wait=False, timeout=0.001, output=False),
            call(cmd='/ghi', user_id=user_id, custom_env=user_env, wait=False, timeout=0.001, output=False)
        ])

    @patch(f'{__app_name__}.common.scripts.is_root_user', return_value=True)
    @patch('asyncio.create_subprocess_shell', return_value=MagicMock(pid=788))
    async def test_run__must_run_scripts_as_root_user_when_user_id_is_not_defined_and_root_scripts_are_allowed(self, create_subprocess_shell: Mock, is_root_user: Mock):
        self.task.root_allowed = True

        mocked_proc_wait = MagicMock(return_value=Future())
        mocked_proc_wait.return_value.set_result(None)

        create_subprocess_shell.return_value.wait = mocked_proc_wait

        scripts = [ScriptSettings(node_name='', scripts=['/abc'], run_as_root=False, wait_execution=False)]
        self.assertEqual({788}, await self.task.run(scripts, user_id=None, user_env=None))

        is_root_user.assert_called_once()

        exp_env = self.task.get_environ()
        create_subprocess_shell.assert_called_once_with(cmd='/abc', stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=exp_env)
        mocked_proc_wait.assert_not_called()

    @patch(f'{__app_name__}.common.scripts.is_root_user', return_value=True)
    @patch('asyncio.create_subprocess_shell', return_value=MagicMock())
    async def test_run__must_not_run_scripts_as_root_user_when_user_id_is_not_defined_and_root_scripts_are_forbidden(self, create_subprocess_shell: Mock, is_root_user: Mock):
        self.task.root_allowed = False

        mocked_proc_wait = MagicMock(return_value=Future())
        mocked_proc_wait.return_value.set_result(None)

        create_subprocess_shell.return_value.wait = mocked_proc_wait

        scripts = [ScriptSettings(node_name='', scripts=['/abc'], run_as_root=False, wait_execution=False)]
        self.assertEqual(set(), await self.task.run(scripts, user_id=None, user_env=None))

        is_root_user.assert_called_once()
        create_subprocess_shell.assert_not_called()
        mocked_proc_wait.assert_not_called()

    @patch('os.getuid', return_value=12312)
    @patch(f'{__app_name__}.common.scripts.run_async_process', return_value=MagicMock())
    async def test_run__must_not_run_scripts_as_root_user_when_current_user_is_not_root(self, *mocks: Mock):
        run_async_process, getuid = mocks
        scripts = [ScriptSettings(node_name='', scripts=['/abc'], run_as_root=True, wait_execution=False)]
        self.assertEqual(set(), await self.task.run(scripts, user_id=12312, user_env=None))

        getuid.assert_called_once()
        run_async_process.assert_not_called()

    @patch("os.getuid", return_value=12312)
    @patch(f"{__app_name__}.common.scripts.run_async_process", return_value=(888, 0, None))
    async def test_run__run_as_current_user_when_informed_id_matches_and_root_run_was_not_requested(self, *mocks: Mock):
        run_async_process, getuid = mocks

        scripts = [ScriptSettings(node_name='', scripts=['/abc'], run_as_root=False, wait_execution=False)]
        self.assertEqual({888}, await self.task.run(scripts, user_id=12312, user_env={}))

        getuid.assert_called_once()

        exp_env = self.task.get_environ()
        run_async_process.assert_called_once_with(cmd='/abc', user_id=None, custom_env=exp_env, wait=False,
                                                  timeout=None, output=False)

    @patch('os.getuid', return_value=12312)
    @patch(f"{__app_name__}.common.scripts.run_async_process")
    async def test_run__must_run_scripts_as_current_user_and_waits_until_time_out(self, *mocks: Mock):
        run_async_process, getuid = mocks
        run_async_process.side_effect = [(4, 0, None), (5, 0, None)]

        scripts = [ScriptSettings(node_name='', scripts=['/abc', '/def'], run_as_root=False, wait_execution=True,
                                  timeout=0.005)]
        self.assertEqual({4, 5}, await self.task.run(scripts, user_id=12312, user_env={}))

        getuid.assert_called_once()

        exp_env = self.task.get_environ()
        run_async_process.assert_has_calls([
            call(cmd='/abc', user_id=None, custom_env=exp_env, wait=True, timeout=0.005, output=False),
            call(cmd='/def', user_id=None, custom_env=exp_env, wait=True, timeout=0.005, output=False)
        ])

    @patch('os.getuid', return_value=12312)
    @patch(f'{__app_name__}.common.scripts.run_async_process', return_value=(888, 0, None))
    async def test_run__run_as_current_user_when_informed_id_is_none_and_root_run_not_requested(self, *mocks: Mock):
        run_async_process, getuid = mocks

        scripts = [ScriptSettings(node_name='', scripts=['/abc'], run_as_root=False, wait_execution=False)]
        self.assertEqual({888}, await self.task.run(scripts, user_id=None, user_env={}))

        getuid.assert_called_once()

        exp_env = self.task.get_environ()
        run_async_process.assert_called_once_with(cmd='/abc', user_id=None, custom_env=exp_env,
                                                  wait=False, timeout=None, output=False)
