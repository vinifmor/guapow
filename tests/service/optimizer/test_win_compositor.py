import re
from asyncio import Future
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch, Mock, MagicMock, AsyncMock

from guapow import __app_name__
from guapow.service.optimizer.win_compositor import get_window_compositor, KWinCompositor, Xfwm4Compositor, \
    MarcoCompositor, \
    PicomCompositor, WindowCompositorNoCLI, CompizCompositor, WindowCompositorWithCLI, NvidiaCompositor, \
    get_window_compositor_by_name


class GetWindowCompositorTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.expected_inxi_cmd = 'inxi -Gxx -c 0'

    @patch(f'{__app_name__}.service.optimizer.win_compositor.run_async_user_process', return_value=(0, 'compositor: xpto'))
    @patch(f'{__app_name__}.service.optimizer.win_compositor.which', return_value='/usr/bin/inxi')
    async def test_return_none_when_inxi_returns_a_not_supported_compositor_name(self, which: Mock, run_user_process: Mock):
        env = {'abc': '123'}
        compositor = await get_window_compositor(logger=Mock(), user_id=123, user_env=env)
        which.assert_called_once_with('inxi')
        run_user_process.assert_called_once_with(cmd=self.expected_inxi_cmd, user_id=123, user_env=env)
        self.assertIsNone(compositor)

    @patch(f'{__app_name__}.service.optimizer.win_compositor.run_async_user_process', return_value=(0, """Device-1: InnoTek Systemberatung VirtualBox Graphics Adapter 
  driver: vboxvideo v: kernel bus-ID: 00:02.0 chip-ID: 80ee:beef 
  Display: x11 server: X.Org 1.20.11 compositor: kwin_x11 driver: 
  loaded: modesetting alternate: fbdev,vboxvideo,vesa"""))
    @patch(f'{__app_name__}.service.optimizer.win_compositor.which', return_value='/usr/bin/inxi')
    async def test__return_kwin_when_inxi_returns_it_as_compositor(self, which: Mock, run_user_process: Mock):
        env = {'abc': '123'}
        compositor = await get_window_compositor(logger=Mock(), user_id=123, user_env=env)
        which.assert_called_with('inxi')
        run_user_process.assert_called_once_with(cmd=self.expected_inxi_cmd, user_id=123, user_env=env)
        self.assertIsNotNone(compositor)
        self.assertIsInstance(compositor, KWinCompositor)

    @patch(f'{__app_name__}.service.optimizer.win_compositor.run_async_user_process', return_value=(0, """  Device-1: InnoTek Systemberatung VirtualBox Graphics Adapter 
  driver: vboxvideo v: kernel bus-ID: 00:02.0 chip-ID: 80ee:beef 
  Display: x11 server: X.Org 1.20.11 compositor: xfwm4 driver: 
  loaded: modesetting alternate: fbdev,vboxvideo,vesa"""))
    @patch(f'{__app_name__}.service.optimizer.win_compositor.which', return_value='/usr/bin/inxi')
    async def test__return_xfwm4_when_inxi_returns_it_as_compositor(self, which: Mock, run_user_process: Mock):
        env = {'abc': '123'}
        compositor = await get_window_compositor(logger=Mock(), user_id=123, user_env=env)
        which.assert_called_with('inxi')
        run_user_process.assert_called_once_with(cmd=self.expected_inxi_cmd, user_id=123, user_env=env)
        self.assertIsNotNone(compositor)
        self.assertIsInstance(compositor, Xfwm4Compositor)

    @patch(f'{__app_name__}.service.optimizer.win_compositor.run_async_user_process', return_value=(0, """  Device-1: InnoTek Systemberatung VirtualBox Graphics Adapter 
  driver: vboxvideo v: kernel bus-ID: 00:02.0 chip-ID: 80ee:beef 
  Display: x11 server: X.Org 1.20.11 compositor: metacity driver: 
  loaded: modesetting alternate: fbdev,vboxvideo,vesa"""))
    @patch(f'{__app_name__}.service.optimizer.win_compositor.which', return_value='/usr/bin/inxi')
    async def test__return_marco_when_inxi_returns_metacity_as_compositor(self, which: Mock, run_user_process: Mock):
        env = {'abc': '123'}
        compositor = await get_window_compositor(logger=Mock(), user_id=123, user_env=env)
        which.assert_called_once_with('inxi')
        run_user_process.assert_called_once_with(cmd=self.expected_inxi_cmd, user_id=123, user_env=env)
        self.assertIsNotNone(compositor)
        self.assertIsInstance(compositor, MarcoCompositor)

    @patch(f'{__app_name__}.service.optimizer.win_compositor.run_async_user_process', return_value=(0, """  Device-1: InnoTek Systemberatung VirtualBox Graphics Adapter 
  driver: vboxvideo v: kernel bus-ID: 00:02.0 chip-ID: 80ee:beef 
  Display: x11 server: X.Org 1.20.11 compositor: marco driver: 
  loaded: modesetting alternate: fbdev,vboxvideo,vesa"""))
    @patch(f'{__app_name__}.service.optimizer.win_compositor.which', return_value='/usr/bin/inxi')
    async def test__return_marco_when_inxi_returns_it_as_compositor(self, which: Mock, run_user_process: Mock):
        env = {'abc': '123'}
        compositor = await get_window_compositor(logger=Mock(), user_id=123, user_env=env)
        which.assert_called_once_with('inxi')
        run_user_process.assert_called_once_with(cmd=self.expected_inxi_cmd, user_id=123, user_env=env)
        self.assertIsNotNone(compositor)
        self.assertIsInstance(compositor, MarcoCompositor)

    @patch(f'{__app_name__}.service.optimizer.win_compositor.run_async_user_process', return_value=(0, """  Device-1: InnoTek Systemberatung VirtualBox Graphics Adapter 
    driver: vboxvideo v: kernel bus-ID: 00:02.0 chip-ID: 80ee:beef 
    Display: x11 server: X.Org 1.20.11 compositor: compton driver: 
    loaded: modesetting alternate: fbdev,vboxvideo,vesa"""))
    @patch(f'{__app_name__}.service.optimizer.win_compositor.which', return_value='/usr/bin/inxi')
    async def test__return_picom_when_inxi_returns_compton_as_compositor(self, which: Mock, run_user_process: Mock):
        env = {'abc': '123'}
        compositor = await get_window_compositor(logger=Mock(), user_id=123, user_env=env)
        which.assert_called_once_with('inxi')
        run_user_process.assert_called_once_with(cmd=self.expected_inxi_cmd, user_id=123, user_env=env)
        self.assertIsNotNone(compositor)
        self.assertIsInstance(compositor, PicomCompositor)
        self.assertEqual('Compton', compositor.get_name())

    @patch(f'{__app_name__}.service.optimizer.win_compositor.run_async_user_process', return_value=(0, """  Device-1: InnoTek Systemberatung VirtualBox Graphics Adapter 
    driver: vboxvideo v: kernel bus-ID: 00:02.0 chip-ID: 80ee:beef 
    Display: x11 server: X.Org 1.20.11 compositor: picom driver: 
    loaded: modesetting alternate: fbdev,vboxvideo,vesa"""))
    @patch(f'{__app_name__}.service.optimizer.win_compositor.which', return_value='/usr/bin/inxi')
    async def test__return_picom_when_inxi_returns_it_as_compositor(self, which: Mock, run_user_process: Mock):
        env = {'abc': '123'}
        compositor = await get_window_compositor(logger=Mock(), user_id=123, user_env=env)
        which.assert_called_once_with('inxi')
        run_user_process.assert_called_once_with(cmd=self.expected_inxi_cmd, user_id=123, user_env=env)
        self.assertIsNotNone(compositor)
        self.assertIsInstance(compositor, PicomCompositor)
        self.assertEqual('Picom', compositor.get_name())

    @patch(f'{__app_name__}.service.optimizer.win_compositor.run_async_user_process', return_value=(0, """  Device-1: InnoTek Systemberatung VirtualBox Graphics Adapter 
    driver: vboxvideo v: kernel bus-ID: 00:02.0 chip-ID: 80ee:beef 
    Display: x11 server: X.Org 1.20.11 compositor: compiz driver: 
    loaded: modesetting alternate: fbdev,vboxvideo,vesa"""))
    @patch(f'{__app_name__}.service.optimizer.win_compositor.which', return_value='/usr/bin/inxi')
    async def test__return_compiz_when_inxi_returns_it_as_compositor(self, which: Mock, run_user_process: Mock):
        env = {'abc': '123'}
        compositor = await get_window_compositor(logger=Mock(), user_id=123, user_env=env)
        which.assert_called_once_with('inxi')
        run_user_process.assert_called_once_with(cmd=self.expected_inxi_cmd, user_id=123, user_env=env)
        self.assertIsNotNone(compositor)
        self.assertIsInstance(compositor, CompizCompositor)
        self.assertEqual('Compiz', compositor.get_name())

    @patch(f'{__app_name__}.service.optimizer.win_compositor.run_async_user_process', return_value=(0, "Device: xpto"))
    @patch(f'{__app_name__}.service.optimizer.win_compositor.which', return_value='/usr/bin/inxi')
    async def test__return_kwin_when_inxi_does_not_return_it_but_desktop_env_is_kde(self, which: Mock, run_user_process: Mock):
        env = {'XDG_CURRENT_DESKTOP': 'KDE'}
        compositor = await get_window_compositor(logger=Mock(), user_id=123, user_env=env)
        which.assert_called_with('inxi')
        run_user_process.assert_called_once_with(cmd=self.expected_inxi_cmd, user_id=123, user_env=env)
        self.assertIsNotNone(compositor)
        self.assertIsInstance(compositor, KWinCompositor)
        run_user_process.assert_called_once_with(cmd=self.expected_inxi_cmd, user_id=123, user_env=env)

    @patch(f'{__app_name__}.service.optimizer.win_compositor.run_async_user_process', return_value=(0, "Device: xpto"))
    @patch(f'{__app_name__}.service.optimizer.win_compositor.which', return_value='/usr/bin/inxi')
    async def test__return_marco_when_inxi_does_not_return_it_but_desktop_env_is_mate(self, which: Mock, run_user_process: Mock):
        env = {'XDG_CURRENT_DESKTOP': 'Mate'}
        compositor = await get_window_compositor(logger=Mock(), user_id=123, user_env=env)
        which.assert_called_with('inxi')
        run_user_process.assert_called_once_with(cmd=self.expected_inxi_cmd, user_id=123, user_env=env)
        self.assertIsNotNone(compositor)
        self.assertIsInstance(compositor, MarcoCompositor)

    @patch(f'{__app_name__}.service.optimizer.win_compositor.run_async_user_process', return_value=(0, "Device: xpto"))
    @patch(f'{__app_name__}.service.optimizer.win_compositor.which', return_value='/usr/bin/inxi')
    async def test__return_xfwm4_when_inxi_does_not_return_it_but_desktop_env_is_xfce(self, which: Mock, run_user_process: Mock):
        env = {'XDG_CURRENT_DESKTOP': 'XFCE'}
        compositor = await get_window_compositor(logger=Mock(), user_id=123, user_env=env)
        which.assert_called_with('inxi')
        run_user_process.assert_called_once_with(cmd=self.expected_inxi_cmd, user_id=123, user_env=env)
        self.assertIsNotNone(compositor)
        self.assertIsInstance(compositor, Xfwm4Compositor)

    @patch(f'{__app_name__}.service.optimizer.win_compositor.run_async_user_process', return_value=(0, "Device: xpto"))
    @patch(f'{__app_name__}.service.optimizer.win_compositor.which', return_value='/usr/bin/inxi')
    async def test__return_none_when_inxi_does_not_return_it_and_desktop_env_is_not_supported(self, which: Mock, run_user_process: Mock):
        env = {'XDG_CURRENT_DESKTOP': 'Gnome'}
        compositor = await get_window_compositor(logger=Mock(), user_id=123, user_env=env)
        which.assert_called_with('inxi')
        run_user_process.assert_called_once_with(cmd=self.expected_inxi_cmd, user_id=123, user_env=env)
        self.assertIsNone(compositor)

    @patch(f'{__app_name__}.service.optimizer.win_compositor.run_async_user_process', return_value=(0, "Device: xpto"))
    @patch(f'{__app_name__}.service.optimizer.win_compositor.which', return_value='/usr/bin/inxi')
    async def test__return_none_when_inxi_does_not_return_it_and_desktop_env_is_not_available(self, which: Mock, run_user_process: Mock):
        env = {'abc': '123'}
        compositor = await get_window_compositor(logger=Mock(), user_id=123, user_env=env)
        which.assert_called_with('inxi')
        run_user_process.assert_called_once_with(cmd=self.expected_inxi_cmd, user_id=123, user_env=env)
        self.assertIsNone(compositor)


