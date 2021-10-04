from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, patch

from guapow import __app_name__
from guapow.common.dto import OptimizationRequest
from guapow.common.profile import StopProcessSettings
from guapow.service.optimizer.gpu import NvidiaGPUDriver, GPUPowerMode, GPUState, AMDGPUDriver
from guapow.service.optimizer.profile import OptimizationProfile
from guapow.service.optimizer.flow import OptimizationQueue
from guapow.service.optimizer.task.model import OptimizedProcess, OptimizationContext
from guapow.service.optimizer.watch import DeadProcessWatcher


class DeadProcessWatcherTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.context = OptimizationContext.empty()
        self.context.logger = Mock()
        self.context.queue = OptimizationQueue.empty()

    async def test_watch__must_set_processes_stopped_before_the_optimized_process_launch_that_should_be_relaunched(self):
        watcher = DeadProcessWatcher(check_interval=1, restore_man=Mock(), context=self.context, to_relaunch={})

        request = OptimizationRequest(pid=123, user_name='test', created_at=1, command='/a', stopped_processes={'a': '/a', 'b': '/b'},
                                      relaunch_stopped_processes=True)
        profile = OptimizationProfile.empty('test')
        profile.stop_after = None

        proc = OptimizedProcess(request, 1, profile)

        await watcher.watch(proc)
        self.assertEqual({'a': '/a', 'b': '/b'}, watcher.get_to_relaunch_view())

    async def test_watch__must_not_set_processes_stopped_before_the_optimized_process_launch_that_should_not_be_relaunched(self):
        watcher = DeadProcessWatcher(check_interval=1, restore_man=Mock(), context=self.context, to_relaunch={})

        request = OptimizationRequest(pid=123, user_name='test', created_at=1, command='/a', stopped_processes={'a': '/a', 'b': '/b'},
                                      relaunch_stopped_processes=False)
        profile = OptimizationProfile.empty('test')
        profile.stop_after = None

        proc = OptimizedProcess(request, 1, profile)

        await watcher.watch(proc)
        self.assertEqual({}, watcher.get_to_relaunch_view())

    async def test_watch__must_update_a_cached_process_to_be_relaunched_command_when_it_does_not_start_with_a_forward_slash(self):
        watcher = DeadProcessWatcher(check_interval=1, restore_man=Mock(), context=self.context, to_relaunch={'a': 'a'})

        request = OptimizationRequest(pid=123, user_name='test', created_at=1, command='/a', stopped_processes={'a': '/a'},
                                      relaunch_stopped_processes=True)
        profile = OptimizationProfile.empty('test')

        proc = OptimizedProcess(request, 1, profile)

        await watcher.watch(proc)
        self.assertEqual({'a': '/a'}, watcher.get_to_relaunch_view())

    async def test_watch__must_set_processes_stopped_after_the_optimized_process_launch_that_should_be_relaunched(self):
        watcher = DeadProcessWatcher(check_interval=1, restore_man=Mock(), context=self.context, to_relaunch={})

        request = OptimizationRequest(pid=123, user_name='test', created_at=1, command='/a', stopped_processes=None)
        profile = OptimizationProfile.empty('test')
        profile.stop_after = StopProcessSettings(node_name='', processes={'b', 'c', 'd'}, relaunch=True)
        proc = OptimizedProcess(request, 1, profile)
        proc.stopped_after_launch = {'b': '/b', 'c': '/c'}

        await watcher.watch(proc)
        self.assertEqual({'b': '/b', 'c': '/c'}, watcher.get_to_relaunch_view())

    async def test_watch__must_not_set_processes_stopped_after_the_optimized_process_launch_that_should_not_be_relaunched(self):
        watcher = DeadProcessWatcher(check_interval=1, restore_man=Mock(), context=self.context, to_relaunch={})

        request = OptimizationRequest(pid=123, user_name='test', created_at=1, command='/a', stopped_processes=None)
        profile = OptimizationProfile.empty('test')
        profile.stop_after = StopProcessSettings(node_name='', processes={'b', 'c', 'd'}, relaunch=False)
        proc = OptimizedProcess(request, 1, profile)
        proc.stopped_after_launch = {'b', 'c'}

        await watcher.watch(proc)
        self.assertEqual({}, watcher.get_to_relaunch_view())

    @patch(f'{__app_name__}.service.optimizer.watch.system.read_current_pids', return_value={2})  # process 1 is not active anymore
    async def test_map_context__must_not_return_gpus_still_in_use_for_active_processes(self, read_current_pids: Mock):
        pid_1_states = {NvidiaGPUDriver: {GPUState('0', NvidiaGPUDriver, GPUPowerMode.ON_DEMAND),
                                          GPUState('1', NvidiaGPUDriver, GPUPowerMode.ON_DEMAND)},
                        AMDGPUDriver: {GPUState('0', AMDGPUDriver, GPUPowerMode.AUTO)}}

        pid_2_states = {NvidiaGPUDriver: {GPUState('0', NvidiaGPUDriver, GPUPowerMode.ON_DEMAND)}}

        request_1 = OptimizationRequest(pid=1, user_name='user', command='/bin')
        request_2 = OptimizationRequest(pid=2, user_name='user', command='/bin')

        watched = [OptimizedProcess(request=request_1, created_at=21321321, previous_gpus_states=pid_1_states),
                   OptimizedProcess(request=request_2, created_at=21382320, previous_gpus_states=pid_2_states)]

        watcher = DeadProcessWatcher(check_interval=1, restore_man=Mock(), to_watch=watched, context=self.context)

        context = await watcher.map_context()
        self.assertIsNotNone(context)

        self.assertIsNone(context.restorable_cpus)
        self.assertIsNone(context.pids_to_stop)
        self.assertIsNotNone(context.restorable_gpus)

        self.assertEqual(2, len(context.restorable_gpus))
        self.assertIn(NvidiaGPUDriver, context.restorable_gpus)

        nvidia_to_restore = context.restorable_gpus[NvidiaGPUDriver]
        self.assertIsNotNone(nvidia_to_restore)
        self.assertEqual(1, len(nvidia_to_restore))
        self.assertIn(GPUState('1', NvidiaGPUDriver, GPUPowerMode.ON_DEMAND), nvidia_to_restore)

        self.assertIn(AMDGPUDriver, context.restorable_gpus)
        amd_to_restore = context.restorable_gpus[AMDGPUDriver]
        self.assertIsNotNone(amd_to_restore)
        self.assertEqual(1, len(amd_to_restore))
        self.assertIn(GPUState('0', AMDGPUDriver, GPUPowerMode.AUTO), amd_to_restore)

        read_current_pids.assert_called_once()

    @patch(f'{__app_name__}.service.optimizer.watch.system.read_current_pids', return_value={1})  # process 2 is not active anymore
    async def test_map_context__must_not_return_gpus_when_all_are_in_use(self, read_current_pids: Mock):
        pid_1_states = {NvidiaGPUDriver: {GPUState('0', NvidiaGPUDriver, GPUPowerMode.ON_DEMAND),
                                          GPUState('1', NvidiaGPUDriver, GPUPowerMode.ON_DEMAND)},
                        AMDGPUDriver: {GPUState('0', AMDGPUDriver, GPUPowerMode.AUTO)}}

        pid_2_states = {NvidiaGPUDriver: {GPUState('0', NvidiaGPUDriver, GPUPowerMode.ON_DEMAND)}}

        request_1 = OptimizationRequest(pid=1, user_name='user', command='/bin')
        request_2 = OptimizationRequest(pid=2, user_name='user', command='/bin')

        watched = [OptimizedProcess(request=request_1, created_at=21312312, previous_gpus_states=pid_1_states),
                   OptimizedProcess(request=request_2, created_at=34343312, previous_gpus_states=pid_2_states)]

        watcher = DeadProcessWatcher(check_interval=1, to_watch=watched, restore_man=Mock(), context=self.context)

        context = await watcher.map_context()
        self.assertIsNotNone(context)

        self.assertIsNone(context.restorable_cpus)
        self.assertIsNone(context.pids_to_stop)
        self.assertIsNone(context.restorable_gpus)
        read_current_pids.assert_called_once()

    @patch(f'{__app_name__}.service.optimizer.watch.system.read_current_pids', return_value={3, 5, 7})
    async def test_map_context__must_return_related_pids_that_are_still_alive(self, read_current_pids: Mock):
        request_1 = OptimizationRequest(pid=1, user_name='user', command='/bin', related_pids={4, 5})  # 4: dead, 5: alive
        request_2 = OptimizationRequest(pid=2, user_name='user', command='/bin', related_pids={7})     # 7: alive
        request_3 = OptimizationRequest(pid=3, user_name='user', command='/bin', related_pids={9})     # 3 alive, so 9 must not be returned

        watched = [OptimizedProcess(request=request_1, created_at=21321321),
                   OptimizedProcess(request=request_2, created_at=21321322),
                   OptimizedProcess(request=request_3, created_at=21321323)]

        watcher = DeadProcessWatcher(check_interval=1, restore_man=Mock(), to_watch=watched, context=self.context)

        context = await watcher.map_context()
        self.assertIsNotNone(context)
        self.assertIsNone(context.restorable_cpus)
        self.assertIsNone(context.restorable_gpus)
        self.assertEqual({5, 7}, context.pids_to_stop)

        read_current_pids.assert_called_once()

    @patch(f'{__app_name__}.service.optimizer.watch.system.read_current_pids', side_effect=[{2}, set(), set()])
    async def test_map_context__processes_to_relaunch_scenario_01(self, read_current_pids: Mock):
        request_1 = OptimizationRequest(pid=1, stopped_processes={'a': '/a', 'b': '/b', 'c': '/c'}, user_name='user', command='/bin', relaunch_stopped_processes=True)
        request_2 = OptimizationRequest(pid=2, stopped_processes={'a': 'a', 'c': 'c'}, user_name='user', command='/bin', relaunch_stopped_processes=True)
        watched = [OptimizedProcess(request=request_1, created_at=21321321), OptimizedProcess(request=request_2, created_at=21321322)]

        to_relaunch = {}
        watcher = DeadProcessWatcher(check_interval=1, restore_man=Mock(), to_watch=watched, to_relaunch=to_relaunch, context=self.context)
        self.assertEqual({'a': '/a', 'b': '/b', 'c': '/c'}, to_relaunch)

        #  process 1 dies: all processes not associated with process 2 must be returned
        context = await watcher.map_context()
        self.assertIsNotNone(context.stopped_processes)
        self.assertEqual([('b', '/b')], context.stopped_processes)
        self.assertEqual({'a': '/a', 'c': '/c'}, to_relaunch)

        #  process 2 dies: all remaining processes must be returned
        context = await watcher.map_context()
        self.assertIsNotNone(context.stopped_processes)
        self.assertEqual(2, len(context.stopped_processes))
        self.assertIn(('a', '/a'), context.stopped_processes)
        self.assertIn(('c', '/c'), context.stopped_processes)
        self.assertEqual(0, len(to_relaunch))

        self.assertEqual(2, read_current_pids.call_count)

    @patch(f'{__app_name__}.service.optimizer.watch.system.read_current_pids', side_effect=[{2}, set()])
    async def test_map_context__processes_to_relaunch_scenario_02(self, read_current_pids: Mock):
        request_1 = OptimizationRequest(pid=1, user_name='user', command='/bin', stopped_processes={'a': '/a', 'b': '/b', 'c': '/c'}, relaunch_stopped_processes=True)
        request_2 = OptimizationRequest(pid=2, user_name='user', command='/bin', stopped_processes={'a': '/a', 'c': '/c'}, relaunch_stopped_processes=False)
        watched = [OptimizedProcess(request=request_1, created_at=21321321), OptimizedProcess(request=request_2, created_at=21321322)]

        to_relaunch = {}
        watcher = DeadProcessWatcher(check_interval=1, restore_man=Mock(), to_watch=watched, to_relaunch=to_relaunch, context=self.context)
        self.assertEqual({'a': '/a', 'b': '/b', 'c': '/c'}, to_relaunch)

        # process 1 dies: all processes not related to process 2 should be relaunched.
        context = await watcher.map_context()
        self.assertIsNotNone(context.stopped_processes)
        self.assertEqual([('b', '/b')], context.stopped_processes)

        # process 2 dies: all processes previously defined as "to relaunch" must be returned because of process 1 settings
        context = await watcher.map_context()
        self.assertIsNotNone(context.stopped_processes)
        self.assertEqual(2, len(context.stopped_processes))
        self.assertIn(('a', '/a'), context.stopped_processes)
        self.assertIn(('c', '/c'), context.stopped_processes)
        self.assertEqual(0, len(to_relaunch))

        self.assertEqual(2, read_current_pids.call_count)

    @patch(f'{__app_name__}.service.optimizer.watch.system.read_current_pids', side_effect=[{2}, set()])
    async def test_map_context__processes_to_relaunch_scenario_03(self, read_current_pids: Mock):
        request_1 = OptimizationRequest(pid=1, user_name='user', command='/bin', stopped_processes={'a': '/a', 'b': '/b', 'c': '/c'},
                                        relaunch_stopped_processes=False)
        request_2 = OptimizationRequest(pid=2, user_name='user', command='/bin', stopped_processes={'a': '/a', 'c': '/c'},
                                        relaunch_stopped_processes=True)

        watched = [OptimizedProcess(request=request_1, created_at=21321321), OptimizedProcess(request=request_2, created_at=21321322)]

        to_relaunch = {}
        watcher = DeadProcessWatcher(check_interval=1, restore_man=Mock(), to_watch=watched, to_relaunch=to_relaunch, context=self.context)
        self.assertEqual({'a': '/a', 'c': '/c'}, to_relaunch)

        # process 1 dies: no process must be returned since "relaunch" is set to false
        context = await watcher.map_context()
        self.assertIsNone(context.stopped_processes)
        self.assertEqual({'a': '/a', 'c': '/c'}, to_relaunch)

        # process 2  dies: two processes must be returned
        context = await watcher.map_context()
        self.assertIsNotNone(context.stopped_processes)
        self.assertEqual(2, len(context.stopped_processes))
        self.assertIn(('a', '/a'), context.stopped_processes)
        self.assertIn(('c', '/c'), context.stopped_processes)
        self.assertEqual(0, len(to_relaunch))

        self.assertEqual(2, read_current_pids.call_count)

    @patch(f'{__app_name__}.service.optimizer.watch.system.read_current_pids', side_effect=[{2}, set()])
    async def test_map_context__processes_to_relaunch_scenario_04(self, read_current_pids: Mock):
        request_1 = OptimizationRequest(pid=1, user_name='user', command='/bin', stopped_processes={'a': '/a', 'b': '/b', 'c': '/c'},
                                        relaunch_stopped_processes=False)
        request_2 = OptimizationRequest(pid=2, user_name='user', command='/bin', stopped_processes={'a': '/a', 'c': '/c'},
                                        relaunch_stopped_processes=False)

        watched = [OptimizedProcess(request=request_1, created_at=21321321), OptimizedProcess(request=request_2, created_at=21321322)]

        to_relaunch = {}
        watcher = DeadProcessWatcher(check_interval=1, restore_man=Mock(), to_watch=watched, to_relaunch=to_relaunch, context=self.context)
        self.assertEqual(0, len(to_relaunch))

        # process 1 dies: no process must be returned since "relaunch" is set to false
        context = await watcher.map_context()
        self.assertIsNone(context.stopped_processes)
        self.assertEqual(0, len(to_relaunch))

        # process 2 dies: no process must be returned since "relaunch" is set to false
        context = await watcher.map_context()
        self.assertIsNone(context.stopped_processes)
        self.assertEqual(0, len(to_relaunch))

        self.assertEqual(2, read_current_pids.call_count)

    @patch(f'{__app_name__}.service.optimizer.watch.system.read_current_pids', return_value=set())
    async def test_map_context__processes_to_relaunch_scenario_05(self, read_current_pids: Mock):
        request_1 = OptimizationRequest(pid=1, stopped_processes={'a': '/a', 'b': None, 'c': '/c'}, user_name='user', command='/bin', relaunch_stopped_processes=True)
        watched = [OptimizedProcess(request=request_1, created_at=21321321)]

        to_relaunch = {}
        watcher = DeadProcessWatcher(check_interval=1, restore_man=Mock(), to_watch=watched, to_relaunch=to_relaunch, context=self.context)
        self.assertEqual({'a': '/a', 'b': None, 'c': '/c'}, to_relaunch)

        #  process 1 dies: all processes not associated with process 2 must be returned (except those without commands)
        context = await watcher.map_context()
        self.assertEqual({'b'}, context.not_stopped_processes)
        self.assertEqual([('a', '/a'), ('c', '/c')], context.stopped_processes)
        self.assertEqual({}, to_relaunch)  # cleans all process to be relaunched (not not stopped)

        self.assertEqual(1, read_current_pids.call_count)

    @patch(f'{__app_name__}.service.optimizer.watch.system.read_current_pids', side_effect=[{1}, set(), set()])
    async def test_map_context__processes_to_relaunch_scenario_06(self, read_current_pids: Mock):
        request_1 = OptimizationRequest(pid=1, stopped_processes={'a': '/a', 'b': None, 'c': '/c'}, user_name='user', command='/bin', relaunch_stopped_processes=True)
        request_2 = OptimizationRequest(pid=2, stopped_processes={'a': 'a', 'b': '/b'}, user_name='user', command='/bin', relaunch_stopped_processes=True)
        watched = [OptimizedProcess(request=request_1, created_at=21321321), OptimizedProcess(request=request_2, created_at=21321322)]

        to_relaunch = {}
        watcher = DeadProcessWatcher(check_interval=1, restore_man=Mock(), to_watch=watched, to_relaunch=to_relaunch, context=self.context)
        self.assertEqual({'a': '/a', 'b': '/b', 'c': '/c'}, to_relaunch)

        # 'b' was not stopped by the request 1, but was for the 2 (so it will be possible to relaunch it

        #  process 2 dies: all processes not associated with process 1 must be returned
        context = await watcher.map_context()
        self.assertIsNone(context.stopped_processes)  # 'all processes from request 2 are associated with 1
        self.assertIsNone(context.not_stopped_processes)
        self.assertEqual({'a': '/a', 'b': '/b', 'c': '/c'}, to_relaunch)

        #  process 1 dies: all remaining processes must be returned
        context = await watcher.map_context()
        self.assertIsNotNone(context.stopped_processes)
        self.assertIn(('a', '/a'), context.stopped_processes)
        self.assertIn(('b', '/b'), context.stopped_processes)  # even 'b' command was unknown for request 1, it was known for 2
        self.assertIn(('c', '/c'), context.stopped_processes)
        self.assertIsNone(context.not_stopped_processes)
        self.assertEqual(0, len(to_relaunch))

        self.assertEqual(2, read_current_pids.call_count)
