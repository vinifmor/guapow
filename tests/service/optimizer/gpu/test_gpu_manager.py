import asyncio
from asyncio import Lock
from typing import List, Tuple, Set
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, AsyncMock, call, MagicMock

from guapow.service.optimizer.gpu import GPUManager, GPUPowerMode, NvidiaGPUDriver, AMDGPUDriver, GPUState, GPUDriver


class GPUManagerTest(IsolatedAsyncioTestCase):

    async def test_map_working_drivers_and_gpus__no_instance_yield_when_no_driver_has_available_gpus(self):
        driver_1 = MagicMock()
        driver_1.can_work.return_value = True, None
        driver_1.get_cached_gpus = AsyncMock(return_value=set())

        driver_2 = MagicMock()
        driver_2.can_work.return_value = True, None
        driver_2.get_cached_gpus = AsyncMock(return_value=set())

        instances = [(driver, gpus) async for driver, gpus in GPUManager(Mock(), drivers=[driver_1, driver_2]).map_working_drivers_and_gpus()]
        self.assertEqual([], instances)

        driver_1.can_work.assert_called_once()
        driver_1.get_cached_gpus.assert_called_once()
        driver_2.can_work.assert_called_once()
        driver_2.get_cached_gpus.assert_called_once()

    async def test_map_working_drivers_and_gpus__no_instance_yield_when_drivers_cannot_work(self):
        driver_1 = MagicMock()
        driver_1.can_work.return_value = False, ''
        driver_1.get_cached_gpus = AsyncMock(return_value=set())

        driver_2 = MagicMock()
        driver_2.can_work.return_value = False, ''
        driver_2.get_cached_gpus = AsyncMock(return_value=set())

        instances = [(driver, gpus) async for driver, gpus in GPUManager(Mock(), drivers=[driver_1, driver_2]).map_working_drivers_and_gpus()]
        self.assertEqual([], instances)

        driver_1.can_work.assert_called_once()
        driver_1.get_cached_gpus.assert_not_called()
        driver_2.can_work.assert_called_once()
        driver_2.get_cached_gpus.assert_not_called()

    async def test_map_working_drivers_and_gpus__return_working_drivers_with_available_gpus(self):
        driver_1 = Mock()
        driver_1.can_work.return_value = True, None
        driver_1.get_cached_gpus = AsyncMock(return_value={'1'})

        driver_2 = Mock()
        driver_2.can_work.return_value = True, None
        driver_2.get_cached_gpus = AsyncMock(return_value={'a'})

        instances = [(driver, gpus) async for driver, gpus in GPUManager(Mock(), drivers=[driver_1, driver_2]).map_working_drivers_and_gpus()]
        self.assertIn((driver_1, {'1'}), instances)
        self.assertIn((driver_2, {'a'}), instances)
        self.assertEqual(2, len(instances))

        driver_1.can_work.assert_called_once()
        driver_1.get_cached_gpus.assert_called_once()
        driver_2.can_work.assert_called_once()
        driver_2.get_cached_gpus.assert_called_once()

    async def test_map_working_drivers_and_gpus__must_lock_concurrent_requests_when_cache_is_on(self):
        driver_1 = AMDGPUDriver(cache=True, logger=Mock())
        driver_1.can_work = Mock(return_value=(True, None))
        driver_1.get_gpus = AsyncMock(return_value={'0'})

        man = GPUManager(Mock(), drivers=[driver_1], cache_gpus=True)
        self.assertIsNone(man.get_cached_working_drivers())

        async def mock_map_working_drivers() -> List[Tuple[GPUDriver, Set[str]]]:
            return [(gpu, driver) async for gpu, driver in man.map_working_drivers_and_gpus()]

        tasks = [mock_map_working_drivers(), mock_map_working_drivers()]
        tasks_res = await asyncio.gather(*tasks)

        for res in tasks_res:
            self.assertEqual([(driver_1, {'0'})], res)

        self.assertEqual([driver_1], man.get_cached_working_drivers())
        driver_1.can_work.assert_called_once()  # only one call when cache is on  (even for concurrent requests)
        driver_1.get_gpus.assert_called_once()  # only one call when cache is on (even for concurrent requests)

    async def test_activate_performance__set_all_drivers_gpus_to_performance_when_not_in_performance_first_exec(self):
        driver_1 = Mock()
        driver_1.__class__ = GPUDriver
        driver_1.lock.return_value = Lock()
        driver_1.can_work.return_value = True, None
        driver_1.get_cached_gpus = AsyncMock(return_value={'0'})
        driver_1.get_power_mode = AsyncMock(return_value={'0': GPUPowerMode.ON_DEMAND})
        driver_1.set_power_mode = AsyncMock(return_value={'0': True})

        driver_2 = Mock()
        driver_2.__class__ = AMDGPUDriver
        driver_2.lock.return_value = Lock()
        driver_2.can_work.return_value = True, None
        driver_2.get_cached_gpus = AsyncMock(return_value={'1'})
        driver_2.get_power_mode = AsyncMock(return_value={'1': GPUPowerMode.AUTO})
        driver_2.set_power_mode = AsyncMock(return_value={'1': True})

        gpu_man = GPUManager(logger=Mock(), drivers=[driver_1, driver_2])
        actual_changes = await gpu_man.activate_performance()

        driver_1.lock.assert_called_once()
        driver_1.get_cached_gpus.assert_called_once()
        driver_1.can_work.assert_called_once()
        driver_1.get_power_mode.assert_called_once_with({'0'}, None)
        driver_1.set_power_mode.assert_called_once_with({'0': GPUPowerMode.PERFORMANCE}, None)

        driver_2.lock.assert_called_once()
        driver_2.get_cached_gpus.assert_called_once()
        driver_2.can_work.assert_called_once()
        driver_2.get_power_mode.assert_called_once_with({'1'}, None)
        driver_2.set_power_mode.assert_called_once_with({'1': GPUPowerMode.PERFORMANCE}, None)

        self.assertIsNotNone(actual_changes)

        expected_changes = {GPUDriver: {GPUState('0', GPUDriver, GPUPowerMode.ON_DEMAND)},
                            AMDGPUDriver: {GPUState('1', AMDGPUDriver, GPUPowerMode.AUTO)}}

        self.assertEqual(expected_changes, actual_changes)

        expected_state_cache = {GPUDriver: {'0': GPUPowerMode.ON_DEMAND},
                                AMDGPUDriver: {'1': GPUPowerMode.AUTO}}

        self.assertEqual(expected_state_cache, gpu_man.get_gpu_state_cache_view())

    async def test_activate_performance__should_only_activate_gpu_performance_for_concurrent_calls(self):
        driver_lock = Lock()

        driver = Mock()
        driver.__class__ = GPUDriver
        driver.lock.return_value = driver_lock
        driver.can_work.return_value = True, None
        driver.get_cached_gpus = AsyncMock(return_value={'0'})
        driver.get_power_mode = AsyncMock(side_effect=[{'0': GPUPowerMode.ON_DEMAND}, {'0': GPUPowerMode.PERFORMANCE}])
        driver.set_power_mode = AsyncMock(return_value={'0': True})

        gpu_man = GPUManager(Mock(), [driver], cache_gpus=False)

        changes = await asyncio.gather(gpu_man.activate_performance(), gpu_man.activate_performance())

        for change in changes:
            self.assertEqual({GPUDriver: {GPUState('0', GPUDriver, GPUPowerMode.PERFORMANCE)}}, change)

        self.assertEqual(2, driver.can_work.call_count)
        self.assertEqual(2, driver.get_cached_gpus.call_count)
        self.assertEqual(2, driver.lock.call_count)
        driver.get_power_mode.assert_has_calls([call({'0'}, None), call({'0'}, None)])

        driver.set_power_mode.assert_called_once_with({'0': GPUPowerMode.PERFORMANCE}, None)

        expected_state_cache = {GPUDriver: {'0': GPUPowerMode.ON_DEMAND}}
        self.assertEqual(expected_state_cache, gpu_man.get_gpu_state_cache_view())

    async def test_activate_performance__should_not_set_gpu_to_performance_when_previously_set(self):
        driver_1 = Mock()
        driver_1.__class__ = GPUDriver
        driver_1.lock.return_value = Lock()
        driver_1.can_work.return_value = True, None
        driver_1.get_cached_gpus = AsyncMock(return_value={'0'})
        driver_1.get_power_mode = AsyncMock(return_value={'0': GPUPowerMode.PERFORMANCE})
        driver_1.set_power_mode = AsyncMock(return_value={'0', True})

        initial_state_cache = {GPUDriver: {'0': GPUPowerMode.ON_DEMAND}}
        gpu_man = GPUManager(logger=Mock(), drivers=[driver_1])
        gpu_man._gpu_state_cache = initial_state_cache

        actual_changes = await gpu_man.activate_performance()
        self.assertIsNotNone(actual_changes)

        expected_changes = {GPUDriver: {GPUState('0', GPUDriver, GPUPowerMode.ON_DEMAND)}}

        self.assertEqual(expected_changes, actual_changes)

        driver_1.can_work.assert_called_once()
        driver_1.get_cached_gpus.assert_called_once()
        driver_1.lock.assert_called_once()
        driver_1.get_power_mode.assert_called_once_with({'0'}, None)
        driver_1.set_power_mode.assert_not_called()
        self.assertEqual(initial_state_cache, gpu_man.get_gpu_state_cache_view())

    async def test_activate_performance__should_activate_gpu_performance_when_not_in_performance_anymore(self):
        driver_1 = Mock()
        driver_1.__class__ = GPUDriver
        driver_1.lock.return_value = Lock()
        driver_1.can_work.return_value = True, None
        driver_1.get_cached_gpus = AsyncMock(return_value={'0'})
        driver_1.get_power_mode = AsyncMock(return_value={'0': GPUPowerMode.AUTO})
        driver_1.set_power_mode = AsyncMock(return_value={'0': True})

        initial_state_cache = {GPUDriver: {'0': GPUPowerMode.ON_DEMAND}}
        gpu_man = GPUManager(logger=Mock(), drivers=[driver_1])
        gpu_man._gpu_state_cache = initial_state_cache

        actual_changes = await gpu_man.activate_performance()
        self.assertIsNotNone(actual_changes)

        expected_changes = {GPUDriver: {GPUState('0', GPUDriver, GPUPowerMode.AUTO)}}

        self.assertEqual(expected_changes, actual_changes)

        driver_1.can_work.assert_called_once()
        driver_1.get_cached_gpus.assert_called_once()
        driver_1.lock.assert_called_once()

        driver_1.get_power_mode.assert_called_once_with({'0'}, None)
        driver_1.set_power_mode.assert_called_once_with({'0': GPUPowerMode.PERFORMANCE}, None)

        self.assertEqual({GPUDriver: {'0': GPUPowerMode.AUTO}}, gpu_man.get_gpu_state_cache_view())
