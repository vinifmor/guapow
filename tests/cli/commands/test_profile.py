import os
from unittest import TestCase
from unittest.mock import Mock, patch

from guapow import __app_name__
from guapow.cli.commands.profile import GenerateProfile
from guapow.service.optimizer.profile import OptimizationProfile
from tests import RESOURCES_DIR


class GenerateProfileTest(TestCase):

    def tearDown(self):
        temp_file = f'{RESOURCES_DIR}/media.profile'
        if os.path.isfile(temp_file):
            os.remove(temp_file)

    def test_get_command__must_be_equal_to_gen_profile(self):
        self.assertEqual('gen-profile', GenerateProfile(Mock()).get_command())

    def test_PROFILES__must_have_all_expected_profiles(self):
        exp_profiles = {'media', 'default', 'game', 'steam'}
        self.assertEqual(exp_profiles, GenerateProfile.PROFILES)

        for profile in exp_profiles:
            hasattr(GenerateProfile, f'generate_{profile}')

    def test_generate_default__must_return_a_valid_instance(self):
        instance = GenerateProfile.generate_default(f'/etc/{__app_name__}/default.profile')
        self.assertIsInstance(instance, OptimizationProfile)
        self.assertTrue(instance.is_valid())
        self.assertEqual('default', instance.name)

    def test_generate_default__to_file_str(self):
        instance = GenerateProfile.generate_default(f'/etc/{__app_name__}/default.profile')
        self.assertEqual("cpu.performance=true\nproc.io.class=best_effort\nproc.io.nice=0\nproc.nice=-1\n", instance.to_file_str())

    def test_generate_media__must_return_a_valid_instance(self):
        instance = GenerateProfile.generate_media(f'/etc/{__app_name__}/media.profile')
        self.assertIsInstance(instance, OptimizationProfile)
        self.assertTrue(instance.is_valid())
        self.assertEqual('media', instance.name)

    def test_generate_media__to_file_str(self):
        instance = GenerateProfile.generate_media(f'/etc/{__app_name__}/media.profile')
        self.assertEqual("cpu.performance=true\nproc.io.class=best_effort\nproc.io.nice=0\nproc.nice=-4\n", instance.to_file_str())

    def test_generate_game__must_return_a_valid_instance(self):
        instance = GenerateProfile.generate_game(f'/etc/{__app_name__}/game.profile')
        self.assertIsInstance(instance, OptimizationProfile)
        self.assertTrue(instance.is_valid())
        self.assertEqual('game', instance.name)

    def test_generate_game__to_file_str(self):
        instance = GenerateProfile.generate_game(f'/etc/{__app_name__}/game.profile')
        self.assertEqual("compositor.off=true\ncpu.performance=true\ngpu.performance=true\nproc.io.class=best_effort\nproc.io.nice=0\nproc.nice=-4\nproc.nice.watch=true\n",
                         instance.to_file_str())

    def test_generate_steam__must_return_a_valid_instance(self):
        instance = GenerateProfile.generate_steam(f'/etc/{__app_name__}/steam.profile')
        self.assertIsInstance(instance, OptimizationProfile)
        self.assertTrue(instance.is_valid())
        self.assertEqual('steam', instance.name)

    def test_generate_steam__to_file_str(self):
        instance = GenerateProfile.generate_steam(f'/etc/{__app_name__}/steam.profile')
        self.assertEqual("compositor.off=true\ncpu.performance=true\ngpu.performance=true\nproc.io.class=best_effort\nproc.io.nice=0\nproc.nice=-4\nproc.nice.watch=true\nsteam=true\n",
                         instance.to_file_str())

    @patch(f'{__app_name__}.cli.commands.profile.get_profile_dir', return_value=RESOURCES_DIR)
    def test_run__must_generate_a_new_file(self, get_profile_dir: Mock):
        gen_profile = GenerateProfile(Mock())

        args = Mock()
        args.name = 'media'

        self.assertTrue(gen_profile.run(args))
        get_profile_dir.assert_called_once()

        self.assertTrue(os.path.isfile(f'{RESOURCES_DIR}/{args.name}.profile'))

    @patch(f'{__app_name__}.cli.commands.profile.get_profile_dir', return_value=RESOURCES_DIR)
    def test_run__must_not_overwrite_an_existing_file(self, get_profile_dir: Mock):
        gen_profile = GenerateProfile(Mock())

        args = Mock()
        args.name = 'simple_props'

        self.assertFalse(gen_profile.run(args))
        get_profile_dir.assert_called_once()

        self.assertTrue(os.path.isfile(f'{RESOURCES_DIR}/{args.name}.profile'))