class GetWindowCompositorByNameTest(IsolatedAsyncioTestCase):

    async def test__return_nvidia_compositor_when_name_equals_to_nvidia(self):
        compositor = get_window_compositor_by_name('nvidia', Mock())
        self.assertIsInstance(compositor, NvidiaCompositor)

    async def test__return_compiz_compositor_when_compiz_in_name(self):
        compositor = get_window_compositor_by_name('Compiz', Mock())
        self.assertIsInstance(compositor, CompizCompositor)

    async def test__return_marco_compositor_when_metacity_in_name(self):
        compositor = get_window_compositor_by_name(' metacity ', Mock())
        self.assertIsInstance(compositor, MarcoCompositor)

    async def test__return_marco_compositor_when_marco_in_name(self):
        compositor = get_window_compositor_by_name('Marco', Mock())
        self.assertIsInstance(compositor, MarcoCompositor)

    async def test__return_picom_compositor_when_compton_in_name(self):
        compositor = get_window_compositor_by_name('compton', Mock())
        self.assertIsInstance(compositor, PicomCompositor)

    async def test__return_picom_compositor_when_picom_in_name(self):
        compositor = get_window_compositor_by_name('Picom', Mock())
        self.assertIsInstance(compositor, PicomCompositor)

    async def test__return_xfwm4_compositor_when_xfwm4_in_name(self):
        compositor = get_window_compositor_by_name('XfWM4', Mock())
        self.assertIsInstance(compositor, Xfwm4Compositor)

    async def test__return_kwin_compositor_when_kwin_in_name(self):
        compositor = get_window_compositor_by_name(' Kwin ', Mock())
        self.assertIsInstance(compositor, KWinCompositor)


class KWinCompositorTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.compositor = KWinCompositor(Mock())

    def test__inner_compositor_must_be_an_instanceof_window_compositor_with_cli(self):
        self.assertIsInstance(self.compositor._compositor, WindowCompositorWithCLI)

    @patch(f'{__app_name__}.service.optimizer.win_compositor.shutil.which', return_value=['/qdbus'])
    def test_can_be_managed__true_when_qdbus_is_installed(self, which: Mock):
        res, msg = self.compositor.can_be_managed()
        self.assertTrue(res)
        self.assertIsNone(msg)
        which.assert_called_once_with('qdbus')

    @patch(f'{__app_name__}.service.optimizer.win_compositor.shutil.which', return_value=[])
    def test_can_be_managed__false_when_qdbus_is_not_installed(self, which: Mock):
        res, msg = self.compositor.can_be_managed()
        self.assertEqual(False, res)
        self.assertIsInstance(msg, str)
        which.assert_called_once_with('qdbus')

    async def test_is_enabled__must_delegate_to_inner_compositor(self):
        inner_compositor = Mock()
        inner_compositor.is_enabled = MagicMock(return_value=Future())
        inner_compositor.is_enabled.return_value.set_result(True)

        self.compositor._compositor = inner_compositor

        user_id, user_env, context = 123, {'abc': '123'}, {}
        self.assertTrue(await self.compositor.is_enabled(user_id=user_id, user_env=user_env, context=context))
        inner_compositor.is_enabled.assert_called_once_with(user_id=user_id, user_env=user_env, context=context)

    async def test_enable__must_delegate_to_inner_compositor(self):
        inner_compositor = Mock()
        inner_compositor.enable = MagicMock(return_value=Future())
        inner_compositor.enable.return_value.set_result(True)

        self.compositor._compositor = inner_compositor

        user_id, user_env, context = 123, {'abc': '123'}, {}
        self.assertTrue(await self.compositor.enable(user_id=user_id, user_env=user_env, context=context))
        inner_compositor.enable.assert_called_once_with(user_id=user_id, user_env=user_env, context=context)

    async def test_disable__must_delegate_to_inner_compositor(self):
        inner_compositor = Mock()
        inner_compositor.disable = MagicMock(return_value=Future())
        inner_compositor.disable.return_value.set_result(True)

        self.compositor._compositor = inner_compositor

        user_id, user_env, context = 123, {'abc': '123'}, {}
        self.assertTrue(await self.compositor.disable(user_id=user_id, user_env=user_env, context=context))
        inner_compositor.disable.assert_called_once_with(user_id=user_id, user_env=user_env, context=context)


