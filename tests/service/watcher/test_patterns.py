import re
from unittest import TestCase
from unittest.mock import Mock

from guapow.common.steam import RE_STEAM_CMD
from guapow.service.watcher.patterns import RegexMapper


class RegexMapperTest(TestCase):

    def setUp(self):
        self.mapper = RegexMapper(cache=False, logger=Mock())

    def test_map_for_profiles__must_return_pattern_keys_only_for_strings_with_asterisk(self):
        cmd_profs = {'abc': 'default', '/*/xpto': 'prof', 'def*abc*': 'prof2'}
        pattern_mappings = self.mapper.map_for_profiles(cmd_profs)
        self.assertIsInstance(pattern_mappings, tuple)
        self.assertEqual({re.compile(r'^/.+/xpto$'): 'prof'}, pattern_mappings[0])  # cmd
        self.assertEqual({re.compile(r'^def.+abc.+$'): 'prof2'}, pattern_mappings[1])  # comm

    def test_map_for_profiles__must_return_pattern_keys_when_key_starts_with_python_regex_pattern(self):
        cmd_profs = {'abc': 'default', 'r:/.+/xpto': 'prof', 'r:def.+abc\d+': 'prof2'}
        pattern_mappings = self.mapper.map_for_profiles(cmd_profs)
        self.assertIsInstance(pattern_mappings, tuple)
        self.assertEqual({re.compile(r'^/.+/xpto$'): 'prof'}, pattern_mappings[0])  # cmd
        self.assertEqual({re.compile(r'^def.+abc\d+$'): 'prof2'}, pattern_mappings[1])  # comm

    def test_map_for_profiles__must_cache_a_valid_pattern_when_cache_is_true(self):
        self.mapper = RegexMapper(cache=True, logger=Mock())
        cmd_profs = {'abc': 'default', 'r:/.+/xpto': 'prof', 'def*ihk*': 'prof2'}

        self.assertFalse(self.mapper.is_cached_as_no_pattern('abc'))
        self.assertIsNone(self.mapper.get_cached_pattern('r:/.+/xpto'))
        self.assertIsNone(self.mapper.get_cached_pattern('def*ihk*'))
        self.assertIsNone(self.mapper.get_cached_pattern('abc'))

        pattern_mappings = self.mapper.map_for_profiles(cmd_profs)
        self.assertIsInstance(pattern_mappings, tuple)

        self.assertIsNone(self.mapper.get_cached_pattern('abc'))
        self.assertEqual(re.compile(r'^/.+/xpto$'), self.mapper.get_cached_pattern('r:/.+/xpto'))
        self.assertEqual(re.compile(r'^def.+ihk.+$'), self.mapper.get_cached_pattern('def*ihk*'))

        self.assertTrue(self.mapper.is_cached_as_no_pattern('abc'))

    def test_map_for_profiles__must_not_cache_a_valid_pattern_when_cache_is_false(self):
        cmd_profs = {'abc': 'default', 'r:/.+/xpto': 'prof', 'def*ihk*': 'prof2'}

        self.assertFalse(self.mapper.is_cached_as_no_pattern('abc'))
        self.assertIsNone(self.mapper.get_cached_pattern('r:/.+/xpto'))
        self.assertIsNone(self.mapper.get_cached_pattern('def*ihk*'))

        pattern_mappings = self.mapper.map_for_profiles(cmd_profs)
        self.assertIsInstance(pattern_mappings, tuple)

        self.assertFalse(self.mapper.is_cached_as_no_pattern('abc'))
        self.assertIsNone(self.mapper.get_cached_pattern('r:/.+/xpto'))
        self.assertIsNone(self.mapper.get_cached_pattern('def*ihk*'))

    def test_map_for_profiles__must_return_steam_cmd_pattern_when_steam_keyword_is_informed(self):
        cmd_profs = {'__steam__': 'default'}

        pattern_mappings = self.mapper.map_for_profiles(cmd_profs)
        self.assertIsInstance(pattern_mappings, tuple)

        self.assertEqual({RE_STEAM_CMD: 'default'}, pattern_mappings[0])
        self.assertEqual({}, pattern_mappings[1])

    def test_map_for_profiles__default_patterns_must_not_be_cached(self):
        self.mapper = RegexMapper(cache=True, logger=Mock())

        cmd_profs = {'__steam__': 'default'}

        pattern_mappings = self.mapper.map_for_profiles(cmd_profs)
        self.assertIsInstance(pattern_mappings, tuple)

        self.assertTrue(pattern_mappings[0])
        self.assertFalse(pattern_mappings[1])

        self.assertIsNone(self.mapper.get_cached_pattern('__steam__'))
        self.assertIsNone(self.mapper.get_cached_pattern(RE_STEAM_CMD.pattern))

    def test_map__must_return_none_when_string_with_no_pattern_associated_is_already_cached(self):
        self.mapper = RegexMapper(cache=True, logger=Mock())
        self.mapper._string_no_pattern_cache.add('abc')
        self.assertIsNone(self.mapper.map('abc'))
