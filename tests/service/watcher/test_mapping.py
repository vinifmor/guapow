import re
from unittest import TestCase, IsolatedAsyncioTestCase
from unittest.mock import Mock, patch, call

from guapow import __app_name__
from guapow.common.profile import get_default_profile_name
from guapow.common.steam import RE_STEAM_CMD
from guapow.service.watcher import mapping
from guapow.service.watcher.mapping import RegexMapper
from tests import RESOURCES_DIR


class GetFilePathTest(TestCase):

    def test__must_return_etc_path_for_root_user(self):
        file_path = mapping.get_file_path(0, 'root')
        self.assertEqual(f'/etc/{__app_name__}/watch.map', file_path)

    def test__must_return_user_home_path_for_noon_root_user(self):
        file_path = mapping.get_file_path(1, 'abc')
        self.assertEqual(f'/home/abc/.config/{__app_name__}/watch.map', file_path)


class GetExistingFilePathTest(TestCase):

    @patch(f'{__app_name__}.common.config.os.path.isfile', return_value=True)
    def test__return_etc_file_when_root_user(self, isfile: Mock):
        exp_path = f'/etc/{__app_name__}/watch.map'
        path = mapping.get_existing_file_path(0, 'root', Mock())
        self.assertEqual(exp_path, path)
        isfile.assert_called_once_with(exp_path)

    @patch(f'{__app_name__}.common.config.os.path.isfile', return_value=True)
    def test__return_home_file_when_normal_user(self, isfile: Mock):
        exp_path = f'/home/test/.config/{__app_name__}/watch.map'
        path = mapping.get_existing_file_path(123, 'test', Mock())
        self.assertEqual(exp_path, path)
        isfile.assert_called_once_with(exp_path)

    @patch(f'{__app_name__}.common.config.os.path.isfile', side_effect=[False, True])
    def test__return_etc_file_when_no_home_file_for_user(self, isfile: Mock):
        exp_user_path = f'/home/test/.config/{__app_name__}/watch.map'
        exp_root_path = f'/etc/{__app_name__}/watch.map'

        path = mapping.get_existing_file_path(123, 'test', Mock())
        self.assertEqual(exp_root_path, path)

        isfile.assert_has_calls([call(exp_user_path), call(exp_root_path)])

    @patch(f'{__app_name__}.common.config.os.path.isfile', side_effect=[False, False])
    def test__return_none_when_neither_etc_nor_home_file_exist_for_user(self, isfile: Mock):
        exp_user_path = f'/home/test/.config/{__app_name__}/watch.map'
        exp_root_path = f'/etc/{__app_name__}/watch.map'

        path = mapping.get_existing_file_path(123, 'test', Mock())
        self.assertIsNone(path)

        isfile.assert_has_calls([call(exp_user_path), call(exp_root_path)])


class GetDefaultFilePathTest(TestCase):

    @patch(f'{__app_name__}.common.config.os.path.isfile', return_value=True)
    def test__return_existing_etc_file_when_root_user(self, isfile: Mock):
        exp_path = f'/etc/{__app_name__}/watch.map'
        path = mapping.get_default_file_path(0, 'root', Mock())
        self.assertEqual(exp_path, path)
        isfile.assert_called_once_with(exp_path)

    @patch(f'{__app_name__}.common.config.os.path.isfile', return_value=True)
    def test__return_existing_home_file_when_normal_user(self, isfile: Mock):
        exp_path = f'/home/test/.config/{__app_name__}/watch.map'
        path = mapping.get_default_file_path(123, 'test', Mock())
        self.assertEqual(exp_path, path)
        isfile.assert_called_once_with(exp_path)

    @patch(f'{__app_name__}.common.config.os.path.isfile', side_effect=[False, True])
    def test__return_existing_etc_file_when_no_home_file_for_user(self, isfile: Mock):
        exp_user_path = f'/home/test/.config/{__app_name__}/watch.map'
        exp_root_path = f'/etc/{__app_name__}/watch.map'

        path = mapping.get_default_file_path(123, 'test', Mock())
        self.assertEqual(exp_root_path, path)

        isfile.assert_has_calls([call(exp_user_path), call(exp_root_path)])

    @patch(f'{__app_name__}.common.config.os.path.isfile', side_effect=[False, False])
    def test__return_home_file_path_when_neither_etc_nor_home_file_exist_for_user(self, isfile: Mock):
        exp_user_path = f'/home/test/.config/{__app_name__}/watch.map'
        exp_root_path = f'/etc/{__app_name__}/watch.map'

        path = mapping.get_default_file_path(123, 'test', Mock())
        self.assertEqual(exp_user_path, path)

        isfile.assert_has_calls([call(exp_user_path), call(exp_root_path)])

    @patch(f'{__app_name__}.common.config.os.path.isfile', side_effect=[False, False])
    def test__return_etc_path_even_when_it_does_not_exist_for_root_user(self, isfile: Mock):
        exp_root_path = f'/etc/{__app_name__}/watch.map'

        path = mapping.get_default_file_path(0, 'root', Mock())
        self.assertEqual(exp_root_path, exp_root_path)

        isfile.assert_called_once_with(exp_root_path)