class Xfwm4CompositorTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.compositor = Xfwm4Compositor(Mock())

    def test__inner_compositor_must_be_an_instanceof_window_compositor_with_cli(self):
        self.assertIsInstance(self.compositor._compositor, WindowCompositorWithCLI)

    @patch(f'{__app_name__}.service.optimizer.win_compositor.shutil.which', return_value=['/xconf-query'])
    def test_can_be_managed__true_when_xconfquery_is_installed(self, which: Mock):
        res, msg = self.compositor.can_be_managed()
        self.assertTrue(res)
        self.assertIsNone(msg)
        which.assert_called_once_with('xfconf-query')

    @patch(f'{__app_name__}.service.optimizer.win_compositor.shutil.which', return_value=[])
    def test_can_be_managed__false_when_xconfquery_is_not_installed(self, which: Mock):
        res, msg = self.compositor.can_be_managed()
        self.assertEqual(False, res)
        self.assertIsInstance(msg, str)
        which.assert_called_once_with('xfconf-query')

    async def test_is_enabled__must_delegate_to_inner_compositor(self):
        inner_compositor = Mock()
        inner_compositor.is_enabled = MagicMock(return_value=Future())
        inner_compositor.is_enabled.return_value.set_result(True)

        self.compositor._compositor = inner_compositor

        user_id, user_env, context = 123, {'abc': '123'}, {}
        self.assertTrue(await self.compositor.is_enabled(user_id=user_id, user_env=user_env, context=context))
        inner_compositor.is_enabled.assert_called_once_with(user_id=user_id, user_env=user_env, context=context)

    async def test_enable__must_delegate_to_inner_compositor(self):
        inner_compositor = Mock()
        inner_compositor.enable = MagicMock(return_value=Future())
        inner_compositor.enable.return_value.set_result(True)

        self.compositor._compositor = inner_compositor

        user_id, user_env, context = 123, {'abc': '123'}, {}
        self.assertTrue(await self.compositor.enable(user_id=user_id, user_env=user_env, context=context))
        inner_compositor.enable.assert_called_once_with(user_id=user_id, user_env=user_env, context=context)

    async def test_disable__must_delegate_to_inner_compositor(self):
        inner_compositor = Mock()
        inner_compositor.disable = MagicMock(return_value=Future())
        inner_compositor.disable.return_value.set_result(True)

        self.compositor._compositor = inner_compositor

        user_id, user_env, context = 123, {'abc': '123'}, {}
        self.assertTrue(await self.compositor.disable(user_id=user_id, user_env=user_env, context=context))
        inner_compositor.disable.assert_called_once_with(user_id=user_id, user_env=user_env, context=context)


class MarcoCompositorTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.compositor = MarcoCompositor(Mock())

    def test__inner_compositor_must_be_an_instanceof_window_compositor_with_cli(self):
        self.assertIsInstance(self.compositor._compositor, WindowCompositorWithCLI)

    @patch(f'{__app_name__}.service.optimizer.win_compositor.shutil.which', return_value=['/gsettings'])
    def test_can_be_managed__true_when_gsettings_is_installed(self, which: Mock):
        res, msg = self.compositor.can_be_managed()
        self.assertTrue(res)
        self.assertIsNone(msg)
        which.assert_called_once_with('gsettings')

    @patch(f'{__app_name__}.service.optimizer.win_compositor.shutil.which', return_value=[])
    def test_can_be_managed__false_when_gsettings_is_not_installed(self, which: Mock):
        res, msg = self.compositor.can_be_managed()
        self.assertEqual(False, res)
        self.assertIsInstance(msg, str)
        which.assert_called_once_with('gsettings')

    async def test_is_enabled__must_delegate_to_inner_compositor(self):
        inner_compositor = Mock()
        inner_compositor.is_enabled = MagicMock(return_value=Future())
        inner_compositor.is_enabled.return_value.set_result(True)

        self.compositor._compositor = inner_compositor

        user_id, user_env, context = 123, {'abc': '123'}, {}
        self.assertTrue(await self.compositor.is_enabled(user_id=user_id, user_env=user_env, context=context))
        inner_compositor.is_enabled.assert_called_once_with(user_id=user_id, user_env=user_env, context=context)

    async def test_enable__must_delegate_to_inner_compositor(self):
        inner_compositor = Mock()
        inner_compositor.enable = MagicMock(return_value=Future())
        inner_compositor.enable.return_value.set_result(True)

        self.compositor._compositor = inner_compositor

        user_id, user_env, context = 123, {'abc': '123'}, {}
        self.assertTrue(await self.compositor.enable(user_id=user_id, user_env=user_env, context=context))
        inner_compositor.enable.assert_called_once_with(user_id=user_id, user_env=user_env, context=context)

    async def test_disable__must_delegate_to_inner_compositor(self):
        inner_compositor = Mock()
        inner_compositor.disable = MagicMock(return_value=Future())
        inner_compositor.disable.return_value.set_result(True)

        self.compositor._compositor = inner_compositor

        user_id, user_env, context = 123, {'abc': '123'}, {}
        self.assertTrue(await self.compositor.disable(user_id=user_id, user_env=user_env, context=context))
        inner_compositor.disable.assert_called_once_with(user_id=user_id, user_env=user_env, context=context)


