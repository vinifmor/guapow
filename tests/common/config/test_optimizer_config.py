import os
from unittest import TestCase

from guapow.common.config import OptimizerConfig, HTTP_SERVER_PORT, RequestSettings


class RequestSettingsTest(TestCase):

    def test_is_valid__true_when_encrypted_is_true(self):
        instance = RequestSettings.empty()
        instance.encrypted = True
        self.assertTrue(instance.is_valid())

    def test_is_valid__true_when_encrypted_is_false(self):
        instance = RequestSettings.empty()
        instance.encrypted = False
        self.assertTrue(instance.is_valid())

    def test_is_valid__false_when_encrypted_is_none(self):
        instance = RequestSettings.empty()
        instance.encrypted = None
        self.assertFalse(instance.is_valid())

    def test_setup_valid_properties__is_valid_must_return_true(self):
        instance = RequestSettings.empty()
        self.assertFalse(instance.is_valid())

        instance.setup_valid_properties()
        self.assertTrue(instance.is_valid())

    def test_default__must_be_valid(self):
        self.assertTrue(RequestSettings.default().is_valid())


class OptimizerConfigTest(TestCase):

    def setUp(self):
        if HTTP_SERVER_PORT in os.environ:
            del os.environ[HTTP_SERVER_PORT]

    def test_has_valid_port__false_when_port_is_none(self):
        config = OptimizerConfig(None)
        self.assertFalse(config.has_valid_port())

    def test_has_valid_port__false_when_port_is_negative(self):
        config = OptimizerConfig(-1)
        self.assertFalse(config.has_valid_port())

    def test_has_valid_port__true_when_port_is_zero(self):
        config = OptimizerConfig(0)
        self.assertTrue(config.has_valid_port())

    def test_has_valid_port__true_when_port_is_higher_than_zero(self):
        config = OptimizerConfig(65535)
        self.assertTrue(config.has_valid_port())

    def test_has_valid_port__false_when_port_is_higher_than_limit(self):
        config = OptimizerConfig(65536)
        self.assertFalse(config.has_valid_port())

    def test_has_valid_check_finished_interval__true_when_higher_than_zero(self):
        config = OptimizerConfig(check_finished_interval=1)
        self.assertTrue(config.has_valid_check_finished_interval())

    def test_has_valid_check_finished_interval__false_when_zero(self):
        config = OptimizerConfig(check_finished_interval=0)
        self.assertFalse(config.has_valid_check_finished_interval())

    def test_has_valid_check_finished_interval__false_when_negative(self):
        config = OptimizerConfig(check_finished_interval=-1)
        self.assertFalse(config.has_valid_check_finished_interval())

    def test_has_valid_launcher_mapping_timeout__true_when_zero(self):
        config = OptimizerConfig(launcher_mapping_timeout=0)
        self.assertTrue(config.has_valid_launcher_mapping_timeout())

    def test_has_valid_launcher_mapping_timeout__true_when_higher_than_zero(self):
        config = OptimizerConfig(launcher_mapping_timeout=1)
        self.assertTrue(config.has_valid_launcher_mapping_timeout())

    def test_has_valid_launcher_mapping_timeout__false_when_less_than_zero(self):
        config = OptimizerConfig(launcher_mapping_timeout=-1)
        self.assertFalse(config.has_valid_launcher_mapping_timeout())

    def test_has_valid_renicer_interval__false_when_none(self):
        config = OptimizerConfig(renicer_interval=None)
        self.assertFalse(config.has_valid_renicer_interval())

    def test_has_valid_renicer_interval__false_when_zero(self):
        config = OptimizerConfig(renicer_interval=0)
        self.assertFalse(config.has_valid_renicer_interval())

    def test_has_valid_renicer_interval__false_when_negative(self):
        config = OptimizerConfig(renicer_interval=-1)
        self.assertFalse(config.has_valid_renicer_interval())

    def test_has_valid_renicer_interval__true_when_higher_than_zero(self):
        config = OptimizerConfig(renicer_interval=0.001)
        self.assertTrue(config.has_valid_renicer_interval())

    def test_is_valid__true_when_cpu_performance_is_not_none(self):
        config = OptimizerConfig.default()
        config.cpu_performance = False
        self.assertTrue(config.is_valid())

    def test_is_valid__true_when_allowed_users_are_not_defined(self):
        config = OptimizerConfig.empty()
        config.setup_valid_properties()
        config.allowed_users = None
        self.assertTrue(config.is_valid())

    def test_is_valid__true_when_allowed_users_are_empty(self):
        config = OptimizerConfig.empty()
        config.setup_valid_properties()
        config.allowed_users = set()
        self.assertTrue(config.is_valid())

    def test_is_valid__true_when_allowed_users_are_defined(self):
        config = OptimizerConfig.empty()
        config.setup_valid_properties()
        config.allowed_users = {'user'}
        self.assertTrue(config.is_valid())

    def test_is_valid__true_when_profile_cache_is_true(self):
        config = OptimizerConfig.default()
        config.profile_cache = True
        self.assertTrue(config.is_valid())

    def test_is_valid__true_when_profile_cache_is_false(self):
        config = OptimizerConfig.default()
        config.profile_cache = False
        self.assertTrue(config.is_valid())

    def test_is_valid__true_when_profile_cache_is_true_and_pre_caching_is_true(self):
        config = OptimizerConfig.default()
        config.profile_cache = True
        config.pre_cache_profiles = True
        self.assertTrue(config.is_valid())

    def test_is_valid__true_when_profile_cache_is_false_and_pre_caching_is_false(self):
        config = OptimizerConfig.default()
        config.profile_cache = False
        config.pre_cache_profiles = False
        self.assertTrue(config.is_valid())

    def test_is_valid__true_when_request_is_valid(self):
        config = OptimizerConfig.empty()
        config.request = RequestSettings.default()
        self.assertTrue(config.is_valid())

    def test_is_valid__false_when_request_is_none(self):
        config = OptimizerConfig.empty()
        config.request = None
        self.assertFalse(config.is_valid())

    def test_is_valid__true_when_gpu_vendor_is_not_defined(self):
        config = OptimizerConfig.default()
        config.gpu_vendor = None
        self.assertTrue(config.is_valid())

    def test_is_valid__true_when_gpu_vendor_is_defined(self):
        config = OptimizerConfig.default()
        config.gpu_vendor = 'amd'
        self.assertTrue(config.is_valid())

    def test_is_valid__false_when_renicer_interval_is_invalid(self):
        config = OptimizerConfig.empty()
        config.renicer_interval = 0
        self.assertFalse(config.is_valid())

    def test_is_valid__false_when_check_valid_finished_interval_is_invalid(self):
        config = OptimizerConfig.empty()
        config.check_finished_interval = 0
        self.assertFalse(config.is_valid())

    def test_is_valid__false_when_launcher_mapping_timeout_is_invalid(self):
        config = OptimizerConfig.empty()
        config.launcher_mapping_timeout = 0
        self.assertFalse(config.is_valid())

    def test_default__must_be_valid(self):
        self.assertTrue(OptimizerConfig.default().is_valid())

    def test_default__gpu_cache_must_be_false(self):
        instance = OptimizerConfig.default()
        self.assertEqual(False, instance.gpu_cache)

    def test_default__allow_root_scripts_must_be_false(self):
        instance = OptimizerConfig.default()
        self.assertEqual(False, instance.allow_root_scripts)

    def test_default__launcher_mapping_timeout_must_be_15_seconds(self):
        instance = OptimizerConfig.default()
        self.assertEqual(15, instance.launcher_mapping_timeout)

    def test_default__check_finished_interval_must_be_3_seconds(self):
        instance = OptimizerConfig.default()
        self.assertEqual(3, instance.check_finished_interval)

    def test_default__renicer_interval_must_be_5_seconds(self):
        instance = OptimizerConfig.default()
        self.assertEqual(5, instance.renicer_interval)
