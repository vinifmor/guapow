import re
from asyncio import Future
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import Mock, patch, AsyncMock, MagicMock, call

from guapow import __app_name__
from guapow.common import util
from guapow.common.dto import OptimizationRequest
from guapow.common.steam import get_proton_exec_name_and_paths, get_steam_runtime_command
from guapow.service.optimizer.launcher import map_launchers_file, gen_possible_launchers_file_paths, \
    LauncherSearchMode, map_launchers_dict, ExplicitLauncherMapper, SteamLauncherMapper, LauncherMapperManager
from guapow.service.optimizer.profile import OptimizationProfile, LauncherSettings
from tests import RESOURCES_DIR


def new_steam_profile(enabled: bool) -> OptimizationProfile:
    prof = OptimizationProfile.empty('test')
    prof.steam = enabled
    return prof


class MapLaunchersDict(TestCase):

    def test__return_a_command_mapping_for_strings_starting_with_c_followed_by_percentage(self):
        launchers = {' comm ': ' c%c%xpto/abc/tralala --123 --456=978 '}

        res = map_launchers_dict(launchers, Mock())
        self.assertEqual({'comm': ('c%xpto/abc/tralala --123 --456=978', LauncherSearchMode.COMMAND)}, res)

    def test__return_a_command_mapping_for_strings_starting_with_upper_c_followed_by_percentage(self):
        launchers = {' comm ': ' C%C%xpto/abc/tralala --123 --456=978 '}

        res = map_launchers_dict(launchers, Mock())
        self.assertEqual({'comm': ('C%xpto/abc/tralala --123 --456=978', LauncherSearchMode.COMMAND)}, res)

    def test__return_a_name_mapping_for_strings_starting_with_n_followed_by_percentage(self):
        launchers = {' app ': ' n%n%xpto/abc/tralala --123 --456=978 '}

        res = map_launchers_dict(launchers, Mock())
        self.assertEqual({'app': ('n%xpto/abc/tralala --123 --456=978', LauncherSearchMode.NAME)}, res)

    def test__return_a_name_mapping_for_strings_not_starting_with_forward_slash(self):
        launchers = {' app ': ' xpto/abc/tralala --123 --456=978 '}

        res = map_launchers_dict(launchers, Mock())
        self.assertEqual({'app': ('xpto/abc/tralala --123 --456=978', LauncherSearchMode.NAME)}, res)

    def test__return_a_command_mapping_for_strings_starting_with_forward_slash(self):
        launchers = {' app ': ' /xpto/abc/tralala --123 --456=978 '}

        res = map_launchers_dict(launchers, Mock())
        self.assertEqual({'app': ('/xpto/abc/tralala --123 --456=978', LauncherSearchMode.COMMAND)}, res)


class LauncherSearchModeTest(TestCase):

    def test_map_string__return_command_when_string_starts_with_slash(self):
        returned_type = LauncherSearchMode.map_string('/usr/bin')
        self.assertEqual(LauncherSearchMode.COMMAND, returned_type)

    def test_map_string__return_name_when_string_does_not_start_with_slash(self):
        returned_type = LauncherSearchMode.map_string('abc')
        self.assertEqual(LauncherSearchMode.NAME, returned_type)


class MapLaunchersFileTest(IsolatedAsyncioTestCase):

    async def test_map_launchers__it_should_map_valid_definitions(self):
        launcher_file = f'{RESOURCES_DIR}/valid_launchers'

        launchers = await map_launchers_file(launcher_file, Mock())
        self.assertIsNotNone(launchers)

        expected_mapping = {'BootGGXrd.bat': ('GuiltyGearXrd.e', LauncherSearchMode.NAME),
                            'xpto': ('abcd.exe', LauncherSearchMode.COMMAND),
                            '1234': ('5678', LauncherSearchMode.NAME),
                            '_a1d3': ('trala-la', LauncherSearchMode.NAME),
                            'rrr': ('/usr/bin/program', LauncherSearchMode.COMMAND)}

        self.assertEqual(expected_mapping, launchers)

    async def test_map_launchers__it_should_ignore_sharps(self):
        launcher_file = f'{RESOURCES_DIR}/launchers_and_comments'

        launchers = await map_launchers_file(launcher_file, Mock())
        self.assertIsNotNone(launchers)

        expected_mapping = {'BootGGXrd.bat': ('GuiltyGearXrd.e', LauncherSearchMode.NAME),
                            'aaa': ('bb', LauncherSearchMode.NAME)}

        self.assertEqual(expected_mapping, launchers)


class ExplicitLauncherMapperTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.logger = Mock()
        self.mapper = ExplicitLauncherMapper(wait_time=30, logger=self.logger)

    @patch(f'{__app_name__}.service.optimizer.launcher.map_launchers_file', side_effect=FileNotFoundError)
    async def test_map_pid__return_none_when_there_is_no_possible_launchers_file_available(self, map_launchers: Mock):
        request = OptimizationRequest(pid=123, command='/usr/local/bin/game', user_name='user')
        profile = new_steam_profile(enabled=False)

        returned_pid = await self.mapper.map_pid(request, profile)
        self.assertIsNone(returned_pid)

        exp_file_paths = gen_possible_launchers_file_paths(user_id=123, user_name='user')
        map_launchers.assert_has_calls([call(fpath, self.logger) for fpath in exp_file_paths])

    @patch(f'{__app_name__}.service.optimizer.launcher.map_launchers_file', return_value={'game': ('game_x86_64.bin', LauncherSearchMode.NAME)})
    @patch(f'{__app_name__}.common.system.find_process_by_name', return_value=(456, 'game_x86_64.bin'))
    async def test_map_pid__return_pid_for_matched_launcher_mapped_name(self, find_process_by_name: Mock, map_launchers: Mock):
        request = OptimizationRequest(pid=123, command='/usr/local/bin/game', user_name='user')
        profile = new_steam_profile(enabled=False)

        returned_pid = await self.mapper.map_pid(request, profile)
        self.assertEqual(456, returned_pid)

        exp_file_paths = [*gen_possible_launchers_file_paths(user_id=123, user_name='user')]
        map_launchers.assert_called_once_with(exp_file_paths[0], self.logger)
        find_process_by_name.assert_called_once_with(util.map_any_regex('game_x86_64.bin'), last_match=True)

    @patch(f'{__app_name__}.service.optimizer.launcher.map_launchers_file', side_effect=[FileNotFoundError, {'game': ('game_x86_64.bin', LauncherSearchMode.NAME)}])
    @patch(f'{__app_name__}.common.system.find_process_by_name', return_value=(456, 'game_x86_64.bin'))
    async def test_map_pid__return_pid_for_matched_etc_launchers_file_when_user_file_does_not_exist(self, find_process_by_name: Mock, map_launchers: Mock):
        request = OptimizationRequest(pid=123, command='/usr/local/bin/game', user_name='user')
        profile = new_steam_profile(enabled=False)

        returned_pid = await self.mapper.map_pid(request, profile)
        self.assertEqual(456, returned_pid)

        exp_file_paths = [*gen_possible_launchers_file_paths(user_id=123, user_name='user')]
        map_launchers.assert_has_calls([call(fpath, self.logger) for fpath in exp_file_paths])
        find_process_by_name.assert_called_once_with(util.map_any_regex('game_x86_64.bin'), last_match=True)

    @patch(f'{__app_name__}.service.optimizer.launcher.map_launchers_file', return_value={'game': ('game_x86_64.bin', LauncherSearchMode.NAME)})
    @patch(f'{__app_name__}.common.system.find_process_by_name', return_value=(456, 'game_x86_64.bin'))
    async def test_map_pid__return_pid_for_matched_etc_launchers_file_for_root_call(self, find_process_by_name: Mock, map_launchers: Mock):
        request = OptimizationRequest(pid=123, command='/usr/local/bin/game', user_name='root')
        request.user_id = 0

        profile = new_steam_profile(enabled=False)

        returned_pid = await self.mapper.map_pid(request, profile)
        self.assertEqual(456, returned_pid)

        map_launchers.assert_called_once_with(f'/etc/{__app_name__}/launchers', self.logger)
        find_process_by_name.assert_called_once_with(util.map_any_regex('game_x86_64.bin'), last_match=True)

    @patch(f'{__app_name__}.service.optimizer.launcher.map_launchers_file', return_value={'game': ('/path/to/game_x86_64.bin', LauncherSearchMode.COMMAND)})
    @patch(f'{__app_name__}.common.system.find_process_by_command', return_value=(456, '/path/to/game_x86_64.bin'))
    async def test_map_pid__return_pid_for_matched_launcher_mapped_cmd(self, find_process_by_command: Mock, map_launchers: Mock):
        request = OptimizationRequest(pid=123, command='/usr/local/bin/game', user_name='user')
        profile = new_steam_profile(enabled=False)

        returned_pid = await self.mapper.map_pid(request, profile)
        self.assertEqual(456, returned_pid)
        map_launchers.assert_called_once()
        find_process_by_command.assert_called_once_with({util.map_any_regex('/path/to/game_x86_64.bin')}, last_match=True)

    @patch(f'{__app_name__}.service.optimizer.launcher.map_launchers_file', return_value={'game': (' *game_x86_64.bin ', LauncherSearchMode.NAME)})
    @patch(f'{__app_name__}.common.system.find_process_by_name', return_value=(456, '/game_x86_64.bin'))
    async def test_map_pid__return_pid_for_matched_launcher_mapped_name_regex(self, find_process_by_name: Mock, map_launchers: Mock):
        request = OptimizationRequest(pid=123, command='/usr/local/bin/game', user_name='user')
        profile = new_steam_profile(enabled=False)

        returned_pid = await self.mapper.map_pid(request, profile)
        self.assertEqual(456, returned_pid)

        exp_file_paths = [*gen_possible_launchers_file_paths(user_id=123, user_name='user')]
        map_launchers.assert_called_once_with(exp_file_paths[0], self.logger)
        find_process_by_name.assert_called_once_with(util.map_any_regex(' *game_x86_64.bin '), last_match=True)

    @patch(f'{__app_name__}.service.optimizer.launcher.map_launchers_file', return_value={'game': ('/*game_x86_64.bin ', LauncherSearchMode.COMMAND)})
    @patch(f'{__app_name__}.common.system.find_process_by_command', return_value=(456, '/game_x86_64.bin'))
    async def test_map_pid__return_pid_for_matched_launcher_mapped_cmd_regex(self, find_process_by_command: Mock, map_launchers: Mock):
        request = OptimizationRequest(pid=123, command='/usr/local/bin/game', user_name='user')
        profile = new_steam_profile(enabled=False)

        returned_pid = await self.mapper.map_pid(request, profile)
        self.assertEqual(456, returned_pid)
        map_launchers.assert_called_once()
        find_process_by_command.assert_called_once_with({util.map_any_regex('/*game_x86_64.bin ')}, last_match=True)

    @patch(f'{__app_name__}.service.optimizer.launcher.map_launchers_file', return_value={'hl2.sh*': ('hl2.linux', LauncherSearchMode.NAME)})
    @patch(f'{__app_name__}.common.system.find_process_by_name', return_value=(456, 'hl2.linux'))
    async def test_map_pid__return_pid_for_matched_launcher_using_a_wild_card(self, find_process_by_name: Mock, map_launchers: Mock):
        cmd = '/home/user/.local/share/Steam/steamapps/common/Team Fortress 2/hl2.sh -game tf -steam'
        request = OptimizationRequest(pid=123, command=cmd, user_name='user')
        profile = new_steam_profile(enabled=False)

        returned_pid = await self.mapper.map_pid(request, profile)
        self.assertEqual(456, returned_pid)
        map_launchers.assert_called_once()
        find_process_by_name.assert_called_once_with(util.map_any_regex('hl2.linux'), last_match=True)

    @patch(f'{__app_name__}.common.system.find_process_by_command', return_value=(456, '/bin/proc_abc'))
    async def test_map_pid__return_pid_for_matched_launcher_defined_via_profile(self, find_process_by_command: Mock):
        request = OptimizationRequest(pid=123, command='/home/user/.local/bin/proc1', user_name='user')
        profile = OptimizationProfile.empty('test')
        profile.launcher = LauncherSettings({'proc1': 'c%/bin/proc_abc'}, None)

        returned_pid = await self.mapper.map_pid(request, profile)
        self.assertEqual(456, returned_pid)
        find_process_by_command.assert_called_once_with({util.map_any_regex('/bin/proc_abc')}, last_match=True)

    @patch(f'{__app_name__}.common.system.find_process_by_command', return_value=(456, '/bin/proc_abc'))
    async def test_map_pid__return_pid_for_matched_launcher_defined_via_profile_using_wildcards(self, find_process_by_command: Mock):
        request = OptimizationRequest(pid=123, command='/home/user/.local/bin/proc1', user_name='user')
        profile = OptimizationProfile.empty('test')
        profile.launcher = LauncherSettings({'proc1': 'c%/bin/proc_*'}, False)

        returned_pid = await self.mapper.map_pid(request, profile)
        self.assertEqual(456, returned_pid)
        find_process_by_command.assert_called_once_with({util.map_any_regex('/bin/proc_*')}, last_match=True)

    @patch(f'{__app_name__}.common.system.find_process_by_command', return_value=None)
    @patch(f'{__app_name__}.common.system.find_process_by_name', return_value=None)
    async def test_map_pid__return_none_for_when_defined_launchers_via_profile_are_invalid(self, find_process_by_command: Mock, find_latest_process_by_cmd: Mock):
        request = OptimizationRequest(pid=123, command='/home/user/.local/bin/proc1', user_name='user')
        profile = OptimizationProfile.empty('test')
        profile.launcher = LauncherSettings({'proc1': ''}, None)

        returned_pid = await self.mapper.map_pid(request, profile)
        self.assertIsNone(returned_pid)
        find_latest_process_by_cmd.assert_not_called()
        find_process_by_command.assert_not_called()

    @patch(f'{__app_name__}.common.system.find_process_by_command', return_value=None)
    @patch(f'{__app_name__}.common.system.find_process_by_name', return_value=None)
    async def test_map_pid__return_none_when_skip_mapping_is_true(self, find_process_by_name: Mock, find_process_by_command: Mock):
        request = OptimizationRequest(pid=123, command='/home/user/.local/bin/proc1', user_name='user')
        profile = OptimizationProfile.empty('test')
        profile.launcher = LauncherSettings({'proc1': '/bin/proc1'}, True)

        returned_pid = await self.mapper.map_pid(request, profile)
        self.assertIsNone(returned_pid)
        find_process_by_command.assert_not_called()
        find_process_by_name.assert_not_called()


class SteamLauncherMapperTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.mapper = SteamLauncherMapper(wait_time=0.001, logger=Mock())

    @patch(f'{__app_name__}.common.system.find_process_by_command', return_value=(456, 'Game_x64.exe'))
    async def test_map_pid__return_id_when_proton_command_not_from_runtime(self, find_process_by_command: Mock):
        cmd = 'home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=123 -- /home/user/.local/share/Steam/steamapps/common/Proton 3.16/proton waitforexitandrun /home/user/.local/share/Steam/steamapps/common/Game II/Game_x64.exe'

        request = OptimizationRequest(pid=123, command=cmd, user_name='user')
        profile = new_steam_profile(enabled=True)

        returned_pid = await self.mapper.map_pid(request=request, profile=profile)
        self.assertEqual(456, returned_pid)

        expected_wine_path = {util.map_any_regex(c) for c in get_proton_exec_name_and_paths(cmd)[1:]}
        find_process_by_command.assert_called_once_with(expected_wine_path, last_match=True)

    @patch(f'{__app_name__}.common.system.find_process_by_command', return_value=(456, 'Game_x64.exe'))
    async def test_map_pid__return_id_when_proton_command_from_runtime(self, find_process_by_command: Mock):
        cmd = '/home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=123 -- /home/user/.local/share/Steam/steamapps/common/SteamLinuxRuntime_soldier/_v2-entry-point --verb=waitforexitandrun -- /home/user/.local/share/Steam/steamapps/common/Proton 6.3/proton waitforexitandrun /home/user/.local/share/Steam/steamapps/common/Game II/Game_x64.exe'

        request = OptimizationRequest(pid=123, command=cmd, user_name='user')
        profile = new_steam_profile(enabled=True)

        returned_pid = await self.mapper.map_pid(request=request, profile=profile)
        self.assertEqual(456, returned_pid)

        expected_wine_path = {util.map_any_regex(c) for c in get_proton_exec_name_and_paths(cmd)[1:]}
        find_process_by_command.assert_called_once_with(expected_wine_path, last_match=True)

    @patch(f'{__app_name__}.common.system.find_process_by_name', return_value=(456, 'Game_x64.exe'))
    @patch(f'{__app_name__}.common.system.find_process_by_command', return_value=None)
    async def test_map_pid__return_id_when_proton_command_patterns_not_match_but_name_does(self, find_process_by_command: AsyncMock, find_process_by_name: AsyncMock):
        cmd = '/home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=123 -- /home/user/.local/share/Steam/steamapps/common/SteamLinuxRuntime_soldier/_v2-entry-point --verb=waitforexitandrun -- /home/user/.local/share/Steam/steamapps/common/Proton 6.3/proton waitforexitandrun /home/user/.local/share/Steam/steamapps/common/Game II/Game_x64.exe'

        request = OptimizationRequest(pid=123, command=cmd, user_name='user')
        profile = new_steam_profile(enabled=True)

        returned_pid = await self.mapper.map_pid(request=request, profile=profile)
        self.assertEqual(456, returned_pid)

        find_process_by_command.assert_awaited()
        find_process_by_name.assert_awaited_once_with(re.compile(r'^Game_x64.exe$'), last_match=True)

    @patch(f'{__app_name__}.common.system.find_process_by_command', return_value=(456, 'gm2.sh'))
    async def test_map_pid__return_id_when_command_not_from_proton(self, find_process_by_command: Mock):
        cmd = '/home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=123 -- /home/user/.local/share/Steam/steamapps/common/Game 2/gm2.sh -game tf -steam'

        request = OptimizationRequest(pid=123, command=cmd, user_name='user')
        profile = new_steam_profile(enabled=True)

        returned_pid = await self.mapper.map_pid(request=request, profile=profile)
        self.assertEqual(456, returned_pid)

        expected_wine_path = {re.compile(r'(/bin/\w+\s+)?{}'.format(re.escape(get_steam_runtime_command(cmd))))}
        find_process_by_command.assert_called_once_with(expected_wine_path, last_match=True)


