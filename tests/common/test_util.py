from re import Pattern
from unittest import TestCase

from guapow.common import steam, util


class GetProtonExecNameAndPathsTest(TestCase):

    def test__must_return_valid_path_for_runtime_cmd(self):
        cmd = '/home/user/.local/share/Steam/steamapps/common/SteamLinuxRuntime_soldier/_v2-entry-point --verb=waitforexitandrun -- /home/user/.local/share/Steam/steamapps/common/Proton 5.13/proton waitforexitandrun /home/user/.local/share/Steam/steamapps/common/Abc Bcd/AbcBcd.exe'
        expected = ('AbcBcd.exe',
                    'Z:\\home\\user\\.local\\share\\Steam\\steamapps\\common\\Abc Bcd\\AbcBcd.exe',
                    '/home/user/.local/share/Steam/steamapps/common/Abc Bcd/AbcBcd.exe')
        actual = steam.get_proton_exec_name_and_paths(cmd)
        self.assertEqual(expected, actual)

    def test__must_return_valid_name_for_exe_with_spaces_dots_and_params(self):
        cmd = '/home/user/.local/share/Steam/steamapps/common/SteamLinuxRuntime_soldier/_v2-entry-point --verb=waitforexitandrun -- /home/user/.local/share/Steam/steamapps/common/Proton 5.13/proton waitforexitandrun /home/user/.local/share/Steam/steamapps/common/Abc Bcd/Abc T51_Bcd.123.exe -xpto 1'
        expected = ('Abc T51_Bcd.123.exe',
                    'Z:\\home\\user\\.local\\share\\Steam\\steamapps\\common\\Abc Bcd\\Abc T51_Bcd.123.exe -xpto 1',
                    '/home/user/.local/share/Steam/steamapps/common/Abc Bcd/Abc T51_Bcd.123.exe -xpto 1')
        actual = steam.get_proton_exec_name_and_paths(cmd)
        self.assertEqual(expected, actual)

    def test__must_return_valid_path_for_proton_3_7_cmd(self):
        cmd = '/home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=443860 -- /home/user/.local/share/Steam/steamapps/common/Proton 3.7/proton waitforexitandrun /home/user/.local/share/Steam/steamapps/common/My Game II/GameData/GameII.exe'
        expected = ('GameII.exe',
                    'Z:\\home\\user\\.local\\share\\Steam\\steamapps\\common\\My Game II\\GameData\\GameII.exe',
                    '/home/user/.local/share/Steam/steamapps/common/My Game II/GameData/GameII.exe')
        actual = steam.get_proton_exec_name_and_paths(cmd)
        self.assertEqual(expected, actual)

    def test__must_return_valid_path_for_proton_3_16_cmd(self):
        cmd = 'home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=123 -- /home/user/.local/share/Steam/steamapps/common/Proton 3.16/proton waitforexitandrun /home/user/.local/share/Steam/steamapps/common/My Game II/GameData/GameII.exe'
        expected = ('GameII.exe',
                    'Z:\\home\\user\\.local\\share\\Steam\\steamapps\\common\\My Game II\\GameData\\GameII.exe',
                    '/home/user/.local/share/Steam/steamapps/common/My Game II/GameData/GameII.exe')
        actual = steam.get_proton_exec_name_and_paths(cmd)
        self.assertEqual(expected, actual)

    def test__must_return_valid_path_for_proton_4_2_cmd(self):
        cmd = '/home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=123 -- /home/user/.local/share/Steam/steamapps/common/Proton 4.2/proton waitforexitandrun /home/user/.local/share/Steam/steamapps/common/My Game/Game_x64.exe'
        expected = ('Game_x64.exe',
                    'Z:\\home\\user\\.local\\share\\Steam\\steamapps\\common\\My Game\\Game_x64.exe',
                    '/home/user/.local/share/Steam/steamapps/common/My Game/Game_x64.exe')
        actual = steam.get_proton_exec_name_and_paths(cmd)
        self.assertEqual(expected, actual)

    def test__must_return_valid_path_for_proton_4_11_cmd(self):
        cmd = '/home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=123 -- /home/user/.local/share/Steam/steamapps/common/Proton 4.11/proton waitforexitandrun /home/user/.local/share/Steam/steamapps/common/My Game/Game_x64.exe'
        expected = ('Game_x64.exe',
                    'Z:\\home\\user\\.local\\share\\Steam\\steamapps\\common\\My Game\\Game_x64.exe',
                    '/home/user/.local/share/Steam/steamapps/common/My Game/Game_x64.exe')

        actual = steam.get_proton_exec_name_and_paths(cmd)
        self.assertEqual(expected, actual)
    
    def test__must_return_valid_path_for_proton_5_0_cmd(self):
        cmd = '/home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=123 -- /home/user/.local/share/Steam/steamapps/common/Proton 5.0/proton waitforexitandrun /home/user/.local/share/Steam/steamapps/common/My Game/Game_x64.exe'
        expected = ('Game_x64.exe',
                    'Z:\\home\\user\\.local\\share\\Steam\\steamapps\\common\\My Game\\Game_x64.exe',
                    '/home/user/.local/share/Steam/steamapps/common/My Game/Game_x64.exe')
        actual = steam.get_proton_exec_name_and_paths(cmd)
        self.assertEqual(expected, actual)
        
    def test__must_return_valid_path_for_proton_5_13_cmd(self):
        cmd = '/home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=123 -- /home/user/.local/share/Steam/steamapps/common/SteamLinuxRuntime_soldier/_v2-entry-point --verb=waitforexitandrun -- /home/user/.local/share/Steam/steamapps/common/Proton 5.13/proton waitforexitandrun /home/user/.local/share/Steam/steamapps/common/My Game/Game_x64.exe'
        expected = ('Game_x64.exe',
                    'Z:\\home\\user\\.local\\share\\Steam\\steamapps\\common\\My Game\\Game_x64.exe',
                    '/home/user/.local/share/Steam/steamapps/common/My Game/Game_x64.exe')
        actual = steam.get_proton_exec_name_and_paths(cmd)
        self.assertEqual(expected, actual)
        
    def test__must_return_valid_path_for_proton_6_3_cmd(self):
        cmd = '/home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=123 -- /home/user/.local/share/Steam/steamapps/common/SteamLinuxRuntime_soldier/_v2-entry-point --verb=waitforexitandrun -- /home/user/.local/share/Steam/steamapps/common/Proton 6.3/proton waitforexitandrun /home/user/.local/share/Steam/steamapps/common/My Game/Game_x64.exe'
        expected = ('Game_x64.exe',
                    'Z:\\home\\user\\.local\\share\\Steam\\steamapps\\common\\My Game\\Game_x64.exe',
                    '/home/user/.local/share/Steam/steamapps/common/My Game/Game_x64.exe')
        actual = steam.get_proton_exec_name_and_paths(cmd)
        self.assertEqual(expected, actual)
    
    def test__must_return_valid_path_for_proton_ge_cmd(self):
        cmd = '/home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=443860 -- /home/user/.local/share/Steam/steamapps/common/SteamLinuxRuntime_soldier/_v2-entry-point --verb=waitforexitandrun -- /home/user/.local/share/Steam/compatibilitytools.d/Proton-6.9-GE-2/proton waitforexitandrun /home/user/.local/share/Steam/steamapps/common/My Game/Game_x64.exe'
        expected = ('Game_x64.exe',
                    'Z:\\home\\user\\.local\\share\\Steam\\steamapps\\common\\My Game\\Game_x64.exe',
                    '/home/user/.local/share/Steam/steamapps/common/My Game/Game_x64.exe')
        actual = steam.get_proton_exec_name_and_paths(cmd)
        self.assertEqual(expected, actual)
        
    def test__must_return_none_when_path_not_from_proton(self):
        cmd = '/home/user/.local/share/Steam/steamapps/common/My Game/MyGame.exe'
        self.assertIsNone(steam.get_proton_exec_name_and_paths(cmd))


