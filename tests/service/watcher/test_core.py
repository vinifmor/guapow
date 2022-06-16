import re
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, patch, call

from guapow import __app_name__
from guapow.common.config import OptimizerConfig
from guapow.common.dto import OptimizationRequest
from guapow.service.watcher.config import ProcessWatcherConfig
from guapow.service.watcher.core import ProcessWatcher, ProcessWatcherContext
from guapow.service.watcher.patterns import RegexMapper


class ProcessWatcherTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.context = ProcessWatcherContext(user_id=1, user_name='xpto', user_env={'a': '1'}, logger=Mock(),
                                             mapping_file_path='test.map', optimized={}, opt_config=OptimizerConfig.default(),
                                             watch_config=ProcessWatcherConfig.default(), machine_id='abc126517ha',
                                             ignored_procs=dict(), ignored_file_path='test.ignore')
        self.watcher = ProcessWatcher(regex_mapper=RegexMapper(cache=False, logger=Mock()), context=self.context)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(False, None))
    @patch(f'{__app_name__}.service.watcher.core.ignored.read', return_value=(False, None))
    @patch(f'{__app_name__}.service.watcher.core.map_processes')
    async def test_check_mappings__must_not_map_processes_when_no_mapping_is_found(self, map_processes: Mock, ignored_read: Mock, mapping_read: Mock):
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
        ignored_read.assert_not_called()
        map_processes.assert_not_called()

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'abc': 'default'}))
    @patch(f'{__app_name__}.service.watcher.core.ignored.read', return_value=(False, None))
    @patch(f'{__app_name__}.service.watcher.core.map_processes', return_value={})
    async def test_check_mappings__must_clear_the_optimized_context_when_no_process_could_be_retrieved(self, map_processes: Mock, ignored_read: Mock, mapping_read: Mock):
        self.context.optimized.update({1: 'abc', 2: 'def'})
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
        ignored_read.assert_called_once()
        map_processes.assert_called_once()
        self.assertEqual({}, self.context.optimized)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'abc': 'default'}))
    @patch(f'{__app_name__}.service.watcher.core.ignored.read', return_value=(False, None))
    @patch(f'{__app_name__}.service.watcher.core.map_processes', return_value={123: ('/bin/def', 'def')})
    @patch(f'{__app_name__}.service.watcher.core.network.send')
    async def test_check_mappings__must_no_perform_any_request_in_case_of_no_mapping_matches(self, send_async: Mock, map_processes: Mock, ignored_read: Mock, mapping_read: Mock):
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
        ignored_read.assert_called_once()
        map_processes.assert_called_once()
        send_async.assert_not_called()
        self.assertEqual({}, self.context.optimized)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'a': 'default', 'b': 'prof_1', '/bin/c': 'prof_2'}))
    @patch(f'{__app_name__}.service.watcher.core.ignored.read', return_value=(False, None))
    @patch(f'{__app_name__}.service.watcher.core.map_processes', return_value={1: ('/bin/a', 'a'),
                                                                                       2: ('/bin/b', 'b'),
                                                                                       3: ('/bin/c', 'c'),
                                                                                       4: ('/bin/d', 'd')})  # no profile for this process
    @patch(f'{__app_name__}.service.watcher.core.network.send', return_value=True)
    @patch(f'{__app_name__}.service.watcher.core.time.time', return_value=12345)
    async def test_check_mappings__must_trigger_requests_for_mapped_processes(self, time: Mock, send_async: Mock, map_processes: Mock, ignored_read: Mock, mapping_read: Mock):
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
        ignored_read.assert_called_once()
        map_processes.assert_called_once()
        time.assert_called()

        req_a = OptimizationRequest(pid=1, command='/bin/a', user_name=self.context.user_name,
                                    user_env=self.context.user_env, profile='default', created_at=12345)

        req_b = OptimizationRequest(pid=2, command='/bin/b', user_name=self.context.user_name,
                                    user_env=self.context.user_env, profile='prof_1', created_at=12345)

        req_c = OptimizationRequest(pid=3, command='/bin/c', user_name=self.context.user_name,
                                    user_env=self.context.user_env, profile='prof_2', created_at=12345)

        send_async.assert_has_calls([call(req_a, self.context.opt_config, self.context.machine_id, self.context.logger),
                                     call(req_b, self.context.opt_config, self.context.machine_id, self.context.logger),
                                     call(req_c, self.context.opt_config, self.context.machine_id, self.context.logger)], any_order=True)

        self.assertEqual({1: 'a', 2: 'b', 3: '/bin/c'}, self.context.optimized)

        self.assertIsNone(self.watcher._mappings)
        self.assertIsNone(self.watcher._cmd_patterns)
        self.assertIsNone(self.watcher._comm_patterns)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'a': 'prof_1', '/bin/a': 'prof_2'}))
    @patch(f'{__app_name__}.service.watcher.core.ignored.read', return_value=(False, None))
    @patch(f'{__app_name__}.service.watcher.core.map_processes', return_value={1: ('/bin/a', 'a'),
                                                                                       2: ('/bin/b', 'b')})  # no profile for this process
    @patch(f'{__app_name__}.service.watcher.core.network.send', return_value=True)
    @patch(f'{__app_name__}.service.watcher.core.time.time', return_value=12345)
    async def test_check_mappings__cmd_mapping_must_have_higher_priority_than_comm(self, time: Mock, send_async: Mock, map_processes: Mock, ignored_read: Mock, mapping_read: Mock):
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
        ignored_read.assert_called_once()
        map_processes.assert_called_once()
        time.assert_called()

        req_a = OptimizationRequest(pid=1, command='/bin/a', user_name=self.context.user_name,
                                    user_env=self.context.user_env, profile='prof_2', created_at=12345)

        send_async.assert_has_calls([call(req_a, self.context.opt_config, self.context.machine_id, self.context.logger)], any_order=True)

        self.assertEqual({1: '/bin/a'}, self.context.optimized)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'a': 'default'}))
    @patch(f'{__app_name__}.service.watcher.core.ignored.read', return_value=(False, None))
    @patch(f'{__app_name__}.service.watcher.core.map_processes',
           return_value={1: ('/bin/a', 'a')})
    @patch(f'{__app_name__}.service.watcher.core.network.send', return_value=False)
    async def test_check_mappings__must_add_process_to_the_optimized_context_when_request_fail(self, send_async: Mock, map_processes: Mock, ignored_read: Mock, mapping_read: Mock):
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
        ignored_read.assert_called_once()
        map_processes.assert_called_once()
        send_async.assert_called_once()
        self.assertEqual({1: 'a'}, self.context.optimized)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'a': 'default'}))
    @patch(f'{__app_name__}.service.watcher.core.ignored.read', return_value=(False, None))
    @patch(f'{__app_name__}.service.watcher.core.map_processes',
           return_value={1: ('/bin/a', 'a')})
    @patch(f'{__app_name__}.service.watcher.core.network.send', return_value=True)
    async def test_check_mappings__must_remove_an_optimized_process_from_the_context_when_it_is_not_alive(self, send_async: Mock, map_processes: Mock, ignored_read: Mock, mapping_read: Mock):
        self.context.optimized.update({2: 'b'})  # 'b' was previously optimized, but will not me mapped as a process alive
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
        ignored_read.assert_called_once()
        map_processes.assert_called_once()
        send_async.assert_called_once()
        self.assertEqual({1: 'a'}, self.context.optimized)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'a': 'default'}))
    @patch(f'{__app_name__}.service.watcher.core.ignored.read', return_value=(False, None))
    @patch(f'{__app_name__}.service.watcher.core.map_processes',
           return_value={1: ('/bin/a', 'a')})
    @patch(f'{__app_name__}.service.watcher.core.network.send')
    async def test_check_mappings__must_not_send_a_new_request_for_a_previously_optimized_process(self, send_async: Mock, map_processes: Mock, ignored_read: Mock, mapping_read: Mock):
        self.context.optimized.update({1: 'a'})  # 'a' was previously optimized and still alive
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
        ignored_read.assert_called_once()
        map_processes.assert_called_once()
        send_async.assert_not_called()
        self.assertEqual({1: 'a'}, self.context.optimized)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'a': 'default'}))
    @patch(f'{__app_name__}.service.watcher.core.ignored.read', return_value=(False, None))
    @patch(f'{__app_name__}.service.watcher.core.map_processes',
           return_value={1: ('/bin/a', 'a'), 2: ('/bin/a', 'a')})
    @patch(f'{__app_name__}.service.watcher.core.network.send')
    @patch(f'{__app_name__}.service.watcher.core.time.time', return_value=12345)
    async def test_check_mappings__must_send_a_new_request_for_a_previously_optimized_command_with_a_different_pid(self, time: Mock, send_async: Mock, map_processes: Mock, ignored_read: Mock, mapping_read: Mock):
        self.context.optimized.update({1: 'a'})  # 'a' (1) was previously optimized and still alive
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
        ignored_read.assert_called_once()
        map_processes.assert_called_once()
        time.assert_called()

        exp_req = OptimizationRequest(pid=2, command='/bin/a', user_name=self.context.user_name,
                                      user_env=self.context.user_env, profile='default', created_at=12345)

        send_async.assert_called_once_with(exp_req, self.context.opt_config, self.context.machine_id, self.context.logger)
        self.assertEqual({1: 'a', 2: 'a'}, self.context.optimized)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'a*': 'default', '/bin/*': 'prof_1', '/local/d': 'prof_2'}))
    @patch(f'{__app_name__}.service.watcher.core.ignored.read', return_value=(False, None))
    @patch(f'{__app_name__}.service.watcher.core.map_processes', return_value={1: ('/local/bin/abacaxi', 'abacaxi'),
                                                                                       2: ('/bin/b', 'b'),
                                                                                       3: ('/bin/c', 'c')})
    @patch(f'{__app_name__}.service.watcher.core.network.send', return_value=True)
    @patch(f'{__app_name__}.service.watcher.core.time.time', return_value=12345)
    async def test_check_mappings__must_trigger_requests_for_mapped_using_regex(self, time: Mock, send_async: Mock, map_processes: Mock, ignored_read: Mock, mapping_read: Mock):
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
        ignored_read.assert_called_once()
        map_processes.assert_called_once()
        time.assert_called()

        req_a = OptimizationRequest(pid=1, command='/local/bin/abacaxi', user_name=self.context.user_name,
                                    user_env=self.context.user_env, profile='default', created_at=12345)

        req_b = OptimizationRequest(pid=2, command='/bin/b', user_name=self.context.user_name,
                                    user_env=self.context.user_env, profile='prof_1', created_at=12345)
        req_c = OptimizationRequest(pid=3, command='/bin/c', user_name=self.context.user_name,
                                    user_env=self.context.user_env, profile='prof_1', created_at=12345)

        send_async.assert_has_calls([call(req_a, self.context.opt_config, self.context.machine_id, self.context.logger),
                                     call(req_b, self.context.opt_config, self.context.machine_id, self.context.logger),
                                     call(req_c, self.context.opt_config, self.context.machine_id, self.context.logger)], any_order=True)

        self.assertEqual({1: 'abacaxi', 2: '/bin/b', 3: '/bin/c'}, self.context.optimized)

        self.assertIsNone(self.watcher._mappings)
        self.assertIsNone(self.watcher._cmd_patterns)
        self.assertIsNone(self.watcher._comm_patterns)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'abacax': 'default', 'a*': 'prof1'}))
    @patch(f'{__app_name__}.service.watcher.core.ignored.read', return_value=(False, None))
    @patch(f'{__app_name__}.service.watcher.core.map_processes', return_value={1: ('/local/bin/abacaxi', 'abacaxi'),
                                                                                       2: ('/bin/b', 'b')})
    @patch(f'{__app_name__}.service.watcher.core.network.send', return_value=True)
    @patch(f'{__app_name__}.service.watcher.core.time.time', return_value=12345)
    async def test_check_mappings__a_request_must_be_sent_when_an_exact_comm_match_fails_but_a_pattern_works(self, time: Mock, send_async: Mock, map_processes: Mock, ignored_read: Mock, mapping_read: Mock):
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
        ignored_read.assert_called_once()
        map_processes.assert_called_once()
        time.assert_called()

        req_a = OptimizationRequest(pid=1, command='/local/bin/abacaxi', user_name=self.context.user_name,
                                    user_env=self.context.user_env, profile='prof1', created_at=12345)

        send_async.assert_has_calls([call(req_a, self.context.opt_config, self.context.machine_id, self.context.logger)], any_order=True)

        self.assertEqual({1: 'abacaxi'}, self.context.optimized)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'abacaxi': 'default', 'a**': 'prof1'}))  # both matches
    @patch(f'{__app_name__}.service.watcher.core.ignored.read', return_value=(False, None))
    @patch(f'{__app_name__}.service.watcher.core.map_processes', return_value={1: ('/local/bin/abacaxi', 'abacaxi'),
                                                                                       2: ('/bin/b', 'b')})
    @patch(f'{__app_name__}.service.watcher.core.network.send', return_value=True)
    @patch(f'{__app_name__}.service.watcher.core.time.time', return_value=12345)
    async def test_check_mappings__comm_exact_match_must_prevail_over_a_regex_match(self, time: Mock, send_async: Mock, map_processes: Mock, ignored_read: Mock, mapping_read: Mock):
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
        ignored_read.assert_called_once()
        map_processes.assert_called_once()
        time.assert_called()

        req_a = OptimizationRequest(pid=1, command='/local/bin/abacaxi', user_name=self.context.user_name,
                                    user_env=self.context.user_env, profile='default', created_at=12345)  # the comm exact match points to 'default' profile

        send_async.assert_has_calls([call(req_a, self.context.opt_config, self.context.machine_id, self.context.logger)], any_order=True)

        self.assertEqual({1: 'abacaxi'}, self.context.optimized)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'/local/bin/abacaxi': 'default', '/local/*': 'prof1'}))  # both matches
    @patch(f'{__app_name__}.service.watcher.core.ignored.read', return_value=(False, None))
    @patch(f'{__app_name__}.service.watcher.core.map_processes', return_value={1: ('/local/bin/abacaxi', 'abacaxi'),
                                                                                       2: ('/bin/b', 'b')})
    @patch(f'{__app_name__}.service.watcher.core.network.send', return_value=True)
    @patch(f'{__app_name__}.service.watcher.core.time.time', return_value=12345)
    async def test_check_mappings__cmd_exact_match_must_prevail_over_a_regex_match(self, time: Mock, send_async: Mock, map_processes: Mock, ignored_read: Mock, mapping_read: Mock):
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
        ignored_read.assert_called_once()
        map_processes.assert_called_once()
        time.assert_called()

        req_a = OptimizationRequest(pid=1, command='/local/bin/abacaxi', user_name=self.context.user_name,
                                    user_env=self.context.user_env, profile='default', created_at=12345)  # the cmd exact match points to 'default' profile

        send_async.assert_has_calls([call(req_a, self.context.opt_config, self.context.machine_id, self.context.logger)], any_order=True)

        self.assertEqual({1: '/local/bin/abacaxi'}, self.context.optimized)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'abacaxi': 'default', '/local/*': 'prof1'}))  # both matches
    @patch(f'{__app_name__}.service.watcher.core.ignored.read', return_value=(False, None))
    @patch(f'{__app_name__}.service.watcher.core.map_processes', return_value={1: ('/local/bin/abacaxi', 'abacaxi'), 2: ('/bin/b', 'b')})
    @patch(f'{__app_name__}.service.watcher.core.network.send', return_value=True)
    @patch(f'{__app_name__}.service.watcher.core.time.time', return_value=12345)
    async def test_check_mappings__cmd_regex_match_must_prevail_over_a_comm_exact_match(self, time: Mock,
                                                                                        send_async: Mock,
                                                                                        map_processes: Mock,
                                                                                        ignore_read: Mock,
                                                                                        mapping_read: Mock):
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
        ignore_read.assert_called_once()
        map_processes.assert_called_once()
        time.assert_called()

        req_a = OptimizationRequest(pid=1, command='/local/bin/abacaxi', user_name=self.context.user_name,
                                    user_env=self.context.user_env, profile='prof1',  # the cmd regex match points to 'prof1' profile
                                    created_at=12345)

        send_async.assert_has_calls([call(req_a, self.context.opt_config, self.context.machine_id, self.context.logger)], any_order=True)

        self.assertEqual({1: '/local/bin/abacaxi'}, self.context.optimized)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'/local/*': 'default', '/local/*/a*': 'prof1'}))  # both matches
    @patch(f'{__app_name__}.service.watcher.core.ignored.read', return_value=(False, None))
    @patch(f'{__app_name__}.service.watcher.core.map_processes', return_value={1: ('/local/bin/abacaxi', 'abacaxi'), 2: ('/bin/b', 'b')})
    @patch(f'{__app_name__}.service.watcher.core.network.send', return_value=True)
    @patch(f'{__app_name__}.service.watcher.core.time.time', return_value=12345)
    async def test_check_mappings__more_specific_cmd_match_must_prevail_over_others(self, time: Mock,
                                                                                    send_async: Mock,
                                                                                    map_processes: Mock,
                                                                                    ignore_read: Mock,
                                                                                    mapping_read: Mock):
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
        ignore_read.assert_called_once()
        map_processes.assert_called_once()
        time.assert_called()

        req_a = OptimizationRequest(pid=1, command='/local/bin/abacaxi', user_name=self.context.user_name,
                                    user_env=self.context.user_env, profile='prof1',  # the cmd regex match points to 'prof1' profile
                                    created_at=12345)

        send_async.assert_has_calls([call(req_a, self.context.opt_config, self.context.machine_id, self.context.logger)], any_order=True)
        self.assertEqual({1: '/local/bin/abacaxi'}, self.context.optimized)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'ab*': 'default', 'aba*': 'prof1'}))  # both matches
    @patch(f'{__app_name__}.service.watcher.core.ignored.read', return_value=(False, None))
    @patch(f'{__app_name__}.service.watcher.core.map_processes', return_value={1: ('/local/bin/abacaxi', 'abacaxi'), 2: ('/bin/b', 'b')})
    @patch(f'{__app_name__}.service.watcher.core.network.send', return_value=True)
    @patch(f'{__app_name__}.service.watcher.core.time.time', return_value=12345)
    async def test_check_mappings__more_specific_comm_match_must_prevail_over_others(self, time: Mock,
                                                                                     send_async: Mock,
                                                                                     map_processes: Mock,
                                                                                     ignore_read: Mock,
                                                                                     mapping_read: Mock):
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
        ignore_read.assert_called_once()
        map_processes.assert_called_once()
        time.assert_called()

        req_a = OptimizationRequest(pid=1, command='/local/bin/abacaxi', user_name=self.context.user_name,
                                    user_env=self.context.user_env, profile='prof1',  # the cmd regex match points to 'prof1' profile
                                    created_at=12345)

        send_async.assert_has_calls([call(req_a, self.context.opt_config, self.context.machine_id, self.context.logger)], any_order=True)
        self.assertEqual({1: 'abacaxi'}, self.context.optimized)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'a*': 'default', '/bin/*': 'prof_1', '/local/d': 'prof_2'}))
    @patch(f'{__app_name__}.service.watcher.core.ignored.read', return_value=(False, None))
    @patch(f'{__app_name__}.service.watcher.core.map_processes', side_effect=[{1: ('/local/bin/abacaxi', 'abacaxi'),
                                                                                       2: ('/bin/b', 'b'),
                                                                                       3: ('/bin/c', 'c')},
                                                                                      {4: ('/xpto', 'xpto')}])
    @patch(f'{__app_name__}.service.watcher.core.network.send', return_value=True)
    @patch(f'{__app_name__}.service.watcher.core.time.time', return_value=12345)
    async def test_check_mappings__must_cache_mapping_when_defined_on_config(self, time: Mock, send_async: Mock, map_processes: Mock, ignored_read: Mock, mapping_read: Mock):
        self.assertIsNone(self.watcher._mappings)
        self.assertIsNone(self.watcher._cmd_patterns)
        self.assertIsNone(self.watcher._comm_patterns)

        self.context.watch_config.mapping_cache = True

        # first call
        await self.watcher.check_mappings()

        req_a = OptimizationRequest(pid=1, command='/local/bin/abacaxi', user_name=self.context.user_name,
                                    user_env=self.context.user_env, profile='default', created_at=12345)

        req_b = OptimizationRequest(pid=2, command='/bin/b', user_name=self.context.user_name,
                                    user_env=self.context.user_env, profile='prof_1', created_at=12345)
        req_c = OptimizationRequest(pid=3, command='/bin/c', user_name=self.context.user_name,
                                    user_env=self.context.user_env, profile='prof_1', created_at=12345)

        send_async.assert_has_calls([call(req_a, self.context.opt_config, self.context.machine_id, self.context.logger),
                                     call(req_b, self.context.opt_config, self.context.machine_id, self.context.logger),
                                     call(req_c, self.context.opt_config, self.context.machine_id, self.context.logger)], any_order=True)

        self.assertEqual({1: 'abacaxi', 2: '/bin/b', 3: '/bin/c'}, self.context.optimized)

        self.assertEqual({'a*': 'default', '/bin/*': 'prof_1', '/local/d': 'prof_2'}, self.watcher._mappings)
        self.assertEqual({re.compile(r'^/bin/.+$'): 'prof_1'}, self.watcher._cmd_patterns)
        self.assertEqual({re.compile(r'^a.+$'): 'default'}, self.watcher._comm_patterns)

        # second call
        await self.watcher.check_mappings()

        mapping_read.assert_called_once()
        self.assertEqual(2, ignored_read.call_count)
        self.assertEqual(2, map_processes.call_count)
        time.assert_called()

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'a*': 'default', '/bin/*': 'prof_1', '/local/d': 'prof_2'}))
    @patch(f'{__app_name__}.service.watcher.core.ignored.read', return_value=(False, None))
    @patch(f'{__app_name__}.service.watcher.core.map_processes', side_effect=[{1: ('/local/bin/abacaxi', 'abacaxi')},
                                                                                      {4: ('/bin/b', 'b')}])
    @patch(f'{__app_name__}.service.watcher.core.network.send', return_value=True)
    @patch(f'{__app_name__}.service.watcher.core.time.time', return_value=12345)
    async def test_check_mappings__must_always_read_mapping_from_disk_when_cache_is_off(self, time: Mock, send_async: Mock, map_processes: Mock, ignored_read: Mock, mapping_read: Mock):
        self.assertIsNone(self.watcher._mappings)
        self.assertIsNone(self.watcher._cmd_patterns)
        self.assertIsNone(self.watcher._comm_patterns)

        self.context.watch_config.mapping_cache = False

        # first call
        await self.watcher.check_mappings()

        req_a = OptimizationRequest(pid=1, command='/local/bin/abacaxi', user_name=self.context.user_name,
                                    user_env=self.context.user_env, profile='default', created_at=12345)

        self.assertEqual({1: 'abacaxi'}, self.context.optimized)

        self.assertIsNone(self.watcher._mappings)
        self.assertIsNone(self.watcher._cmd_patterns)
        self.assertIsNone(self.watcher._comm_patterns)

        # second call
        await self.watcher.check_mappings()

        req_b = OptimizationRequest(pid=4, command='/bin/b', user_name=self.context.user_name,
                                    user_env=self.context.user_env, profile='prof_1', created_at=12345)

        send_async.assert_has_calls([call(req_a, self.context.opt_config, self.context.machine_id, self.context.logger),
                                     call(req_b, self.context.opt_config, self.context.machine_id, self.context.logger)])

        self.assertEqual({4: '/bin/b'}, self.context.optimized)
        self.assertEqual(2, mapping_read.call_count)
        self.assertEqual(2, ignored_read.call_count)
        self.assertEqual(2, map_processes.call_count)
        time.assert_called()

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', side_effect=[(True, None), (False, None), (False, None), (True, None), (False, None)])
    @patch(f'{__app_name__}.service.watcher.core.ignored.read', return_value=(False, None))
    @patch(f'{__app_name__}.service.watcher.core.map_processes')
    @patch(f'{__app_name__}.service.watcher.core.network.send')
    async def test_check_mappings__must_always_call_read_with_the_last_file_found_result(self, send: Mock, map_processes: Mock, ignored_read: Mock, mapping_read: Mock):
        for _ in range(5):
            await self.watcher.check_mappings()

        mapping_read.assert_has_calls([call(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None),
                                       call(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=True),
                                       call(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=False),
                                       call(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=False),
                                       call(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=True)])

        send.assert_not_called()
        ignored_read.assert_not_called()
        map_processes.assert_not_called()

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'def': 'default',
                                                                                     'abc': 'default',
                                                                                     'ghi': 'default'}))
    @patch(f'{__app_name__}.service.watcher.core.ignored.read', return_value=(True, {'/bin/a*', 'de*', 'ghi'}))
    @patch(f'{__app_name__}.service.watcher.core.map_processes', return_value={123: ('/bin/def', 'def'),
                                                                               456: ('/bin/abc', 'abc'),
                                                                               789: ('/bin/ghi', 'ghi')})
    @patch(f'{__app_name__}.service.watcher.core.network.send')
    async def test_check_mappings__must_not_perform_any_request_if_ignored_matches(self, *mocks: Mock):
        send_async, map_processes, ignored_read, mapping_read = mocks

        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path,
                                             logger=self.context.logger,
                                             last_file_found_log=None)
        ignored_read.assert_called_once()
        map_processes.assert_called_once()
        send_async.assert_not_called()
        self.assertEqual({}, self.context.optimized)
        self.assertEqual({re.compile(r'^de.+$'): {'123:def'},
                          re.compile(r'^/bin/a.+$'): {'456:abc'},
                          'ghi': {'789:ghi'}}, self.context.ignored_procs)
        self.assertFalse(self.watcher._ignored_cached)  # ensuring nothing was cached (when disabled)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'def': 'default',
                                                                                     'abc': 'default',
                                                                                     'ghi': 'default'}))
    @patch(f'{__app_name__}.service.watcher.core.ignored.read', return_value=(True, {'def', 'ghi'}))
    @patch(f'{__app_name__}.service.watcher.core.map_processes', return_value={123: ('/bin/def', 'def'),
                                                                               789: ('/bin/ghi', 'ghi')})
    @patch(f'{__app_name__}.service.watcher.core.network.send')
    async def test_check_mappings__must_not_perform_any_request_if_only_exact_ignored_matches(self, *mocks: Mock):
        send_async, map_processes, ignored_read, mapping_read = mocks

        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path,
                                             logger=self.context.logger,
                                             last_file_found_log=None)
        ignored_read.assert_called_once()
        map_processes.assert_called_once()
        send_async.assert_not_called()
        self.assertEqual({}, self.context.optimized)
        self.assertEqual({'def': {'123:def'},
                          'ghi': {'789:ghi'}}, self.context.ignored_procs)
        self.assertFalse(self.watcher._ignored_cached)  # ensuring nothing was cached (when disabled)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'def': 'default',
                                                                                     'abc': 'default',
                                                                                     'ghi': 'default'}))
    @patch(f'{__app_name__}.service.watcher.core.ignored.read', return_value=(True, {'de*'}))
    @patch(f'{__app_name__}.service.watcher.core.map_processes', return_value={123: ('/bin/def', 'def'),
                                                                               456: ('/bin/abc', 'abc'),
                                                                               789: ('/bin/ghi', 'ghi')})
    @patch(f'{__app_name__}.service.watcher.core.network.send')
    async def test_check_mappings__must_clean_ignored_context_when_pattern_is_no_long_returned(self, *mocks: Mock):
        send_async, map_processes, ignored_read, mapping_read = mocks

        self.context.ignored_procs.update({re.compile(r'^de.+$'): {'123:def'},
                                           re.compile(r'^/bin/a.+$'): {'456:abc'},
                                           'ghi': {'789:ghi'}})
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path,
                                             logger=self.context.logger,
                                             last_file_found_log=None)
        ignored_read.assert_called_once()
        map_processes.assert_called_once()
        self.assertEqual(2, send_async.call_count)
        self.assertEqual(2, len(self.context.optimized))
        self.assertEqual({re.compile(r'^de.+$'): {'123:def'}}, self.context.ignored_procs)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'def': 'default',
                                                                                     'abc': 'default'}))
    @patch(f'{__app_name__}.service.watcher.core.ignored.read', return_value=(True, {'/bin/a*', 'de*', 'ghi'}))
    @patch(f'{__app_name__}.service.watcher.core.map_processes', return_value={123: ('/bin/def', 'def')})
    @patch(f'{__app_name__}.service.watcher.core.network.send')
    async def test_check_mappings__must_clean_ignored_context_when_ignored_proc_stops(self, *mocks: Mock):
        send_async, map_processes, ignored_read, mapping_read = mocks

        self.context.ignored_procs.update({r'^de.+$': {'123:def'},
                                           r'^/bin/a.+$': {'456:abc'},
                                           'ghi': {'789:ghi'}})
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path,
                                             logger=self.context.logger,
                                             last_file_found_log=None)
        ignored_read.assert_called_once()
        map_processes.assert_called_once()
        self.assertEqual(0, send_async.call_count)
        self.assertEqual(0, len(self.context.optimized))
        self.assertEqual({re.compile(r'^de.+$'): {'123:def'}}, self.context.ignored_procs)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'def': 'default',
                                                                                     'abc': 'default',
                                                                                     'ghi': 'default'}))
    @patch(f'{__app_name__}.service.watcher.core.ignored.read', return_value=(True, {'/bin/a*', 'de*', 'ghi'}))
    @patch(f'{__app_name__}.service.watcher.core.map_processes', return_value={123: ('/bin/def', 'def'),
                                                                               456: ('/bin/abc', 'abc'),
                                                                               789: ('/bin/ghi', 'ghi')})
    @patch(f'{__app_name__}.service.watcher.core.network.send')
    async def test_check_mappings__must_cache_all_types_of_ignored_mappings_if_enabled(self, *mocks: Mock):
        send_async, map_processes, ignored_read, mapping_read = mocks

        self.context.watch_config.ignored_cache = True  # enabling ignored caching

        self.assertFalse(self.watcher._ignored_cached)
        self.assertIsNone(self.watcher._ignored_exact_strs)
        self.assertIsNone(self.watcher._ignored_cmd_patterns)
        self.assertIsNone(self.watcher._ignored_comm_patterns)

        await self.watcher.check_mappings()  # first call

        self.assertTrue(self.watcher._ignored_cached)
        self.assertEqual({'ghi', 'de*', '/bin/a*'}, self.watcher._ignored_exact_strs)
        self.assertEqual({re.compile(r'^/bin/a.+$')}, self.watcher._ignored_cmd_patterns)
        self.assertEqual({re.compile(r'^de.+$')}, self.watcher._ignored_comm_patterns)

        await self.watcher.check_mappings()  # second call

        self.assertTrue(self.watcher._ignored_cached)
        self.assertEqual({'ghi', 'de*', '/bin/a*'}, self.watcher._ignored_exact_strs)
        self.assertEqual({re.compile(r'^/bin/a.+$')}, self.watcher._ignored_cmd_patterns)
        self.assertEqual({re.compile(r'^de.+$')}, self.watcher._ignored_comm_patterns)

        ignored_read.assert_called_once()
        self.assertEqual(2, mapping_read.call_count)
        self.assertEqual(2, map_processes.call_count)
        send_async.assert_not_called()

        self.assertEqual({}, self.context.optimized)
        self.assertEqual({re.compile(r'^de.+$'): {'123:def'},
                          re.compile(r'^/bin/a.+$'): {'456:abc'},
                          'ghi': {'789:ghi'}}, self.context.ignored_procs)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'def': 'default',
                                                                                     'ghi': 'default'}))
    @patch(f'{__app_name__}.service.watcher.core.ignored.read', return_value=(True, {'def', 'ghi'}))
    @patch(f'{__app_name__}.service.watcher.core.map_processes', return_value={123: ('/bin/def', 'def'),
                                                                               789: ('/bin/ghi', 'ghi')})
    @patch(f'{__app_name__}.service.watcher.core.network.send')
    async def test_check_mappings__must_cache_only_exact_ignored_mappings_available_if_enabled(self, *mocks: Mock):
        send_async, map_processes, ignored_read, mapping_read = mocks

        self.context.watch_config.ignored_cache = True  # enabling ignored caching

        self.assertFalse(self.watcher._ignored_cached)
        self.assertIsNone(self.watcher._ignored_exact_strs)
        self.assertIsNone(self.watcher._ignored_cmd_patterns)
        self.assertIsNone(self.watcher._ignored_comm_patterns)

        await self.watcher.check_mappings()  # first call

        self.assertTrue(self.watcher._ignored_cached)
        self.assertEqual({'ghi', 'def'}, self.watcher._ignored_exact_strs)
        self.assertIsNone(self.watcher._ignored_cmd_patterns)
        self.assertIsNone(self.watcher._ignored_comm_patterns)

        await self.watcher.check_mappings()  # second call

        self.assertTrue(self.watcher._ignored_cached)
        self.assertEqual({'ghi', 'def'}, self.watcher._ignored_exact_strs)
        self.assertIsNone(self.watcher._ignored_cmd_patterns)
        self.assertIsNone(self.watcher._ignored_comm_patterns)

        ignored_read.assert_called_once()
        self.assertEqual(2, mapping_read.call_count)
        self.assertEqual(2, map_processes.call_count)
        send_async.assert_not_called()

        self.assertEqual({}, self.context.optimized)
        self.assertEqual({'def': {'123:def'},
                          'ghi': {'789:ghi'}}, self.context.ignored_procs)