class ReadTest(IsolatedAsyncioTestCase):

    async def test__must_return_none_when_file_not_found(self):
        file_found, instance = await mapping.read(f'{RESOURCES_DIR}/xpto_1234.map', Mock(), None)
        self.assertFalse(file_found)
        self.assertIsNone(instance)

    async def test__must_return_none_when_no_valid_mapping_is_defined(self):
        file_found, instance = await mapping.read(f'{RESOURCES_DIR}/empty.map', Mock(), None)
        self.assertTrue(file_found)
        self.assertIsNone(instance)

    async def test__must_return_the_default_profile_name_when_no_profile_is_defined_for_entry(self):
        file_found, instance = await mapping.read(f'{RESOURCES_DIR}/no_profiles.map', Mock(), None)
        self.assertTrue(file_found)
        self.assertIsInstance(instance, dict)

        expected_res = {cmd: get_default_profile_name() for cmd in ('abc', 'def', 'ghi', 'jkl')}
        self.assertEqual(expected_res, instance)

    async def test__must_return_none_when_no_valid_mapping_defined(self):
        file_found, instance = await mapping.read(f'{RESOURCES_DIR}/with_comments.map', Mock(), None)
        self.assertEqual(True, file_found)
        self.assertIsInstance(instance, dict)
        self.assertEqual({'abc': get_default_profile_name(),
                          'fgh': 'prof1',
                          'ijk': 'prof2'}, instance)

    async def test__must_return_python_regex_mapping_using_equal_sign(self):
        file_found, instance = await mapping.read(f'{RESOURCES_DIR}/python_regex_equal.map', Mock(), None)
        self.assertTrue(file_found)
        self.assertIsInstance(instance, dict)
        self.assertEqual({'r:/.+\s+SteamLaunch\s+AppId=\d+\s+--\s+/.+': 'steam'}, instance)


class RegexMapperTest(TestCase):

    def setUp(self):
        self.mapper = RegexMapper(cache=False, logger=Mock())

    def test_map__must_return_pattern_keys_only_for_strings_with_asterisk(self):
        cmd_profs = {'abc': 'default', '/*/xpto': 'prof', 'def*abc*': 'prof2'}
        pattern_mappings = self.mapper.map(cmd_profs)
        self.assertIsInstance(pattern_mappings, tuple)
        self.assertEqual({re.compile(r'^/.+/xpto$'): 'prof'}, pattern_mappings[0])  # cmd
        self.assertEqual({re.compile(r'^def.+abc.+$'): 'prof2'}, pattern_mappings[1])  # comm

    def test_map__must_return_pattern_keys_when_key_starts_with_python_regex_pattern(self):
        cmd_profs = {'abc': 'default', 'r:/.+/xpto': 'prof', 'r:def.+abc\d+': 'prof2'}
        pattern_mappings = self.mapper.map(cmd_profs)
        self.assertIsInstance(pattern_mappings, tuple)
        self.assertEqual({re.compile(r'^/.+/xpto$'): 'prof'}, pattern_mappings[0])  # cmd
        self.assertEqual({re.compile(r'^def.+abc\d+$'): 'prof2'}, pattern_mappings[1])  # comm

    def test_map__must_cache_a_valid_pattern_when_cache_is_true(self):
        self.mapper = RegexMapper(cache=True, logger=Mock())
        cmd_profs = {'abc': 'default', 'r:/.+/xpto': 'prof', 'def*ihk*': 'prof2'}

        self.assertFalse(self.mapper.is_no_pattern_string_cached('abc'))
        self.assertIsNone(self.mapper.get_cached_pattern('r:/.+/xpto'))
        self.assertIsNone(self.mapper.get_cached_pattern('def*ihk*'))
        self.assertIsNone(self.mapper.get_cached_pattern('abc'))

        pattern_mappings = self.mapper.map(cmd_profs)
        self.assertIsInstance(pattern_mappings, tuple)

        self.assertIsNone(self.mapper.get_cached_pattern('abc'))
        self.assertEqual(re.compile(r'^/.+/xpto$'), self.mapper.get_cached_pattern('r:/.+/xpto'))
        self.assertEqual(re.compile(r'^def.+ihk.+$'), self.mapper.get_cached_pattern('def*ihk*'))

        self.assertTrue(self.mapper.is_no_pattern_string_cached('abc'))

    def test_map__must_not_cache_a_valid_pattern_when_cache_is_false(self):
        cmd_profs = {'abc': 'default', 'r:/.+/xpto': 'prof', 'def*ihk*': 'prof2'}

        self.assertFalse(self.mapper.is_no_pattern_string_cached('abc'))
        self.assertIsNone(self.mapper.get_cached_pattern('r:/.+/xpto'))
        self.assertIsNone(self.mapper.get_cached_pattern('def*ihk*'))

        pattern_mappings = self.mapper.map(cmd_profs)
        self.assertIsInstance(pattern_mappings, tuple)

        self.assertFalse(self.mapper.is_no_pattern_string_cached('abc'))
        self.assertIsNone(self.mapper.get_cached_pattern('r:/.+/xpto'))
        self.assertIsNone(self.mapper.get_cached_pattern('def*ihk*'))

    def test_map__must_return_steam_cmd_pattern_when_steam_keyword_is_informed(self):
        cmd_profs = {'__steam__': 'default'}

        pattern_mappings = self.mapper.map(cmd_profs)
        self.assertIsInstance(pattern_mappings, tuple)

        self.assertEqual({RE_STEAM_CMD: 'default'}, pattern_mappings[0])
        self.assertEqual({}, pattern_mappings[1])

    def test_map__default_patterns_must_not_be_cached(self):
        self.mapper = RegexMapper(cache=True, logger=Mock())

        cmd_profs = {'__steam__': 'default'}

        pattern_mappings = self.mapper.map(cmd_profs)
        self.assertIsInstance(pattern_mappings, tuple)

        self.assertTrue(pattern_mappings[0])
        self.assertFalse(pattern_mappings[1])

        self.assertIsNone(self.mapper.get_cached_pattern('__steam__'))
        self.assertIsNone(self.mapper.get_cached_pattern(RE_STEAM_CMD.pattern))
