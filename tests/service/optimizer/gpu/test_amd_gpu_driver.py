import os
import re
import shutil
import sys
import traceback
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, patch, AsyncMock

from guapow.service.optimizer.gpu import AMDGPUDriver
from tests import RESOURCES_DIR

TEST_GPU_FOLDER = RESOURCES_DIR + '/amd/gpu/card{id}'
TEMP_GPU_FOLDER = TEST_GPU_FOLDER.format(id=5)


class AMDGPUDriverTest(IsolatedAsyncioTestCase):

    def tearDown(self):
        if os.path.exists(TEMP_GPU_FOLDER):
            try:
                shutil.rmtree(TEMP_GPU_FOLDER)
            except:
                sys.stderr.write(f"Could not remove temp AMD gpu folder '{TEMP_GPU_FOLDER}'")
                traceback.print_exc()

    def test_get_vendor_name__must_return_AMD(self):
        self.assertEqual('AMD', AMDGPUDriver.get_vendor_name())

    async def test_can_work__always_true(self):
        driver = AMDGPUDriver(cache=False, only_connected=False, logger=Mock(), gpus_path=TEST_GPU_FOLDER)
        res, msg = driver.can_work()
        self.assertTrue(res)
        self.assertIsNone(msg)

    def test_get_default_mode__must_return_auto_and_3(self):
        driver = AMDGPUDriver(cache=False, only_connected=False,  logger=Mock(), gpus_path=TEST_GPU_FOLDER)
        self.assertEqual('auto:3', driver.get_default_mode())

    def test_get_performance_mode__must_return_manual_and_5(self):
        driver = AMDGPUDriver(cache=False, only_connected=False, logger=Mock(), gpus_path=TEST_GPU_FOLDER)
        self.assertEqual('manual:5', driver.get_performance_mode())

    async def test_get_gpus__empty_when_there_are_no_files(self):
        driver = AMDGPUDriver(cache=False, only_connected=False, logger=Mock(), gpus_path=RESOURCES_DIR)
        returned = await driver.get_gpus()
        self.assertIsNone(returned)

    async def test_get_gpus__return_available_gpus_when_required_files_exist(self):
        driver = AMDGPUDriver(cache=False, only_connected=False, logger=Mock(), gpus_path=TEST_GPU_FOLDER)
        returned = await driver.get_gpus()
        self.assertIsNotNone(returned)

        self.assertEqual({'1', '2', '3', '4'}, returned)

    async def test_get_gpus__return_only_connected_gpus_when_required_files_exist(self):
        driver = AMDGPUDriver(cache=False, only_connected=True, logger=Mock(), gpus_path=TEST_GPU_FOLDER)
        returned = await driver.get_gpus()
        self.assertIsNotNone(returned)

        self.assertEqual({'1', '4'}, returned)

    @patch("guapow.service.optimizer.gpu.AMDGPUDriver.get_connected_gpus", return_value=set())
    async def test_get_gpus__return_none_if_no_available_gpu_connected_even_if_required_files_exist(self, *mocks: Mock):
        driver = AMDGPUDriver(cache=False, only_connected=True, logger=Mock(), gpus_path=TEST_GPU_FOLDER)
        returned = await driver.get_gpus()

        get_connected_gpus: AsyncMock = mocks[0]
        get_connected_gpus.assert_awaited_once()

        self.assertIsNone(returned)

    async def test_get_power_mode__return_a_string_concatenating_the_performance_and_profile_ids(self):
        driver = AMDGPUDriver(cache=False, only_connected=False, logger=Mock(), gpus_path=TEST_GPU_FOLDER)

        gpu_ids = {str(n) for n in range(1, 5)}
        actual_modes = await driver.get_power_mode(gpu_ids)

        expected = {
            '1': 'manual:3',
            '2': 'manual:5',
            '3': 'auto:5',
            '4': 'auto:0'
        }
        self.assertEqual(expected, actual_modes)

    async def test_set_power_mode__write_the_expected_content_within_the_parsed_mode_string(self):
        example_folder = TEST_GPU_FOLDER.format(id=1)
        try:
            shutil.copytree(example_folder, TEMP_GPU_FOLDER)
        except:
            self.fail(f"Could not copy example folder '{example_folder}'")

        driver = AMDGPUDriver(cache=False, only_connected=False, logger=Mock(), gpus_path=TEST_GPU_FOLDER)
        card_id = re.compile(r'/card(\d+)$').findall(TEMP_GPU_FOLDER)[0]

        res = await driver.set_power_mode({card_id: driver.get_performance_mode()})
        self.assertEqual({card_id: True}, res)

        with open(f'{TEMP_GPU_FOLDER}/device/{AMDGPUDriver.PERFORMANCE_FILE}') as f:
            control_mode = f.read()

        self.assertEqual('manual', control_mode)

        with open(f'{TEMP_GPU_FOLDER}/device/{AMDGPUDriver.PROFILE_FILE}') as f:
            power_mode = f.read()

        self.assertEqual('5', power_mode)
