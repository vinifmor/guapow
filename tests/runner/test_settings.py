import os
from unittest import TestCase
from unittest.mock import Mock

from guapow.runner.settings import map_config_str, read_valid_full_config, InvalidConfigurationException, \
    read_additional_profile_config


class MapConfigStrTest(TestCase):

    def test__map_entries_separated_by_space_semicolon_or_new_line(self):
        returned = map_config_str('proc.cpu.nice_level =-10 proc.affinity= 0,1,10,3\ngpu.performance=true ;  cpu.performance = 0 ')
        expected = 'proc.cpu.nice_level=-10\nproc.affinity=0,1,10,3\ngpu.performance=true\ncpu.performance=0'
        self.assertEqual(expected, returned)

    def test__map_entries_with_values_starting_with_forward_slashes(self):
        returned = map_config_str('before.scripts = /home/user/start_firefox.sh')
        expected = 'before.scripts=/home/user/start_firefox.sh'
        self.assertEqual(expected, returned)

    def test_map_properties_without_values_defined(self):
        returned = map_config_str('cpu.performance gpu.performance=1 compositor.off scripts.finish=/abc')
        expected = 'cpu.performance\ngpu.performance=1\ncompositor.off\nscripts.finish=/abc'
        self.assertEqual(expected, returned)

    def test_map_dict_props(self):
        returned = map_config_str('proc.env=ABC:123 proc.env= DEF:456 launcher=xpto:c%*/xpto/bin compositor.off=1')
        expected = 'proc.env=ABC:123\nproc.env=DEF:456\nlauncher=xpto:c%*/xpto/bin\ncompositor.off=1'
        self.assertEqual(expected, returned)


class ReadValidFullConfigTest(TestCase):

    def test__return_a_valid_config_defined_through_the_env_var(self):
        os.environ['GUAPOW_CONFIG'] = 'cpu.performance = 1; gpu.performance=false'
        config = read_valid_full_config(Mock())
        self.assertIsNotNone(config)
        self.assertEqual('cpu.performance=1\ngpu.performance=false', config)

    def test__raise_an_exception_when_invalid_config_defined_through_the_env_var(self):
        os.environ['GUAPOW_CONFIG'] = 'abc='

        with self.assertRaises(InvalidConfigurationException):
            read_valid_full_config(Mock())

    def setUp(self):
        self._clean_var()

    def tearDown(self):
        self._clean_var()

    @staticmethod
    def _clean_var():
        if 'GUAPOW_CONFIG' in os.environ:
            del os.environ['GUAPOW_CONFIG']


class ReadAdditionalProfileConfigTest(TestCase):

    def test__return_a_valid_config_defined_through_the_env_var(self):
        os.environ['GUAPOW_PROFILE_ADD'] = 'cpu.performance = 1; gpu.performance=false'
        config = read_additional_profile_config(Mock())
        self.assertIsNotNone(config)
        self.assertEqual('cpu.performance=1\ngpu.performance=false', config)

    def test__return_a_valid_config_with_dict_property_defined_through_the_env_var(self):
        os.environ['GUAPOW_PROFILE_ADD'] = 'launcher=proc.bat:xpto.e launcher=myproc:/proc'
        config = read_additional_profile_config(Mock())
        self.assertIsNotNone(config)
        self.assertEqual('launcher=proc.bat:xpto.e\nlauncher=myproc:/proc', config)

    def test__return_none_when_invalid_config_defined_through_the_env_var(self):
        os.environ['GUAPOW_PROFILE_ADD'] = 'abc'
        self.assertIsNone(read_valid_full_config(Mock()))

    def setUp(self):
        self._clean_var()

    def tearDown(self):
        self._clean_var()

    @staticmethod
    def _clean_var():
        if 'GUAPOW_PROFILE_ADD' in os.environ:
            del os.environ['GUAPOW_PROFILE_ADD']
