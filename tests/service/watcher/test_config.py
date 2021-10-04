from unittest import TestCase
from unittest.mock import Mock, patch, call

from guapow import __app_name__
from guapow.common.model_util import FileModelFiller
from guapow.service.watcher.config import ProcessWatcherConfigReader, ProcessWatcherConfig
from tests import RESOURCES_DIR


class ProcessWatcherConfigTest(TestCase):

    def test_empty__returned_instance_must_be_invalid(self):
        instance = ProcessWatcherConfig.empty()
        self.assertFalse(instance.is_valid())

    def test_default__returned_instance_must_be_valid(self):
        instance = ProcessWatcherConfig.default()
        self.assertTrue(instance.is_valid())

    def test_is_valid__false_when_check_interval_is_none(self):
        instance = ProcessWatcherConfig.empty()
        instance.check_interval = None
        self.assertFalse(instance.is_valid())

    def test_is_valid__false_when_check_interval_is_zero(self):
        instance = ProcessWatcherConfig.empty()
        instance.check_interval = 0
        self.assertFalse(instance.is_valid())

    def test_is_valid__false_when_check_interval_is_negative(self):
        instance = ProcessWatcherConfig.default()
        instance.check_interval = -1
        self.assertFalse(instance.is_valid())

    def test_is_valid__true_when_check_interval_is_higher_than_zero(self):
        instance = ProcessWatcherConfig.default()
        instance.check_interval = 0.01
        self.assertTrue(instance.is_valid())

    def test_is_valid__false_when_regex_cache_is_none(self):
        instance = ProcessWatcherConfig.default()
        instance.regex_cache = None
        self.assertFalse(instance.is_valid())

    def test_is_valid__true_when_regex_cache_is_not_none(self):
        instance = ProcessWatcherConfig.default()
        instance.regex_cache = False
        self.assertTrue(instance.is_valid())

    def test_is_valid__false_when_mapping_cache_is_none(self):
        instance = ProcessWatcherConfig.default()
        instance.mapping_cache = None
        self.assertFalse(instance.is_valid())

    def test_is_valid__true_when_mapping_cache_is_not_none(self):
        instance = ProcessWatcherConfig.default()
        instance.mapping_cache = False
        self.assertTrue(instance.is_valid())

    def test_setup_valid_properties__must_set_check_interval_to_1_when_invalid(self):
        instance = ProcessWatcherConfig.empty()
        instance.check_interval = -1
        instance.setup_valid_properties()
        self.assertEqual(1.0, instance.check_interval)

    def test_setup_valid_properties__must_set_regex_cache_to_true_when_invalid(self):
        instance = ProcessWatcherConfig.empty()
        self.assertIsNone(instance.regex_cache)
        instance.setup_valid_properties()
        self.assertTrue(instance.regex_cache)

    def test_setup_valid_properties__must_set_mapping_cache_to_false_when_invalid(self):
        instance = ProcessWatcherConfig.empty()
        self.assertIsNone(instance.mapping_cache)
        instance.setup_valid_properties()
        self.assertEqual(False, instance.mapping_cache)

    @patch(f'{__app_name__}.service.watcher.config.os.path.isfile', return_value=True)
    def test_get_by_path_by_user__return_etc_path_for_root_user_when_exists(self, isfile: Mock):
        exp_path = f'/etc/{__app_name__}/watch.conf'
        file_path = ProcessWatcherConfig.get_file_path_by_user(user_id=0, user_name='root', logger=Mock())
        self.assertEqual(exp_path, file_path)
        isfile.assert_called_once_with(exp_path)

    @patch(f'{__app_name__}.service.watcher.config.os.path.isfile', return_value=True)
    def test_get_by_path_by_user__return_home_path_for_non_root_user_when_exists(self, isfile: Mock):
        exp_path = f'/home/xpto/.config/{__app_name__}/watch.conf'
        file_path = ProcessWatcherConfig.get_file_path_by_user(user_id=123, user_name='xpto', logger=Mock())
        self.assertEqual(exp_path, file_path)
        isfile.assert_called_once_with(exp_path)

    @patch(f'{__app_name__}.service.watcher.config.os.path.isfile', side_effect=[False, True])
    def test_get_by_path_by_user__return_etc_path_for_non_root_user_when_home_path_not_exist(self, isfile: Mock):
        exp_root_path = f'/etc/{__app_name__}/watch.conf'
        exp_user_path = f'/home/xpto/.config/{__app_name__}/watch.conf'
        file_path = ProcessWatcherConfig.get_file_path_by_user(user_id=123, user_name='xpto', logger=Mock())
        self.assertEqual(exp_root_path, file_path)
        isfile.assert_has_calls([call(exp_user_path), call(exp_root_path)])

    @patch(f'{__app_name__}.service.watcher.config.os.path.isfile', side_effect=[False, False])
    def test_get_by_path_by_user__return_none_when_neither_home_nor_etc_path_exists_for_non_root_user(self, isfile: Mock):
        exp_root_path = f'/etc/{__app_name__}/watch.conf'
        exp_user_path = f'/home/xpto/.config/{__app_name__}/watch.conf'
        file_path = ProcessWatcherConfig.get_file_path_by_user(user_id=123, user_name='xpto', logger=Mock())
        self.assertIsNone(file_path)
        isfile.assert_has_calls([call(exp_user_path), call(exp_root_path)])


