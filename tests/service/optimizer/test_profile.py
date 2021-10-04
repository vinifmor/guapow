from unittest import TestCase, IsolatedAsyncioTestCase
from unittest.mock import Mock, patch, AsyncMock, call

from guapow import __app_name__
from guapow.common.config import OptimizerConfig
from guapow.common.model_util import FileModelFiller
from guapow.common.profile import StopProcessSettings
from guapow.service.optimizer.profile import CPUSchedulingPolicy, IOSchedulingClass, CPUSettings, \
    GPUSettings, ProcessSchedulingSettings, ProcessSettings, OptimizationProfileReader, ProcessNiceSettings, \
    OptimizationProfile, OptimizationProfileCache, cache_profiles, IOScheduling
from tests import RESOURCES_DIR


class CPUSchedulingPolicyTest(TestCase):

    def test_from_str__should_convert_a_upper_string_match(self):
        self.assertEqual(CPUSchedulingPolicy.OTHER, CPUSchedulingPolicy.from_str('OTHER'))

    def test_from_str__should_convert_a_lower_string_match(self):
        self.assertEqual(CPUSchedulingPolicy.RR, CPUSchedulingPolicy.from_str('rr'))

    def test_from_str__should_convert_different_cases_string_match(self):
        self.assertEqual(CPUSchedulingPolicy.FIFO, CPUSchedulingPolicy.from_str('FiFo'))

    def test_fifo__should_support_priority(self):
        self.assertTrue(CPUSchedulingPolicy.FIFO.requires_priority())

    def test_rr__should_support_priority(self):
        self.assertTrue(CPUSchedulingPolicy.RR.requires_priority())

    def test_other__should_not_support_priority(self):
        self.assertFalse(CPUSchedulingPolicy.OTHER.requires_priority())

    def test_batch__should_not_support_priority(self):
        self.assertFalse(CPUSchedulingPolicy.BATCH.requires_priority())

    def test_idle__should_not_support_priority(self):
        self.assertFalse(CPUSchedulingPolicy.IDLE.requires_priority())


class IOSchedulingClassTest(TestCase):

    def test_from_str__should_convert_a_upper_string_match(self):
        self.assertEqual(IOSchedulingClass.REALTIME, IOSchedulingClass.from_str('REALTIME'))

    def test_from_str__should_convert_a_lower_string_match(self):
        self.assertEqual(IOSchedulingClass.BEST_EFFORT, IOSchedulingClass.from_str('best_effort'))

    def test_from_str__should_convert_different_cases_string_match(self):
        self.assertEqual(IOSchedulingClass.IDLE, IOSchedulingClass.from_str('IdlE'))

    def test_realtime__should_support_priority(self):
        self.assertTrue(IOSchedulingClass.REALTIME.supports_priority())

    def test_best_effort__should_support_priority(self):
        self.assertTrue(IOSchedulingClass.BEST_EFFORT.supports_priority())

    def test_idle__should_not_support_priority(self):
        self.assertFalse(IOSchedulingClass.IDLE.supports_priority())


class IOSchedulingTest(TestCase):

    def test_is_valid__true_when_ioclass_is_defined(self):
        sched = IOScheduling(ioclass=IOSchedulingClass.REALTIME, nice_level=None)
        self.assertTrue(sched.is_valid())

    def test_is_valid__false_when_ioclass_is_defined(self):
        sched = IOScheduling(ioclass=None, nice_level=1)
        self.assertFalse(sched.is_valid())