class MapAnyRegex(TestCase):

    def test_map_any_regex__should_preserve_str_when_no_asterisk(self):
        regex = util.map_any_regex(' abc ')
        self.assertIsNotNone(regex)
        self.assertIsInstance(regex, Pattern)
        self.assertEqual(r'^\ abc\ $', regex.pattern)

    def test_map_any_regex__should_replace_several_asterisk_by_equivalent_regex(self):
        regex = util.map_any_regex(' *****ab****c**** ')
        self.assertIsNotNone(regex)
        self.assertIsInstance(regex, Pattern)
        self.assertEqual(r'^\ .+ab.+c.+\ $', regex.pattern)
        self.assertIsNotNone(regex.match(' xptoab tralalac pqpwq '))

    def test_map_any_regex__should_escape_backlashes(self):
        regex = util.map_any_regex("\*Win64\MVCI.exe")
        self.assertIsNotNone(regex)
        self.assertIsInstance(regex, Pattern)
        self.assertEqual(r'^\\.+Win64\\MVCI\.exe$', regex.pattern)
        self.assertIsNotNone(regex.match(r'\path\to\Win64\MVCI.exe'))


class MapOnlyAnyRegex(TestCase):

    def test__generated_pattern_must_match_long_commands(self):
        pattern = util.map_only_any_regex('/*/Steam/ubuntu*/reaper*')
        self.assertTrue(pattern.match('/home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=6060  -- /home/user/.local/share/'))
