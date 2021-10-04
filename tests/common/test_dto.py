from unittest import TestCase
from unittest.mock import patch, Mock

from guapow import __app_name__
from guapow.common.dto import OptimizationRequest


class OptimizationRequestTest(TestCase):

    def test_is_valid__must_return_false_when_pid_is_not_defined(self):
        req = OptimizationRequest(pid=None, command='bin', user_name='xpto', profile=None)
        self.assertFalse(req.is_valid())

    def test_is_valid__must_return_false_when_pid_is_less_than_zero(self):
        req = OptimizationRequest(pid=-1, command='bin', user_name='xpto', profile=None)
        self.assertFalse(req.is_valid())

    def test_is_valid__must_return_true_when_pid_is_higher_than_zero(self):
        req = OptimizationRequest(pid=0, command='bin', user_name='xpto', profile=None)
        req.user_id = 1
        self.assertTrue(req.is_valid())

    def test_is_valid__must_return_false_when_user_is_not_defined(self):
        req = OptimizationRequest(pid=123, command='abc', user_name=None, profile=None)
        self.assertFalse(req.is_valid())

        req = OptimizationRequest(pid=123, command='abc', user_name='', profile=None)
        self.assertFalse(req.is_valid())

    def test_is_valid__must_return_false_when_command_is_not_defined(self):
        req = OptimizationRequest(pid=123, command=None, user_name='xpto', profile=None)
        self.assertFalse(req.is_valid())

        req = OptimizationRequest(pid=123, command='', user_name='xpto', profile=None)
        self.assertFalse(req.is_valid())

    def test_self_request__pid_command_and_user_must_not_be_defined(self):
        request = OptimizationRequest.self_request()
        self.assertIsNone(request.pid)
        self.assertIsNone(request.user_name)
        self.assertIsNone(request.command)
        self.assertTrue(request.is_self_request)

    @patch(f'{__app_name__}.common.dto.os.getenv', return_value=':1')
    def test_prepare__must_get_DISPLAY_env_var_from_the_system_when_not_defined(self, getenv: Mock):
        request = OptimizationRequest.self_request()
        request.user_env = {'xpto': '1'}

        request.prepare()
        getenv.assert_called_once_with('DISPLAY', ':0')

        self.assertIn('DISPLAY', request.user_env)
        self.assertEqual(':1', request.user_env['DISPLAY'])
