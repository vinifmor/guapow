from unittest import TestCase

from guapow.service.optimizer.post_process.context import PostProcessContextMapper, RestorableCPUsFiller, \
    RestorableGPUsFiller, \
    SortedFinishScriptsFiller, SortedProcessesToRelaunchFiller, PostProcessContext
from guapow.service.optimizer.post_process.summary import PostProcessSummary


class SortedProcessesToRelaunchTest(TestCase):

    def setUp(self):
        self.task = SortedProcessesToRelaunchFiller()
        self.post_summary = PostProcessSummary.empyt()
        self.context = PostProcessContext.empty()

    def test_fill__must_not_add_duplicate_comm_cmds_to_the_context(self):
        self.post_summary.processes_relaunch_by_time = {1: {'abc': '/bin/abc'},
                                                        2: {'abc': '/bin/abc'},  # duplicate
                                                        3: {'def': '/bin/def'},
                                                        4: {'def': '/bin/def --xpto'},  # different command (must be relaunched),
                                                        5: {'xpto': '/bin/def'}  # different name (must be relaunched)
                                                        }

        self.assertIsNone(self.context.stopped_processes)
        self.task.fill(self.context, self.post_summary)

        exp_procs = [('abc', '/bin/abc'), ('def', '/bin/def'), ('def', '/bin/def --xpto'), ('xpto', ('/bin/def'))]

        self.assertEqual(exp_procs, self.context.stopped_processes)
        self.assertIsNone(self.context.not_stopped_processes)

    def test_fill__must_add_processes_with_no_commands_to_the_context_as_not_stopped(self):
        self.post_summary.processes_relaunch_by_time = {1: {'abc': '/bin/abc'},
                                                        2: {'def': None},  # not stooped
                                                        3: {'ghi': '/bin/ghi'},
                                                        4: {'jkl': None},  # not stopped
                                                        5: {'mno': None},  # not stopped
                                                        6: {'mno': '/bin/mno'}
                                                        }

        self.assertIsNone(self.context.stopped_processes)
        self.task.fill(self.context, self.post_summary)

        self.assertEqual([('abc', '/bin/abc'), ('ghi', '/bin/ghi'), ('mno', '/bin/mno')], self.context.stopped_processes)
        self.assertEqual({'def', 'jkl'}, self.context.not_stopped_processes)


class PostProcessContextMapperTest(TestCase):

    def test_instance__must_always_return_the_same_instance(self):
        instance = PostProcessContextMapper.instance()
        self.assertEqual(instance, PostProcessContextMapper.instance())

    def test_instance__must_be_filled_with_the_correct_fillers_order(self):
        fillers = PostProcessContextMapper.instance().get_fillers()
        self.assertIsNotNone(fillers)

        expected_fillers = [RestorableCPUsFiller, RestorableGPUsFiller, SortedFinishScriptsFiller, SortedProcessesToRelaunchFiller]

        self.assertEqual(len(expected_fillers), len(fillers))

        for idx, cls in enumerate(expected_fillers):
            self.assertEqual(1, len([f for f in fillers if type(f) == cls]))
