import os
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock

from guapow.common.config import OptimizerConfigReader, HTTP_SERVER_PORT, OptimizerConfig
from guapow.common.model_util import FileModelFiller
from tests import RESOURCES_DIR


class OptimizerConfigReaderTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.reader = OptimizerConfigReader(FileModelFiller(Mock()), Mock())

    @classmethod
    def tearDownClass(cls) -> None:
        if HTTP_SERVER_PORT in os.environ:
            del os.environ[HTTP_SERVER_PORT]

    async def test_read_valid__return_valid_instance_when_no_existent_property_is_defined(self):
        file_path = f'{RESOURCES_DIR}/opt_no_property.conf'
        config = await self.reader.read_valid(file_path=file_path)
        self.assertIsNotNone(config)
        self.assertEqual(OptimizerConfig.DEFAULT_PORT, config.port)
        self.assertFalse(config.gpu_cache)
        self.assertEqual(3, config.check_finished_interval)
        self.assertFalse(config.allow_root_scripts)
        self.assertEqual(15, config.launcher_mapping_timeout)
        self.assertIsNotNone(config.request)
        self.assertTrue(config.request.encrypted)
        self.assertIsNone(config.request.allowed_users)

    async def test_read_valid__return_valid_instance_when_file_does_not_exist(self):
        file_path = f'{RESOURCES_DIR}/123opt.conf'
        config = await self.reader.read_valid(file_path=file_path)
        self.assertIsNotNone(config)
        self.assertEqual(OptimizerConfig.DEFAULT_PORT, config.port)

    async def test_read_valid__return_valid_port_defined_through_env_var(self):
        file_path = f'{RESOURCES_DIR}/123opt.conf'
        os.environ[HTTP_SERVER_PORT] = '123'
        config = await self.reader.read_valid(file_path=file_path)
        self.assertIsNotNone(config)
        self.assertEqual(123, config.port)

    async def test_read_valid__return_default_port_when_env_var_is_invalid(self):
        file_path = f'{RESOURCES_DIR}/123opt.conf'
        os.environ[HTTP_SERVER_PORT] = 'abc'
        config = await self.reader.read_valid(file_path=file_path)
        self.assertIsNotNone(config)
        self.assertEqual(OptimizerConfig.DEFAULT_PORT, config.port)

    async def test_read_valid__return_valid_instance_when_invalid_properties_are_defined(self):
        file_path = f'{RESOURCES_DIR}/opt_invalid_properties.conf'
        config = await self.reader.read_valid(file_path=file_path)
        self.assertIsNotNone(config)
        self.assertEqual(OptimizerConfig.DEFAULT_PORT, config.port)

    async def test_read_valid__return_instance_with_a_not_supported_compositor_name(self):
        file_path = f'{RESOURCES_DIR}/opt_compositor.conf'
        config = await self.reader.read_valid(file_path=file_path)
        self.assertIsNotNone(config)
        self.assertEqual('xpto', config.compositor)

    async def test_read_valid__return_instance_with_scripts_allowed_to_run_as_root(self):
        file_path = f'{RESOURCES_DIR}/opt_root_scripts.conf'
        config = await self.reader.read_valid(file_path=file_path)
        self.assertIsNotNone(config)
        self.assertEqual(True, config.allow_root_scripts)

    async def test_read_valid__return_instance_with_not_root_scripts_settings_defined(self):
        file_path = f'{RESOURCES_DIR}/opt_compositor.conf'
        config = await self.reader.read_valid(file_path=file_path)
        self.assertIsNotNone(config)
        self.assertEqual(False, config.allow_root_scripts)

    async def test_read_valid__return_instance_with_valid_check_finished_interval_value(self):
        file_path = f'{RESOURCES_DIR}/opt_check_finished_interval.conf'
        config = await self.reader.read_valid(file_path=file_path)
        self.assertIsNotNone(config)
        self.assertEqual(1, config.check_finished_interval)

    async def test_read_valid__return_instance_with_valid_check_finished_interval_value_for_invalid_definition(self):
        file_path = f'{RESOURCES_DIR}/opt_invalid_check_interval.conf'
        config = await self.reader.read_valid(file_path=file_path)
        self.assertIsNotNone(config)
        self.assertEqual(3, config.check_finished_interval)

    async def test_read_valid__return_instance_with_default_check_finished_interval_value_when_not_defined(self):
        file_path = f'{RESOURCES_DIR}/opt_compositor.conf'
        config = await self.reader.read_valid(file_path=file_path)
        self.assertIsNotNone(config)
        self.assertEqual(3, config.check_finished_interval)

    async def test_read_valid__return_instance_with_default_real_cmd_check_time_when_not_defined(self):
        file_path = f'{RESOURCES_DIR}/opt_compositor.conf'
        config = await self.reader.read_valid(file_path=file_path)
        self.assertIsNotNone(config)
        self.assertEqual(15, config.launcher_mapping_timeout)

    async def test_read_valid__return_instance_with_valid_launcher_mapping_timeout_defined(self):
        file_path = f'{RESOURCES_DIR}/opt_launcher_timeout.conf'
        config = await self.reader.read_valid(file_path=file_path)
        self.assertIsNotNone(config)
        self.assertEqual(0.5, config.launcher_mapping_timeout)

    async def test_read_valid__return_instance_with_valid_gpu_cache(self):
        file_path = f'{RESOURCES_DIR}/opt_gpu_cache.conf'
        config = await self.reader.read_valid(file_path=file_path)
        self.assertIsNotNone(config)
        self.assertTrue(config.gpu_cache)

    async def test_read_valid__return_instance_with_valid_cpu_performance(self):
        file_path = f'{RESOURCES_DIR}/opt_cpu.conf'
        config = await self.reader.read_valid(file_path=file_path)
        self.assertIsNotNone(config)
        self.assertTrue(config.cpu_performance)

    async def test_read_valid__return_instance_with_valid_encryption_settings(self):
        file_path = f'{RESOURCES_DIR}/opt_encrypted.conf'
        config = await self.reader.read_valid(file_path=file_path)
        self.assertIsNotNone(config)
        self.assertIsNotNone(config.request)
        self.assertEqual(False, config.request.encrypted)

    async def test_read_valid__return_instance_with_valid_allowed_users_defined(self):
        file_path = f'{RESOURCES_DIR}/opt_allowed_users.conf'
        config = await self.reader.read_valid(file_path=file_path)
        self.assertIsNotNone(config)
        self.assertIsNotNone(config.request)
        self.assertEqual({'abc', 'def', 'xpto'}, config.request.allowed_users)

    async def test_read_valid__return_instance_with_valid_profile_cache_settings(self):
        file_path = f'{RESOURCES_DIR}/opt_profile_cache.conf'
        config = await self.reader.read_valid(file_path=file_path)
        self.assertIsNotNone(config)
        self.assertEqual(False, config.profile_cache)

    async def test_read_valid__return_instance_with_valid_profile_pre_caching_settings(self):
        file_path = f'{RESOURCES_DIR}/profile_pre_cache.conf'
        config = await self.reader.read_valid(file_path=file_path)
        self.assertIsNotNone(config)
        self.assertTrue(config.profile_cache)
        self.assertTrue(config.pre_cache_profiles)

    async def test_read_valid__return_instance_with_valid_renicer_interval(self):
        file_path = f'{RESOURCES_DIR}/opt_renicer.conf'
        config = await self.reader.read_valid(file_path=file_path)
        self.assertIsNotNone(config)
        self.assertTrue(config.is_valid())
        self.assertEqual(0.5, config.renicer_interval)

    async def test_read_valid__return_instance_with_valid_renicer_interval_for_invalid_definition(self):
        file_path = f'{RESOURCES_DIR}/opt_renicer_invalid.conf'  # defines '0'
        config = await self.reader.read_valid(file_path=file_path)
        self.assertIsNotNone(config)
        self.assertTrue(config.is_valid())
        self.assertEqual(5, config.renicer_interval)  # default value is 5