class WindowCompositorNoCLITest(IsolatedAsyncioTestCase):

    COMPTON_MATCH_PATTERN = re.compile(r'^compton$')

    def setUp(self):
        self.compositor = WindowCompositorNoCLI(name='compton', process_name='compton', logger=Mock())

    @patch(f'{__app_name__}.service.optimizer.win_compositor.shutil.which', return_value=['/compton'])
    def test_can_be_managed__must_call_which_for_process_name(self, which: Mock):
        res, msg = self.compositor.can_be_managed()
        self.assertTrue(res)
        self.assertIsNone(msg)
        which.assert_called_once_with('compton')

    @patch(f'{__app_name__}.service.optimizer.win_compositor.system.find_process_by_name', return_value=(456, 'compton -b'))
    async def test_is_enabled__true_when_compositor_process_is_alive(self, find_process_by_name: Mock):
        context = {}
        self.assertTrue(await self.compositor.is_enabled(123, {'abc': '123'}, context=context))

        self.assertIn('pid', context)
        self.assertEqual(456, context['pid'])
        self.assertIn('cmd', context)
        self.assertEqual('compton -b', context['cmd'])

        find_process_by_name.assert_called_once_with(self.COMPTON_MATCH_PATTERN)

    @patch(f'{__app_name__}.service.optimizer.win_compositor.system.find_process_by_name', return_value=None)
    async def test_is_enabled__false_when_compositor_process_does_not_exist(self, find_process_by_name: Mock):
        context = {}
        self.assertFalse(await self.compositor.is_enabled(123, {'abc': '123'}, context=context))
        find_process_by_name.assert_called_once_with(self.COMPTON_MATCH_PATTERN)
        self.assertEqual({}, context)

    @patch(f'{__app_name__}.service.optimizer.win_compositor.system.async_syscall', return_value=(0, None))
    async def test_disable__true_when_the_compositor_process_could_be_killed(self, async_syscall: Mock):
        context = {'pid': 8383737}
        self.assertTrue(await self.compositor.disable(123, {'abc': '123'}, context=context))
        async_syscall.assert_called_once_with(f"kill -9 {context.get('pid')}")

    @patch(f'{__app_name__}.service.optimizer.win_compositor.system.async_syscall', return_value=(1, 'error'))
    async def test_disable__false_when_the_compositor_process_is_alive_but_could_not_be_killed(self, async_syscall: Mock):
        context = {'pid': 8383737}
        self.assertFalse(await self.compositor.disable(123, {'abc': '123'}, context=context))
        async_syscall.assert_called_once_with(f"kill -9 {context.get('pid')}")

    async def test_enable__false_when_enable_command_is_not_defined_on_context(self):
        self.assertFalse(await self.compositor.enable(123, {'abc': '123'}, context={}))

    @patch(f'{__app_name__}.service.optimizer.win_compositor.system.run_async_user_process', return_value=(1, 'error'))
    async def test_enable__false_when_compositor_process_could_not_be_started(self, run_async_user_process: Mock):
        user_env = {'abc': '123'}
        context = {'cmd': 'compton -b'}

        self.assertFalse(await self.compositor.enable(123, user_env, context))

        run_async_user_process.assert_called_once_with(cmd=context['cmd'], user_id=123, user_env=user_env)

    @patch(f'{__app_name__}.service.optimizer.win_compositor.system.run_async_user_process', return_value=(0, None))
    async def test_enable__true_when_compositor_could_be_started(self, run_async_user_process: Mock):
        user_env = {'abc': '123'}
        context = {'cmd': 'compton -b'}

        self.assertTrue(await self.compositor.enable(123, user_env, context=context))

        run_async_user_process.assert_called_once_with(cmd=context['cmd'], user_id=123, user_env=user_env)


class PicomCompositorTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.compositor = PicomCompositor('picom', Mock())
        self.compositor_no_cli = Mock()

        self.compositor._compositor = self.compositor_no_cli
        self.context = {'cmd': 'picom -b'}

    @patch(f'{__app_name__}.service.optimizer.win_compositor.shutil.which', return_value=['/picom'])
    def test_can_be_managed__true_when_picom_is_installed(self, which: Mock):
        self.compositor = PicomCompositor('picom', Mock())
        res, msg = self.compositor.can_be_managed()
        self.assertTrue(res)
        self.assertIsNone(msg)
        which.assert_called_once_with('picom')

    @patch(f'{__app_name__}.service.optimizer.win_compositor.shutil.which', return_value=[])
    def test_can_be_managed__false_when_picom_is_not_installed(self, which: Mock):
        self.compositor = PicomCompositor('picom', Mock())
        res, msg = self.compositor.can_be_managed()
        self.assertEqual(False, res)
        self.assertIsInstance(msg, str)
        which.assert_called_once_with('picom')

    async def test_is_enabled__must_delegate_to_compositor_no_cli(self):
        self.compositor_no_cli.is_enabled = MagicMock(return_value=Future())
        self.compositor_no_cli.is_enabled.return_value.set_result(True)

        user_env = {'abc': '123'}

        self.assertTrue(await self.compositor.is_enabled(123, user_env, self.context))
        self.compositor_no_cli.is_enabled.assert_called_once_with(123, user_env, self.context)

    async def test_enable__must_delegate_to_compositor_no_cli(self):
        self.compositor_no_cli.enable = MagicMock(return_value=Future())
        self.compositor_no_cli.enable.return_value.set_result(False)

        user_env = {'abc': '123'}

        self.assertFalse(await self.compositor.enable(123, user_env, self.context))
        self.compositor_no_cli.enable.assert_called_once_with(123, user_env, self.context)

    async def test_disable__must_delegate_to_compositor_no_cli(self):
        self.compositor_no_cli.disable = MagicMock(return_value=Future())
        self.compositor_no_cli.disable.return_value.set_result(True)

        user_env = {'abc': '123'}

        self.assertTrue(await self.compositor.disable(123, user_env, self.context))
        self.compositor_no_cli.disable.assert_called_once_with(123, user_env, self.context)

    def test_get_name__must_delegate_to_compositor_no_cli(self):
        self.compositor_no_cli.get_name = MagicMock(return_value='compton')

        self.assertEqual('compton', self.compositor.get_name())
        self.compositor_no_cli.get_name.assert_called_once()


class CompizCompositorTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.compositor = CompizCompositor(Mock())
        self.compositor_no_cli = Mock()

        self.compositor._compositor = self.compositor_no_cli
        self.context = {'cmd': 'compiz'}

    @patch(f'{__app_name__}.service.optimizer.win_compositor.shutil.which', return_value=['/compiz'])
    def test_can_be_managed__true_when_compiz_is_installed(self, which: Mock):
        self.compositor = CompizCompositor(Mock())
        res, msg = self.compositor.can_be_managed()
        self.assertTrue(res)
        self.assertIsNone(msg)
        which.assert_called_once_with('compiz')

    @patch(f'{__app_name__}.service.optimizer.win_compositor.shutil.which', return_value=[])
    def test_can_be_managed__false_when_compiz_is_not_installed(self, which: Mock):
        self.compositor = CompizCompositor(Mock())
        res, msg = self.compositor.can_be_managed()
        self.assertEqual(False, res)
        self.assertIsInstance(msg, str)
        which.assert_called_once_with('compiz')

    async def test_is_enabled__must_delegate_to_compositor_no_cli(self):
        self.compositor_no_cli.is_enabled = MagicMock(return_value=Future())
        self.compositor_no_cli.is_enabled.return_value.set_result(True)

        user_env = {'abc': '123'}

        self.assertTrue(await self.compositor.is_enabled(123, user_env, self.context))
        self.compositor_no_cli.is_enabled.assert_called_once_with(123, user_env, self.context)

    async def test_enable__must_delegate_to_compositor_no_cli(self):
        self.compositor_no_cli.enable = MagicMock(return_value=Future())
        self.compositor_no_cli.enable.return_value.set_result(False)

        user_env = {'abc': '123'}

        self.assertFalse(await self.compositor.enable(123, user_env, self.context))
        self.compositor_no_cli.enable.assert_called_once_with(123, user_env, self.context)

    async def test_disable__must_delegate_to_compositor_no_cli(self):
        self.compositor_no_cli.disable = MagicMock(return_value=Future())
        self.compositor_no_cli.disable.return_value.set_result(True)

        user_env = {'abc': '123'}
        self.assertTrue(await self.compositor.disable(123, user_env, self.context))
        self.compositor_no_cli.disable.assert_called_once_with(123, user_env, self.context)

    def test_get_name__must_delegate_to_compositor_no_cli(self):
        self.compositor_no_cli.get_name = MagicMock(return_value='compton')

        self.assertEqual('compton', self.compositor.get_name())
        self.compositor_no_cli.get_name.assert_called_once()


