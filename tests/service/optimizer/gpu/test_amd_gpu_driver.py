import os
import shutil
import sys
import traceback
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, AsyncMock

from guapow.service.optimizer.gpu import AMDGPUDriver, GPUPowerMode
from tests import RESOURCES_DIR

TEST_GPU_FOLDER = f'{RESOURCES_DIR}/amd/gpu'
TEMP_GPU_FOLDER = f'{TEST_GPU_FOLDER}/4'


class AMDGPUDriverTest(IsolatedAsyncioTestCase):

    def tearDown(self):
        if os.path.exists(TEMP_GPU_FOLDER):
            try:
                shutil.rmtree(TEMP_GPU_FOLDER)
            except:
                sys.stderr.write(f"Could not remove temp AMD gpu folder '{TEMP_GPU_FOLDER}'")
                traceback.print_exc()

    async def get_cached_gpus__must_always_return_the_same_cached_result_when_cache_is_true(self):
        driver = AMDGPUDriver(cache=True, logger=Mock(), gpus_path=RESOURCES_DIR)
        driver.get_gpus = AsyncMock(side_effect=[{'a'}, {'b'}])

        for _ in range(2):
            self.assertEqual({'a'}, await driver.get_cached_gpus())

        driver.get_gpus.assert_called_once()

    async def get_cached_gpus__must_always_return_the_same_cached_result_even_when_none(self):
        driver = AMDGPUDriver(cache=True, logger=Mock(), gpus_path=RESOURCES_DIR)
        driver.get_gpus = AsyncMock(side_effect=[None, {'b'}])

        for _ in range(2):
            self.assertIsNone(await driver.get_cached_gpus())

        driver.get_gpus.assert_called_once()

    async def get_cached_gpus__must_always_call_get_gpus_when_cache_is_false(self):
        driver = AMDGPUDriver(cache=False, logger=Mock(), gpus_path=RESOURCES_DIR)
        driver.get_gpus = AsyncMock(side_effect=[{'a'}, {'b'}])

        self.assertEqual({'a'}, await driver.get_cached_gpus())
        self.assertEqual({'b'}, await driver.get_cached_gpus())

        self.assertEqual(2, driver.get_gpus.call_count)

    async def test_get_gpus__empty_when_there_are_no_files(self):
        driver = AMDGPUDriver(cache=False, logger=Mock(), gpus_path=RESOURCES_DIR)
        returned = await driver.get_gpus()
        self.assertIsNotNone(returned)
        self.assertEqual(set(), returned)

    async def test_get_gpus__return_available_gpus_when_required_files_exist(self):
        driver = AMDGPUDriver(cache=False, logger=Mock(), gpus_path=TEST_GPU_FOLDER)
        returned = await driver.get_gpus()
        self.assertIsNotNone(returned)
        self.assertEqual({'1', '2', '3'}, returned)

    def test_can_work__always_true(self):
        driver = AMDGPUDriver(cache=False, logger=Mock(), gpus_path=TEST_GPU_FOLDER)
        driver._gpus = {'1'}
        res, msg = driver.can_work()
        self.assertTrue(res)
        self.assertIsNone(msg)

    async def test_get_power_mode__return_auto_when_both_files_content_not_meet_expected_words(self):
        driver = AMDGPUDriver(cache=False, logger=Mock(), gpus_path=TEST_GPU_FOLDER)

        actual_modes = await driver.get_power_mode({'1', '3'})
        self.assertEqual({'1': GPUPowerMode.AUTO, '3': GPUPowerMode.AUTO}, actual_modes)

        self.assertIsNotNone(driver._default_performance_level)
        self.assertEqual('', driver._default_performance_level['1'])
        self.assertNotIn('3', driver._default_performance_level)

        self.assertIsNotNone(driver._default_power_profile)
        self.assertEqual('', driver._default_power_profile['1'])
        self.assertEqual('unknown', driver._default_power_profile['3'])

    async def test_get_power_mode__return_performance_when_both_files_content_meet_expected_words(self):
        driver = AMDGPUDriver(cache=False, logger=Mock(), gpus_path=TEST_GPU_FOLDER)
        actual_modes = await driver.get_power_mode({'2'})
        self.assertEqual({'2': GPUPowerMode.PERFORMANCE}, actual_modes)

    async def test_set_power_mode__write_the_expected_performance_related_words_to_both_files(self):
        example_folder = f'{TEST_GPU_FOLDER}/1'
        try:
            shutil.copytree(example_folder, TEMP_GPU_FOLDER)
        except:
            self.fail(f"Could not copy example folder '{example_folder}'")

        driver = AMDGPUDriver(cache=False, logger=Mock(), gpus_path=TEST_GPU_FOLDER)
        res = await driver.set_power_mode({'4': GPUPowerMode.PERFORMANCE})
        self.assertEqual({'4': True}, res)

        with open(f'{TEMP_GPU_FOLDER}/{AMDGPUDriver.PERFORMANCE_FILE}') as f:
            current_performance = f.read()

        self.assertEqual('auto', current_performance)

        with open(f'{TEMP_GPU_FOLDER}/{AMDGPUDriver.PROFILE_FILE}') as f:
            current_profile = f.read()

        self.assertEqual('set', current_profile)

    async def test_set_power_mode__write_cached_strings_when_not_performance(self):
        example_folder = f'{TEST_GPU_FOLDER}/1'
        try:
            shutil.copytree(example_folder, TEMP_GPU_FOLDER)
        except:
            self.fail(f"Could not copy example folder '{example_folder}'")

        driver = AMDGPUDriver(cache=False, logger=Mock(), gpus_path=TEST_GPU_FOLDER)
        driver._default_performance_level = {'4': 'low'}
        driver._default_power_profile = {'4': 'get'}

        res = await driver.set_power_mode({'4': GPUPowerMode.AUTO})
        self.assertEqual({'4': True}, res)

        with open(f'{TEMP_GPU_FOLDER}/{AMDGPUDriver.PERFORMANCE_FILE}') as f:
            current_performance = f.read()

        self.assertEqual(driver._default_performance_level['4'], current_performance)

        with open(f'{TEMP_GPU_FOLDER}/{AMDGPUDriver.PROFILE_FILE}') as f:
            current_profile = f.read()

        self.assertEqual(driver._default_power_profile['4'], current_profile)
