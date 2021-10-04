from unittest import TestCase

from guapow import __app_name__
from guapow.common.profile import get_root_profile_path, get_user_profile_path, \
    get_possible_profile_paths_by_priority


class GetRootProfilePathTest(TestCase):

    def test__must_return_concatenated_etc_path_to_name(self):
        self.assertEqual(f'/etc/{__app_name__}/xpto.profile',  get_root_profile_path('xpto'))


class GetUserProfilePathTest(TestCase):

    def test__must_return_concatenated_home_config_path_to_name(self):
        self.assertEqual(f'/home/test/.config/{__app_name__}/xpto.profile',  get_user_profile_path('xpto', 'test'))


class GetPossibleProfilePathsByPriority(TestCase):

    def test__return_only_etc_path_for_root_user(self):
        paths = get_possible_profile_paths_by_priority('test', 0, 'root')
        self.assertEqual((f'/etc/{__app_name__}/test.profile', None), paths)

    def test__return_only_etc_path_when_user_name_is_not_defined(self):
        paths = get_possible_profile_paths_by_priority('test', 1, None)
        self.assertEqual((f'/etc/{__app_name__}/test.profile', None), paths)

    def test__return_home_config_and_etc_paths_for_non_root_user(self):
        paths = get_possible_profile_paths_by_priority('test', 123, 'xpto')

        exp_paths = (f'/home/xpto/.config/{__app_name__}/test.profile',
                     f'/etc/{__app_name__}/test.profile')

        self.assertEqual(exp_paths, paths)
