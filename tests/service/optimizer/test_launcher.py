from typing import Set, Optional
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import Mock, patch, AsyncMock, call

from guapow import __app_name__
from guapow.common.dto import OptimizationRequest
from guapow.service.optimizer.launcher import map_launchers_file, gen_possible_launchers_file_paths, \
    LauncherSearchMode, map_launchers_dict, ExplicitLauncherMapper, SteamLauncherMapper, LauncherMapperManager
from guapow.service.optimizer.profile import OptimizationProfile, LauncherSettings
from tests import RESOURCES_DIR, AsyncIterator, MockedAsyncCall


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
        self.mapper = ExplicitLauncherMapper(check_time=0.1, found_check_time=0, logger=self.logger)

    @patch(f'{__app_name__}.service.optimizer.launcher.map_launchers_file', side_effect=FileNotFoundError)
    async def test_map_pids__it_should_not_yield_when_no_launcher_files_available(self, map_launchers: Mock):
        request = OptimizationRequest(pid=123, command='/usr/local/bin/game', user_name='user')
        profile = new_steam_profile(enabled=False)

        async def map_pids() -> Set[int]:
            return {pid async for pid in self.mapper.map_pids(request, profile)}

        self.assertFalse(await map_pids())

        exp_file_paths = gen_possible_launchers_file_paths(user_id=123, user_name='user')
        map_launchers.assert_has_calls([call(fpath, self.logger) for fpath in exp_file_paths])

    @patch(f'{__app_name__}.service.optimizer.launcher.map_launchers_file')
    @patch(f'{__app_name__}.service.optimizer.launcher.async_syscall')
    async def test_map_pids__it_should_yield_pid_for_only_one_name_match(self, *mocks: AsyncMock):
        async_syscall, map_launchers = mocks[0], mocks[1]
        async_syscall.return_value = (0, "456 game_x86_64.bin\n789 other")
        map_launchers.return_value = {"game": ("game_x86_64.bin", LauncherSearchMode.NAME)}

        request = OptimizationRequest(pid=123, command='/usr/local/bin/game', user_name='user')
        profile = new_steam_profile(enabled=False)

        async def map_pids() -> Set[int]:
            return {pid async for pid in self.mapper.map_pids(request, profile)}

        mapped_pids = await map_pids()

        exp_file_paths = [*gen_possible_launchers_file_paths(user_id=123, user_name='user')]
        map_launchers.assert_awaited_once_with(exp_file_paths[0], self.logger)
        async_syscall.assert_awaited_once_with('ps -Ao pid,comm -ww --no-headers')

        self.assertEqual({456}, mapped_pids)

    @patch(f'{__app_name__}.service.optimizer.launcher.map_launchers_file')
    @patch(f'{__app_name__}.service.optimizer.launcher.async_syscall')
    async def test_map_pids__it_should_yield_pids_for_several_name_matches(self, *mocks: AsyncMock):
        async_syscall, map_launchers = mocks[0], mocks[1]
        async_syscall.return_value = (0, "456 game_x86_64.bin\n789 other\n1011 game_x86_64.bin")
        map_launchers.return_value = {"game": ("game_x86_64.bin", LauncherSearchMode.NAME)}

        request = OptimizationRequest(pid=123, command='/usr/local/bin/game', user_name='user')
        profile = new_steam_profile(enabled=False)

        async def map_pids() -> Set[int]:
            return {pid async for pid in self.mapper.map_pids(request, profile)}

        mapped_pids = await map_pids()

        exp_file_paths = [*gen_possible_launchers_file_paths(user_id=123, user_name='user')]
        map_launchers.assert_awaited_once_with(exp_file_paths[0], self.logger)
        async_syscall.assert_awaited_once_with('ps -Ao pid,comm -ww --no-headers')

        self.assertEqual({456, 1011}, mapped_pids)

    @patch(f'{__app_name__}.service.optimizer.launcher.map_launchers_file')
    @patch(f'{__app_name__}.service.optimizer.launcher.async_syscall')
    async def test_map_pids__it_should_yield_pid_for_matched_etc_launchers_file_when_no_user_file(self, *mocks: Mock):
        async_syscall, map_launchers = mocks[0], mocks[1]

        map_launchers.side_effect = [FileNotFoundError, {'game': ('game_x86_64.bin', LauncherSearchMode.NAME)}]
        async_syscall.return_value = (0, "456 game_x86_64.bin\n789 other\n")

        request = OptimizationRequest(pid=123, command='/usr/local/bin/game', user_name='user')
        profile = new_steam_profile(enabled=False)

        async def map_pids() -> Set[int]:
            return {pid async for pid in self.mapper.map_pids(request, profile)}

        mapped_pids = await map_pids()

        exp_file_paths = [*gen_possible_launchers_file_paths(user_id=123, user_name='user')]
        map_launchers.assert_has_calls([call(fpath, self.logger) for fpath in exp_file_paths])
        async_syscall.assert_awaited_with('ps -Ao pid,comm -ww --no-headers')

        self.assertEqual({456}, mapped_pids)

    @patch(f'{__app_name__}.service.optimizer.launcher.map_launchers_file')
    @patch(f'{__app_name__}.service.optimizer.launcher.async_syscall')
    async def test_map_pids__it_should_yield_pid_for_matched_etc_launchers_file_for_root_user_call(self, *mocks: Mock):
        async_syscall, map_launchers = mocks[0], mocks[1]
        map_launchers.return_value = {'game': ('game_x86_64.bin', LauncherSearchMode.NAME)}
        async_syscall.return_value = (0, "456 game_x86_64.bin\n789 other\n")

        request = OptimizationRequest(pid=123, command='/usr/local/bin/game', user_name='root')
        request.user_id = 0

        profile = new_steam_profile(enabled=False)

        async def map_pids() -> Set[int]:
            return {pid async for pid in self.mapper.map_pids(request, profile)}

        mapped_pids = await map_pids()

        map_launchers.assert_awaited_once_with(f'/etc/{__app_name__}/launchers', self.logger)
        async_syscall.assert_awaited_with('ps -Ao pid,comm -ww --no-headers')

        self.assertEqual(mapped_pids, await map_pids())

    @patch(f'{__app_name__}.service.optimizer.launcher.map_launchers_file')
    @patch(f'{__app_name__}.service.optimizer.launcher.async_syscall')
    async def test_map_pids__it_should_yield_pid_for_only_one_matched_launcher_mapped_cmd(self, *mocks: AsyncMock):
        async_syscall, map_launchers = mocks[0], mocks[1]

        map_launchers.return_value = {'game': ('/path/to/game_x86_64.bin', LauncherSearchMode.COMMAND)}
        async_syscall.return_value = (0, "456 /path/to/game_x86_64.bin\n789 other\n")

        request = OptimizationRequest(pid=123, command='/usr/local/bin/game', user_name='user')
        profile = new_steam_profile(enabled=False)

        async def map_pids() -> Set[int]:
            return {pid async for pid in self.mapper.map_pids(request, profile)}

        mapped_pids = await map_pids()
        map_launchers.assert_awaited_once()
        async_syscall.assert_awaited_once_with('ps -Ao pid,args -ww --no-headers')

        self.assertEqual({456}, mapped_pids)

    @patch(f'{__app_name__}.service.optimizer.launcher.map_launchers_file')
    @patch(f'{__app_name__}.service.optimizer.launcher.async_syscall')
    async def test_map_pids__it_should_yield_pid_for_mapped_name_regex(self, *mocks: AsyncMock):
        async_syscall, map_launchers = mocks[0], mocks[1]

        map_launchers.return_value = {'game': (' *game_x86_64.bin ', LauncherSearchMode.NAME)}
        async_syscall.return_value = (0, "456 /game_x86_64.bin\n789 other\n")

        request = OptimizationRequest(pid=123, command='/usr/local/bin/game', user_name='user')
        profile = new_steam_profile(enabled=False)

        async def map_pids() -> Set[int]:
            return {pid async for pid in self.mapper.map_pids(request, profile)}

        mapped_pids = await map_pids()

        exp_file_paths = [*gen_possible_launchers_file_paths(user_id=123, user_name='user')]
        map_launchers.assert_awaited_once_with(exp_file_paths[0], self.logger)
        async_syscall.assert_awaited_once_with('ps -Ao pid,comm -ww --no-headers')

        self.assertEqual({456}, mapped_pids)

    @patch(f'{__app_name__}.service.optimizer.launcher.map_launchers_file')
    @patch(f'{__app_name__}.service.optimizer.launcher.async_syscall')
    async def test_map_pids__it_should_yield_pid_for_mapped_cmd_regex(self, *mocks: Mock):
        async_syscall, map_launchers = mocks[0], mocks[1]

        map_launchers.return_value = {'game': ('/*game_x86_64.bin ', LauncherSearchMode.COMMAND)}
        async_syscall.return_value = (0, "456 /game_x86_64.bin\n789 other\n")

        request = OptimizationRequest(pid=123, command='/usr/local/bin/game', user_name='user')
        profile = new_steam_profile(enabled=False)

        async def map_pids() -> Set[int]:
            return {pid async for pid in self.mapper.map_pids(request, profile)}

        mapped_pids = await map_pids()

        map_launchers.assert_awaited_once()
        async_syscall.assert_awaited_once_with('ps -Ao pid,args -ww --no-headers')

        self.assertEqual({456}, mapped_pids)

    @patch(f'{__app_name__}.service.optimizer.launcher.map_launchers_file')
    @patch(f'{__app_name__}.service.optimizer.launcher.async_syscall')
    async def test_map_pids__it_should_yield_pid_for_matched_launcher_using_a_wild_card(self, *mocks: Mock):
        async_syscall, map_launchers = mocks[0], mocks[1]

        map_launchers.return_value = {'hl2.sh*': ('hl2.linux', LauncherSearchMode.NAME)}
        async_syscall.return_value = (0, "456 hl2.linux\n789 other\n")

        cmd = '/home/user/.local/share/Steam/steamapps/common/Team Fortress 2/hl2.sh -game tf -steam'
        request = OptimizationRequest(pid=123, command=cmd, user_name='user')
        profile = new_steam_profile(enabled=False)

        async def map_pids() -> Set[int]:
            return {pid async for pid in self.mapper.map_pids(request, profile)}

        mapped_pids = await map_pids()

        map_launchers.assert_awaited_once()
        async_syscall.assert_awaited_once_with('ps -Ao pid,comm -ww --no-headers')

        self.assertEqual({456}, mapped_pids)

    @patch(f'{__app_name__}.service.optimizer.launcher.async_syscall')
    async def test_map_pids__it_should_yield_pid_for_matched_launcher_via_profile(self, async_syscall: AsyncMock):
        async_syscall.return_value = (0, "456  /bin/proc_abc\n789  other\n")

        request = OptimizationRequest(pid=123, command='/home/user/.local/bin/proc1', user_name='user')
        profile = OptimizationProfile.empty('test')
        profile.launcher = LauncherSettings({'proc1': 'c%/bin/proc_abc'}, None)

        async def map_pids() -> Set[int]:
            return {pid async for pid in self.mapper.map_pids(request, profile)}

        mapped_pids = await map_pids()

        async_syscall.assert_awaited_once_with('ps -Ao pid,args -ww --no-headers')
        self.assertEqual({456}, mapped_pids)

    @patch(f'{__app_name__}.service.optimizer.launcher.async_syscall')
    async def test_map_pids__it_should_yield_pid_for_matched_launcher_via_profile_using_wildcards(self, *mocks: Mock):
        async_syscall = mocks[0]
        async_syscall.return_value = (0, "456  /bin/proc_abc\n789  other\n")

        request = OptimizationRequest(pid=123, command='/home/user/.local/bin/proc1', user_name='user')
        profile = OptimizationProfile.empty('test')
        profile.launcher = LauncherSettings({'proc1': 'c%/bin/proc_*'}, False)

        async def map_pids() -> Set[int]:
            return {pid async for pid in self.mapper.map_pids(request, profile)}

        mapped_pids = await map_pids()

        async_syscall.assert_awaited_once_with('ps -Ao pid,args -ww --no-headers')
        self.assertEqual({456}, mapped_pids)

    @patch(f'{__app_name__}.service.optimizer.launcher.async_syscall')
    async def test_map_pids__it_should_not_yield_when_defined_launchers_via_profile_are_invalid(self, *mocks: Mock):
        async_syscall = mocks[0]

        request = OptimizationRequest(pid=123, command='/home/user/.local/bin/proc1', user_name='user')
        profile = OptimizationProfile.empty('test')
        profile.launcher = LauncherSettings({'proc1': ''}, None)

        async def map_pids() -> Set[int]:
            return {pid async for pid in self.mapper.map_pids(request, profile)}

        mapped_pids = await map_pids()

        async_syscall.assert_not_awaited()
        self.assertEqual(set(), mapped_pids)

    @patch(f'{__app_name__}.service.optimizer.launcher.async_syscall')
    async def test_map_pids__it_should_not_yield_when_skip_mapping_is_true(self, async_syscall: AsyncMock):
        request = OptimizationRequest(pid=123, command='/home/user/.local/bin/proc1', user_name='user')
        profile = OptimizationProfile.empty('test')
        profile.launcher = LauncherSettings({'proc1': '/bin/proc1'}, True)

        async def map_pids() -> Set[int]:
            return {pid async for pid in self.mapper.map_pids(request, profile)}

        mapped_pids = await map_pids()

        async_syscall.assert_not_awaited()
        self.assertEqual(set(), mapped_pids)

    @patch(f'{__app_name__}.service.optimizer.launcher.map_launchers_file')
    @patch(f'{__app_name__}.service.optimizer.launcher.async_syscall')
    async def test_map_pids__it_should_yield_pid_for_several_matches_while_not_timed_out(self, *mocks: AsyncMock):
        async_syscall, map_launchers = mocks[0], mocks[1]

        mocked_call = MockedAsyncCall(results=[(0, "456  game_x86_64.bin\n789  other\n"),
                                               (0, "456  game_x86_64.bin\n789  other\n1011 game_x86_64.bin")],
                                      await_time=0.001)
        async_syscall.side_effect = mocked_call.call

        map_launchers.return_value = {"game": ("game_x86_64.bin", LauncherSearchMode.NAME)}

        request = OptimizationRequest(pid=123, command='/usr/local/bin/game', user_name='user')
        profile = new_steam_profile(enabled=False)

        self.mapper = ExplicitLauncherMapper(check_time=0.1, found_check_time=-1, iteration_sleep_time=0,
                                             logger=self.logger)

        async def map_pids() -> Set[int]:
            return {pid async for pid in self.mapper.map_pids(request, profile)}

        mapped_pids = await map_pids()

        exp_file_paths = [*gen_possible_launchers_file_paths(user_id=123, user_name='user')]
        map_launchers.assert_awaited_once_with(exp_file_paths[0], self.logger)
        async_syscall.assert_awaited_with('ps -Ao pid,comm -ww --no-headers')
        self.assertGreaterEqual(async_syscall.await_count, 2)

        self.assertEqual({456, 1011}, mapped_pids)

    @patch(f'{__app_name__}.service.optimizer.launcher.map_launchers_file')
    @patch(f'{__app_name__}.service.optimizer.launcher.async_syscall')
    async def test_map_pids__it_should_stop_yielding_when_found_timeout_is_reached(self, *mocks: AsyncMock):
        async_syscall, map_launchers = mocks[0], mocks[1]

        async_syscall.side_effect = [(0, "456  game_x86_64.bin\n789  other\n"),
                                     (0, "456  game_x86_64.bin\n789  other\n1011# game_x86_64.bin")]

        map_launchers.return_value = {"game": ("game_x86_64.bin", LauncherSearchMode.NAME)}

        request = OptimizationRequest(pid=123, command='/usr/local/bin/game', user_name='user')
        profile = new_steam_profile(enabled=False)

        # setting 'found_check_time' to zero, so the next iteration wouldn't happen
        self.mapper = ExplicitLauncherMapper(check_time=1, found_check_time=0, iteration_sleep_time=0,
                                             logger=self.logger)

        async def map_pids() -> Set[int]:
            return {pid async for pid in self.mapper.map_pids(request, profile)}

        mapped_pids = await map_pids()

        exp_file_paths = [*gen_possible_launchers_file_paths(user_id=123, user_name='user')]
        map_launchers.assert_awaited_once_with(exp_file_paths[0], self.logger)
        async_syscall.assert_awaited_with('ps -Ao pid,comm -ww --no-headers')
        self.assertEqual(1, async_syscall.await_count)

        self.assertEqual({456}, mapped_pids)


class SteamLauncherMapperTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.mapper = SteamLauncherMapper(check_time=0.1, found_check_time=0, iteration_sleep_time=0,
                                          logger=Mock())

    @patch(f"{__app_name__}.common.system.async_syscall", return_value=(0, """
            1403    2601 reaper
            2601    2602 ABC.x86_
            2601    2603 ABC.x86_-thread
    """))
    async def test_map_pids__yield_several_ids_when_native_command_not_from_runtime(self, async_syscall: AsyncMock):
        cmd = "/home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=999999 -- " \
              "/home/user/.local/share/Steam/ubuntu12_32/steam-launch-wrapper -- " \
              "/media/hd0/Steam/steamapps/common/Game/ABC.x86_"

        request = OptimizationRequest(pid=2601, command=cmd, user_name='user')
        profile = new_steam_profile(enabled=True)

        async def map_pids() -> Optional[Set[int]]:
            return {pid async for pid in self.mapper.map_pids(request, profile)}

        mapped_pids = await map_pids()
        async_syscall.assert_awaited_with("ps -Ao ppid,pid,comm -ww --no-headers")
        self.assertGreaterEqual(async_syscall.await_count, 1)
        self.assertEqual({2602, 2603}, mapped_pids)

    @patch(f"{__app_name__}.common.system.async_syscall", return_value=(0, """
       1403    11573 reaper
       11573   11574 pv-bwrap
       11574   11728 pressure-vessel
       11728   13786 ABC.x86_
       11728   13787 ABC.x86_-thread
    """))
    async def test_map_pids__yield_several_ids_when_native_command_from_runtime(self, async_syscall: AsyncMock):
        cmd = "/home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=245170 -- " \
              "/home/user/.local/share/Steam/ubuntu12_32/steam-launch-wrapper -- " \
              "/home/user/.local/share/Steam/steamapps/common/SteamLinuxRuntime_soldier/_v2-entry-point " \
              "--verb=waitforexitandrun -- " \
              "/home/user/.local/share/Steam/steamapps/common/SteamLinuxRuntime/scout-on-soldier-entry-point-v2 -- " \
              "/media/hd0/Steam/steamapps/common/Game/ABC.x86_"

        request = OptimizationRequest(pid=11573, command=cmd, user_name='user')
        profile = new_steam_profile(enabled=True)

        async def map_pids() -> Optional[Set[int]]:
            return {pid async for pid in self.mapper.map_pids(request, profile)}

        mapped_pids = await map_pids()
        async_syscall.assert_awaited_with("ps -Ao ppid,pid,comm -ww --no-headers")
        self.assertGreaterEqual(async_syscall.await_count, 1)
        self.assertEqual({13786, 13787}, mapped_pids)

    @patch(f"{__app_name__}.common.system.async_syscall", return_value=(0, """
        1435    5614 reaper
        5614    5615 python3
        5615    5661 Game_x64.exe
        5615    5662 Game_x64-thread
    """))
    async def test_map_pids__yield_several_ids_when_proton_command_not_from_runtime(self, async_syscall: AsyncMock):
        cmd = '/home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=123 -- ' \
              '/home/user/.local/share/Steam/steamapps/common/Proton 3.16/proton waitforexitandrun ' \
              '/home/user/.local/share/Steam/steamapps/common/Game II/Game_x64.exe'

        request = OptimizationRequest(pid=5614, command=cmd, user_name='user')
        profile = new_steam_profile(enabled=True)

        async def map_pids() -> Optional[Set[int]]:
            return {pid async for pid in self.mapper.map_pids(request, profile)}

        mapped_pids = await map_pids()
        async_syscall.assert_awaited_with("ps -Ao ppid,pid,comm -ww --no-headers")
        self.assertGreaterEqual(async_syscall.await_count, 1)
        self.assertEqual({5661, 5662}, mapped_pids)

    @patch(f"{__app_name__}.common.system.async_syscall")
    async def test_map_pids__yield_several_ids_when_proton_command_from_runtime(self, async_syscall: AsyncMock):
        mocked_call = MockedAsyncCall(results=[(0, """12 123  reaper
                                                      123 456   pv-bwrap
                                                      456  789   pressure-vessel
                                                      789  1011 python3
                                                      789  1213 Game_x64.exe"""),
                                               (0, """12 123  reaper
                                                      123 456   pv-bwrap
                                                      456  789   pressure-vessel
                                                      789  1011 python3
                                                      789  1213 Game_x64.exe
                                                      789  1214 Game_x64-thread""")  # one more child found
                                               ])
        async_syscall.side_effect = mocked_call.call

        cmd = '/home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=123 -- ' \
              '/home/user/.local/share/Steam/steamapps/common/SteamLinuxRuntime_soldier/_v2-entry-point ' \
              '--verb=waitforexitandrun -- ' \
              '/home/user/.local/share/Steam/steamapps/common/Proton 6.3/proton waitforexitandrun ' \
              '/home/user/.local/share/Steam/steamapps/common/Game II/Game_x64.exe'

        self.mapper = SteamLauncherMapper(check_time=0.5,  # using a higher wait time for this test case
                                          found_check_time=-1,
                                          logger=Mock())
        request = OptimizationRequest(pid=123, command=cmd, user_name='user')
        profile = new_steam_profile(enabled=True)

        async def map_pids() -> Optional[Set[int]]:
            return {pid async for pid in self.mapper.map_pids(request, profile)}

        mapped_pids = await map_pids()
        async_syscall.assert_awaited_with("ps -Ao ppid,pid,comm -ww --no-headers")
        self.assertGreaterEqual(async_syscall.await_count, 2)
        self.assertEqual({1213, 1214}, mapped_pids)

    @patch(f"{__app_name__}.common.system.async_syscall", return_value=(0, """
        1435    5614 reaper
        5614    30324 pv-bwrap
        30324   30408 pressure-vessel
        30408    5615 python3
        30408    5676 wineserver
        30408    5711 services.exe
        30408    5745 winedevice.exe
        30408    5760 plugplay.exe
        30408    5765 winedevice.exe
        30408    5774 explorer.exe
        30408    5775 OriginWebHelper
        30408    5776 Origin.exe
        30408    5777 OriginClientSer
        30408    5778 QtWebEngineProc
        30408    5779 EASteamProxy.ex
        30408    5780 PnkBstrA.exe
        30408    5781 UPlayBrowser.exe
        30408    5782 wine
        30408    5783 wine64
        30408    5784 proton
        30408    5785 gzip
        30408    5786 steam.exe
        30408    5787 python 
        30408    5661 Game_x64.exe
    """))
    async def test_map_pids__should_not_yield_ignored_processes(self, async_syscall: AsyncMock):
        cmd = '/home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=123 -- ' \
              '/home/user/.local/share/Steam/steamapps/common/SteamLinuxRuntime_soldier/_v2-entry-point ' \
              '--verb=waitforexitandrun -- ' \
              '/home/user/.local/share/Steam/steamapps/common/Proton 6.3/proton waitforexitandrun ' \
              '/home/user/.local/share/Steam/steamapps/common/Game II/Game_x64.exe'

        request = OptimizationRequest(pid=5614, command=cmd, user_name='user')
        profile = new_steam_profile(enabled=True)

        async def map_pids() -> Optional[Set[int]]:
            return {pid async for pid in self.mapper.map_pids(request, profile)}

        mapped_pids = await map_pids()
        async_syscall.assert_awaited_with("ps -Ao ppid,pid,comm -ww --no-headers")
        self.assertGreaterEqual(async_syscall.await_count, 1)
        self.assertEqual({5661}, mapped_pids)

    @patch(f"{__app_name__}.common.system.async_syscall", return_value=(0, """
        1435    5614 reaper
        5614    30324 pv-bwrap
        30324   30408 pressure-vessel
        30408    5615 python3
        30408    5676 wineserver
        30408    5661 Game_x64.exe
        5661     5662 wine64
        5662     5663 wineboot.exe
    """))
    async def test_map_pids__should_not_yield_ignored_that_are_children_of_targets(self, async_syscall: AsyncMock):
        cmd = '/home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=123 -- ' \
              '/home/user/.local/share/Steam/steamapps/common/SteamLinuxRuntime_soldier/_v2-entry-point ' \
              '--verb=waitforexitandrun -- ' \
              '/home/user/.local/share/Steam/steamapps/common/Proton 6.3/proton waitforexitandrun ' \
              '/home/user/.local/share/Steam/steamapps/common/Game II/Game_x64.exe'

        request = OptimizationRequest(pid=5614, command=cmd, user_name='user')
        profile = new_steam_profile(enabled=True)

        async def map_pids() -> Optional[Set[int]]:
            return {pid async for pid in self.mapper.map_pids(request, profile)}

        mapped_pids = await map_pids()
        async_syscall.assert_awaited_with("ps -Ao ppid,pid,comm -ww --no-headers")
        self.assertGreaterEqual(async_syscall.await_count, 1)
        self.assertEqual({5661}, mapped_pids)

    @patch(f"{__app_name__}.common.system.async_syscall", return_value=(0, """
        1435    5614 reaper
        5614    30324 pv-bwrap
        30324   30408 pressure-vessel
        30408    5661 Game_x64.exe
        30408    5662 Game_thread <defunct>
    """))
    async def test_map_pids__should_not_yield_defunct_processes(self, async_syscall: AsyncMock):
        cmd = '/home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=123 -- ' \
              '/home/user/.local/share/Steam/steamapps/common/SteamLinuxRuntime_soldier/_v2-entry-point ' \
              '--verb=waitforexitandrun -- ' \
              '/home/user/.local/share/Steam/steamapps/common/Proton 6.3/proton waitforexitandrun ' \
              '/home/user/.local/share/Steam/steamapps/common/Game II/Game_x64.exe'

        request = OptimizationRequest(pid=5614, command=cmd, user_name='user')
        profile = new_steam_profile(enabled=True)

        async def map_pids() -> Optional[Set[int]]:
            return {pid async for pid in self.mapper.map_pids(request, profile)}

        mapped_pids = await map_pids()
        async_syscall.assert_awaited_with("ps -Ao ppid,pid,comm -ww --no-headers")
        self.assertGreaterEqual(async_syscall.await_count, 1)
        self.assertEqual({5661}, mapped_pids)

    @patch(f"{__app_name__}.common.system.async_syscall", return_value=(0, """
        1435    5614 reaper
        5614    30324 pv-bwrap
        30324   30408 pressure-vessel
        30408    5661 Game_x64.exe
        30408    5662 pressure-vessel
        30408    5663 pv-bwrap
        30408    5664 reaper
    """))
    async def test_map_pids__should_not_yield_children_with_name_in_hierachy(self, async_syscall: AsyncMock):
        cmd = '/home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=123 -- ' \
              '/home/user/.local/share/Steam/steamapps/common/SteamLinuxRuntime_soldier/_v2-entry-point ' \
              '--verb=waitforexitandrun -- ' \
              '/home/user/.local/share/Steam/steamapps/common/Proton 6.3/proton waitforexitandrun ' \
              '/home/user/.local/share/Steam/steamapps/common/Game II/Game_x64.exe'

        request = OptimizationRequest(pid=5614, command=cmd, user_name='user')
        profile = new_steam_profile(enabled=True)

        async def map_pids() -> Optional[Set[int]]:
            return {pid async for pid in self.mapper.map_pids(request, profile)}

        mapped_pids = await map_pids()
        async_syscall.assert_awaited_with("ps -Ao ppid,pid,comm -ww --no-headers")
        self.assertGreaterEqual(async_syscall.await_count, 1)
        self.assertEqual({5661}, mapped_pids)

    @patch(f"{__app_name__}.common.system.async_syscall", return_value=(0, """
        1435    5614 reaper
        5614    30324 pv-bwrap
        30324   30408 pressure-vessel
        30408    5661 Game_x64.exe
        5661     5662 pressure-vessel
        5662     5663 pv-bwrap
        5663     5664 reaper
    """))
    async def test_map_pids__should_not_yield_children_of_children_with_name_in_hierachy(self, async_syscall: AsyncMock):
        cmd = '/home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=123 -- ' \
              '/home/user/.local/share/Steam/steamapps/common/SteamLinuxRuntime_soldier/_v2-entry-point ' \
              '--verb=waitforexitandrun -- ' \
              '/home/user/.local/share/Steam/steamapps/common/Proton 6.3/proton waitforexitandrun ' \
              '/home/user/.local/share/Steam/steamapps/common/Game II/Game_x64.exe'

        request = OptimizationRequest(pid=5614, command=cmd, user_name='user')
        profile = new_steam_profile(enabled=True)

        async def map_pids() -> Optional[Set[int]]:
            return {pid async for pid in self.mapper.map_pids(request, profile)}

        mapped_pids = await map_pids()
        async_syscall.assert_awaited_with("ps -Ao ppid,pid,comm -ww --no-headers")
        self.assertGreaterEqual(async_syscall.await_count, 1)
        self.assertEqual({5661}, mapped_pids)

    @patch(f"{__app_name__}.common.system.async_syscall", return_value=(0, """
        12 123  reaper
        123 456   pv-bwrap
        456  789   pressure-vessel
        789  1011 python3
        789  1213 Game_x64.exe
        789  1214 Game_x64-thread   
    """))
    async def test_map_pids__yield_children_until_timeout_is_reached(self, async_syscall: AsyncMock):
        cmd = '/home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=123 -- ' \
              '/home/user/.local/share/Steam/steamapps/common/SteamLinuxRuntime_soldier/_v2-entry-point ' \
              '--verb=waitforexitandrun -- ' \
              '/home/user/.local/share/Steam/steamapps/common/Proton 6.3/proton waitforexitandrun ' \
              '/home/user/.local/share/Steam/steamapps/common/Game II/Game_x64.exe'

        request = OptimizationRequest(pid=123, command=cmd, user_name='user')
        profile = new_steam_profile(enabled=True)

        async def map_pids() -> Optional[Set[int]]:
            return {pid async for pid in self.mapper.map_pids(request, profile)}

        mapped_pids = await map_pids()
        async_syscall.assert_awaited_with("ps -Ao ppid,pid,comm -ww --no-headers")
        self.assertGreaterEqual(async_syscall.await_count, 1)
        self.assertEqual({1213, 1214}, mapped_pids)

    @patch(f"{__app_name__}.common.system.async_syscall", return_value=(0, """
        12 123  reaper
        123 456   pv-bwrap
        456  789   pressure-vessel
        789  1011 python3
    """))
    async def test_map_pids__yield_nothing_when_no_children_is_found(self, async_syscall: AsyncMock):
        cmd = '/home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=123 -- ' \
              '/home/user/.local/share/Steam/steamapps/common/SteamLinuxRuntime_soldier/_v2-entry-point ' \
              '--verb=waitforexitandrun -- ' \
              '/home/user/.local/share/Steam/steamapps/common/Proton 6.3/proton waitforexitandrun ' \
              '/home/user/.local/share/Steam/steamapps/common/Game II/Game_x64.exe'

        request = OptimizationRequest(pid=123, command=cmd, user_name='user')
        profile = new_steam_profile(enabled=True)

        async def map_pids() -> Optional[Set[int]]:
            return {pid async for pid in self.mapper.map_pids(request, profile)}

        mapped_pids = await map_pids()
        async_syscall.assert_awaited_with("ps -Ao ppid,pid,comm -ww --no-headers")
        self.assertGreaterEqual(async_syscall.await_count, 1)
        self.assertEqual(set(), mapped_pids)

    @patch(f"{__app_name__}.common.system.async_syscall")
    async def test_map_pids__it_should_stopping_yielding_if_found_check_time_reached(self, *mocks: AsyncMock):
        async_syscall = mocks[0]

        async_syscall.side_effect = [(0, "1403    2601 reaper\n2601    2602 ABC.x86_"),
                                     (0, """1403    2601 reaper
                                            2601    2602 ABC.x86_
                                            2601    2603 ABC.x86_-thread""")]

        cmd = "/home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=999999 -- " \
              "/home/user/.local/share/Steam/ubuntu12_32/steam-launch-wrapper -- " \
              "/media/hd0/Steam/steamapps/common/Game/ABC.x86_"

        self.mapper = SteamLauncherMapper(check_time=0.1, found_check_time=0, iteration_sleep_time=0.001, logger=Mock())
        request = OptimizationRequest(pid=2601, command=cmd, user_name='user')
        profile = new_steam_profile(enabled=True)

        async def map_pids() -> Optional[Set[int]]:
            return {pid async for pid in self.mapper.map_pids(request, profile)}

        mapped_pids = await map_pids()
        async_syscall.assert_awaited_with("ps -Ao ppid,pid,comm -ww --no-headers")
        self.assertEqual(1, async_syscall.await_count)
        self.assertEqual({2602}, mapped_pids)

    @patch(f"{__app_name__}.common.system.async_syscall", return_value=(0, """
            1403    2601 reaper
            2601    2602 ABC.x86_
            2602    2603 ABC.x86_-thread
            2603    2604 ABC.x86_-thread-2
    """))
    async def test_map_pids__it_should_not_yield_children_of_target_children(self, async_syscall: AsyncMock):
        cmd = "/home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=999999 -- " \
              "/home/user/.local/share/Steam/ubuntu12_32/steam-launch-wrapper -- " \
              "/media/hd0/Steam/steamapps/common/Game/ABC.x86_"

        request = OptimizationRequest(pid=2601, command=cmd, user_name='user')
        profile = new_steam_profile(enabled=True)

        async def map_pids() -> Optional[Set[int]]:
            return {pid async for pid in self.mapper.map_pids(request, profile)}

        mapped_pids = await map_pids()
        async_syscall.assert_awaited_with("ps -Ao ppid,pid,comm -ww --no-headers")
        self.assertGreaterEqual(async_syscall.await_count, 1)
        self.assertEqual({2602}, mapped_pids)

    def test_map_expected_hierarchy__when_proton_command(self):
        cmd = "/home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=443860 -- " \
              "/home/user/.local/share/Steam/ubuntu12_32/steam-launch-wrapper -- " \
              "/media/ssd_01/Steam/steamapps/common/Proton 3.16/proton waitforexitandrun " \
              "/media/ssd_01/Steam/steamapps/common/Game AB Defghij/Game_x64.exe"
        request = OptimizationRequest(pid=2601, command=cmd, user_name='user')

        expected_hierarchy = ["python3", "reaper"]
        self.assertEqual(expected_hierarchy, self.mapper.map_expected_hierarchy(request, "reaper"))

    def test_map_expected_hierarchy__when_proton_command_executed_from_container(self):
        cmd = "/home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=622020 -- " \
              "/home/user/.local/share/Steam/ubuntu12_32/steam-launch-wrapper -- " \
              "/home/user/.local/share/Steam/steamapps/common/SteamLinuxRuntime_soldier/_v2-entry-point " \
              "--verb=waitforexitandrun -- /home/user/.local/share/Steam/steamapps/common/Proton 7.0/proton " \
              "waitforexitandrun /media/ssd_02/Steam/steamapps/common/Game Abc & def/ABC.exe"
        request = OptimizationRequest(pid=2601, command=cmd, user_name='user')

        expected_hierarchy = ["pressure-vessel", "pv-bwrap", "reaper"]
        self.assertEqual(expected_hierarchy, self.mapper.map_expected_hierarchy(request, "reaper"))

    def test_map_expected_hierarchy__when_native_command(self):
        cmd = "/home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=245170 -- " \
              "/home/user/.local/share/Steam/ubuntu12_32/steam-launch-wrapper -- " \
              "/media/ssd_02/Steam/steamapps/common/Game/Game.x86_64-pc-linux-gnu"
        request = OptimizationRequest(pid=2601, command=cmd, user_name='user')

        expected_hierarchy = ["reaper"]
        self.assertEqual(expected_hierarchy, self.mapper.map_expected_hierarchy(request, "reaper"))

    def test_map_expected_hierarchy__when_native_command_from_container(self):
        cmd = "/home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=245170 -- " \
              "/home/user/.local/share/Steam/ubuntu12_32/steam-launch-wrapper -- " \
              "/home/user/.local/share/Steam/steamapps/common/SteamLinuxRuntime_soldier/_v2-entry-point " \
              "--verb=waitforexitandrun -- " \
              "/home/user/.local/share/Steam/steamapps/common/SteamLinuxRuntime/scout-on-soldier-entry-point-v2 -- " \
              "/media/ssd_02/Steam/steamapps/common/Game/Game.x86_64-pc-linux-gnu"
        request = OptimizationRequest(pid=2601, command=cmd, user_name='user')

        expected_hierarchy = ["pressure-vessel", "pv-bwrap", "reaper"]
        self.assertEqual(expected_hierarchy, self.mapper.map_expected_hierarchy(request, "reaper"))

    def test_extract_root_process_name__must_return_the_first_command_call_name(self):
        cmd = "/home/user/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=622020 -- " \
              "/home/user/.local/share/Steam/ubuntu12_32/steam-launch-wrapper -- " \
              "/home/user/.local/share/Steam/steamapps/common/SteamLinuxRuntime_soldier/_v2-entry-point " \
              "--verb=waitforexitandrun -- /home/user/.local/share/Steam/steamapps/common/Proton 7.0/proton " \
              "waitforexitandrun /media/ssd_02/Steam/steamapps/common/Game Abc & def/ABC.exe"

        root_cmd = self.mapper.extract_root_process_name(cmd)
        self.assertEqual("reaper", root_cmd)

    def test_find_target_in_hierarchy__return_the_root_id_when_just_one_element_hierarchy(self):
        hierarchy = ["reaper"]
        pids_by_comm = dict()

        target_id = self.mapper.find_target_in_hierarchy(reverse_hierarchy=hierarchy, root_element_pid=456,
                                                         processes_by_parent=dict(), pid_by_comm=pids_by_comm)
        self.assertEqual(456, target_id)

    def test_find_target_in_hierarchy__return_the_target_child_id_when_parent_has_children_first_run(self):
        hierarchy = ["pressure-vessel", "pv-bwrap", "reaper"]
        pids_by_comm = dict()
        parent_procs = {
            123: {(456, "reaper")},
            456: {(789, "pv-bwrap")},
            789: {(1011, "pressure-vessel")}
        }

        target_id = self.mapper.find_target_in_hierarchy(reverse_hierarchy=hierarchy, root_element_pid=456,
                                                         processes_by_parent=parent_procs, pid_by_comm=pids_by_comm)
        self.assertEqual(1011, target_id)
        self.assertEqual({"pressure-vessel": 1011, "pv-bwrap": 789, "reaper": 456}, pids_by_comm)

    def test_find_target_in_hierarchy__return_the_target_child_id_when_parent_has_children_on_second_run(self):
        hierarchy = ["pressure-vessel", "pv-bwrap", "reaper"]
        pids_by_comm = dict()
        first_mapping = {
            123: {(456, "reaper")},
            456: {(789, "pv-bwrap")},
        }

        target_id_first_run = self.mapper.find_target_in_hierarchy(reverse_hierarchy=hierarchy, root_element_pid=456,
                                                                   processes_by_parent=first_mapping,
                                                                   pid_by_comm=pids_by_comm)
        self.assertIsNone(target_id_first_run)
        self.assertEqual({"pv-bwrap": 789, "reaper": 456}, pids_by_comm)

        second_mapping = {**first_mapping, 789: {(1011, "pressure-vessel")}}

        target_id_second_run = self.mapper.find_target_in_hierarchy(reverse_hierarchy=hierarchy, root_element_pid=456,
                                                                    processes_by_parent=second_mapping,
                                                                    pid_by_comm=pids_by_comm)
        self.assertEqual(1011, target_id_second_run)
        self.assertEqual({"pressure-vessel": 1011, "pv-bwrap": 789, "reaper": 456}, pids_by_comm)

    def test_find_target_in_hierarchy__return_the_latest_target_child_id_when_multiple_matches(self):
        hierarchy = ["pressure-vessel", "pv-bwrap", "reaper"]
        pids_by_comm = dict()
        parent_procs = {
            123: {(456, "reaper")},
            456: {(789, "pv-bwrap")},
            789: {(1011, "pressure-vessel"), (1012, "pressure-vessel")}
        }

        target_id = self.mapper.find_target_in_hierarchy(reverse_hierarchy=hierarchy, root_element_pid=456,
                                                         processes_by_parent=parent_procs, pid_by_comm=pids_by_comm)
        self.assertEqual(1012, target_id)
        self.assertEqual({"pressure-vessel": 1012, "pv-bwrap": 789, "reaper": 456}, pids_by_comm)

    def test_to_ignore__must_contain_ea_origin_processes(self):
        expected_processes = {"OriginWebHelper", "Origin.exe", "OriginClientSer", "QtWebEngineProc",
                              "EASteamProxy.ex", "UPlayBrowser.exe", "ldconfig", "EALink.exe", "OriginLegacyCLI",
                              "IGOProxy.exe", "IGOProxy64.exe", "igoproxy64.exe", "ActivationUI.ex"}

        self.assertTrue(expected_processes.issubset(self.mapper.to_ignore))

    def test_to_ignore__must_contain_wine_processes(self):
        expected_processes = {"wineserver", "services.exe", "winedevice.exe", "plugplay.exe", "svchost.exe",
                              "explorer.exe", "rpcss.exe", "tabtip.exe", "wine", "wine64", "wineboot.exe",
                              "cmd.exe", "conhost.exe", "start.exe"}

        self.assertTrue(expected_processes.issubset(self.mapper.to_ignore))

    def test_to_ignore__must_contain_proton_processes(self):
        expected_processes = {"steam-runtime-l", "proton", "gzip", "steam.exe", "python", "python3"}
        self.assertTrue(expected_processes.issubset(self.mapper.to_ignore))

    def test_to_ignore__must_contain_anticheat_processes(self):
        expected_processes = {"PnkBstrA.exe"}
        self.assertTrue(expected_processes.issubset(self.mapper.to_ignore))

    def test_to_ignore__must_contain_unknown_unneeded_processes(self):
        expected_processes = {"whql:off"}
        self.assertTrue(expected_processes.issubset(self.mapper.to_ignore))

    def test_to_ignore__must_contain_ubisoft_launcher_processes(self):
        expected_processes = {"UPlayBrowser.exe", "UbisoftGameLaun", "upc.exe", "UplayService.ex",
                              "UplayWebCore.ex", "CrRendererMain", "regsvr32", "CrGpuMain", "CrUtilityMain"}
        self.assertTrue(expected_processes.issubset(self.mapper.to_ignore))