class ProcessWatcherConfigReaderTest(TestCase):

    def setUp(self):
        self.reader = ProcessWatcherConfigReader(filler=FileModelFiller(Mock()), logger=Mock())

    def test_read_valid__must_return_a_valid_default_instance_when_config_file_not_found(self):
        instance = self.reader.read_valid(f'{RESOURCES_DIR}/dasjdh8312301ksjd01230.conf')
        self.assertIsInstance(instance, ProcessWatcherConfig)
        self.assertTrue(instance.is_valid())

    def test_read_valid__must_return_an_instance_with_the_default_property_values_when_not_defined(self):
        instance = self.reader.read_valid(f'{RESOURCES_DIR}/empty.conf')
        self.assertIsInstance(instance, ProcessWatcherConfig)
        self.assertEqual(1.0, instance.check_interval)
        self.assertTrue(instance.regex_cache)

    def test_read_valid__must_return_an_instance_with_the_default_check_interval_when_invalid(self):
        instance = self.reader.read_valid(f'{RESOURCES_DIR}/watcher_bad_interval.conf')
        self.assertIsInstance(instance, ProcessWatcherConfig)
        self.assertEqual(1.0, instance.check_interval)

    def test_read_valid__must_return_an_instance_with_the_a_defined_check_interval_higher_than_zero(self):
        instance = self.reader.read_valid(f'{RESOURCES_DIR}/watcher_custom_interval.conf')
        self.assertIsInstance(instance, ProcessWatcherConfig)
        self.assertEqual(1.5, instance.check_interval)

    def test_read_valid__must_return_an_instance_with_valid_regex_cache_defined(self):
        instance = self.reader.read_valid(f'{RESOURCES_DIR}/watch_regex_cache.conf')
        self.assertIsInstance(instance, ProcessWatcherConfig)
        self.assertEqual(False, instance.regex_cache)

    def test_read_valid__must_return_an_instance_with_valid_mapping_cache_defined(self):
        instance = self.reader.read_valid(f'{RESOURCES_DIR}/watch_mapping_cache.conf')
        self.assertIsInstance(instance, ProcessWatcherConfig)
        self.assertTrue(instance.mapping_cache)

    def test_read_valid__must_return_default_config_when_no_path_is_defined(self):
        instance = self.reader.read_valid(None)
        self.assertIsInstance(instance, ProcessWatcherConfig)
        self.assertEqual(instance, ProcessWatcherConfig.default())
