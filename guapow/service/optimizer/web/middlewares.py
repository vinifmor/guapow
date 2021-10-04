from typing import Callable

from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import Response

from guapow.common.encryption import decrypt


@web.middleware
async def decrypt_request(request: Request, handler: Callable):
    machine_id = request.app.get('machine_id')

    if machine_id:
        try:
            encrypted_token = (await request.text()).strip()
        except:
            return Response(status=401)

        if not encrypted_token:
            return Response(status=401)

        try:
            decrypted_text = decrypt(encrypted_token, machine_id)
        except:
            return Response(status=401)

        if not decrypted_text:
            return Response(status=401)

        request['decrypted_text'] = decrypted_text

    return await handler(request)


@web.middleware
async def hide_server_headers(request: Request, handler: Callable):
    response = await handler(request)
    response.headers['Server'] = ''
    return response
