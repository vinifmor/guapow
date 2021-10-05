from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, patch

from aiohttp import web

from guapow import __app_name__
from guapow.common.config import OptimizerConfig, RequestSettings
from guapow.service.optimizer.flow import OptimizationQueue
from guapow.service.optimizer.web import middlewares, routes
from guapow.service.optimizer.web.application import create_web_app


class CreateWebAppTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.config = OptimizerConfig.empty()
        self.config.encryption = True
        self.config.request = RequestSettings.default()

    @patch(f'{__app_name__}.service.optimizer.web.application.read_machine_id', return_value='123')
    @patch(f'{__app_name__}.service.optimizer.web.application.map_home_users', return_value={'test': 1})
    async def test__must_add_decrypt_text_middleware_when_machine_id_is_available(self, map_home_users: Mock, read_machine_id: Mock):
        app = await create_web_app(handler=Mock(), queue=OptimizationQueue.empty(),  config=self.config, logger=Mock())
        self.assertIsInstance(app, web.Application)

        self.assertIn('machine_id', app)
        self.assertEqual('123', app['machine_id'])

        self.assertEqual([middlewares.decrypt_request, middlewares.hide_server_headers], app.middlewares)

        read_machine_id.assert_called_once()
        map_home_users.assert_called_once()

    @patch(f'{__app_name__}.service.optimizer.web.application.read_machine_id', return_value=None)
    @patch(f'{__app_name__}.service.optimizer.web.application.map_home_users', return_value={'test': 1})
    async def test__must_not_add_decrypt_request_middleware_when_machine_id_is_unavailable(self, map_home_users: Mock, read_machine_id: Mock):
        app = await create_web_app(handler=Mock(), queue=OptimizationQueue.empty(),  config=self.config, logger=Mock())
        self.assertIsInstance(app, web.Application)

        self.assertNotIn('machine_id', app)
        self.assertEqual([middlewares.hide_server_headers], app.middlewares)  # only 'hide_server_headers' must have been added

        read_machine_id.assert_called_once()
        map_home_users.assert_called_once()

    @patch(f'{__app_name__}.service.optimizer.web.application.read_machine_id')
    @patch(f'{__app_name__}.service.optimizer.web.application.map_home_users', return_value={'test': 1})
    async def test__must_not_add_decrypt_request_middleware_when_optimizer_config_has_decryption_set_to_false(self, map_home_users: Mock, read_machine_id: Mock):
        self.config.request.encrypted = False
        app = await create_web_app(handler=Mock(), queue=OptimizationQueue.empty(),  config=self.config, logger=Mock())
        self.assertIsInstance(app, web.Application)

        self.assertNotIn('machine_id', app)
        self.assertNotIn(middlewares.decrypt_request, app.middlewares)

        read_machine_id.assert_not_called()
        map_home_users.assert_called_once()

    @patch(f'{__app_name__}.service.optimizer.web.application.read_machine_id', return_value=None)
    @patch(f'{__app_name__}.service.optimizer.web.application.map_home_users', return_value={'test': 1})
    async def test__must_always_add_the_optimize_route(self, map_home_users: Mock, read_machine_id: Mock):
        handler = Mock()
        app = await create_web_app(handler=handler, config=self.config, logger=Mock(), queue=OptimizationQueue.empty())
        self.assertIsInstance(app, web.Application)

        self.assertIn('handler', app)
        self.assertEqual(handler, app['handler'])

        app_routes = [r for r in app.router.routes()]
        self.assertEqual(1, len(app_routes))
        self.assertEqual('POST', app_routes[0].method)
        self.assertEqual('/', app_routes[0].url_for().path)
        self.assertEqual(routes.optimize, app_routes[0].handler)

        read_machine_id.assert_called_once()
        map_home_users.assert_called_once()

    @patch(f'{__app_name__}.service.optimizer.web.application.read_machine_id', return_value=None)
    @patch(f'{__app_name__}.service.optimizer.web.application.map_home_users', return_value={'test': 1, 'root': 0})
    async def test__must_add_home_users_to_the_context_when_allowed_are_not_defined(self, map_home_users: Mock, read_machine_id: Mock):
        app = await create_web_app(handler=Mock(), queue=OptimizationQueue.empty(),  config=self.config, logger=Mock())
        self.assertIsInstance(app, web.Application)
        self.assertEqual({'test': 1, 'root': 0}, app['allowed_users'])
        read_machine_id.assert_called_once()
        map_home_users.assert_called_once()

    @patch(f'{__app_name__}.service.optimizer.web.application.read_machine_id', return_value=None)
    @patch(f'{__app_name__}.service.optimizer.web.application.map_home_users')
    @patch(f'{__app_name__}.service.optimizer.web.application.map_all_users', return_value={'root': 0, 'test': 1})
    async def test__must_only_add_defined_existing_allowed_users_to_the_context(self, map_all_users: Mock, map_home_users: Mock, read_machine_id: Mock):
        self.config.request.allowed_users = {'test', 'abc'}  # 'abc' does not exist
        app = await create_web_app(handler=Mock(), queue=OptimizationQueue.empty(),  config=self.config, logger=Mock())
        self.assertIsInstance(app, web.Application)
        self.assertEqual({'test': 1}, app['allowed_users'])
        read_machine_id.assert_called_once()
        map_all_users.assert_called_once()
        map_home_users.assert_not_called()
