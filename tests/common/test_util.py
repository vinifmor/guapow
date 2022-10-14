from re import Pattern
from unittest import TestCase

from guapow.common import util


class MapAnyRegexTest(TestCase):

    def test_map_any_regex__should_preserve_str_when_no_asterisk(self):
        regex = util.map_any_regex(' abc ')
        self.assertIsNotNone(regex)
        self.assertIsInstance(regex, Pattern)
        self.assertEqual(r'^\ abc\ $', regex.pattern)

    def test_map_any_regex__should_replace_several_asterisk_by_equivalent_regex(self):
        regex = util.map_any_regex(' *****ab****c**** ')
        self.assertIsNotNone(regex)
        self.assertIsInstance(regex, Pattern)
        self.assertEqual(r'^\ .*ab.*c.*\ $', regex.pattern)
        self.assertIsNotNone(regex.match(' xptoab tralalac pqpwq '))

    def test_map_any_regex__should_escape_backlashes(self):
        regex = util.map_any_regex("\*Win64\MVCI.exe")
        self.assertIsNotNone(regex)
        self.assertIsInstance(regex, Pattern)
        self.assertEqual(r'^\\.*Win64\\MVCI\.exe$', regex.pattern)
        self.assertIsNotNone(regex.match(r'\path\to\Win64\MVCI.exe'))


class MapOnlyAnyRegex(TestCase):

    def test__generated_pattern_must_match_long_commands(self):
        pattern = util.map_only_any_regex('/*/Steam/ubuntu*/reaper*')
        self.assertTrue(pattern.match('/home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=6060  -- /home/user/.local/share/'))
