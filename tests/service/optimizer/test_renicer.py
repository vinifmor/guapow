import asyncio
import os
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, patch, call

from guapow import __app_name__
from guapow.service.optimizer.renicer import Renicer


class RenicerTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.renicer = Renicer(logger=Mock(), watch_interval=0.0001)

    def test_add__return_true_when_pid_has_not_added_yet(self):
        self.assertEqual({}, self.renicer._pid_nice)

        self.assertTrue(self.renicer.add(1, 2, 1))

        self.assertEqual({1: (2, 1)}, self.renicer._pid_nice)

    def test_add__return_false_when_pid_is_already_added(self):
        self.renicer._pid_nice[1] = (-4, 2)

        self.assertEqual(False, self.renicer.add(1, 2, 1))

        self.assertEqual({1: (-4, 2)}, self.renicer._pid_nice)

    @patch(f'{__app_name__}.service.optimizer.renicer.os.setpriority')
    def test_set_priority__return_true_when_no_exception_is_raised(self, setpriority: Mock):
        self.assertEqual(True, self.renicer.set_priority(789, -2, 2))
        setpriority.assert_called_once_with(os.PRIO_PROCESS, 789, -2)

    @patch(f'{__app_name__}.service.optimizer.renicer.os.setpriority', side_effect=OSError)
    def test_set_priority__return_false_when_exception_is_raised(self, setpriority: Mock):
        self.assertEqual(False, self.renicer.set_priority(789, -2, 2))
        setpriority.assert_called_once_with(os.PRIO_PROCESS, 789, -2)

    @patch(f'{__app_name__}.service.optimizer.renicer.os.setpriority')
    @patch(f'{__app_name__}.service.optimizer.renicer.os.getpriority', return_value=0)
    @patch(f'{__app_name__}.service.optimizer.renicer.system.read_current_pids', side_effect=[{1, 2, 3}, {}])   # on the first iteration all watched processes are alive, on the second none
    async def test_watch__must_set_priority_from_watched_processes_with_priorities_different_from_expected(self, read_current_pids: Mock, get_priority: Mock, set_priority: Mock):
        self.renicer.add(1, -1, 1)
        self.renicer.add(2, -2, 2)

        self.assertFalse(self.renicer.is_watching())

        self.assertTrue(self.renicer.watch())

        self.assertTrue(self.renicer.is_watching())

        for _ in range(3):
            await asyncio.sleep(0.0001)  # just to generate 3 interruptions for the async task

        self.assertEqual(2, read_current_pids.call_count)
        get_priority.assert_has_calls([call(os.PRIO_PROCESS, 1), call(os.PRIO_PROCESS, 1)], any_order=True)
        set_priority.assert_has_calls([call(os.PRIO_PROCESS, 1, -1), call(os.PRIO_PROCESS, 2, -2)])

        self.assertFalse(self.renicer.is_watching())

    @patch(f'{__app_name__}.service.optimizer.renicer.os.setpriority')
    @patch(f'{__app_name__}.service.optimizer.renicer.os.getpriority', return_value=-1)
    @patch(f'{__app_name__}.service.optimizer.renicer.system.read_current_pids', side_effect=[{1, 2, 3}, {}])  # on the first iteration all watched processes are alive, on the second none
    async def test_watch__must_not_set_priority_from_watched_processes_when_priorities_equal_expected(self, read_current_pids: Mock, get_priority: Mock, set_priority: Mock):
        self.renicer.add(1, -1, 1)
        self.renicer.add(2, -1, 2)

        self.assertFalse(self.renicer.is_watching())

        self.assertTrue(self.renicer.watch())

        self.assertTrue(self.renicer.is_watching())

        for _ in range(3):
            await asyncio.sleep(0.0001)  # just to generate 3 interruptions for the async task

        self.assertEqual(2, read_current_pids.call_count)
        get_priority.assert_has_calls([call(os.PRIO_PROCESS, 1), call(os.PRIO_PROCESS, 1)], any_order=True)
        set_priority.assert_not_called()

        self.assertFalse(self.renicer.is_watching())

    @patch(f'{__app_name__}.service.optimizer.renicer.os.setpriority')
    @patch(f'{__app_name__}.service.optimizer.renicer.os.getpriority')
    @patch(f'{__app_name__}.service.optimizer.renicer.system.read_current_pids')
    async def test_watch__must_not_create_another_loop_task_when_already_watching(self, read_current_pids: Mock, get_priority: Mock, set_priority: Mock):
        self.renicer.add(1, -1, 1)
        self.renicer._watching = True

        self.assertTrue(self.renicer.is_watching())

        self.assertFalse(self.renicer.watch())

        self.assertTrue(self.renicer.is_watching())

        await asyncio.sleep(0.0001)  # generate an interruption (if the task were created, the mocks would have calls)

        read_current_pids.assert_not_called()
        get_priority.assert_not_called()
        set_priority.assert_not_called()

        self.assertTrue(self.renicer.is_watching())

    @patch(f'{__app_name__}.service.optimizer.renicer.os.setpriority')
    @patch(f'{__app_name__}.service.optimizer.renicer.os.getpriority')
    @patch(f'{__app_name__}.service.optimizer.renicer.system.read_current_pids')
    async def test_watch__must_not_start_watching_when_no_processes_to_watch(self, read_current_pids: Mock, get_priority: Mock, set_priority: Mock):
        self.assertFalse(self.renicer.is_watching())

        self.assertFalse(self.renicer.watch())

        self.assertFalse(self.renicer.is_watching())

        await asyncio.sleep(0.0001)  # generate an interruption (if the task were created, the mocks would have calls)

        read_current_pids.assert_not_called()
        get_priority.assert_not_called()
        set_priority.assert_not_called()

        self.assertFalse(self.renicer.is_watching())
