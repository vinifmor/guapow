import os
import time
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, patch, PropertyMock, AsyncMock

from guapow import __app_name__
from guapow.common.dto import OptimizationRequest
from guapow.service.optimizer.profile import OptimizationProfile, ProcessSettings, CPUSchedulingPolicy, \
    IOSchedulingClass, \
    ProcessNiceSettings
from guapow.service.optimizer.task.model import OptimizationContext, OptimizedProcess
from guapow.service.optimizer.task.process import ReniceProcess, ChangeCPUScalingPolicy, ChangeProcessIOClass, \
    ChangeCPUAffinity


def new_process_profile() -> OptimizationProfile:
    profile = OptimizationProfile.empty('test')
    profile.process = ProcessSettings(None)
    profile.process.nice = None
    profile.process.affinity = None
    profile.process.scheduling.policy = None
    profile.process.scheduling.priority = None
    return profile


class ReniceProcessTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.context = OptimizationContext.empty()
        self.context.logger = Mock()

        self.task = ReniceProcess(self.context)
        self.task._renicer = Mock()
        self.request = OptimizationRequest(pid=123, command='abc', profile='user', user_name='user')
        self.profile = new_process_profile()
        self.profile.process.nice = ProcessNiceSettings(None, None, None)
        self.process = OptimizedProcess(request=PropertyMock(related_pids=None), profile=self.profile, created_at=1)

    async def test_is_available__always_true(self):
        res = await self.task.is_available()
        self.assertTrue(res[0])
        self.assertIsNone(res[1])

    async def test_should_run__false_when_nice_settings_are_not_defined(self):
        self.profile.process.nice = None
        self.assertFalse(await self.task.should_run(self.process))

    async def test_should_run__false_when_nice_level_is_higher_than_19(self):
        self.profile.process.nice.level = 20
        self.assertFalse(await self.task.should_run(self.process))

    async def test_should_run__true_when_nice_level_is_equal_to_19(self):
        self.profile.process.nice.level = 19
        self.assertTrue(await self.task.should_run(self.process))

    async def test_should_run__false_when_nice_level_is_less_than_minus_20(self):
        self.profile.process.nice.level = -21
        self.assertFalse(await self.task.should_run(self.process))

    async def test_should_run__true_when_nice_level_is_equal_to_minus_20(self):
        self.profile.process.nice.level = -20
        self.assertTrue(await self.task.should_run(self.process))

    async def test_should_run__true_when_nice_level_is_equal_to_zero(self):
        self.profile.process.nice.level = 0
        self.assertTrue(await self.task.should_run(self.process))

    async def test_run__must_set_priority_and_not_watch_the_process_nice_level_when_watch_is_false(self):
        self.profile.process.nice.level = -1
        self.profile.process.nice.watch = False

        await self.task.run(OptimizedProcess(request=self.request, created_at=time.time(), profile=self.profile))

        self.task._renicer.set_priority.assert_called_once_with(self.request.pid, self.profile.process.nice.level, self.request.pid)
        self.task._renicer.add.assert_not_called()
        self.task._renicer.watch.assert_not_called()

    async def test_run__must_set_priority_and_call_watch_when_not_watched_yet(self):
        self.task._renicer.add = Mock(return_value=True)

        self.profile.process.nice.level = -1
        self.profile.process.nice.watch = True

        await self.task.run(OptimizedProcess(request=self.request, created_at=time.time(), profile=self.profile))

        self.task._renicer.set_priority.assert_called_once_with(self.request.pid, self.profile.process.nice.level, self.request.pid)
        self.task._renicer.add.assert_called_once_with(self.request.pid, self.profile.process.nice.level, self.request.pid)
        self.task._renicer.watch.assert_called_once()

    async def test_run__must_set_priority_and_do_nothing_when_process_already_being_watched(self):
        self.task._renicer.add = Mock(return_value=False)
        self.profile.process.nice.level = -1
        self.profile.process.nice.watch = True

        await self.task.run(OptimizedProcess(request=self.request, created_at=time.time(), profile=self.profile))

        self.task._renicer.set_priority.assert_called_once_with(self.request.pid, self.profile.process.nice.level, self.request.pid)
        self.task._renicer.add.assert_called_once_with(self.request.pid, self.profile.process.nice.level, self.request.pid)
        self.task._renicer.watch.assert_not_called()

    @patch('asyncio.sleep')
    async def test_run__must_delay_renice_call_when_delay_is_higher_than_zero(self, sleep: AsyncMock):
        self.profile.process.nice.level = -1
        self.profile.process.nice.delay = 0.1
        self.profile.process.nice.watch = False  # to avoid watch call assertions

        await self.task.run(OptimizedProcess(request=self.request, created_at=time.time(), profile=self.profile))

        sleep.assert_awaited_once()
        self.task._renicer.set_priority.assert_called_once_with(self.request.pid, self.profile.process.nice.level, self.request.pid)

    @patch('asyncio.sleep')
    async def test_run__must_not_delay_renice_call_when_delay_is_less_than_zero(self, sleep: Mock):
        self.profile.process.nice.level = -1
        self.profile.process.nice.delay = -1
        self.profile.process.nice.watch = False  # to avoid watch call assertions

        await self.task.run(OptimizedProcess(request=self.request, created_at=time.time(), profile=self.profile))

        sleep.assert_not_called()
        self.task._renicer.set_priority.assert_called_once_with(self.request.pid, self.profile.process.nice.level, self.request.pid)

    @patch('asyncio.sleep')
    async def test_run__must_not_delay_renice_call_when_delay_is_zero(self, sleep: Mock):
        self.profile.process.nice.level = -1
        self.profile.process.nice.delay = 0
        self.profile.process.nice.watch = False  # to avoid watch call assertions

        await self.task.run(OptimizedProcess(request=self.request, created_at=time.time(), profile=self.profile))

        sleep.assert_not_called()
        self.task._renicer.set_priority.assert_called_once_with(self.request.pid, self.profile.process.nice.level, self.request.pid)


class ChangeCPUAffinityTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.context = OptimizationContext.empty()
        self.context.cpu_count = 2
        self.context.logger = Mock()

        self.request = OptimizationRequest(pid=123, command='abc', profile='user', user_name='user')
        self.profile = new_process_profile()
        self.process = OptimizedProcess(self.request, 37912738921, self.profile)

    async def test_is_available__false_when_cpu_count_is_zero(self):
        self.context.cpu_count = 0

        task = ChangeCPUAffinity(self.context)
        available, error_msg = await task.is_available()
        self.assertFalse(available)
        self.assertIsNotNone(error_msg)

    async def test_is_available__true_when_cpu_count_higher_than_zero(self):
        self.context.cpu_count = 1
        task = ChangeCPUAffinity(self.context)
        available, error_msg = await task.is_available()
        self.assertTrue(available)
        self.assertIsNone(error_msg)

    async def test_should_run__true_when_a_valid_affinity_is_defined(self):
        task = ChangeCPUAffinity(self.context)
        self.profile.process.cpu_affinity = [0]

        self.assertTrue(await task.should_run(self.process))

    async def test_should_run__false_when_affinity_is_not_defined(self):
        task = ChangeCPUAffinity(self.context)
        self.profile.process.cpu_affinity = []

        self.assertFalse(await task.should_run(self.process))

    async def test_should_run__false_when_affinity_is_invalid(self):
        task = ChangeCPUAffinity(self.context)
        self.profile.process.cpu_affinity = [0, 4]  # cpu count is 1, so there is no '4'

        self.assertFalse(await task.should_run(self.process))

    @patch(f'{__app_name__}.service.optimizer.task.process.os.sched_setaffinity')
    async def test_run__must_call_sched_setaffinity(self, setaffinity: Mock):
        self.context.cpu_count = 3
        task = ChangeCPUAffinity(self.context)
        self.profile.process.cpu_affinity = [1, 0]

        await task.run(self.process)
        setaffinity.assert_called_once_with(self.request.pid, [1, 0])

    @patch(f'{__app_name__}.service.optimizer.task.process.os.sched_setaffinity', side_effect=OSError)
    async def test_run__must_do_nothing_when_sched_setaffinity_raises_exception(self, setaffinity: Mock):
        self.context.cpu_count = 3
        task = ChangeCPUAffinity(self.context)
        self.profile.process.cpu_affinity = [1, 0]

        await task.run(self.process)
        setaffinity.assert_called_once_with(self.request.pid, [1, 0])


class ChangeCPUScalingPolicyTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.context = OptimizationContext.empty()
        self.context.logger = Mock()

        self.task = ChangeCPUScalingPolicy(self.context)
        self.request = OptimizationRequest(pid=123, command='abc', profile='user', user_name='user')
        self.profile = new_process_profile()
        self.process = OptimizedProcess(self.request, 627361321, self.profile)

    async def test_is_available__always_true(self):
        res = await self.task.is_available()
        self.assertTrue(res[0])
        self.assertIsNone(res[1])

    async def test_should_run__true_when_policy_is_defined_and_not_require_priority_and_not_root_user(self):
        self.profile.process.scheduling.policy = CPUSchedulingPolicy.OTHER
        self.assertTrue(await self.task.should_run(self.process))

    async def test_should_run__false_when_policy_is_not_defined(self):
        self.profile.process.scheduling.policy = None
        self.assertFalse(await self.task.should_run(self.process))

    @patch(f'{__app_name__}.service.optimizer.task.process.is_root_user', return_value=False)
    async def test_should_run__false_when_policy_requires_root_user_and_user_is_not_root(self, is_root_user: Mock):
        self.profile.process.scheduling.policy = CPUSchedulingPolicy.FIFO
        self.assertFalse(await self.task.should_run(self.process))
        is_root_user.assert_called_once()

    @patch(f'{__app_name__}.service.optimizer.task.process.is_root_user', return_value=True)
    async def test_should_run__false_when_policy_requires_priority_and_it_is_invalid(self, is_root_user: Mock):
        self.profile.process.scheduling.policy = CPUSchedulingPolicy.FIFO
        self.profile.process.scheduling.priority = 500
        self.assertFalse(await self.task.should_run(self.process))
        is_root_user.assert_called_once()

    @patch(f'{__app_name__}.service.optimizer.task.process.is_root_user', return_value=True)
    async def test_should_run__true_when_policy_requires_priority_and_it_is_not_defined(self, is_root_user: Mock):
        self.profile.process.scheduling.policy = CPUSchedulingPolicy.FIFO
        self.profile.process.scheduling.priority = None
        self.assertTrue(await self.task.should_run(self.process))
        is_root_user.assert_called_once()

    @patch(f'{__app_name__}.service.optimizer.task.process.is_root_user', return_value=True)
    async def test_should_run__true_when_policy_requires_priority_and_a_valid_is_defined(self, is_root_user: Mock):
        self.profile.process.scheduling.policy = CPUSchedulingPolicy.FIFO
        self.profile.process.scheduling.priority = 2
        self.assertTrue(await self.task.should_run(self.process))
        is_root_user.assert_called_once()

    async def test_should_run__true_when_policy_not_require_priority_and_invalid_is_defined(self):
        self.profile.process.scheduling.policy = CPUSchedulingPolicy.OTHER
        self.profile.process.scheduling.priority = 500
        self.assertTrue(await self.task.should_run(self.process))

    @patch(f'{__app_name__}.service.optimizer.task.process.os.sched_setscheduler')
    async def test_run__call_sched_setscheduler_when_policy_not_supports_priority_but_specified(self, setscheduler: Mock):
        self.profile.process.scheduling.policy = CPUSchedulingPolicy.BATCH
        self.profile.process.scheduling.priority = 5

        await self.task.run(self.process)
        setscheduler.assert_called_once_with(self.request.pid, CPUSchedulingPolicy.BATCH.value(), os.sched_param(0))

    @patch(f'{__app_name__}.service.optimizer.task.process.os.sched_setscheduler')
    async def test_run__call_sched_setscheduler_when_policy_requires_priority_but_not_defined(self, setscheduler: Mock):
        self.profile.process.scheduling.policy = CPUSchedulingPolicy.FIFO
        self.profile.process.scheduling.priority = None

        await self.task.run(self.process)
        setscheduler.assert_called_once_with(self.request.pid, CPUSchedulingPolicy.FIFO.value(), os.sched_param(1))

    @patch(f'{__app_name__}.service.optimizer.task.process.os.sched_setscheduler')
    async def test_run__call_schedtool_when_policy_requires_priority_and_defined_valid(self, setscheduler: Mock):
        self.profile.process.scheduling.policy = CPUSchedulingPolicy.FIFO
        self.profile.process.scheduling.priority = 5

        await self.task.run(self.process)
        setscheduler.assert_called_once_with(self.request.pid, CPUSchedulingPolicy.FIFO.value(), os.sched_param(5))

    @patch(f'{__app_name__}.service.optimizer.task.process.os.sched_setscheduler', side_effect=OSError)
    async def test_run__must_do_nothing_when_setscheduler_raises_exception(self, setscheduler: Mock):
        self.profile.process.scheduling.policy = CPUSchedulingPolicy.BATCH
        self.profile.process.scheduling.priority = 5

        await self.task.run(self.process)
        setscheduler.assert_called_once_with(self.request.pid, CPUSchedulingPolicy.BATCH.value(), os.sched_param(0))


