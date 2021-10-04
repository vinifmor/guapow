import re
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, patch, call

from guapow import __app_name__
from guapow.common.config import OptimizerConfig
from guapow.common.dto import OptimizationRequest
from guapow.service.watcher.config import ProcessWatcherConfig
from guapow.service.watcher.core import ProcessWatcher, ProcessWatcherContext
from guapow.service.watcher.mapping import RegexMapper


class ProcessWatcherTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.context = ProcessWatcherContext(user_id=1, user_name='xpto', user_env={'a': '1'}, logger=Mock(),
                                             mapping_file_path='test.map', optimized={}, opt_config=OptimizerConfig.default(),
                                             watch_config=ProcessWatcherConfig.default(), machine_id='abc126517ha')
        self.watcher = ProcessWatcher(regex_mapper=RegexMapper(cache=False, logger=Mock()), context=self.context)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(False, None))
    @patch(f'{__app_name__}.service.watcher.core.map_processes')
    async def test_check_mappings__must_not_map_processes_when_no_mapping_is_found(self, map_processes: Mock, mapping_read: Mock):
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
        map_processes.assert_not_called()

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'abc': 'default'}))
    @patch(f'{__app_name__}.service.watcher.core.map_processes', return_value={})
    async def test_check_mappings__must_clear_the_optimized_context_when_no_process_could_be_retrieved(self, map_processes: Mock, mapping_read: Mock):
        self.context.optimized.update({1: 'abc', 2: 'def'})
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
        map_processes.assert_called_once()
        self.assertEqual({}, self.context.optimized)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'abc': 'default'}))
    @patch(f'{__app_name__}.service.watcher.core.map_processes', return_value={123: ('/bin/def', 'def')})
    @patch(f'{__app_name__}.service.watcher.core.network.send')
    async def test_check_mappings__must_no_perform_any_request_in_case_of_no_mapping_matches(self, send_async: Mock, map_processes: Mock, mapping_read: Mock):
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
        map_processes.assert_called_once()
        send_async.assert_not_called()
        self.assertEqual({}, self.context.optimized)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'a': 'default', 'b': 'prof_1', '/bin/c': 'prof_2'}))
    @patch(f'{__app_name__}.service.watcher.core.map_processes', return_value={1: ('/bin/a', 'a'),
                                                                                       2: ('/bin/b', 'b'),
                                                                                       3: ('/bin/c', 'c'),
                                                                                       4: ('/bin/d', 'd')})  # no profile for this process
    @patch(f'{__app_name__}.service.watcher.core.network.send', return_value=True)
    @patch(f'{__app_name__}.service.watcher.core.time.time', return_value=12345)
    async def test_check_mappings__must_trigger_requests_for_mapped_processes(self, time: Mock, send_async: Mock, map_processes: Mock, mapping_read: Mock):
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
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
    @patch(f'{__app_name__}.service.watcher.core.map_processes', return_value={1: ('/bin/a', 'a'),
                                                                                       2: ('/bin/b', 'b')})  # no profile for this process
    @patch(f'{__app_name__}.service.watcher.core.network.send', return_value=True)
    @patch(f'{__app_name__}.service.watcher.core.time.time', return_value=12345)
    async def test_check_mappings__cmd_mapping_must_have_higher_priority_than_comm(self, time: Mock, send_async: Mock, map_processes: Mock, mapping_read: Mock):
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
        map_processes.assert_called_once()
        time.assert_called()

        req_a = OptimizationRequest(pid=1, command='/bin/a', user_name=self.context.user_name,
                                    user_env=self.context.user_env, profile='prof_2', created_at=12345)

        send_async.assert_has_calls([call(req_a, self.context.opt_config, self.context.machine_id, self.context.logger)], any_order=True)

        self.assertEqual({1: '/bin/a'}, self.context.optimized)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'a': 'default'}))
    @patch(f'{__app_name__}.service.watcher.core.map_processes',
           return_value={1: ('/bin/a', 'a')})
    @patch(f'{__app_name__}.service.watcher.core.network.send', return_value=False)
    async def test_check_mappings__must_add_process_to_the_optimized_context_when_request_fail(self, send_async: Mock, map_processes: Mock, mapping_read: Mock):
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
        map_processes.assert_called_once()
        send_async.assert_called_once()
        self.assertEqual({1: 'a'}, self.context.optimized)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'a': 'default'}))
    @patch(f'{__app_name__}.service.watcher.core.map_processes',
           return_value={1: ('/bin/a', 'a')})
    @patch(f'{__app_name__}.service.watcher.core.network.send', return_value=True)
    async def test_check_mappings__must_remove_an_optimized_process_from_the_context_when_it_is_not_alive(self, send_async: Mock, map_processes: Mock, mapping_read: Mock):
        self.context.optimized.update({2: 'b'})  # 'b' was previously optimized, but will not me mapped as a process alive
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
        map_processes.assert_called_once()
        send_async.assert_called_once()
        self.assertEqual({1: 'a'}, self.context.optimized)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'a': 'default'}))
    @patch(f'{__app_name__}.service.watcher.core.map_processes',
           return_value={1: ('/bin/a', 'a')})
    @patch(f'{__app_name__}.service.watcher.core.network.send')
    async def test_check_mappings__must_not_send_a_new_request_for_a_previously_optimized_process(self, send_async: Mock, map_processes: Mock, mapping_read: Mock):
        self.context.optimized.update({1: 'a'})  # 'a' was previously optimized and still alive
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
        map_processes.assert_called_once()
        send_async.assert_not_called()
        self.assertEqual({1: 'a'}, self.context.optimized)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'a': 'default'}))
    @patch(f'{__app_name__}.service.watcher.core.map_processes',
           return_value={1: ('/bin/a', 'a'), 2: ('/bin/a', 'a')})
    @patch(f'{__app_name__}.service.watcher.core.network.send')
    @patch(f'{__app_name__}.service.watcher.core.time.time', return_value=12345)
    async def test_check_mappings__must_send_a_new_request_for_a_previously_optimized_command_with_a_different_pid(self, time: Mock, send_async: Mock, map_processes: Mock, mapping_read: Mock):
        self.context.optimized.update({1: 'a'})  # 'a' (1) was previously optimized and still alive
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
        map_processes.assert_called_once()

        exp_req = OptimizationRequest(pid=2, command='/bin/a', user_name=self.context.user_name,
                                      user_env=self.context.user_env, profile='default', created_at=12345)

        send_async.assert_called_once_with(exp_req, self.context.opt_config, self.context.machine_id, self.context.logger)
        self.assertEqual({1: 'a', 2: 'a'}, self.context.optimized)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'a*': 'default', '/bin/*': 'prof_1', '/local/d': 'prof_2'}))
    @patch(f'{__app_name__}.service.watcher.core.map_processes', return_value={1: ('/local/bin/abacaxi', 'abacaxi'),
                                                                                       2: ('/bin/b', 'b'),
                                                                                       3: ('/bin/c', 'c')})
    @patch(f'{__app_name__}.service.watcher.core.network.send', return_value=True)
    @patch(f'{__app_name__}.service.watcher.core.time.time', return_value=12345)
    async def test_check_mappings__must_trigger_requests_for_mapped_using_regex(self, time: Mock, send_async: Mock, map_processes: Mock, mapping_read: Mock):
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
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
    @patch(f'{__app_name__}.service.watcher.core.map_processes', return_value={1: ('/local/bin/abacaxi', 'abacaxi'),
                                                                                       2: ('/bin/b', 'b')})
    @patch(f'{__app_name__}.service.watcher.core.network.send', return_value=True)
    @patch(f'{__app_name__}.service.watcher.core.time.time', return_value=12345)
    async def test_check_mappings__a_request_must_be_sent_when_an_exact_comm_match_fails_but_a_pattern_works(self, time: Mock, send_async: Mock, map_processes: Mock, mapping_read: Mock):
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
        map_processes.assert_called_once()
        time.assert_called()

        req_a = OptimizationRequest(pid=1, command='/local/bin/abacaxi', user_name=self.context.user_name,
                                    user_env=self.context.user_env, profile='prof1', created_at=12345)

        send_async.assert_has_calls([call(req_a, self.context.opt_config, self.context.machine_id, self.context.logger)], any_order=True)

        self.assertEqual({1: 'abacaxi'}, self.context.optimized)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'abacaxi': 'default', 'a**': 'prof1'}))  # both matches
    @patch(f'{__app_name__}.service.watcher.core.map_processes', return_value={1: ('/local/bin/abacaxi', 'abacaxi'),
                                                                                       2: ('/bin/b', 'b')})
    @patch(f'{__app_name__}.service.watcher.core.network.send', return_value=True)
    @patch(f'{__app_name__}.service.watcher.core.time.time', return_value=12345)
    async def test_check_mappings__comm_exact_match_must_prevail_over_a_regex_match(self, time: Mock, send_async: Mock, map_processes: Mock, mapping_read: Mock):
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
        map_processes.assert_called_once()
        time.assert_called()

        req_a = OptimizationRequest(pid=1, command='/local/bin/abacaxi', user_name=self.context.user_name,
                                    user_env=self.context.user_env, profile='default', created_at=12345)  # the comm exact match points to 'default' profile

        send_async.assert_has_calls([call(req_a, self.context.opt_config, self.context.machine_id, self.context.logger)], any_order=True)

        self.assertEqual({1: 'abacaxi'}, self.context.optimized)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'/local/bin/abacaxi': 'default', '/local/*': 'prof1'}))  # both matches
    @patch(f'{__app_name__}.service.watcher.core.map_processes', return_value={1: ('/local/bin/abacaxi', 'abacaxi'),
                                                                                       2: ('/bin/b', 'b')})
    @patch(f'{__app_name__}.service.watcher.core.network.send', return_value=True)
    @patch(f'{__app_name__}.service.watcher.core.time.time', return_value=12345)
    async def test_check_mappings__cmd_exact_match_must_prevail_over_a_regex_match(self, time: Mock, send_async: Mock, map_processes: Mock, mapping_read: Mock):
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
        map_processes.assert_called_once()
        time.assert_called()

        req_a = OptimizationRequest(pid=1, command='/local/bin/abacaxi', user_name=self.context.user_name,
                                    user_env=self.context.user_env, profile='default', created_at=12345)  # the cmd exact match points to 'default' profile

        send_async.assert_has_calls([call(req_a, self.context.opt_config, self.context.machine_id, self.context.logger)], any_order=True)

        self.assertEqual({1: '/local/bin/abacaxi'}, self.context.optimized)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'abacaxi': 'default', '/local/*': 'prof1'}))  # both matches
    @patch(f'{__app_name__}.service.watcher.core.map_processes', return_value={1: ('/local/bin/abacaxi', 'abacaxi'), 2: ('/bin/b', 'b')})
    @patch(f'{__app_name__}.service.watcher.core.network.send', return_value=True)
    @patch(f'{__app_name__}.service.watcher.core.time.time', return_value=12345)
    async def test_check_mappings__cmd_regex_match_must_prevail_over_a_comm_exact_match(self, time: Mock,
                                                                                        send_async: Mock,
                                                                                        map_processes: Mock,
                                                                                        mapping_read: Mock):
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
        map_processes.assert_called_once()
        time.assert_called()

        req_a = OptimizationRequest(pid=1, command='/local/bin/abacaxi', user_name=self.context.user_name,
                                    user_env=self.context.user_env, profile='prof1',  # the cmd regex match points to 'prof1' profile
                                    created_at=12345)

        send_async.assert_has_calls([call(req_a, self.context.opt_config, self.context.machine_id, self.context.logger)], any_order=True)

        self.assertEqual({1: '/local/bin/abacaxi'}, self.context.optimized)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'/local/*': 'default', '/local/*/a*': 'prof1'}))  # both matches
    @patch(f'{__app_name__}.service.watcher.core.map_processes', return_value={1: ('/local/bin/abacaxi', 'abacaxi'), 2: ('/bin/b', 'b')})
    @patch(f'{__app_name__}.service.watcher.core.network.send', return_value=True)
    @patch(f'{__app_name__}.service.watcher.core.time.time', return_value=12345)
    async def test_check_mappings__more_specific_cmd_match_must_prevail_over_others(self, time: Mock,
                                                                                    send_async: Mock,
                                                                                    map_processes: Mock,
                                                                                    mapping_read: Mock):
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
        map_processes.assert_called_once()
        time.assert_called()

        req_a = OptimizationRequest(pid=1, command='/local/bin/abacaxi', user_name=self.context.user_name,
                                    user_env=self.context.user_env, profile='prof1',  # the cmd regex match points to 'prof1' profile
                                    created_at=12345)

        send_async.assert_has_calls([call(req_a, self.context.opt_config, self.context.machine_id, self.context.logger)], any_order=True)
        self.assertEqual({1: '/local/bin/abacaxi'}, self.context.optimized)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'ab*': 'default', 'aba*': 'prof1'}))  # both matches
    @patch(f'{__app_name__}.service.watcher.core.map_processes', return_value={1: ('/local/bin/abacaxi', 'abacaxi'), 2: ('/bin/b', 'b')})
    @patch(f'{__app_name__}.service.watcher.core.network.send', return_value=True)
    @patch(f'{__app_name__}.service.watcher.core.time.time', return_value=12345)
    async def test_check_mappings__more_specific_comm_match_must_prevail_over_others(self, time: Mock,
                                                                                     send_async: Mock,
                                                                                     map_processes: Mock,
                                                                                     mapping_read: Mock):
        await self.watcher.check_mappings()
        mapping_read.assert_called_once_with(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None)
        map_processes.assert_called_once()
        time.assert_called()

        req_a = OptimizationRequest(pid=1, command='/local/bin/abacaxi', user_name=self.context.user_name,
                                    user_env=self.context.user_env, profile='prof1',  # the cmd regex match points to 'prof1' profile
                                    created_at=12345)

        send_async.assert_has_calls([call(req_a, self.context.opt_config, self.context.machine_id, self.context.logger)], any_order=True)
        self.assertEqual({1: 'abacaxi'}, self.context.optimized)

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'a*': 'default', '/bin/*': 'prof_1', '/local/d': 'prof_2'}))
    @patch(f'{__app_name__}.service.watcher.core.map_processes', side_effect=[{1: ('/local/bin/abacaxi', 'abacaxi'),
                                                                                       2: ('/bin/b', 'b'),
                                                                                       3: ('/bin/c', 'c')},
                                                                                      {4: ('/xpto', 'xpto')}])
    @patch(f'{__app_name__}.service.watcher.core.network.send', return_value=True)
    @patch(f'{__app_name__}.service.watcher.core.time.time', return_value=12345)
    async def test_check_mappings__must_cache_mapping_when_defined_on_config(self, time: Mock, send_async: Mock, map_processes: Mock, mapping_read: Mock):
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
        self.assertEqual(2, map_processes.call_count)
        time.assert_called()

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', return_value=(True, {'a*': 'default', '/bin/*': 'prof_1', '/local/d': 'prof_2'}))
    @patch(f'{__app_name__}.service.watcher.core.map_processes', side_effect=[{1: ('/local/bin/abacaxi', 'abacaxi')},
                                                                                      {4: ('/bin/b', 'b')}])
    @patch(f'{__app_name__}.service.watcher.core.network.send', return_value=True)
    @patch(f'{__app_name__}.service.watcher.core.time.time', return_value=12345)
    async def test_check_mappings__must_always_read_mapping_from_disk_when_cache_is_off(self, time: Mock, send_async: Mock, map_processes: Mock, mapping_read: Mock):
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
        self.assertEqual(2, map_processes.call_count)
        time.assert_called()

    @patch(f'{__app_name__}.service.watcher.core.mapping.read', side_effect=[(True, None), (False, None), (False, None), (True, None), (False, None)])
    @patch(f'{__app_name__}.service.watcher.core.map_processes')
    @patch(f'{__app_name__}.service.watcher.core.network.send')
    async def test_check_mappings__must_always_call_read_with_the_last_file_found_result(self, send: Mock, map_processes: Mock, mapping_read: Mock):
        for _ in range(5):
            await self.watcher.check_mappings()

        mapping_read.assert_has_calls([call(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=None),
                                       call(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=True),
                                       call(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=False),
                                       call(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=False),
                                       call(file_path=self.context.mapping_file_path, logger=self.context.logger, last_file_found_log=True)])

        send.assert_not_called()
        map_processes.assert_not_called()