class ProcessSchedulingSettingsTest(TestCase):

    def test_has_valid_priority__false_when_less_than_1(self):
        proc_cpu = ProcessSchedulingSettings(policy=CPUSchedulingPolicy.FIFO, policy_priority=0)
        self.assertFalse(proc_cpu.has_valid_priority())

    def test_has_valid_priority__true_when_equal_to_1(self):
        proc_cpu = ProcessSchedulingSettings(policy=CPUSchedulingPolicy.FIFO, policy_priority=1)
        self.assertTrue(proc_cpu.has_valid_priority())

    def test_has_valid_priority__false_when_higher_than_99(self):
        proc_cpu = ProcessSchedulingSettings(policy=CPUSchedulingPolicy.FIFO, policy_priority=100)
        self.assertFalse(proc_cpu.has_valid_priority())
    
    def test_has_valid_priority__true_when_equal_to_99(self):
        proc_cpu = ProcessSchedulingSettings(policy=CPUSchedulingPolicy.FIFO, policy_priority=99)
        self.assertTrue(proc_cpu.has_valid_priority())

    def test_has_valid_priority__false_when_policy_does_not_support(self):
        proc_cpu = ProcessSchedulingSettings(policy=CPUSchedulingPolicy.OTHER, policy_priority=50)
        self.assertFalse(proc_cpu.has_valid_priority())

    def test_is_valid__false_if_no_property_is_defined(self):
        proc_cpu = ProcessSchedulingSettings(policy=None, policy_priority=None)
        self.assertFalse(proc_cpu.is_valid())

    def test_is_valid__true_if_only_policy_is_defined(self):
        proc_cpu = ProcessSchedulingSettings(policy=CPUSchedulingPolicy.OTHER)
        self.assertTrue(proc_cpu.is_valid())


class ProcessSettingsTest(TestCase):

    def setUp(self):
        self.proc = ProcessSettings(None)
        self.proc.scheduling = None
        self.proc.io = None
        self.proc.nice = None

    def test_is_valid__false_when_no_property_is_valid(self):
        self.assertFalse(self.proc.is_valid())

    def test_is_valid__true_if_only_a_valid_nice_level_is_defined(self):
        self.proc.nice = ProcessNiceSettings(nice_level=-1, delay=None, watch=None)
        self.assertTrue(self.proc.is_valid())

    def test_is_valid__true_if_only_the_nice_level_is_set_to_zero(self):
        self.proc.nice = ProcessNiceSettings(nice_level=0, delay=None, watch=None)
        self.assertTrue(self.proc.is_valid())

    def test_has_valid_cpu_affinity__false_when_there_are_values_less_than_zero(self):
        self.proc.cpu_affinity = [-1, 0]
        self.assertFalse(self.proc.has_valid_cpu_affinity(2))

    def test_has_valid_cpu_affinity__false_when_there_are_values_equal_to_cpu_count(self):
        self.proc.cpu_affinity = [0, 2]
        self.assertFalse(self.proc.has_valid_cpu_affinity(2))

    def test_has_valid_cpu_affinity__false_when_there_are_values_higher_than_cpu_count(self):
        self.proc.cpu_affinity = [0, 3]
        self.assertFalse(self.proc.has_valid_cpu_affinity(2))

    def test_has_valid_cpu_affinity__true_when_there_are_values_less_than_cpu_count(self):
        self.proc.cpu_affinity = [0, 1]
        self.assertTrue(self.proc.has_valid_cpu_affinity(2))

    def test_is_valid__true_if_only_cpu_affinity_is_defined(self):
        self.proc.cpu_affinity = [0]
        self.assertTrue(self.proc.is_valid())


class CPUSettingsTest(TestCase):

    def test_is_valid__false_if_no_property_is_defined(self):
        cpu = CPUSettings(performance=None)
        self.assertFalse(cpu.is_valid())

    def test_is_valid__true_if_only_performance_is_defined(self):
        cpu = CPUSettings(performance=False)
        self.assertTrue(cpu.is_valid())


class GPUSettingsTest(TestCase):

    def test_is_valid__false_when_performance_is_none(self):
        settings = GPUSettings(performance=None)
        self.assertFalse(settings.is_valid())


class OptimizationProfileReaderTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.reader = OptimizationProfileReader(FileModelFiller(Mock()), Mock(), None)

    async def test_read__return_a_profile_with_only_valid_io_settings_defined(self):
        profile_path = f'{RESOURCES_DIR}/only_valid_io.profile'
        profile = await self.reader.read(profile_path=profile_path)
        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_valid())
        self.assertIsNone(profile.steam)
        self.assertIsNone(profile.cpu)

        self.assertIsNotNone(profile.process)
        self.assertIsNotNone(profile.process.io)

        self.assertTrue(profile.process.io.is_valid())
        self.assertEqual(IOSchedulingClass.BEST_EFFORT, profile.process.io.ioclass)
        self.assertEqual(3, profile.process.io.nice_level)

    async def test_read__return_a_profile_with_only_valid_cpu_settings_defined(self):
        profile_path = f'{RESOURCES_DIR}/only_valid_cpu.profile'
        profile = await self.reader.read(profile_path=profile_path)
        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_valid())

        self.assertIsNone(profile.steam)
        self.assertIsNone(profile.gpu)
        self.assertIsNone(profile.process)

        self.assertIsNotNone(profile.cpu)
        self.assertTrue(profile.cpu.is_valid())
        self.assertFalse(profile.cpu.performance)

    async def test_read__return_a_profile_with_only_valid_process_settings_defined(self):
        profile_path = f'{RESOURCES_DIR}/only_valid_process.profile'
        profile = await self.reader.read(profile_path=profile_path)
        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_valid())
        self.assertIsNone(profile.steam)
        self.assertIsNone(profile.gpu)

        self.assertIsNotNone(profile.process)
        self.assertTrue(profile.process.scheduling.is_valid())
        self.assertIsNotNone(profile.process.nice)
        self.assertEqual(-10, profile.process.nice.level)
        self.assertIsNone(profile.process.nice.watch)
        self.assertEqual(CPUSchedulingPolicy.FIFO, profile.process.scheduling.policy)
        self.assertEqual(2, profile.process.scheduling.priority)
        self.assertEqual([0, 1], profile.process.cpu_affinity)

    async def test_read_return_a_profile_with_nice_watching_settings(self):
        profile_path = f'{RESOURCES_DIR}/nice_watch.profile'
        profile = await self.reader.read(profile_path=profile_path)
        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_valid())

        self.assertIsNotNone(profile.process)
        self.assertIsNotNone(profile.process.nice)
        self.assertTrue(profile.process.nice.is_valid())
        self.assertEqual(-1, profile.process.nice.level)
        self.assertEqual(True, profile.process.nice.watch)
        self.assertIsNone(profile.process.nice.delay)

    async def test_read_return_a_profile_with_nice_watching_settings_off(self):
        profile_path = f'{RESOURCES_DIR}/nice_no_watch.profile'
        profile = await self.reader.read(profile_path=profile_path)
        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_valid())

        self.assertIsNotNone(profile.process)
        self.assertIsNotNone(profile.process.nice)
        self.assertTrue(profile.process.nice.is_valid())
        self.assertEqual(-1, profile.process.nice.level)
        self.assertEqual(False, profile.process.nice.watch)
        self.assertIsNone(profile.process.nice.delay)

    async def test_read__should_ignore_lines_starting_with_sharps(self):
        profile_path = f'{RESOURCES_DIR}/lines_starting_with_sharps.profile'
        profile = await self.reader.read(profile_path=profile_path)
        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_valid())
        self.assertIsNone(profile.steam)
        self.assertIsNone(profile.cpu)

        self.assertIsNotNone(profile.process)
        self.assertIsNone(profile.process.nice)
        self.assertIsNone(profile.process.scheduling.priority)
        self.assertEqual(CPUSchedulingPolicy.IDLE, profile.process.scheduling.policy)

    async def test_read__should_not_ignore_the_value_content_starting_with_sharps(self):
        profile_path = f'{RESOURCES_DIR}/values_containing_sharps.profile'
        profile = await self.reader.read(profile_path=profile_path)
        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_valid())
        self.assertIsNone(profile.steam)

        self.assertIsNotNone(profile.process)
        self.assertIsNotNone(profile.process.nice)
        self.assertEqual(1, profile.process.nice.level)  # nice_level = 1#0
        self.assertIsNone(profile.process.scheduling)  # policy = # iso
        self.assertEqual([0], profile.process.cpu_affinity)

    async def test_read__return_valid_cpu_proc_and_io_settings(self):
        profile_path = f'{RESOURCES_DIR}/valid_cpu_proc_and_io.profile'
        profile = await self.reader.read(profile_path=profile_path)

        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_valid())

        self.assertIsNone(profile.steam)

        self.assertIsNotNone(profile.process)
        self.assertIsNotNone(profile.process.io)
        self.assertTrue(profile.process.io.is_valid())
        self.assertEqual(IOSchedulingClass.REALTIME, profile.process.io.ioclass)
        self.assertEqual(1, profile.process.io.nice_level)

        self.assertIsNotNone(profile.cpu)
        self.assertTrue(profile.cpu.is_valid())
        self.assertTrue(profile.cpu.performance)

        self.assertIsNotNone(profile.process)
        self.assertIsNotNone(profile.process.nice)
        self.assertEqual(-11, profile.process.nice.level)
        self.assertEqual(CPUSchedulingPolicy.FIFO, profile.process.scheduling.policy)
        self.assertEqual(20, profile.process.scheduling.priority)
        self.assertEqual([0], profile.process.cpu_affinity)

    async def test_read__return_valid_steam_settings(self):
        profile_path = f'{RESOURCES_DIR}/valid_steam.profile'
        profile = await self.reader.read(profile_path=profile_path)

        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_valid())

        self.assertIsNone(profile.process)
        self.assertIsNone(profile.cpu)

        self.assertTrue(profile.steam)

    async def test_read__must_not_return_invalid_steam_settings(self):
        profile_path = f'{RESOURCES_DIR}/invalid_steam.profile'
        profile = await self.reader.read(profile_path=profile_path)

        self.assertIsNotNone(profile)
        self.assertFalse(profile.is_valid())

        self.assertIsNone(profile.cpu)
        self.assertIsNone(profile.steam)

    async def test_read__return_a_profile_with_valid_gpu_settings(self):
        profile_path = f'{RESOURCES_DIR}/gpu_valid.profile'
        profile = await self.reader.read(profile_path=profile_path)

        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_valid())

        self.assertIsNone(profile.cpu)
        self.assertIsNone(profile.steam)

        self.assertIsNotNone(profile.gpu)
        self.assertFalse(profile.gpu.performance)

    async def test_read__return_a_profile_with_only_invalid_settings(self):
        profile_path = f'{RESOURCES_DIR}/gpu_invalid.profile'
        profile = await self.reader.read(profile_path=profile_path)

        self.assertIsNotNone(profile)
        self.assertFalse(profile.is_valid())

        self.assertIsNone(profile.cpu)
        self.assertIsNone(profile.steam)
        self.assertIsNone(profile.gpu)

    async def test_read__return_a_profile_with_valid_settings_and_others_commented(self):
        profile_path = f'{RESOURCES_DIR}/valid_and_commented.profile'
        profile = await self.reader.read(profile_path=profile_path)

        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_valid())

        self.assertIsNone(profile.process)
        self.assertIsNone(profile.cpu)
        self.assertIsNone(profile.steam)

        self.assertIsNotNone(profile.gpu)
        self.assertTrue(profile.gpu.performance)
        self.assertTrue(profile.is_valid())

    async def test__must_merge_additional_settings_to_valid_profile_settings(self):
        profile_path = f'{RESOURCES_DIR}/only_valid_process.profile'
        profile = await self.reader.read(profile_path, 'gpu.performance=1\nsteam=true')

        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_valid())

        self.assertIsNotNone(profile.gpu)
        self.assertTrue(profile.gpu.performance)
        self.assertTrue(profile.steam)

    async def test_read__must_overwrite_valid_profile_settings_for_the_additional_provided(self):
        profile_path = f'{RESOURCES_DIR}/only_valid_process.profile'
        profile = await self.reader.read(profile_path, 'proc.policy.priority=5')

        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_valid())

        self.assertIsNotNone(profile.process)
        self.assertEqual(5, profile.process.scheduling.priority)  # file defines '2'

    async def test_read__must_not_merge_additional_settings_to_invalid_profile(self):
        profile_path = f'{RESOURCES_DIR}/only_valid_process.profile'
        profile = await self.reader.read(profile_path, 'proc.cpu.policy.priority=abc')

        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_valid())

        self.assertIsNotNone(profile.process)
        self.assertEqual(2, profile.process.scheduling.priority)  # file defines '2'

    async def test_read__must_read_valid_post_scripts(self):
        profile_path = f'{RESOURCES_DIR}/only_after_scripts.profile'
        profile = await self.reader.read(profile_path)

        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_valid())

        self.assertIsNotNone(profile.after_scripts)
        self.assertTrue(profile.after_scripts.is_valid())

        self.assertFalse(profile.after_scripts.run_as_root)  # false by default
        self.assertEqual(2, len(profile.after_scripts.scripts))
        self.assertEqual(['/xpto', '/abc'], profile.after_scripts.scripts)

    async def test_read__valid_post_scripts_can_be_set_to_run_as_root(self):
        profile_path = f'{RESOURCES_DIR}/only_after_scripts_root.profile'
        profile = await self.reader.read(profile_path)

        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_valid())

        self.assertIsNotNone(profile.after_scripts)
        self.assertTrue(profile.after_scripts.is_valid())

        self.assertTrue(profile.after_scripts.run_as_root)
        self.assertEqual(2, len(profile.after_scripts.scripts))
        self.assertEqual(['/xpto', '/abc'], profile.after_scripts.scripts)

    async def test_read__must_read_valid_finish_scripts(self):
        profile_path = f'{RESOURCES_DIR}/only_finish_scripts.profile'
        profile = await self.reader.read(profile_path)

        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_valid())

        self.assertIsNotNone(profile.finish_scripts)
        self.assertTrue(profile.finish_scripts.is_valid())

        self.assertFalse(profile.finish_scripts.run_as_root)  # false by default
        self.assertEqual(2, len(profile.finish_scripts.scripts))
        self.assertEqual(['/xpto', '/abc'], profile.finish_scripts.scripts)

    async def test_read__valid_finish_scripts_can_be_set_to_run_as_root(self):
        profile_path = f'{RESOURCES_DIR}/only_finish_scripts_root.profile'
        profile = await self.reader.read(profile_path)

        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_valid())

        self.assertIsNotNone(profile.finish_scripts)
        self.assertTrue(profile.finish_scripts.is_valid())

        self.assertTrue(profile.finish_scripts.run_as_root)
        self.assertEqual(2, len(profile.finish_scripts.scripts))
        self.assertEqual(['/xpto', '/abc'], profile.finish_scripts.scripts)

    async def test_read__return_a_profile_with_only_compositor_valid_settings(self):
        profile_path = f'{RESOURCES_DIR}/only_compositor.profile'
        profile = await self.reader.read(profile_path)

        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_valid())

        self.assertIsNotNone(profile.compositor)
        self.assertTrue(profile.compositor.off)

    async def test_read__return_a_profile_with_only_invalid_compositor_settings(self):
        profile_path = f'{RESOURCES_DIR}/only_invalid_compositor.profile'
        profile = await self.reader.read(profile_path)

        self.assertIsNotNone(profile)
        self.assertFalse(profile.is_valid())

        self.assertIsNone(profile.compositor)

    async def test_read__return_a_valid_profile_without_launchers_defined(self):
        profile_path = f'{RESOURCES_DIR}/only_compositor.profile'
        profile = await self.reader.read(profile_path)

        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_valid())
        self.assertIsNone(profile.launcher)

    async def test_read__return_a_valid_profile_with_only_launchers_defined(self):
        profile_path = f'{RESOURCES_DIR}/only_launchers.profile'
        profile = await self.reader.read(profile_path)

        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_valid())
        self.assertIsNotNone(profile.launcher)
        self.assertIsNone(profile.launcher.skip_mapping)
        self.assertIsNotNone(profile.launcher.mapping)

        self.assertEqual(6, len(profile.launcher.mapping))

        expected_mappping = {
            'proc1': '/bin/proc1',
            'proc2': '/bin/*/proc2',
            'proc3*': '/bin/proc3*',
            'proc4': '/proc4:c',
            'proc5': 'proc7:n',
            'proc.bat': 'xpto.e'
        }

        for laucher, target in expected_mappping.items():
            self.assertIn(laucher, profile.launcher.mapping)
            self.assertEqual(target, profile.launcher.mapping[laucher])

    async def test_read__return_a_valid_profile_with_only_skip_mapping_launcher_defined(self):
        profile_path = f'{RESOURCES_DIR}/only_skip_launcher_mapping.profile'
        profile = await self.reader.read(profile_path)
        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_valid())
        self.assertIsNotNone(profile.launcher)
        self.assertIsNone(profile.launcher.mapping)
        self.assertTrue(profile.launcher.skip_mapping)

    async def test_read__return_valid_profile_with_only_simple_properties(self):
        profile_path = f'{RESOURCES_DIR}/simple_props.profile'

        profile = await self.reader.read(profile_path)
        self.assertIsNotNone(profile)

        self.assertIsNotNone(profile.cpu)
        self.assertTrue(profile.cpu.is_valid())
        self.assertTrue(profile.cpu.performance)

        self.assertIsNotNone(profile.gpu)
        self.assertTrue(profile.gpu.is_valid())
        self.assertTrue(profile.gpu.performance)

        self.assertIsNotNone(profile.compositor)
        self.assertTrue(profile.compositor.is_valid())
        self.assertTrue(profile.compositor.off)

        self.assertIsNotNone(profile.finish_scripts)
        self.assertTrue(profile.finish_scripts.is_valid())
        self.assertTrue(profile.finish_scripts.wait_execution)

        self.assertTrue(profile.steam)

        self.assertIsNotNone(profile.launcher)
        self.assertTrue(profile.launcher.is_valid())
        self.assertTrue(profile.launcher.skip_mapping)

        self.assertTrue(profile.hide_mouse)

    async def test_read__return_valid_profile_with_hide_mouse_defined(self):
        profile_path = f'{RESOURCES_DIR}/hide_mouse.profile'

        profile = await self.reader.read(profile_path)
        self.assertIsNotNone(profile)
        self.assertTrue(profile.hide_mouse)

    async def test_read__return_valid_profile_with_stop_after_launch_settings(self):
        profile_path = f'{RESOURCES_DIR}/stop_after.profile'

        profile = await self.reader.read(profile_path)
        self.assertIsNotNone(profile)
        self.assertIsNotNone(profile.stop_after)
        self.assertEqual({'abc', '/bin/xpto'}, profile.stop_after.processes)
        self.assertTrue(profile.stop_after.relaunch)

    async def test_read_valid__must_cache_valid_profile_when_cache_is_defined(self):
        profile_path = f'{RESOURCES_DIR}/only_valid_cpu.profile'
        cache = OptimizationProfileCache(Mock())
        self.reader._cache = cache

        self.assertIsNone(cache.get(profile_path, None))

        profile = await self.reader.read_valid(profile_path, None)
        self.assertIsInstance(profile, OptimizationProfile)
        self.assertTrue(profile.is_valid())

        self.assertEqual(profile, cache.get(profile_path, None))

        self.reader.read = AsyncMock()
        profile_2 = await self.reader.read_valid(profile_path, None)
        self.assertEqual(profile, profile_2)
        self.reader.read.assert_not_called()

    async def test_read_valid__must_cache_valid_profile_with_additional_settings_when_cache_is_defined(self):
        profile_path = f'{RESOURCES_DIR}/only_valid_cpu.profile'
        add_settings = 'compositor.off'

        cache = OptimizationProfileCache(Mock())
        self.reader._cache = cache

        self.assertIsNone(cache.get(profile_path, add_settings))

        profile = await self.reader.read_valid(profile_path, add_settings)
        self.assertIsInstance(profile, OptimizationProfile)
        self.assertTrue(profile.is_valid())

        self.assertEqual(profile, cache.get(profile_path, add_settings))

    async def test_read_valid__must_not_cache_valid_profile_when_cache_is_not_defined(self):
        profile_path = f'{RESOURCES_DIR}/only_valid_cpu.profile'
        self.reader._cache = None

        profile = await self.reader.read_valid(profile_path, None)
        self.assertIsInstance(profile, OptimizationProfile)
        self.assertTrue(profile.is_valid())

    async def test_read_valid__must_not_cache_invalid_profile_when_cache_is_defined(self):
        profile_path = f'{RESOURCES_DIR}/gpu_invalid.profile'
        cache = OptimizationProfileCache(Mock())
        self.reader._cache = cache

        self.assertIsNone(cache.get(profile_path, None))

        profile = await self.reader.read_valid(profile_path, None)
        self.assertIsNone(profile)

        self.assertIsNone(cache.get(profile_path, None))


