from unittest import TestCase

from guapow.common.dto import OptimizationRequest
from guapow.common.model import ScriptSettings
from guapow.service.optimizer.gpu import AMDGPUDriver, GPUState, NvidiaPowerMode
from guapow.service.optimizer.profile import OptimizationProfile, CompositorSettings
from guapow.service.optimizer.task.model import OptimizedProcess, CPUState


class OptimizedProcessTest(TestCase):
    
    def setUp(self):
        self.request = OptimizationRequest(pid=123, command='/xpto', user_name='user')
        self.profile = OptimizationProfile.empty('test')
        self.proc = OptimizedProcess(self.request, 76151511, self.profile)

    def test_should_be_watched__true_when_only_post_scripts_are_defined(self):
        self.profile.finish_scripts = ScriptSettings('scripts.finish')
        self.assertIsNone(self.proc.previous_gpus_states)
        self.assertIsNone(self.proc.previous_cpu_state)
        self.assertEqual(set(), self.proc.related_pids)
        self.assertIsNone(self.proc.user_env)
        self.assertIsNone(self.proc.user_id)

        self.assertTrue(self.proc.should_be_watched())

    def test_should_be_watched__true_when_only_related_pids_are_defined(self):
        self.request.related_pids = {456, 789}
        self.proc = OptimizedProcess(self.request, 76151511, self.profile)

        self.assertIsNone(self.proc.previous_gpus_states)
        self.assertIsNone(self.proc.previous_cpu_state)
        self.assertIsNone(self.proc.post_scripts)
        self.assertIsNone(self.proc.user_env)
        self.assertIsNone(self.proc.user_id)

        self.assertTrue(self.proc.should_be_watched())

    def test_should_be_watched__true_when_only_previous_cpu_state_is_defined(self):
        self.proc.previous_cpu_state = CPUState({'schedutil': {1}})
        self.assertIsNone(self.proc.previous_gpus_states)
        self.assertEqual(set(), self.proc.related_pids)
        self.assertIsNone(self.proc.post_scripts)
        self.assertIsNone(self.proc.user_env)
        self.assertIsNone(self.proc.user_id)

        self.assertTrue(self.proc.should_be_watched())

    def test_should_be_watched__true_when_only_previous_gpu_states_are_defined(self):
        self.proc.previous_gpus_states = {AMDGPUDriver: {GPUState('0', AMDGPUDriver, NvidiaPowerMode.ON_DEMAND)}}
        self.assertIsNone(self.proc.previous_cpu_state)
        self.assertEqual(set(), self.proc.related_pids)
        self.assertIsNone(self.proc.post_scripts)
        self.assertIsNone(self.proc.user_env)
        self.assertIsNone(self.proc.user_id)

        self.assertTrue(self.proc.should_be_watched())

    def test_should_be_watched__true_when_only_profile_requires_the_compositor_disabled(self):
        self.profile.compositor = CompositorSettings(off=True)
        self.assertTrue(self.proc.should_be_watched())

    def test_should_be_watched__false_when_only_profile_does_not_requires_the_compositor_disabled(self):
        self.profile.compositor = CompositorSettings(off=False)
        self.assertFalse(self.proc.should_be_watched())

    def test_should_be_watched__false_when_only_pid_is_defined(self):
        self.assertIsNone(self.proc.previous_cpu_state)
        self.assertIsNone(self.proc.previous_gpus_states)
        self.assertIsNone(self.proc.post_scripts)
        self.assertIsNone(self.proc.user_env)
        self.assertIsNone(self.proc.user_id)
        self.assertEqual(set(), self.proc.related_pids)

        self.assertFalse(self.proc.should_be_watched())

    def test_should_be_watched__true_when_process_profile_defines_hide_mouse(self):
        self.profile.hide_mouse = True
        self.assertTrue(self.proc.should_be_watched())

    def test_should_be_watched__true_when_processes_stopped_after_launch_are_defined(self):
        self.proc.stopped_after_launch = {'a'}
        self.assertTrue(self.proc.should_be_watched())

    def test_should_be_watched__true_when_cpu_energy_policy_changed(self):
        self.proc.cpu_energy_policy_changed = True
        self.assertTrue(self.proc.should_be_watched())

    def test_get_display__must_return_zero_when_no_user_env_is_defined(self):
        proc = OptimizedProcess(OptimizationRequest.self_request(), 123)
        self.assertEqual(':0', proc.get_display())

    def test_get_display__must_return_zero_when_user_env_has_no_DISPLAY_var(self):
        req = OptimizationRequest.self_request()
        req.user_env = {'a': 1}

        proc = OptimizedProcess(req, 123)
        self.assertEqual(':0', proc.get_display())

    def test_get_display__must_return_user_env_DISPLAY_var_value(self):
        req = OptimizationRequest.self_request()
        req.user_env = {'DISPLAY': ':1'}

        proc = OptimizedProcess(req, 123)
        self.assertEqual(':1', proc.get_display())

    def test_clone__returned_instance_must_be_equal_the_source(self):
        self.proc.previous_cpu_state = CPUState({'schedutil': {1}})
        self.proc.previous_gpus_states = {AMDGPUDriver: {GPUState('0', AMDGPUDriver, NvidiaPowerMode.ON_DEMAND)}}
        self.proc.cpu_energy_policy_changed = True
        self.profile.hide_mouse = True
        self.request.related_pids = {456, 789}

        clone = self.proc.clone()
        self.assertEqual(self.proc, clone)

        # checking every attribute to make sure
        for attr, val in self.proc.__dict__.items():
            self.assertEqual(val, getattr(clone, attr))

        self.assertNotEqual(id(clone), id(self.proc))  # must not have the same memory address

    def test_clone__returned_instance_pid_change_must_not_reflect_on_the_source(self):
        clone = self.proc.clone()
        clone.pid = 525267
        self.assertNotEqual(self.proc.pid, clone.pid)
        self.assertNotEqual(self.proc, clone)
        self.assertEqual(self.proc.source_pid, clone.source_pid)  # source pid must not be changed

    def test_clone__returned_instance_must_be_watchable_if_source_is_watchable(self):
        self.proc.previous_cpu_state = CPUState({'schedutil': {1}})
        self.assertTrue(self.proc.should_be_watched())

        clone = self.proc.clone()
        self.assertTrue(clone.should_be_watched())
