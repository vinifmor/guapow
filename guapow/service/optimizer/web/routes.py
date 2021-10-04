import asyncio
import json
from json import JSONDecodeError

from aiohttp import web

from guapow.common.dto import OptimizationRequest


async def optimize(request: web.Request):
    body = request.get('decrypted_text')

    if body is None:
        body = (await request.text()).strip()

    try:
        opt_req = OptimizationRequest(**json.loads(body))
    except (JSONDecodeError, TypeError):
        request.app.logger.warning('Invalid request')
        return web.Response(status=400)

    if opt_req.user_name:
        opt_req.user_id = request.app['allowed_users'].get(opt_req.user_name)

        if opt_req.user_id is None:
            request.app.logger.info(f"Request not allowed for user '{opt_req.user_name}' (pid={opt_req.pid})")
            return web.Response(status=401)

    if opt_req.is_valid():

        request.app.logger.info(f'New request: {opt_req}')

        if await request.app['queue'].add_pid(opt_req.pid):
            asyncio.create_task(request.app['handler'].handle(opt_req))
            return web.Response(status=200)
        else:
            request.app.logger.info(f"Repeated request for process {opt_req.pid}. Ignoring it.")
            return web.Response(status=202)
    else:
        request.app.logger.warning(f'Invalid request: {opt_req}')
        return web.Response(status=400)
