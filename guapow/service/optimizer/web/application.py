from logging import Logger

from aiohttp import web

from guapow.common.auth import read_machine_id
from guapow.common.config import OptimizerConfig
from guapow.common.users import map_home_users, map_all_users
from guapow.service.optimizer.flow import OptimizationQueue
from guapow.service.optimizer.handler import OptimizationHandler
from guapow.service.optimizer.web import routes, middlewares


async def create_web_app(handler: OptimizationHandler, queue: OptimizationQueue, config: OptimizerConfig, logger: Logger) -> web.Application:
    app = web.Application()
    app.logger = logger
    app['queue'] = queue
    app['handler'] = handler

    if config.request and config.request.allowed_users:
        all_users = map_all_users()
        app['allowed_users'] = {user: all_users.get(user) for user in config.request.allowed_users if user in all_users}
    else:
        app['allowed_users'] = map_home_users()

    logger.info(f"Requests allowed for users: {', '.join(sorted(app['allowed_users']))}")

    if config.encrypted_requests:
        machine_id = await read_machine_id()

        if machine_id:
            app['machine_id'] = machine_id
            app.middlewares.append(middlewares.decrypt_request)
            logger.info("Requests encryption is enabled")
        else:
            logger.warning("Requests encryption is disabled since machine-id could not be read")
    else:
        logger.warning("Requests encryption is disabled")

    app.middlewares.append(middlewares.hide_server_headers)
    app.add_routes([web.post('/', routes.optimize)])
    return app
