from unittest import TestCase, IsolatedAsyncioTestCase
from unittest.mock import Mock, patch, call

from guapow import __app_name__
from guapow.common.profile import get_default_profile_name
from guapow.service.watcher import mapping
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
        self.assertEqual(path, exp_root_path)

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
