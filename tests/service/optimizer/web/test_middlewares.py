from asyncio import Future
from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock, Mock, AsyncMock, patch

from aiohttp import web

from guapow import __app_name__
from guapow.service.optimizer.web.middlewares import decrypt_request


class DecryptRequestTest(IsolatedAsyncioTestCase):

    @patch(f'{__app_name__}.service.optimizer.web.middlewares.decrypt')
    async def test__must_not_try_to_decrypt_when_machine_id_not_defined_on_context(self, decrypt: Mock):
        request = MagicMock()
        request.app = web.Application()

        handler = MagicMock(return_value=Future())
        handler.return_value.set_result(web.Response(status=200))

        res = await decrypt_request(request, handler)
        self.assertIsInstance(res, web.Response)
        self.assertEqual(200, res.status)

        decrypt.assert_not_called()
        handler.assert_called_once_with(request)

    @patch(f'{__app_name__}.service.optimizer.web.middlewares.decrypt')
    async def test__must_return_401_when_no_text_is_defined(self, decrypt: Mock):
        request = MagicMock()
        request.app = web.Application()
        request.app['machine_id'] = '123'
        request.app.logger = MagicMock()
        request.text = AsyncMock()
        request.text.return_value = ''

        res = await decrypt_request(request, Mock())
        self.assertIsInstance(res, web.Response)
        self.assertEqual(401, res.status)

        decrypt.assert_not_called()

    @patch(f'{__app_name__}.service.optimizer.web.middlewares.decrypt', side_effect=RuntimeError())
    async def test__must_return_401_when_decryption_fails(self, decrypt: Mock):
        request = MagicMock()
        request.app = web.Application()
        request.app['machine_id'] = '123'
        request.app.logger = MagicMock()
        request.text = AsyncMock()
        request.text.return_value = 'abc'

        res = await decrypt_request(request, Mock())
        self.assertIsInstance(res, web.Response)
        self.assertEqual(401, res.status)

        decrypt.assert_called_once_with('abc', '123')

    @patch(f'{__app_name__}.service.optimizer.web.middlewares.decrypt', return_value='')
    async def test__must_return_401_when_decryption_returns_empty_string(self, decrypt: Mock):
        request = MagicMock()
        request.app = web.Application()
        request.app['machine_id'] = '123'
        request.app.logger = MagicMock()
        request.text = AsyncMock()
        request.text.return_value = 'abc'

        res = await decrypt_request(request, Mock())
        self.assertIsInstance(res, web.Response)
        self.assertEqual(401, res.status)

        decrypt.assert_called_once_with('abc', '123')
