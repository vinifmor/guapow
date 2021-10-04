import subprocess
from asyncio import Future
from multiprocessing.managers import DictProxy
from typing import List
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, MagicMock, patch, call

from guapow import __app_name__
from guapow.common import system
from guapow.common.model import ScriptSettings
from guapow.common.scripts import RunScripts
from tests import AnyInstance


class UserProcessMock:

    def __init__(self, pids: List[int]):
        self._pids = pids
        self._idx = 0

    def run(self, **kwargs) -> MagicMock:
        if kwargs['args'] and len(kwargs['args']) == 6 and isinstance(kwargs['args'][5], DictProxy):
            kwargs['args'][5]['pid'] = self._pids[self._idx]

            if self._idx + 1 < len(self._pids):
                self._idx += 1

        return MagicMock(is_alive=Mock(return_value=False))


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
    @patch(f'{__app_name__}.common.scripts.Process', side_effect=UserProcessMock(pids=[5, 7, 9]).run)
    async def test_run__must_run_scripts_as_another_user_when_current_user_is_root_and_user_is_defined(self, run_user_command: Mock, is_root_user: Mock):
        user_id, user_env = 123, {'DISPLAY': ':0'}

        scripts = [ScriptSettings(node_name='', scripts=['/abc', '/def'], run_as_root=False, wait_execution=False),
                   ScriptSettings(node_name='', scripts=['/ghi'], run_as_root=False, wait_execution=False)]
        self.assertEqual({5, 7, 9}, await self.task.run(scripts, user_id=user_id, user_env=user_env))

        self.assertEqual(3, is_root_user.call_count)

        run_user_command.assert_has_calls([
            call(daemon=True, target=system.run_user_command, args=('/abc', user_id, False, None, user_env, AnyInstance(DictProxy))),
            call(daemon=True, target=system.run_user_command, args=('/def', user_id, False, None, user_env, AnyInstance(DictProxy))),
            call(daemon=True, target=system.run_user_command, args=('/ghi', user_id, False, None, user_env, AnyInstance(DictProxy)))
        ])

    @patch(f'{__app_name__}.common.scripts.is_root_user', side_effect=[True, False, False, False])
    @patch(f'{__app_name__}.common.scripts.Process', side_effect=UserProcessMock(pids=[5, 7, 9]).run)
    async def test_run__must_run_scripts_as_another_user_and_wait_timeout_when_current_user_is_root_and_user_is_defined(self, run_user_command: Mock, is_root_user: Mock):
        user_id, user_env = 123, {'DISPLAY': ':0'}

        scripts = [ScriptSettings(node_name='', scripts=['/abc', '/def'], run_as_root=False, timeout=0.001),
                   ScriptSettings(node_name='', scripts=['/ghi'], run_as_root=False, timeout=0.001)]
        self.assertEqual({5, 7, 9}, await self.task.run(scripts, user_id=user_id, user_env=user_env))

        self.assertEqual(3, is_root_user.call_count)

        run_user_command.assert_has_calls([
            call(daemon=True, target=system.run_user_command, args=('/abc', user_id, False, 0.001, user_env, AnyInstance(DictProxy))),
            call(daemon=True, target=system.run_user_command, args=('/def', user_id, False, 0.001, user_env, AnyInstance(DictProxy))),
            call(daemon=True, target=system.run_user_command, args=('/ghi', user_id, False, 0.001, user_env, AnyInstance(DictProxy)))
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
    @patch(f'{__app_name__}.common.scripts.RunScripts._execute_scripts', return_value=MagicMock())
    @patch(f'{__app_name__}.common.scripts.RunScripts._execute_user_scripts', return_value=MagicMock())
    async def test_run__must_not_run_scripts_as_root_user_when_current_user_is_not_root(self, exec_user_scripts: Mock, exec_scripts: Mock, getuid: Mock):
        scripts = [ScriptSettings(node_name='', scripts=['/abc'], run_as_root=True, wait_execution=False)]
        self.assertEqual(set(), await self.task.run(scripts, user_id=12312, user_env=None))

        getuid.assert_called_once()
        exec_user_scripts.assert_not_called()
        exec_scripts.assert_not_called()

    @patch('os.getuid', return_value=12312)
    @patch('asyncio.create_subprocess_shell', return_value=MagicMock(pid=888))
    @patch(f'{__app_name__}.common.scripts.RunScripts._execute_user_scripts')
    async def test_run__must_run_scripts_as_current_user_when_informed_id_matches_and_root_run_was_not_requested(self, execute_user_scripts: Mock, create_subprocess_shell: Mock, getuid: Mock):
        mocked_proc_wait = MagicMock(return_value=Future())
        mocked_proc_wait.return_value.set_result(None)

        create_subprocess_shell.return_value.wait = mocked_proc_wait

        scripts = [ScriptSettings(node_name='', scripts=['/abc'], run_as_root=False, wait_execution=False)]
        self.assertEqual({888}, await self.task.run(scripts, user_id=12312, user_env={}))

        getuid.assert_called_once()
        execute_user_scripts.assert_not_called()

        exp_env = self.task.get_environ()
        create_subprocess_shell.assert_called_once_with(cmd='/abc', stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=exp_env)
        mocked_proc_wait.assert_not_called()

    @patch('os.getuid', return_value=12312)
    @patch('asyncio.create_subprocess_shell', side_effect=[MagicMock(pid=4, return_code=None), MagicMock(pid=5, return_code=None)])
    @patch(f'{__app_name__}.common.scripts.RunScripts._execute_user_scripts')
    async def test_run__must_run_scripts_as_current_user_and_waits_until_time_out(self, execute_user_scripts: Mock, create_subprocess_shell: Mock, getuid: Mock):
        scripts = [ScriptSettings(node_name='', scripts=['/abc', '/def'], run_as_root=False, wait_execution=True, timeout=0.005)]
        self.assertEqual({4, 5}, await self.task.run(scripts, user_id=12312, user_env={}))

        getuid.assert_called_once()
        execute_user_scripts.assert_not_called()

        exp_env = self.task.get_environ()
        create_subprocess_shell.assert_has_calls([
            call(cmd='/abc', stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=exp_env),
            call(cmd='/def', stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=exp_env)
        ])

    @patch('os.getuid', return_value=12312)
    @patch('asyncio.create_subprocess_shell', return_value=MagicMock(pid=888))
    @patch(f'{__app_name__}.common.scripts.RunScripts._execute_user_scripts')
    async def test_run__must_run_scripts_as_current_user_when_informed_id_is_none_and_root_run_was_not_requested(self, execute_user_scripts: Mock, create_subprocess_shell: Mock, getuid: Mock):
        mocked_proc_wait = MagicMock(return_value=Future())
        mocked_proc_wait.return_value.set_result(None)

        create_subprocess_shell.return_value.wait = mocked_proc_wait

        scripts = [ScriptSettings(node_name='', scripts=['/abc'], run_as_root=False, wait_execution=False)]
        self.assertEqual({888}, await self.task.run(scripts, user_id=None, user_env={}))

        getuid.assert_called_once()
        execute_user_scripts.assert_not_called()

        exp_env = self.task.get_environ()
        create_subprocess_shell.assert_called_once_with(cmd='/abc', stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=exp_env)
        mocked_proc_wait.assert_not_called()
