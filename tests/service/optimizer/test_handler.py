from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, MagicMock, patch, call, AsyncMock

from guapow import __app_name__
from guapow.common.dto import OptimizationRequest
from guapow.common.model_util import FileModelFiller
from guapow.service.optimizer.handler import OptimizationHandler
from guapow.service.optimizer.profile import OptimizationProfile, CPUSettings, OptimizationProfileReader, \
    ProcessSettings, ProcessNiceSettings
from guapow.service.optimizer.flow import OptimizationQueue
from guapow.service.optimizer.task.model import OptimizationContext, OptimizedProcess
from tests import RESOURCES_DIR


def get_test_user_profile_path(name: str, user_name: str):
    return f'{RESOURCES_DIR}/{name}.profile'


def get_test_root_profile_path(name: str):
    return f'{RESOURCES_DIR}/root/{name}.profile'


class OptimizationHandlerTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.context = OptimizationContext.empty()
        self.context.logger = Mock()
        self.context.launcher_mapping_timeout = 1
        self.request = OptimizationRequest(pid=32479274927, profile='test', command='/xpto', user_name='test')
        self.reader = OptimizationProfileReader(model_filler=FileModelFiller(Mock()), cache=None, logger=Mock())
        self.context.queue = OptimizationQueue({self.request.pid})

    @patch('time.time', return_value=1)
    @patch('os.path.exists', return_value=True)
    @patch(f'{__app_name__}.service.optimizer.handler.run_tasks', return_value=None)
    async def test_handle__must_handle_request_with_a_full_valid_configuration_defined(self, run_tasks: Mock, os_path_exists: Mock, time: Mock):
        tasks_man = MagicMock()
        tasks_man.get_available_environment_tasks = AsyncMock(return_value=None)

        self.request.config = 'cpu.performance=1'

        handler = OptimizationHandler(context=self.context, tasks_man=tasks_man, watcher_man=Mock(), profile_reader=self.reader)
        await handler.handle(self.request)

        os_path_exists.assert_called_once_with(f'/proc/{self.request.pid}')

        expected_profile = OptimizationProfile.empty(None)
        expected_profile.cpu = CPUSettings(True)

        expected_process = OptimizedProcess(request=self.request, profile=expected_profile, created_at=1)

        tasks_man.get_available_environment_tasks.assert_called_once_with(expected_process)
        run_tasks.assert_not_called()
        time.assert_called()

    @patch('os.path.exists', return_value=True)
    @patch(f'{__app_name__}.service.optimizer.handler.run_tasks', return_value=None)
    @patch(f'{__app_name__}.service.optimizer.handler.time.time', return_value=123456789)
    async def test_handle__must_watch_request_with_related_pids_but_invalid_config(self, time_mock: Mock, run_tasks: Mock, os_path_exists: Mock):
        tasks_man = MagicMock()
        tasks_man.get_available_environment_tasks = AsyncMock(return_value=None)
        tasks_man.get_available_process_tasks = AsyncMock(return_value=None)

        watcher_man = MagicMock()
        watcher_man.watch = AsyncMock()

        self.request.config = 'xpto=1'  # invalid
        self.request.related_pids = {123, 456}

        handler = OptimizationHandler(context=self.context, tasks_man=tasks_man, watcher_man=watcher_man, profile_reader=self.reader)
        await handler.handle(self.request)

        os_path_exists.assert_called_once_with(f'/proc/{self.request.pid}')
        tasks_man.get_available_environment_tasks.assert_not_called()
        tasks_man.get_available_process_tasks.assert_not_called()
        run_tasks.assert_not_called()
        time_mock.assert_called()

        exp_proc = OptimizedProcess(self.request, 123456789)
        watcher_man.watch.assert_called_once_with(exp_proc)

    @patch(f'{__app_name__}.service.optimizer.handler.os.path.exists', return_value=False)
    @patch('os.getenv', return_value=':1')
    async def test_handle__DISPLAY_env_var_must_always_be_present_for_every_request(self, getenv: Mock, exists: Mock):
        handler = OptimizationHandler(context=self.context, tasks_man=Mock(), watcher_man=Mock(),
                                      profile_reader=Mock())

        self.assertIsNone(self.request.user_env)
        await handler.handle(self.request)
        getenv.assert_called_once_with('DISPLAY', ':0')
        exists.assert_called_once_with(f'/proc/{self.request.pid}')
        self.assertEqual({'DISPLAY': ':1'}, self.request.user_env)

    @patch('time.time', return_value=1)
    @patch('os.path.exists', return_value=True)
    @patch(f'{__app_name__}.common.profile.get_user_profile_path', side_effect=get_test_user_profile_path)
    @patch(f'{__app_name__}.service.optimizer.handler.run_tasks', return_value=None)
    async def test_handle__must_load_profile_from_home_dir_when_request_from_non_root_user(self, run_tasks: Mock, get_user_profile_path: Mock, os_path_exists: Mock, time: Mock):
        tasks_man = MagicMock()
        tasks_man.get_available_environment_tasks = AsyncMock(return_value=None)
        tasks_man.get_available_process_tasks = AsyncMock(return_value=None)
        
        self.request.profile = 'neg_nice'

        handler = OptimizationHandler(context=self.context, tasks_man=tasks_man, watcher_man=Mock(),
                                      profile_reader=self.reader)
        await handler.handle(self.request)

        os_path_exists.assert_called_once_with(f'/proc/{self.request.pid}')
        get_user_profile_path.assert_called_once_with('neg_nice', self.request.user_name)

        expected_profile = OptimizationProfile.empty(f'{RESOURCES_DIR}/{self.request.profile}.profile')
        expected_profile.process = ProcessSettings.empty()
        expected_profile.process.nice = ProcessNiceSettings(nice_level=-1, delay=None, watch=None)

        expected_process = OptimizedProcess(request=self.request, profile=expected_profile, created_at=1)

        tasks_man.get_available_environment_tasks.assert_called_once_with(expected_process)
        tasks_man.get_available_process_tasks.assert_called_once_with(expected_process)
        run_tasks.assert_not_called()
        time.assert_called()

    @patch('time.time', return_value=1)
    @patch('os.path.exists', return_value=True)
    @patch(f'{__app_name__}.common.profile.get_user_profile_path', side_effect=get_test_user_profile_path)
    @patch(f'{__app_name__}.service.optimizer.handler.run_tasks', return_value=None)
    async def test_handle__must_load_profile_from_home_dir_when_request_from_non_root_user(self, run_tasks: Mock, get_user_profile_path: Mock, os_path_exists: Mock, time: Mock):
        tasks_man = MagicMock()
        tasks_man.get_available_environment_tasks = AsyncMock(return_value=None)
        tasks_man.get_available_process_tasks = AsyncMock(return_value=None)
        
        self.request.profile = 'neg_nice'

        handler = OptimizationHandler(context=self.context, tasks_man=tasks_man, watcher_man=Mock(),
                                      profile_reader=self.reader)
        await handler.handle(self.request)

        os_path_exists.assert_called_once_with(f'/proc/{self.request.pid}')
        get_user_profile_path.assert_called_once_with(self.request.profile, self.request.user_name)

        expected_profile = OptimizationProfile.empty(f'{RESOURCES_DIR}/{self.request.profile}.profile')
        expected_profile.process = ProcessSettings.empty()
        expected_profile.process.nice = ProcessNiceSettings(nice_level=-1, delay=None, watch=None)

        expected_process = OptimizedProcess(request=self.request, profile=expected_profile, created_at=1)

        tasks_man.get_available_environment_tasks.assert_called_once_with(expected_process)
        tasks_man.get_available_process_tasks.assert_called_once_with(expected_process)
        run_tasks.assert_not_called()
        time.assert_called()

    @patch('time.time', return_value=1)
    @patch('os.path.exists', return_value=True)
    @patch(f'{__app_name__}.common.profile.get_user_profile_path', side_effect=get_test_user_profile_path)
    @patch(f'{__app_name__}.common.profile.get_root_profile_path', side_effect=get_test_root_profile_path)
    @patch(f'{__app_name__}.service.optimizer.handler.run_tasks', return_value=None)
    async def test_handle__must_load_profile_from_root_dir_when_request_from_non_root_user_but_user_file_not_exist(self, run_tasks: Mock, get_root_profile_path: Mock, get_user_profile_path: Mock, os_path_exists: Mock, time: Mock):
        tasks_man = MagicMock()
        tasks_man.get_available_environment_tasks = AsyncMock(return_value=None)
        tasks_man.get_available_process_tasks = AsyncMock(return_value=None)
        
        self.request.profile = 'nice_delay'

        handler = OptimizationHandler(context=self.context, tasks_man=tasks_man, watcher_man=Mock(),
                                      profile_reader=self.reader)
        await handler.handle(self.request)

        os_path_exists.assert_called_once_with(f'/proc/{self.request.pid}')
        get_user_profile_path.assert_called_once_with(self.request.profile, self.request.user_name)
        get_root_profile_path.assert_called_once_with(self.request.profile)

        expected_profile = OptimizationProfile.empty(f'{RESOURCES_DIR}/root/{self.request.profile}.profile')
        expected_profile.process = ProcessSettings.empty()
        expected_profile.process.nice = ProcessNiceSettings(nice_level=-2, delay=0.5, watch=None)

        expected_process = OptimizedProcess(request=self.request, profile=expected_profile, created_at=1)

        tasks_man.get_available_environment_tasks.assert_called_once_with(expected_process)
        tasks_man.get_available_process_tasks.assert_called_once_with(expected_process)
        run_tasks.assert_not_called()
        time.assert_called()

    @patch('time.time', return_value=1)
    @patch('os.path.exists', return_value=True)
    @patch(f'{__app_name__}.common.profile.get_user_profile_path')
    @patch(f'{__app_name__}.common.profile.get_root_profile_path', side_effect=get_test_root_profile_path)
    @patch(f'{__app_name__}.service.optimizer.handler.run_tasks', return_value=None)
    async def test_handle__must_load_profile_from_root_dir_when_request_from_root_user(self, run_tasks: Mock, get_root_profile_path: Mock, get_user_profile_path: Mock, os_path_exists: Mock, time: Mock):
        tasks_man = MagicMock()
        tasks_man.get_available_environment_tasks = AsyncMock(return_value=None)
        tasks_man.get_available_process_tasks = AsyncMock(return_value=None)
        
        self.request.profile = 'nice_delay'

        handler = OptimizationHandler(context=self.context, tasks_man=tasks_man, watcher_man=Mock(),
                                      profile_reader=self.reader)

        self.request.user_id = 0
        self.request.user_name = 'root'
        await handler.handle(self.request)

        os_path_exists.assert_called_once_with(f'/proc/{self.request.pid}')
        get_user_profile_path.assert_not_called()
        get_root_profile_path.assert_called_once_with(self.request.profile)

        expected_profile = OptimizationProfile.empty(f'{RESOURCES_DIR}/root/{self.request.profile}.profile')
        expected_profile.process = ProcessSettings.empty()
        expected_profile.process.nice = ProcessNiceSettings(nice_level=-2, delay=0.5, watch=None)

        expected_process = OptimizedProcess(request=self.request, profile=expected_profile, created_at=1)

        tasks_man.get_available_environment_tasks.assert_called_once_with(expected_process)
        tasks_man.get_available_process_tasks.assert_called_once_with(expected_process)
        run_tasks.assert_not_called()
        time.assert_called()

    @patch('time.time', return_value=1)
    @patch('os.path.exists', return_value=True)
    @patch(f'{__app_name__}.common.profile.get_user_profile_path')
    @patch(f'{__app_name__}.common.profile.get_root_profile_path', side_effect=get_test_root_profile_path)
    @patch(f'{__app_name__}.service.optimizer.handler.run_tasks', return_value=None)
    async def test_handle__must_read_the_default_profile_when_defined_cannot_be_found(self, run_tasks: Mock, get_root_profile_path: Mock, get_user_profile_path: Mock, os_path_exists: Mock, time: Mock):
        tasks_man = MagicMock()
        tasks_man.get_available_environment_tasks = AsyncMock(return_value=None)
        tasks_man.get_available_process_tasks = AsyncMock(return_value=None)
        
        self.request.profile = 'unknown'

        handler = OptimizationHandler(context=self.context, tasks_man=tasks_man, watcher_man=Mock(),
                                      profile_reader=self.reader)

        self.request.user_id = 0
        self.request.user_name = 'root'
        await handler.handle(self.request)

        os_path_exists.assert_called_once_with(f'/proc/{self.request.pid}')
        get_user_profile_path.assert_not_called()
        get_root_profile_path.assert_has_calls([call(self.request.profile), call('default')])

        expected_profile = OptimizationProfile.empty(f'{RESOURCES_DIR}/root/default.profile')
        expected_profile.process = ProcessSettings.empty()
        expected_profile.process.nice = ProcessNiceSettings(nice_level=-1, delay=None, watch=None)

        expected_process = OptimizedProcess(request=self.request, profile=expected_profile, created_at=1)

        tasks_man.get_available_environment_tasks.assert_called_once_with(expected_process)
        tasks_man.get_available_process_tasks.assert_called_once_with(expected_process)
        run_tasks.assert_not_called()
        time.assert_called()

    @patch('os.path.exists', return_value=True)
    @patch(f'{__app_name__}.common.profile.get_user_profile_path')
    @patch(f'{__app_name__}.common.profile.get_root_profile_path', side_effect=get_test_root_profile_path)
    @patch(f'{__app_name__}.service.optimizer.handler.get_default_profile_name', return_value="teste123")
    @patch(f'{__app_name__}.service.optimizer.handler.run_tasks', return_value=None)
    async def test_handle__must_do_nothing_when_defined_or_default_profiles_cannot_be_found(self, run_tasks: Mock, get_default_profile_name: Mock, get_root_profile_path: Mock, get_user_profile_path: Mock, os_path_exists: Mock):
        tasks_man = MagicMock()
        tasks_man.get_available_environment_tasks = AsyncMock(return_value=None)
        tasks_man.get_available_process_tasks = AsyncMock(return_value=None)
        
        self.request.profile = 'unknown'

        handler = OptimizationHandler(context=self.context, tasks_man=tasks_man, watcher_man=Mock(),
                                      profile_reader=self.reader)

        self.request.user_id = 0
        self.request.user_name = 'root'
        await handler.handle(self.request)

        os_path_exists.assert_called_once_with(f'/proc/{self.request.pid}')
        get_default_profile_name.assert_called_once()
        get_user_profile_path.assert_not_called()
        get_root_profile_path.assert_has_calls([call(self.request.profile), call('teste123')])

        tasks_man.get_available_environment_tasks.assert_not_called()
        tasks_man.get_available_process_tasks.assert_not_called()
        run_tasks.assert_not_called()

    @patch('os.path.exists', return_value=False)
    async def test_handle__must_remove_the_request_pid_from_the_processing_queue_when_process_does_not_exist(self, os_path_exists: Mock):
        tasks_man = MagicMock()
        tasks_man.get_available_environment_tasks = AsyncMock(return_value=None)
        tasks_man.get_available_process_tasks = AsyncMock(return_value=None)

        watcher_man = MagicMock()
        watcher_man.watch = AsyncMock()

        self.request.config = 'cpu.performance'

        self.assertIn(self.request.pid, self.context.queue.get_view())
        handler = OptimizationHandler(context=self.context, tasks_man=tasks_man, watcher_man=watcher_man, profile_reader=self.reader)
        await handler.handle(self.request)

        os_path_exists.assert_called_once_with(f'/proc/{self.request.pid}')
        self.assertNotIn(self.request.pid, self.context.queue.get_view())

    @patch('os.path.exists', return_value=True)
    @patch(f'{__app_name__}.service.optimizer.handler.run_tasks', return_value=None)
    @patch(f'{__app_name__}.service.optimizer.handler.time.time', return_value=123456789)
    async def test_handle__must_remove_the_request_pid_after_the_optimizations(self, time_mock: Mock, run_tasks: Mock, os_path_exists: Mock):
        tasks_man = MagicMock()
        tasks_man.get_available_environment_tasks = AsyncMock(return_value=None)

        proc_task = Mock(run=AsyncMock())
        tasks_man.get_available_process_tasks = AsyncMock(return_value=[proc_task])

        watcher_man = MagicMock()
        watcher_man.watch = AsyncMock()

        self.request.config = 'proc.nice=-1'

        self.assertIn(self.request.pid, self.context.queue.get_view())

        handler = OptimizationHandler(context=self.context, tasks_man=tasks_man, watcher_man=watcher_man, profile_reader=self.reader)
        handler._launcher_mapper = Mock(map_pid=AsyncMock(return_value=4788))  # mapped pid
        await handler.handle(self.request)

        exp_prof = OptimizationProfile.empty()
        exp_prof.process = ProcessSettings(None)
        exp_prof.process.nice.level = -1
        exp_prof.process.io = None
        exp_prof.process.scheduling = None

        exp_proc = OptimizedProcess(self.request, profile=exp_prof, created_at=123456789)
        exp_proc.pid = 4788

        os_path_exists.assert_called_once_with(f'/proc/{self.request.pid}')
        tasks_man.get_available_environment_tasks.assert_called_once_with(exp_proc)
        tasks_man.get_available_process_tasks.assert_called_once_with(exp_proc)
        run_tasks.assert_called_once_with([proc_task], exp_proc)
        time_mock.assert_called()

        watcher_man.watch.assert_not_called()

        self.assertNotIn(self.request.pid, self.context.queue.get_view())
        self.assertNotIn(4788, self.context.queue.get_view())

    @patch('os.path.exists', return_value=True)
    @patch(f'{__app_name__}.service.optimizer.handler.run_tasks', return_value=None)
    @patch(f'{__app_name__}.service.optimizer.handler.time.time', return_value=123456789)
    async def test_handle__must_remove_the_source_pid_and_keep_the_mapped_pid_on_the_processing_queue_when_watched(self, time_mock: Mock, run_tasks: Mock, os_path_exists: Mock):
        tasks_man = MagicMock()
        tasks_man.get_available_environment_tasks = AsyncMock(return_value=None)

        proc_task = Mock(run=AsyncMock())
        tasks_man.get_available_process_tasks = AsyncMock(return_value=[proc_task])

        watcher_man = MagicMock()
        watcher_man.watch = AsyncMock()

        self.request.config = 'proc.nice=-1'
        self.request.related_pids = {998877}
        self.assertIn(self.request.pid, self.context.queue.get_view())

        handler = OptimizationHandler(context=self.context, tasks_man=tasks_man, watcher_man=watcher_man, profile_reader=self.reader)
        handler._launcher_mapper = Mock(map_pid=AsyncMock(return_value=4788))  # mapped pid
        await handler.handle(self.request)

        exp_prof = OptimizationProfile.empty()
        exp_prof.process = ProcessSettings(None)
        exp_prof.process.nice.level = -1
        exp_prof.process.io = None
        exp_prof.process.scheduling = None

        exp_proc = OptimizedProcess(self.request, profile=exp_prof, created_at=123456789)
        exp_proc.pid = 4788

        os_path_exists.assert_called_once_with(f'/proc/{self.request.pid}')
        tasks_man.get_available_environment_tasks.assert_called_once_with(exp_proc)
        tasks_man.get_available_process_tasks.assert_called_once_with(exp_proc)
        run_tasks.assert_called_once_with([proc_task], exp_proc)
        time_mock.assert_called()

        watcher_man.watch.assert_awaited_once_with(exp_proc)

        self.assertIn(4788, self.context.queue.get_view())
        self.assertNotIn(self.request.pid, self.context.queue.get_view())
