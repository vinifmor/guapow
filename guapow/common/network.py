import json
import sys
from logging import Logger
from typing import Optional

import aiohttp
from aiohttp import ServerDisconnectedError, ClientConnectorError

from guapow import __app_name__
from guapow.common import encryption
from guapow.common.config import OptimizerConfig
from guapow.common.dto import OptimizationRequest
from guapow.common.encoder import CustomJSONEncoder


async def send(request: OptimizationRequest, opt_config: OptimizerConfig, machine_id: Optional[str], logger: Logger):

    data = json.dumps(request.to_dict(), cls=CustomJSONEncoder)

    if machine_id:
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        data = encryption.encrypt(data, machine_id)
    else:
        headers = {'Content-Type': 'application/json'}

    try:
        logger.info("Sending request {}".format(request))
        async with aiohttp.ClientSession() as session:
            async with session.post(url=f'http://127.0.0.1:{opt_config.port}/',
                                    data=data,
                                    headers=headers) as response:
                if response.status in (200, 202):
                    logger.debug(f"Request successfully sent for pid '{request.pid}'")
                elif response.status == 401:
                    logger.warning(f"Unauthorized request. Optimizations will not be performed for pid '{request.pid}'")
                else:
                    logger.error(f"Unexpected response for the request (pid: {request.pid}, status: {response.status}. body: {await response.text()})")

    except ClientConnectorError:
        sys.stderr.write(f"[{__app_name__}] Request for pid '{request.pid}' could not reach the Optimizer service. It may not be running.\n")
    except ServerDisconnectedError:
        logger.warning(f"Request for pid '{request.pid}' reached the Optimizer service, but it did not respond")