class NvidiaCompositorTest(IsolatedAsyncioTestCase):

    def setUp(self):
        self.compositor = NvidiaCompositor(Mock())

    def test_extract_attributes__response_must_be_able_must_return_only_one_attribute(self):
        string = """
        (nvidia-settings:1936): Gtk-WARNING **: 09:40:36.901: Theme parsing error: gtk.css:73:46: The style property GtkScrolledWindow:scrollbars-within-bevel is deprecated and shouldn't be used anymore. It will be removed in a future version

          Attribute 'CurrentMetaMode' (user-desktop:0.0): id=50, switchable=no, source=nv-control :: DPY-2:
          nvidia-auto-select @1920x1080 +0+0 {ViewPortIn=1920x1080, ViewPortOut=1920x1080+0+0,
          ForceCompositionPipeline=On} 
        """
        res = self.compositor.extract_attributes(string)
        self.assertEqual({'ForceCompositionPipeline'}, res)

    def test_extract_attributes__response_must_be_able_must_return_two_attributes_if_present(self):
        string = """
        (nvidia-settings:1520): Gtk-WARNING **: 09:39:04.549: Theme parsing error: gtk.css:73:46: The style property GtkScrolledWindow:scrollbars-within-bevel is deprecated and shouldn't be used anymore. It will be removed in a future version

          Attribute 'CurrentMetaMode' (user-desktop:0.0): id=50, switchable=yes, source=xconfig :: DPY-2:
          nvidia-auto-select @1920x1080 +0+0 {ViewPortIn=1920x1080, ViewPortOut=1920x1080+0+0,
          ForceCompositionPipeline=On, ForceFullCompositionPipeline=On}
        """
        res = self.compositor.extract_attributes(string)
        self.assertEqual({'ForceCompositionPipeline', 'ForceFullCompositionPipeline'}, res)

    def test_extract_attributes__response_must_not_return_duplicates(self):
        string = """
        (nvidia-settings:1520): Gtk-WARNING **: 09:39:04.549: Theme parsing error: gtk.css:73:46: The style property GtkScrolledWindow:scrollbars-within-bevel is deprecated and shouldn't be used anymore. It will be removed in a future version

          Attribute 'CurrentMetaMode' (user-desktop:0.0): id=50, switchable=yes, source=xconfig :: DPY-2:
          nvidia-auto-select @1920x1080 +0+0 {ViewPortIn=1920x1080, ViewPortOut=1920x1080+0+0,
          forcefullcompositionpipeline=On, ForceFullCompositionPipeline=On}
        """
        res = self.compositor.extract_attributes(string)
        self.assertEqual({'ForceFullCompositionPipeline'}, res)

    @patch(f'{__app_name__}.service.optimizer.win_compositor.shutil.which', return_value=['/nvidia-settings'])
    def test_can_be_managed__true_when_nvidiasettings_is_installed(self, which: Mock):
        res, msg = self.compositor.can_be_managed()
        self.assertTrue(res)
        self.assertIsNone(msg)
        which.assert_called_once_with('nvidia-settings')

    @patch(f'{__app_name__}.service.optimizer.win_compositor.shutil.which', return_value=[])
    def test_can_be_managed__false_when_nvidiasettings_is_not_installed(self, which: Mock):
        res, msg = self.compositor.can_be_managed()
        self.assertEqual(False, res)
        self.assertIsInstance(msg, str)
        which.assert_called_once_with('nvidia-settings')

    @patch(f'{__app_name__}.service.optimizer.win_compositor.system.async_syscall', return_value=(1, 'error'))
    async def test_is_enabled__none_when_nvidia_settings_exitcode_is_nonzero(self, async_syscall: AsyncMock):
        user_env = {'a': '1'}
        context = {}

        enabled = await self.compositor.is_enabled(user_id=456, user_env=user_env, context=context)
        async_syscall.assert_awaited_once_with('nvidia-settings -q /CurrentMetaMode', custom_env=user_env)
        self.assertIsNone(enabled)
        self.assertEqual({}, context)

    @patch(f'{__app_name__}.service.optimizer.win_compositor.system.async_syscall', return_value=(0, '   '))
    async def test_is_enabled__none_when_nvidia_settings_exitcode_is_zero_but_no_output_and_no_mode_on_context(self, async_syscall: AsyncMock):
        user_env = {'a': '1'}
        context = {}

        enabled = await self.compositor.is_enabled(user_id=456, user_env=user_env, context=context)
        async_syscall.assert_awaited_once_with('nvidia-settings -q /CurrentMetaMode', custom_env=user_env)
        self.assertIsNone(enabled)
        self.assertEqual({}, context)

    @patch(f'{__app_name__}.service.optimizer.win_compositor.system.async_syscall', return_value=(0, '   '))
    async def test_is_enabled__false_when_nvidia_settings_exitcode_is_zero_but_no_output_and_mode_on_context(self, async_syscall: AsyncMock):
        user_env = {'a': '1'}
        context = {'mode': 'ForceCompositionPipeline'}

        enabled = await self.compositor.is_enabled(user_id=456, user_env=user_env, context=context)
        async_syscall.assert_awaited_once_with('nvidia-settings -q /CurrentMetaMode', custom_env=user_env)
        self.assertEqual(False, enabled)
        self.assertEqual({'mode': 'ForceCompositionPipeline'}, context)  # no change

    @patch(f'{__app_name__}.service.optimizer.win_compositor.system.async_syscall', return_value=(0, 'ForceCompositionPipeline=On,ForceFullCompositionPipeline=On'))
    async def test_is_enabled__true_when_nvidia_settings_exitcode_is_zero_and_full_composition_on_output(self, async_syscall: AsyncMock):
        user_env = {'a': '1'}
        context = {}

        enabled = await self.compositor.is_enabled(user_id=456, user_env=user_env, context=context)
        async_syscall.assert_awaited_once_with('nvidia-settings -q /CurrentMetaMode', custom_env=user_env)
        self.assertTrue(enabled)
        self.assertEqual({'mode': 'ForceFullCompositionPipeline'}, context)

    @patch(f'{__app_name__}.service.optimizer.win_compositor.system.async_syscall', return_value=(0, 'ForceCompositionPipeline=On'))
    async def test_is_enabled__true_when_nvidia_settings_exitcode_is_zero_and_default_composition_on_output(self, async_syscall: AsyncMock):
        user_env = {'a': '1'}
        context = {}

        enabled = await self.compositor.is_enabled(user_id=456, user_env=user_env, context=context)
        async_syscall.assert_awaited_once_with('nvidia-settings -q /CurrentMetaMode', custom_env=user_env)
        self.assertTrue(enabled)
        self.assertEqual({'mode': 'ForceCompositionPipeline'}, context)

    @patch(f'{__app_name__}.service.optimizer.win_compositor.system.async_syscall')
    async def test_enable__false_when_no_mode_on_context(self, async_syscall: AsyncMock):
        user_env = {'a': '1'}
        context = {}

        enabled = await self.compositor.enable(user_id=456, user_env=user_env, context=context)
        async_syscall.assert_not_called()
        self.assertEqual(False, enabled)
        self.assertEqual({}, context)

    @patch(f'{__app_name__}.service.optimizer.win_compositor.system.async_syscall', return_value=(0, ''))
    async def test_enable__true_when_nvidia_settings_return_exitcode_zero(self, async_syscall: AsyncMock):
        user_env = {'a': '1'}
        context = {'mode': 'ForceFullCompositionPipeline'}

        enabled = await self.compositor.enable(user_id=456, user_env=user_env, context=context)
        async_syscall.assert_awaited_once_with('nvidia-settings --assign CurrentMetaMode="nvidia-auto-select +0+0 {ForceFullCompositionPipeline=On}"', custom_env=user_env)
        self.assertTrue(enabled)
        self.assertEqual({'mode': 'ForceFullCompositionPipeline'}, context)

    @patch(f'{__app_name__}.service.optimizer.win_compositor.system.async_syscall', return_value=(1, ''))
    async def test_enable__false_when_nvidia_settings_return_exitcode_nonzero(self, async_syscall: AsyncMock):
        user_env = {'a': '1'}
        context = {'mode': 'ForceCompositionPipeline'}

        enabled = await self.compositor.enable(user_id=456, user_env=user_env, context=context)
        async_syscall.assert_awaited_once_with('nvidia-settings --assign CurrentMetaMode="nvidia-auto-select +0+0 {ForceCompositionPipeline=On}"', custom_env=user_env)
        self.assertEqual(False, enabled)
        self.assertEqual({'mode': 'ForceCompositionPipeline'}, context)

    @patch(f'{__app_name__}.service.optimizer.win_compositor.system.async_syscall')
    async def test_disable__false_when_no_mode_on_context(self, async_syscall: AsyncMock):
        user_env = {'a': '1'}
        context = {}

        enabled = await self.compositor.disable(user_id=456, user_env=user_env, context=context)
        async_syscall.assert_not_called()
        self.assertEqual(False, enabled)
        self.assertEqual({}, context)

    @patch(f'{__app_name__}.service.optimizer.win_compositor.system.async_syscall', return_value=(0, ''))
    async def test_disable__true_when_nvidia_settings_return_exitcode_zero(self, async_syscall: AsyncMock):
        user_env = {'a': '1'}
        context = {'mode': 'ForceFullCompositionPipeline'}

        disabled = await self.compositor.disable(user_id=456, user_env=user_env, context=context)
        async_syscall.assert_awaited_once_with('nvidia-settings --assign CurrentMetaMode="nvidia-auto-select +0+0 {ForceFullCompositionPipeline=Off}"', custom_env=user_env)
        self.assertTrue(disabled)
        self.assertEqual({'mode': 'ForceFullCompositionPipeline'}, context)

    @patch(f'{__app_name__}.service.optimizer.win_compositor.system.async_syscall', return_value=(1, ''))
    async def test_disable__false_when_nvidia_settings_return_exitcode_nonzero(self, async_syscall: AsyncMock):
        user_env = {'a': '1'}
        context = {'mode': 'ForceCompositionPipeline'}

        disabled = await self.compositor.disable(user_id=456, user_env=user_env, context=context)
        async_syscall.assert_awaited_once_with('nvidia-settings --assign CurrentMetaMode="nvidia-auto-select +0+0 {ForceCompositionPipeline=Off}"', custom_env=user_env)
        self.assertEqual(False, disabled)
        self.assertEqual({'mode': 'ForceCompositionPipeline'}, context)

    @patch(f'{__app_name__}.service.optimizer.win_compositor.system.async_syscall', return_value=(0, '\n\nERROR: Error assigning value nvidia\n'))
    async def test_disable__false_when_nvidia_settings_return_exitcode_zero_but_with_error_output(self, async_syscall: AsyncMock):
        user_env = {'a': '1'}
        context = {'mode': 'ForceCompositionPipeline'}

        disabled = await self.compositor.disable(user_id=456, user_env=user_env, context=context)
        async_syscall.assert_awaited_once()
        self.assertEqual(False, disabled)