class ProcessLauncherManagerTest(IsolatedAsyncioTestCase):

    async def test_map_pid__should_try_to_retrieve_pid_until_a_mapper_returns_a_pid(self):
        # first sub-mapper that would inspect the request, but no process would be returned
        mocked_mapper = Mock()
        mocked_mapper.map_pid = MagicMock(return_value=Future())
        mocked_mapper.map_pid.return_value.set_result(None)

        # second sub-mapper that would inspect the request and actually find the process
        steam_mapper = SteamLauncherMapper(wait_time=30, logger=Mock())
        steam_mapper.map_pid = MagicMock(return_value=Future())
        steam_mapper.map_pid.return_value.set_result(456)

        manager = LauncherMapperManager(check_time=30, logger=Mock(), mappers=[mocked_mapper, steam_mapper])

        request = OptimizationRequest(pid=123, command='/abc', user_name='user')
        profile = new_steam_profile(enabled=True)
        real_id = await manager.map_pid(request=request, profile=profile)
        self.assertEqual(456, real_id)

        mocked_mapper.map_pid.assert_called_once()
        steam_mapper.map_pid.assert_called_once()

    async def test_get_sub_mappers__order(self):
        manager = LauncherMapperManager(check_time=30, logger=Mock())
        mappers = manager.get_sub_mappers()
        self.assertIsNotNone(mappers)
        self.assertEqual(2, len(mappers))
        self.assertIsInstance(mappers[0], ExplicitLauncherMapper)
        self.assertIsInstance(mappers[1], SteamLauncherMapper)


class GenPossibleLaunchersFilePathsTest(TestCase):

    def test__must_yield_once_the_etc_path_for_root(self):
        res = [*gen_possible_launchers_file_paths(user_id=0, user_name='')]
        self.assertEqual(['/etc/guapow/launchers'], res)

    def test__must_yield_twice_for_non_root_users(self):
        res = [*gen_possible_launchers_file_paths(user_id=567, user_name='test')]
        self.assertEqual(['/home/test/.config/guapow/launchers', '/etc/guapow/launchers'], res)
