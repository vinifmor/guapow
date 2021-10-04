import json
from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock, AsyncMock, Mock

from aiohttp import web

from guapow.common.dto import OptimizationRequest
from guapow.service.optimizer.flow import OptimizationQueue
from guapow.service.optimizer.web import routes


class OptimizeTest(IsolatedAsyncioTestCase):

    async def test__must_add_the_user_id_to_the_request_when_it_exists(self):
        opt_req_dict = {'user_name': 'xpto', 'command': '/bin/a', 'pid': 123}
        req = MagicMock()
        req.get = MagicMock(return_value=None)
        req.text = AsyncMock()
        req.text.return_value = json.dumps(opt_req_dict)
        req.app = web.Application()
        req.app.logger = Mock()
        req.app['allowed_users'] = {'xpto': 345}
        req.app['queue'] = OptimizationQueue.empty()
        req.app['handler'] = Mock()
        req.app['handler'].handle = AsyncMock()

        res = await routes.optimize(req)
        self.assertEqual(200, res.status)

        exp_opt_req = OptimizationRequest(**opt_req_dict)
        exp_opt_req.user_id = 345

        req.app['handler'].handle.assert_called_once_with(exp_opt_req)

    async def test__must_return_401_when_user_name_is_not_allowed(self):
        opt_req_dict = {'user_name': 'x', 'command': '/bin/a', 'pid': 123}
        req = MagicMock()
        req.get = MagicMock(return_value=None)
        req.text = AsyncMock()
        req.text.return_value = json.dumps(opt_req_dict)
        req.app = web.Application()
        req.app.logger = Mock()
        req.app['allowed_users'] = {'xpto': 345}
        req.app['queue'] = OptimizationQueue.empty()
        req.app['handler'] = Mock()
        req.app['handler'].handle = AsyncMock()

        res = await routes.optimize(req)
        self.assertEqual(401, res.status)

        req.app['handler'].handle.assert_not_called()

    async def test__must_return_400_when_user_name_is_not_defined(self):
        opt_req_dict = {'command': '/bin/a', 'pid': 123}
        req = MagicMock()
        req.get = MagicMock(return_value=None)
        req.text = AsyncMock()
        req.text.return_value = json.dumps(opt_req_dict)
        req.app = web.Application()
        req.app.logger = Mock()
        req.app['handler'] = Mock()
        req.app['handler'].handle = AsyncMock()
        req.app['queue'] = OptimizationQueue.empty()

        res = await routes.optimize(req)
        self.assertEqual(400, res.status)

        req.app['handler'].handle.assert_not_called()

    async def test__must_return_202_for_requests_with_pids_already_being_processed(self):
        opt_req_dict = {'command': '/bin/a', 'pid': 123, 'user_name': 'xpto'}
        req = MagicMock()
        req.get = MagicMock(return_value=None)
        req.text = AsyncMock()
        req.text.return_value = json.dumps(opt_req_dict)
        req.app = web.Application()
        req.app.logger = Mock()
        req.app['handler'] = Mock()
        req.app['handler'].handle = AsyncMock()
        req.app['allowed_users'] = {'xpto': 345}
        req.app['queue'] = OptimizationQueue({123})

        res = await routes.optimize(req)
        self.assertEqual(202, res.status)

        req.app['handler'].handle.assert_not_called()