class ProcessLauncherManagerTest(IsolatedAsyncioTestCase):

    async def test_map_pids__should_try_to_retrieve_pid_until_a_mapper_returns_a_pid(self):
        # first sub-mapper that would inspect the request, but no process would be returned
        mocked_mapper = Mock()
        mocked_mapper.map_pids = Mock(return_value=AsyncIterator([]))

        # second sub-mapper that would inspect the request and actually find the process
        steam_mapper = SteamLauncherMapper(check_time=30, found_check_time=0, logger=Mock())
        steam_mapper.map_pids = Mock(return_value=AsyncIterator([456]))

        manager = LauncherMapperManager(check_time=30, found_check_time=0, logger=Mock(),
                                        mappers=(mocked_mapper, steam_mapper))

        request = OptimizationRequest(pid=123, command='/abc', user_name='user')
        profile = new_steam_profile(enabled=True)

        async def map_pids() -> Optional[Set[int]]:
            return {pid async for pid in manager.map_pids(request, profile)}

        self.assertEqual({456}, await map_pids())

        mocked_mapper.map_pids.assert_called_once()
        steam_mapper.map_pids.assert_called_once()

    async def test_get_sub_mappers__order(self):
        manager = LauncherMapperManager(check_time=30, found_check_time=0, logger=Mock())
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
