import asyncio
import os
import re
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, patch, call, PropertyMock, AsyncMock

from guapow import __app_name__
from guapow.service.optimizer.mouse import MouseCursorManager


class MouseCursorManagerTest(IsolatedAsyncioTestCase):

    UNCLUTTER_MATCH_PATTERN = re.compile(r'^unclutter$')

    def setUp(self):
        self.mouse_man = MouseCursorManager(logger=Mock(), renicing=False)

    @patch(f'{__app_name__}.service.optimizer.mouse.shutil.which', side_effect=['/bin/uncluter'])
    async def test_can_work__true_when_unclutter_is_installed(self, which: Mock):
        res = self.mouse_man.can_work()
        self.assertTrue(res[0])
        self.assertIsNone(res[1])
        which.assert_called_once_with('unclutter')

    @patch(f'{__app_name__}.service.optimizer.mouse.shutil.which', return_value=None)
    def test_can_work__false_when_unclutter_is_not_installed(self, which: Mock):
        res = self.mouse_man.can_work()
        self.assertFalse(res[0])
        self.assertIsInstance(res[1], str)
        which.assert_called_once_with('unclutter')

    @patch(f'{__app_name__}.service.optimizer.mouse.find_process_by_name', return_value=None)
    @patch(f'{__app_name__}.service.optimizer.mouse.async_syscall', return_value=(0, None))
    async def test_hide_cursor__set_hidden_to_true_when_cursor_not_previously_hidden_and_unclutter_not_alive_and_succeeds(self, async_syscall: Mock, find_process: Mock):
        self.assertIsNone(await self.mouse_man.is_cursor_hidden())  # unknown at this point

        await self.mouse_man.hide_cursor(user_request=True, user_env={'DISPLAY': ':1'})
        self.assertTrue(await self.mouse_man.is_cursor_hidden())
        find_process.assert_called_once_with(self.UNCLUTTER_MATCH_PATTERN)
        async_syscall.assert_called_once_with('unclutter --timeout 1 -b', custom_env={'DISPLAY': ':1'}, return_output=False)

    @patch(f'{__app_name__}.service.optimizer.mouse.os.setpriority')
    @patch(f'{__app_name__}.service.optimizer.mouse.system.find_pids_by_names', return_value={'unclutter': 37892293})
    @patch(f'{__app_name__}.service.optimizer.mouse.find_process_by_name', return_value=None)
    @patch(f'{__app_name__}.service.optimizer.mouse.async_syscall', return_value=(0, None))
    @patch(f'{__app_name__}.service.optimizer.mouse.os.environ', new_callable=PropertyMock(return_value={}))
    async def test_hide_cursor__must_try_renicing_unclutter_if_renicing_is_true(self, _: PropertyMock, async_syscall: Mock, find_process: Mock, find_pids_by_names: AsyncMock, setpriority: Mock):
        self.mouse_man = MouseCursorManager(logger=Mock(), renicing=True)

        await self.mouse_man.hide_cursor(user_request=True, user_env={'DISPLAY': ':2'})
        self.assertTrue(await self.mouse_man.is_cursor_hidden())
        find_process.assert_called_once_with(self.UNCLUTTER_MATCH_PATTERN)
        async_syscall.assert_called_once()

        await asyncio.sleep(0.001)  # allowing the 'renicing' task to run

        find_pids_by_names.assert_awaited_once_with(names=('unclutter',), last_match=True)
        setpriority.assert_called_once_with(os.PRIO_PROCESS, 37892293, 1)

    @patch(f'{__app_name__}.service.optimizer.mouse.find_process_by_name', return_value=None)
    @patch(f'{__app_name__}.service.optimizer.mouse.async_syscall', return_value=(0, None))
    async def test_hide_cursor__set_cursor_hidden_to_false_when_not_user_request_and_unclutter_succeeds(self, async_syscall: Mock, find_process: Mock):
        self.assertIsNone(await self.mouse_man.is_cursor_hidden())  # unknown at this point

        await self.mouse_man.hide_cursor(user_request=False, user_env={'DISPLAY': ':0'})
        self.assertFalse(await self.mouse_man.is_cursor_hidden())
        find_process.assert_called_once()
        async_syscall.assert_called_once()

    @patch(f'{__app_name__}.service.optimizer.mouse.find_process_by_name', return_value=None)
    @patch(f'{__app_name__}.service.optimizer.mouse.async_syscall', return_value=(1, 'erro\nblabla'))
    async def test_hide_cursor__set_mouse_hidden_as_false_when_cursor_not_previously_hidden_and_unclutter_not_alive_and_fails(self, async_syscall: Mock, find_process: Mock):
        self.assertIsNone(await self.mouse_man.is_cursor_hidden())  # unknown at this point

        await self.mouse_man.hide_cursor(user_request=False, user_env={'DISPLAY': ':2'})
        self.assertFalse(await self.mouse_man.is_cursor_hidden())
        find_process.assert_called_once()
        async_syscall.assert_called_once()

    @patch(f'{__app_name__}.service.optimizer.mouse.find_process_by_name', return_value=None)
    @patch(f'{__app_name__}.service.optimizer.mouse.async_syscall', return_value=(0, None))
    async def test_hide_cursor__set_cursor_hidden_to_true_when_user_request_and_cursor_previously_hidden_and_unclutter_succeeds(self, async_syscall: Mock, find_process: Mock):
        self.mouse_man = MouseCursorManager(logger=Mock(), renicing=False, cursor_hidden=True)  # previously hidden by the Optimizer

        await self.mouse_man.hide_cursor(user_request=True, user_env={'DISPLAY': ':0'})
        self.assertTrue(await self.mouse_man.is_cursor_hidden())
        find_process.assert_called_once()
        async_syscall.assert_called_once()

    @patch(f'{__app_name__}.service.optimizer.mouse.find_process_by_name', return_value=None)
    @patch(f'{__app_name__}.service.optimizer.mouse.async_syscall', return_value=(1, 'erro\nblabla'))
    async def test_hide_cursor__set_mouse_hidden_as_false_when_cursor_previously_hidden_and_unclutter_fails(self, async_syscall: Mock, find_process: Mock):
        self.mouse_man = MouseCursorManager(logger=Mock(), renicing=False, cursor_hidden=True)  # previously hidden by the Optimizer

        await self.mouse_man.hide_cursor(user_request=True, user_env={'DISPLAY': ':1'})
        self.assertTrue(await self.mouse_man.is_cursor_hidden())
        find_process.assert_called_once()
        async_syscall.assert_called_once()

    @patch(f'{__app_name__}.service.optimizer.mouse.find_process_by_name', return_value=(1, 'unclutter'))
    @patch(f'{__app_name__}.service.optimizer.mouse.async_syscall', return_value=(0, None))
    async def test_hide_cursor__set_mouse_hidden_as_false_when_cursor_not_previously_hidden_and_unclutter_alive(self, async_syscall: Mock, find_process: Mock):
        self.mouse_man = MouseCursorManager(logger=Mock(), renicing=False, cursor_hidden=False)

        await self.mouse_man.hide_cursor(user_request=False, user_env={'DISPLAY': ':0'})
        self.assertFalse(await self.mouse_man.is_cursor_hidden())
        find_process.assert_called_once()
        async_syscall.assert_not_called()

    @patch(f'{__app_name__}.service.optimizer.mouse.find_process_by_name', return_value=(1, 'unclutter'))
    @patch(f'{__app_name__}.service.optimizer.mouse.async_syscall', return_value=(0, None))
    async def test_hide_cursor__set_cursor_hidden_to_true_when_cursor_previously_hidden_and_unclutter_alive(self, async_syscall: Mock, find_process: Mock):
        self.mouse_man = MouseCursorManager(logger=Mock(), renicing=False, cursor_hidden=False)

        await self.mouse_man.hide_cursor(user_request=False, user_env={'DISPLAY': ':2'})
        self.assertFalse(await self.mouse_man.is_cursor_hidden())
        find_process.assert_called_once()
        async_syscall.assert_not_called()

    @patch(f'{__app_name__}.service.optimizer.mouse.find_process_by_name', side_effect=[None, (5274523, 'unclutter')])
    @patch(f'{__app_name__}.service.optimizer.mouse.async_syscall', return_value=(0, None))
    @patch(f'{__app_name__}.service.optimizer.mouse.os.environ', new_callable=PropertyMock(return_value={}))
    async def test_hide_cursor__set_cursor_hidden_to_true_once_for_concurrent_calls(self, _: PropertyMock, async_syscall: Mock, find_process: Mock):
        self.assertIsNone(await self.mouse_man.is_cursor_hidden())  # unknown at this point

        await asyncio.gather(self.mouse_man.hide_cursor(user_request=True, user_env=None), self.mouse_man.hide_cursor(user_request=True, user_env=None))
        self.assertTrue(await self.mouse_man.is_cursor_hidden())
        find_process.assert_has_calls([call(self.UNCLUTTER_MATCH_PATTERN), call(self.UNCLUTTER_MATCH_PATTERN)])
        async_syscall.assert_called_once_with('unclutter --timeout 1 -b', custom_env={'DISPLAY': ':0'}, return_output=False)

    @patch(f'{__app_name__}.service.optimizer.mouse.find_process_by_name', return_value=None)
    @patch(f'{__app_name__}.service.optimizer.mouse.async_syscall', return_value=(0, None))
    async def test_hide_cursor__must_not_add_DISPLAY_var_for_user_env_if_already_defined_with_a_value(self, async_syscall: Mock, find_process: Mock):
        self.assertIsNone(await self.mouse_man.is_cursor_hidden())  # unknown at this point

        await self.mouse_man.hide_cursor(user_request=True, user_env={'DISPLAY': ':2'})  # display not defined
        self.assertTrue(await self.mouse_man.is_cursor_hidden())
        find_process.assert_called_once_with(self.UNCLUTTER_MATCH_PATTERN)
        async_syscall.assert_called_once_with('unclutter --timeout 1 -b', custom_env={'DISPLAY': ':2'}, return_output=False)

    @patch(f'{__app_name__}.service.optimizer.mouse.find_process_by_name', return_value=None)
    @patch(f'{__app_name__}.service.optimizer.mouse.async_syscall', return_value=(0, None))
    @patch(f'{__app_name__}.service.optimizer.mouse.os.environ', new_callable=PropertyMock(return_value={'DISPLAY': ':5'}))
    async def test_hide_cursor__must_not_add_DISPLAY_var_for_current_env_if_already_defined_with_a_value(self, _: PropertyMock, async_syscall: Mock, find_process: Mock):
        self.assertIsNone(await self.mouse_man.is_cursor_hidden())  # unknown at this point

        await self.mouse_man.hide_cursor(user_request=True, user_env=None)  # user env not defined (current env will be used)
        self.assertTrue(await self.mouse_man.is_cursor_hidden())
        find_process.assert_called_once_with(self.UNCLUTTER_MATCH_PATTERN)
        async_syscall.assert_called_once_with('unclutter --timeout 1 -b', custom_env={'DISPLAY': ':5'}, return_output=False)

    @patch(f'{__app_name__}.service.optimizer.mouse.find_process_by_name', return_value=None)
    @patch(f'{__app_name__}.service.optimizer.mouse.async_syscall', return_value=(0, None))
    async def test_hide_cursor__must_add_DISPLAY_var_if_not_defined_or_no_value_in_the_user_env(self, async_syscall: Mock, find_process: Mock):
        self.assertIsNone(await self.mouse_man.is_cursor_hidden())  # unknown at this point

        await self.mouse_man.hide_cursor(user_request=True, user_env={'DISPLAY': '  '})  # display not defined
        self.assertTrue(await self.mouse_man.is_cursor_hidden())
        find_process.assert_called_once_with(self.UNCLUTTER_MATCH_PATTERN)
        async_syscall.assert_called_once_with('unclutter --timeout 1 -b', custom_env={'DISPLAY': ':0'}, return_output=False)

    @patch(f'{__app_name__}.service.optimizer.mouse.find_process_by_name', return_value=None)
    @patch(f'{__app_name__}.service.optimizer.mouse.async_syscall', return_value=(0, None))
    @patch(f'{__app_name__}.service.optimizer.mouse.os.environ', new_callable=PropertyMock(return_value={'DISPLAY': '  ', 'var': '1'}))
    async def test_hide_cursor__must_add_DISPLAY_var_if_not_defined_or_no_value_in_the_user_env(self, _: PropertyMock, async_syscall: Mock, find_process: Mock):
        self.assertIsNone(await self.mouse_man.is_cursor_hidden())  # unknown at this point

        await self.mouse_man.hide_cursor(user_request=True, user_env=None)  # user env not defined (current env will be used)
        self.assertTrue(await self.mouse_man.is_cursor_hidden())
        find_process.assert_called_once_with(self.UNCLUTTER_MATCH_PATTERN)
        async_syscall.assert_called_once_with('unclutter --timeout 1 -b', custom_env={'DISPLAY': ':0', 'var': '1'}, return_output=False)

    @patch(f'{__app_name__}.service.optimizer.mouse.system.async_syscall', return_value=(0, None))
    @patch(f'{__app_name__}.service.optimizer.mouse.find_process_by_name', return_value=(1, 'unclutter'))
    async def test_show__must_call_killall_when_unclutter_instances_are_running(self, find_process: Mock, async_syscall: Mock):
        self.mouse_man = MouseCursorManager(logger=Mock(), renicing=False, cursor_hidden=True)
        self.assertTrue(await self.mouse_man.is_cursor_hidden())

        self.assertTrue(await self.mouse_man.show_cursor())

        self.assertIsNone(await self.mouse_man.is_cursor_hidden())  # must reset the optimization context state
        find_process.assert_called_once_with(self.UNCLUTTER_MATCH_PATTERN)
        async_syscall.assert_called_once_with('killall unclutter')

    @patch(f'{__app_name__}.service.optimizer.mouse.system.async_syscall', return_value=(1, 'error'))
    @patch(f'{__app_name__}.service.optimizer.mouse.find_process_by_name', return_value=(1, 'unclutter'))
    async def test_show_cursor__must_not_cleanup_the_context_when_unclutter_could_not_be_killed(self, find_process: Mock, async_syscall: Mock):
        self.mouse_man = MouseCursorManager(logger=Mock(), renicing=False, cursor_hidden=True)
        self.assertTrue(await self.mouse_man.is_cursor_hidden())

        self.assertEqual(False, await self.mouse_man.show_cursor())

        self.assertTrue(await self.mouse_man.is_cursor_hidden())
        find_process.assert_called_once()
        async_syscall.assert_called_once()

    @patch(f'{__app_name__}.service.optimizer.mouse.system.async_syscall')
    @patch(f'{__app_name__}.service.optimizer.mouse.find_process_by_name', return_value=None)
    async def test_show_cursor__must_not_call_killall_when_unclutter_is_not_running(self, find_process: Mock, async_syscall: Mock):
        self.mouse_man = MouseCursorManager(logger=Mock(), renicing=False, cursor_hidden=True)
        self.assertTrue(await self.mouse_man.is_cursor_hidden())

        self.assertEqual(True, await self.mouse_man.show_cursor())
        self.assertIsNone(await self.mouse_man.is_cursor_hidden())  # must reset the optimization context state
        find_process.assert_called_once()
        async_syscall.assert_not_called()