class ChangeProcessIOClassTest(IsolatedAsyncioTestCase):

    def setUp(self):
        context = OptimizationContext.empty()
        context.logger = Mock()

        self.task = ChangeProcessIOClass(context)
        self.request = OptimizationRequest(pid=123, command='abc', profile='user', user_name='user')
        self.profile = new_process_profile()
        self.process = OptimizedProcess(request=PropertyMock(related_pids=None), profile=self.profile, created_at=1)

    async def test_should_run__true_when_ioclass_supports_priority_and_a_valid_is_defined(self):
        self.profile.process.io.ioclass = IOSchedulingClass.BEST_EFFORT
        self.profile.process.io.nice_level = 0
        self.assertTrue(await self.task.should_run(self.process))

    async def test_should_run__true_when_ioclass_supports_priority_and_but_not_defined(self):
        self.profile.process.io.ioclass = IOSchedulingClass.BEST_EFFORT
        self.profile.process.io.nice_level = None
        self.assertTrue(await self.task.should_run(self.process))

    async def test_should_run__false_when_ioclass_supports_priority_an_invalid_is_defined(self):
        self.profile.process.io.ioclass = IOSchedulingClass.REALTIME
        self.profile.process.io.nice_level = 99
        self.assertFalse(await self.task.should_run(self.process))

    async def test_should_run__false_when_ioclass_is_not_defined(self):
        self.profile.process.io.ioclass = None
        self.assertFalse(await self.task.should_run(self.process))

    async def test_should_run__true_when_ioclass_not_supports_priority_and_one_is_defined(self):
        self.profile.process.io.ioclass = IOSchedulingClass.IDLE
        self.profile.process.io.nice_level = 99
        self.assertTrue(await self.task.should_run(self.process))

    @patch(f'{__app_name__}.service.optimizer.task.process.async_syscall', return_value=(0, None))
    async def test_run__must_call_ionice_with_the_given_nice_level_when_class_supports_it(self, async_syscall: Mock):
        self.profile.process.io.ioclass = IOSchedulingClass.BEST_EFFORT
        self.profile.process.io.nice_level = 1

        proc = OptimizedProcess(request=self.request, profile=self.profile, created_at=time.time())
        await self.task.run(proc)
        async_syscall.assert_called_once_with(f'ionice -p {proc.pid} -c 2 -n 1')

    @patch(f'{__app_name__}.service.optimizer.task.process.async_syscall', return_value=(0, None))
    async def test_run__must_call_ionice_with_nice_level_zero_when_class_supports_it_but_no_value_was_defined(self, async_syscall: Mock):
        self.profile.process.io.ioclass = IOSchedulingClass.BEST_EFFORT
        self.profile.process.io.nice_level = None

        proc = OptimizedProcess(request=self.request, profile=self.profile, created_at=time.time())
        await self.task.run(proc)
        async_syscall.assert_called_once_with(f'ionice -p {proc.pid} -c 2 -n 0')

    @patch(f'{__app_name__}.service.optimizer.task.process.async_syscall', return_value=(0, None))
    async def test_run__must_call_ionice_without_the_given_nice_level_when_class_not_support(self, async_syscall: Mock):
        self.profile.process.io.ioclass = IOSchedulingClass.IDLE
        self.profile.process.io.nice_level = 99

        proc = OptimizedProcess(request=self.request, profile=self.profile, created_at=time.time())
        await self.task.run(proc)
        async_syscall.assert_called_once_with(f'ionice -p {proc.pid} -c 3')

    @patch(f'{__app_name__}.service.optimizer.task.process.async_syscall', return_value=(0, None))
    async def test_run__must_call_ionice_without_the_given_nice_level_when_class_not_support_and_no_value_was_defined(self, async_syscall: Mock):
        self.profile.process.io.ioclass = IOSchedulingClass.IDLE
        self.profile.process.io.nice_level = None

        proc = OptimizedProcess(request=self.request, profile=self.profile, created_at=time.time())
        await self.task.run(proc)
        async_syscall.assert_called_once_with(f'ionice -p {proc.pid} -c 3')
