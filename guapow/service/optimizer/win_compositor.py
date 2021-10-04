import re
import shutil
from abc import ABC, abstractmethod
from asyncio import Lock
from logging import Logger
from shutil import which
from typing import Optional, Dict, Set, Tuple

from guapow.common import system
from guapow.common.system import run_async_user_process

RE_COMPOSITOR_NAME = re.compile(r'compositor\s*:\s*(.+)\s')


class WindowCompositor(ABC):
    """ Compositing Window Manager """

    def __init__(self, logger: Logger):
        self._log = logger
        self._lock = Lock()

    def lock(self) -> Lock:
        return self._lock

    @abstractmethod
    def can_be_managed(self) -> Tuple[bool, Optional[str]]:
        pass

    @abstractmethod
    async def enable(self, user_id: Optional[int], user_env: Optional[dict], context: dict) -> bool:
        pass

    @abstractmethod
    async def disable(self, user_id: Optional[int], user_env: Optional[dict], context: dict) -> bool:
        pass

    @abstractmethod
    async def is_enabled(self, user_id: Optional[int], user_env: Optional[dict], context: dict) -> Optional[bool]:
        """
        return: tuple with the first element as the status (enabled/disabled) and the second element a context object that can
        be passed to the other calls
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        pass


class WindowCompositorWithCLI(WindowCompositor):
    """
    Window compositor that has a command line interface to interact with.
    """
    def __init__(self, name: str, enable_cmd: str, disable_cmd: str, is_enable_cmd, logger: Logger):
        super(WindowCompositorWithCLI, self).__init__(logger)
        self._name = name
        self._enable_cmd = enable_cmd
        self._disable_cmd = disable_cmd
        self._is_enable_cmd = is_enable_cmd
        self._commands = {c.split(' ')[0].strip() for c in {enable_cmd, disable_cmd, is_enable_cmd}}

    def can_be_managed(self) -> Tuple[bool, Optional[str]]:
        if self._commands:
            for c in self._commands:
                if not shutil.which(c):
                    return False, f"'{c}' is not installed"

        return True, None

    async def enable(self, user_id: Optional[int], user_env: Optional[dict], context: dict) -> bool:
        code, output = await system.run_async_user_process(self._enable_cmd, user_id, user_env)

        if code == 0:
            return True
        else:
            error_output = output.replace('\n', ' ') if output else ''
            self._log.error(f"Could not enable {self.get_name()}. Command ({self._enable_cmd}) failed. Output: {error_output}")
            return False

    async def disable(self, user_id: Optional[int], user_env: Optional[dict], context: dict) -> bool:
        code, output = await system.run_async_user_process(self._disable_cmd, user_id, user_env)

        if code == 0:
            return True
        else:
            error_output = output.replace('\n', ' ') if output else ''
            self._log.error(f"Could not disable {self.get_name()}. Command ({self._disable_cmd}) failed. Output: {error_output}")
            return False

    async def is_enabled(self, user_id: Optional[int], user_env: Optional[dict], context: dict) -> Optional[bool]:
        exitcode, output = await system.run_async_user_process(self._is_enable_cmd, user_id, user_env)

        if exitcode == 0:
            if not output:
                self._log.error(f"Could not determine if {self.get_name()} is enabled. No output from command: {self._is_enable_cmd}")
                return

            state_str = output.strip().lower()
            if state_str == 'true':
                return True
            elif state_str == 'false':
                return False
            else:
                log_output = output.replace('\n', ' ')
                self._log.warning(f'Could not determine if {self.get_name()} is enabled. Unknown output from command "{self._is_enable_cmd}": {log_output}')
        else:
            log_output = output.replace('\n', ' ') if output is not None else ' '
            self._log.error(f'Could not determine if {self.get_name()} is enabled. Command "{self._is_enable_cmd}" failed (exitcode={exitcode}). Output: {log_output}')

    def get_name(self) -> str:
        return self._name


class KWinCompositor(WindowCompositor):

    def __init__(self, logger: Logger):
        super(KWinCompositor, self).__init__(logger)
        self._compositor = WindowCompositorWithCLI(name='KWin',
                                                   enable_cmd='qdbus org.kde.KWin /Compositor resume',
                                                   disable_cmd='qdbus org.kde.KWin /Compositor suspend',
                                                   is_enable_cmd='qdbus org.kde.KWin /Compositor org.kde.kwin.Compositing.active',
                                                   logger=logger)

    def can_be_managed(self) -> Tuple[bool, Optional[str]]:
        return self._compositor.can_be_managed()

    async def enable(self, user_id: Optional[int], user_env: Optional[dict], context: dict) -> bool:
        return await self._compositor.enable(user_id=user_id, user_env=user_env, context=context)

    async def disable(self, user_id: Optional[int], user_env: Optional[dict], context: dict) -> bool:
        return await self._compositor.disable(user_id=user_id, user_env=user_env, context=context)

    async def is_enabled(self, user_id: Optional[int], user_env: Optional[dict], context: dict) -> Optional[bool]:
        return await self._compositor.is_enabled(user_id=user_id, user_env=user_env, context=context)

    def get_name(self) -> str:
        return self._compositor.get_name()


class Xfwm4Compositor(WindowCompositor):

    def __init__(self, logger: Logger):
        super(Xfwm4Compositor, self).__init__(logger)
        self._compositor = WindowCompositorWithCLI(name='Xfwm4',
                                                   enable_cmd='xfconf-query --channel=xfwm4 --property=/general/use_compositing --set=true',
                                                   disable_cmd='xfconf-query --channel=xfwm4 --property=/general/use_compositing --set=false',
                                                   is_enable_cmd='xfconf-query --channel=xfwm4 --property=/general/use_compositing',
                                                   logger=logger)

    def can_be_managed(self) -> Tuple[bool, Optional[str]]:
        return self._compositor.can_be_managed()

    async def enable(self, user_id: Optional[int], user_env: Optional[dict], context: dict) -> bool:
        return await self._compositor.enable(user_id=user_id, user_env=user_env, context=context)

    async def disable(self, user_id: Optional[int], user_env: Optional[dict], context: dict) -> bool:
        return await self._compositor.disable(user_id=user_id, user_env=user_env, context=context)

    async def is_enabled(self, user_id: Optional[int], user_env: Optional[dict], context: dict) -> Optional[bool]:
        return await self._compositor.is_enabled(user_id=user_id, user_env=user_env, context=context)

    def get_name(self) -> str:
        return self._compositor.get_name()


class MarcoCompositor(WindowCompositor):

    def __init__(self, logger: Logger):
        super(MarcoCompositor, self).__init__(logger)
        self._compositor = WindowCompositorWithCLI(name='Marco',
                                                   enable_cmd='gsettings set org.mate.Marco.general compositing-manager true',
                                                   disable_cmd='gsettings set org.mate.Marco.general compositing-manager false',
                                                   is_enable_cmd='gsettings get org.mate.Marco.general compositing-manager',
                                                   logger=logger)

    def can_be_managed(self) -> Tuple[bool, Optional[str]]:
        return self._compositor.can_be_managed()

    async def enable(self, user_id: Optional[int], user_env: Optional[dict], context: dict) -> bool:
        return await self._compositor.enable(user_id=user_id, user_env=user_env, context=context)

    async def disable(self, user_id: Optional[int], user_env: Optional[dict], context: dict) -> bool:
        return await self._compositor.disable(user_id=user_id, user_env=user_env, context=context)

    async def is_enabled(self, user_id: Optional[int], user_env: Optional[dict], context: dict) -> Optional[bool]:
        return await self._compositor.is_enabled(user_id=user_id, user_env=user_env, context=context)

    def get_name(self) -> str:
        return self._compositor.get_name()


class WindowCompositorNoCLI(WindowCompositor):

    def __init__(self, name: str, process_name: str, logger: Logger):
        super(WindowCompositorNoCLI, self).__init__(logger)
        self._name = name
        self._process_name = process_name.strip()
        self._re_process_name: Optional[re.Pattern] = None

    def get_name(self) -> str:
        return self._name

    def can_be_managed(self) -> Tuple[bool, Optional[str]]:
        if not shutil.which(self._process_name):
            return False, f"'{self._process_name}' is not installed"

        return True, None

    async def enable(self, user_id: Optional[int], user_env: Optional[Dict[str, str]], context: dict) -> bool:
        enable_cmd = context.get('cmd')

        if not enable_cmd:
            self._log.error(f"Enable command not available on context for compositor '{self.get_name()}'")
            return False

        code, output = await system.run_async_user_process(cmd=enable_cmd, user_id=user_id, user_env=user_env)

        if code == 0:
            return True

        error_log = output.replace('\n', ' ') if output else ''
        self._log.error(f"Could not start window compositor '{self.get_name()}'. Command '{enable_cmd}' failed. Output: {error_log}")
        return False

    async def disable(self, user_id: Optional[int], user_env: Optional[dict], context: dict) -> bool:
        pid = context.get('pid')

        if pid is None:
            self._log.error(f"Window compositor {self.get_name()} process id could not be found on the context ({context}). It will not be disabled.")
            return False

        code, output = await system.async_syscall('kill -9 {}'.format(pid))

        if code == 0:
            return True

        error_log = output.replace('\n', ' ') if output else ''
        self._log.error(f"Could stop window compositor process '{self._process_name}' (pid={pid}). Output: {error_log}")
        return False

    async def is_enabled(self, user_id: Optional[int], user_env: Optional[dict], context: dict) -> Optional[bool]:
        if self._re_process_name is None:
            self._re_process_name = re.compile(r'^{}$'.format(self._process_name))

        proc_data = await system.find_process_by_name(self._re_process_name)

        if proc_data:
            context['pid'] = proc_data[0]
            context['cmd'] = proc_data[1]
            return True

        return False


class PicomCompositor(WindowCompositor):

    def __init__(self, name: str, logger: Logger):
        super(PicomCompositor, self).__init__(logger)
        self._compositor = WindowCompositorNoCLI(name=name.capitalize(), process_name=name, logger=logger)

    def can_be_managed(self) -> Tuple[bool, Optional[str]]:
        return self._compositor.can_be_managed()

    async def enable(self, user_id: Optional[int], user_env: Optional[dict], context: dict) -> bool:
        return await self._compositor.enable(user_id, user_env, context)

    async def disable(self, user_id: Optional[int], user_env: Optional[dict], context: dict) -> bool:
        return await self._compositor.disable(user_id, user_env, context)

    async def is_enabled(self, user_id: Optional[int], user_env: Optional[dict], context: dict) -> Optional[bool]:
        return await self._compositor.is_enabled(user_id, user_env, context)

    def get_name(self) -> str:
        return self._compositor.get_name()


class CompizCompositor(WindowCompositor):

    def __init__(self, logger: Logger):
        super(CompizCompositor, self).__init__(logger)
        self._compositor = WindowCompositorNoCLI(name='Compiz', process_name='compiz', logger=logger)

    def can_be_managed(self) -> Tuple[bool, Optional[str]]:
        return self._compositor.can_be_managed()

    async def enable(self, user_id: Optional[int], user_env: Optional[dict], context: dict) -> bool:
        return await self._compositor.enable(user_id, user_env, context)

    async def disable(self, user_id: Optional[int], user_env: Optional[dict], context: dict) -> bool:
        return await self._compositor.disable(user_id, user_env, context)

    async def is_enabled(self, user_id: Optional[int], user_env: Optional[dict], context: dict) -> Optional[bool]:
        return await self._compositor.is_enabled(user_id, user_env, context)

    def get_name(self) -> str:
        return self._compositor.get_name()


class NvidiaCompositor(WindowCompositor):

    def __init__(self, logger: Logger):
        super(NvidiaCompositor, self).__init__(logger)
        self._re_attrs: Optional[re.Pattern] = None
        self._main_cmd = 'nvidia-settings'

    def can_be_managed(self) -> Tuple[bool, Optional[str]]:
        if not shutil.which(self._main_cmd):
            return False, f"'{self._main_cmd}' is not installed"

        return True, None

    def _get_re_attrs(self) -> re.Pattern:
        if self._re_attrs is None:
            self._re_attrs = re.compile(r'((Force(Full)?CompositionPipeline)\s*=\s*\w+)', re.IGNORECASE)

        return self._re_attrs

    def extract_attributes(self, string: str) -> Optional[Set[str]]:
        matches = self._get_re_attrs().findall(string)

        if matches:
            return {*{m[1].strip().lower(): m[1].strip() for m in matches if len(m) == 3}.values()}

    def get_name(self) -> str:
        return 'Nvidia'

    async def _assign_mode(self, enable: bool, user_env: Dict[str, str], context: Dict[str, str]) -> bool:
        mode = context.get('mode')

        if not mode:
            self._log.error(f"Cannot {'enable' if enable else 'disable'} the {self.get_name()} compositor: no mode on context")
            return False

        meta_mode = '{' + f"{mode}={'On' if enable else 'Off'}" + '}'
        cmd = f'{self._main_cmd} --assign CurrentMetaMode="nvidia-auto-select +0+0 {meta_mode}"'
        self._log.debug(f"{'Enabling' if enable else 'Disabling'} {self.get_name()} compositor: {cmd}")
        code, output = await system.async_syscall(cmd, custom_env=user_env)

        if code == 0 and (not output or 'error assigning value' not in output.lower()):
            return True

        log_err = '. Command output: {}'.format(output.replace('\n', ' ')) if output else ''
        self._log.error(f"Could not {'enable' if enable else 'disable'} {self.get_name()} compositor{log_err}")
        return False

    async def enable(self, user_id: Optional[int], user_env: Optional[dict], context: dict) -> bool:
        return await self._assign_mode(True, user_env, context)

    async def disable(self, user_id: Optional[int], user_env: Optional[dict], context: dict) -> bool:
        return await self._assign_mode(False, user_env, context)

    async def is_enabled(self, user_id: Optional[int], user_env: Optional[dict], context: dict) -> Optional[bool]:
        code, output = await system.async_syscall(f'{self._main_cmd} -q /CurrentMetaMode', custom_env=user_env)

        if code == 0:
            output = output.strip()

            if output:
                attrs = self.extract_attributes(output)

                if attrs:
                    context['mode'] = 'ForceFullCompositionPipeline' if len(attrs) == 2 else 'ForceCompositionPipeline'
                    return True

            if context.get('mode'):
                return False
            else:
                output_log = output.replace('\n', ' ')
                self._log.warning(f"Could not determine {self.get_name()} compositor state from 'nvidia-settings' output: {output_log}")
        else:
            output_log = '. Output: {}'.format(output.replace('\n', ' ')) if output else ''
            self._log.error(f"Error while checking {self.get_name()} compositor state. 'nvidia-settings' returned an unexpected exitcode ({code}){output_log}")


async def inxi_read_compositor(user_id: int, user_env: Optional[dict], logger: Logger) -> Optional[str]:
    if which('inxi'):
        cmd = 'inxi -Gxx -c 0'
        code, output = await run_async_user_process(cmd=cmd, user_id=user_id, user_env=user_env)

        if code == 0:
            name = RE_COMPOSITOR_NAME.findall(output)

            if not name:
                logger.warning(f"Command '{cmd}' did not return the window compositor name")
            else:
                return name[0].strip().lower()
        else:
            output_log = output.replace('\n', ' ') if output else ''
            logger.error(f"Error when executing command '{cmd}'. Could not read the current window compositor. Exit code: {code}. Output: {output_log}")


def guess_compositor_for_desktop_environment(user_env: Optional[dict], logger: Logger) -> Optional[str]:
    desk_env = user_env.get('XDG_CURRENT_DESKTOP', '').lower() if user_env else None

    if not desk_env:
        logger.warning("Could not determine the desktop environment and compositor (missing variable 'XDG_CURRENT_DESKTOP'")
        return

    logger.info(f"Guessing window compositor based on desktop environment: {desk_env}")

    if desk_env == 'kde':
        return 'kwin'
    elif desk_env == 'xfce':
        return 'xfwm4'
    elif desk_env == 'mate':
        return 'marco'
    else:
        logger.warning(f"Unknown window compositor for desktop environment: {desk_env}")


async def get_window_compositor(user_id: int, user_env: Optional[Dict[str, str]], logger: Logger) -> Optional[WindowCompositor]:
    name = await inxi_read_compositor(user_id, user_env, logger)

    if not name:
        name = guess_compositor_for_desktop_environment(user_env, logger)

    return get_window_compositor_by_name(name, logger)


def get_window_compositor_by_name(name: str, logger: Logger) -> Optional[WindowCompositor]:
    if name:
        clean_name = name.strip().lower()

        if 'kwin' in clean_name:
            return KWinCompositor(logger)
        elif 'xfwm4' in clean_name:
            return Xfwm4Compositor(logger)
        elif 'marco' in clean_name or 'metacity' in clean_name:
            return MarcoCompositor(logger)
        elif 'compton' in clean_name:
            return PicomCompositor('compton', logger)
        elif 'picom' in clean_name:
            return PicomCompositor('picom', logger)
        elif 'compiz' in clean_name:
            return CompizCompositor(logger)
        elif 'nvidia' == clean_name:
            return NvidiaCompositor(logger)
        else:
            logger.warning(f"Compositor '{name}' is currently not supported")