class OptimizationProfileTest(TestCase):

    def test_set_path__non_empty_path(self):
        exp_path = f'{RESOURCES_DIR}/test .123.profile'
        instance = OptimizationProfile.empty(exp_path)
        self.assertEqual(exp_path, instance.path)
        self.assertEqual('test .123', instance.name)

    def test_is_valid__true_when_only_hide_mouse_is_defined(self):
        profile = OptimizationProfile.empty(None)
        profile.hide_mouse = False
        self.assertTrue(profile.is_valid())

    def test_is_valid__true_when_only_processes_to_stop_after_launch_are_defined(self):
        profile = OptimizationProfile.empty('test')
        profile.stop_after = StopProcessSettings(node_name='', processes={'a'}, relaunch=False)
        self.assertTrue(profile.is_valid())

    def test_is_valid__false_when_no_processes_to_stop_after_launch_is_defined(self):
        profile = OptimizationProfile.empty('test')
        profile.stop_after = StopProcessSettings(node_name='', processes=set(), relaunch=True)
        self.assertFalse(profile.is_valid())

    def test_from_optimizer_config__return_none_when_config_is_invalid(self):
        config = OptimizerConfig.empty()
        self.assertIsNone(OptimizationProfile.from_optimizer_config(config))

    def test_from_optimizer_config__return_an_instance_when_cpu_performance_is_true(self):
        config = OptimizerConfig.empty()
        config.cpu_performance = True
        profile = OptimizationProfile.from_optimizer_config(config)
        self.assertIsNotNone(profile)
        self.assertIsNotNone(profile.cpu)
        self.assertTrue(profile.cpu.performance)


class CacheProfilesTest(IsolatedAsyncioTestCase):

    @patch(f'{__app_name__}.service.optimizer.profile.get_profile_dir', return_value=f'{RESOURCES_DIR}/cache')
    async def test__must_cache_only_valid_profiles(self, get_profile_dir: Mock):
        cache = OptimizationProfileCache(Mock())
        reader = OptimizationProfileReader(model_filler=FileModelFiller(Mock()),
                                           logger=Mock(),
                                           cache=cache)
        await cache_profiles(reader, Mock())
        get_profile_dir.assert_has_calls([call(0, 'root'), call(1, '*')], any_order=True)

        self.assertEqual(1, cache.size)

        cached_profile = cache.get(f'{RESOURCES_DIR}/cache/valid.profile')
        self.assertIsInstance(cached_profile, OptimizationProfile)
        self.assertTrue(cached_profile.is_valid())
