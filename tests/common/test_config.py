from unittest import TestCase
from unittest.mock import Mock, patch, call

from guapow import __app_name__
from guapow.common.config import get_optimizer_config_path_by_user_priority
from guapow.common.profile import get_profile_dir, get_default_profile_name


class GetProfileDirTest(TestCase):

    def test__must_return_etc_path_when_user_id_is_zero(self):
        dir_path = get_profile_dir(0, 'root')
        self.assertEqual(f'/etc/{__app_name__}', dir_path)

    def test__must_return_home_path_when_user_id_is_not_zero(self):
        dir_path = get_profile_dir(1, 'test')
        self.assertEqual(f'/home/test/.config/{__app_name__}', dir_path)


class GetDefaultProfileNameTest(TestCase):

    def test__must_be_equal_to_default(self):
        self.assertEqual('default', get_default_profile_name())


class GetOptimizerConfigPathByUserPriorityTest(TestCase):

    @patch(f'{__app_name__}.common.config.os.path.isfile', return_value=True)
    def test__return_etc_file_when_root_user(self, isfile: Mock):
        exp_path = f'/etc/{__app_name__}/opt.conf'
        path = get_optimizer_config_path_by_user_priority(0, 'root', Mock())
        self.assertEqual(exp_path, path)
        isfile.assert_called_once_with(exp_path)

    @patch(f'{__app_name__}.common.config.os.path.isfile', return_value=True)
    def test__return_home_file_when_normal_user(self, isfile: Mock):
        exp_path = f'/home/test/.config/{__app_name__}/opt.conf'
        path = get_optimizer_config_path_by_user_priority(123, 'test', Mock())
        self.assertEqual(exp_path, path)
        isfile.assert_called_once_with(exp_path)

    @patch(f'{__app_name__}.common.config.os.path.isfile', side_effect=[False, True])
    def test__return_etc_path_when_no_home_file_for_user(self, isfile: Mock):
        exp_user_path = f'/home/test/.config/{__app_name__}/opt.conf'
        exp_root_path = f'/etc/{__app_name__}/opt.conf'

        path = get_optimizer_config_path_by_user_priority(123, 'test', Mock())
        self.assertEqual(exp_root_path, path)

        isfile.assert_has_calls([call(exp_user_path), call(exp_root_path)])

    @patch(f'{__app_name__}.common.config.os.path.isfile', side_effect=[False, False])
    def test__return_none_when_neither_etc_nor_home_file_for_user(self, isfile: Mock):
        exp_user_path = f'/home/test/.config/{__app_name__}/opt.conf'
        exp_root_path = f'/etc/{__app_name__}/opt.conf'

        path = get_optimizer_config_path_by_user_priority(123, 'test', Mock())
        self.assertIsNone(path)

        isfile.assert_has_calls([call(exp_user_path), call(exp_root_path)])
