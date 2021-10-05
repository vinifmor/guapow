import os
import re
import shutil
from logging import Logger
from pathlib import Path
from typing import Dict, Optional, Tuple

from guapow import ROOT_DIR
from guapow.common import system
from guapow.common.users import is_root_user


def get_systemd_root_service_dir() -> str:
    return '/usr/lib/systemd/system'


def get_systemd_user_service_dir() -> str:
    return f'{Path.home()}/.config/systemd/user'


def get_service_dir(root: bool) -> str:
    return get_systemd_root_service_dir() if root else get_systemd_user_service_dir()


def map_service_status(output: str) -> Optional[Tuple[str, str]]:
    res = re.compile(r'\s+loaded\s+\((/.+\.service);\s*(\w+);.*\)').findall(output)
    return res[0] if res else None


def gen_english_environment() -> Dict[str, str]:
    custom_env = dict(os.environ)
    custom_env['LANG'] = 'en_US.UTF-8'
    return custom_env


def get_source_service_path(file_name: str, root: bool) -> str:
    return f"{ROOT_DIR}/dist/daemon/systemd/{'root' if root else 'user'}/{file_name}"


def get_service_status(file_name: str, root: bool, env: Dict[str, str]) -> Optional[str]:
    return system.syscall(f"systemctl status{' --user' if not root else ''} {file_name}", custom_env=env)[1]


def enable_service(file_name: str, root: bool, env: Dict[str, str]) -> Tuple[int, Optional[str]]:
    return system.syscall(f"systemctl enable{' --user' if not root else ''} --now {file_name}", custom_env=env)


def disable_service(file_name: str, root: bool, env: Dict[str, str]) -> Tuple[int, Optional[str]]:
    return system.syscall(f"systemctl disable{' --user' if not root else ''} --now {file_name}", custom_env=env)


class ServiceInstaller:

    def __init__(self, service_cmd: str, service_file: str, requires_root: bool, logger: Logger):
        self._service_cmd = service_cmd
        self._service_file = service_file
        self._requires_root = requires_root
        self._log = logger

    def install(self) -> bool:
        root = is_root_user()

        if self._requires_root and not root:
            self._log.error("Requires root privileges")
            return False

        if not shutil.which('systemctl'):
            self._log.error("'systemctl' is not installed on your system")
            return False

        service_cmd = shutil.which(self._service_cmd)

        if not service_cmd:
            self._log.error(f"'{self._service_cmd}' is not installed on your system")
            return False

        service_dir = get_service_dir(root)
        dest_file = f'{service_dir}/{self._service_file}'

        if not os.path.exists(dest_file):
            try:
                Path(service_dir).mkdir(exist_ok=True, parents=True)
            except OSError:
                self._log.error(f"Could not create directory '{service_dir}'")
                return False

            local_file = get_source_service_path(self._service_file, root)

            if not os.path.exists(local_file):
                self._log.error(f"Service definition file '{local_file}' not found")
                return False

            with open(local_file) as f:
                service_definition = f.read()

            replace_pattern = re.compile(r'ExecStart=.+\n')
            service_definition = replace_pattern.sub(f'ExecStart={service_cmd}\n', service_definition)

            try:
                with open(dest_file, 'w+') as f:
                    f.write(service_definition)
                    
                self._log.info(f"File '{local_file}' copied to '{dest_file}'")
            except OSError:
                self._log.error(f"Could not copy service file '{local_file}' to '{service_dir}'")
                return False

        custom_env = gen_english_environment()
        status_output = get_service_status(self._service_file, root, custom_env)

        status = map_service_status(status_output)

        if status and len(status) != 2:
            self._log.error("Unknown status output from 'systemctl' output: {}".format(status_output.replace('\n', ' ')))
            return False

        if status[1].strip() == 'enabled':
            return True

        enabled_code, enabled_output = enable_service(self._service_file, root, custom_env)

        if enabled_code != 0:
            error_log = ': {}'.format(enabled_output.replace('\n', ' ')) if enabled_output else ''
            self._log.error(f"Could not enable {self._service_file}. Output (exitcode={enabled_code}){error_log}")
            return False

        self._log.info(f"{self._service_file} enabled and started")
        return True


class ServiceUninstaller:

    def __init__(self, service_file: str, requires_root: bool, logger: Logger):
        self._service_file = service_file
        self._requires_root = requires_root
        self._log = logger

    def uninstall(self) -> bool:
        root = is_root_user()

        if self._requires_root and not root:
            self._log.error("Requires root privileges")
            return False

        if not shutil.which('systemctl'):
            self._log.error("'systemctl' is not installed on your system")
            return False

        custom_env = gen_english_environment()

        status_output = get_service_status(self._service_file, root, custom_env)

        if not status_output:
            self._log.error(f"Could not retrieve information of '{self._service_file}'")
            return False

        if ' could not be found' in status_output:
            self._log.info(f"{self._service_file} is not installed")
            return True

        status = map_service_status(status_output)

        if not status or len(status) != 2:
            output_log = status_output.replace('\n', ' ')
            self._log.error(f"Could not determine '{self._service_file}' status on the 'systemctl' output: {output_log}")
            return False

        file_path, service_status = status[0].strip(), status[1].strip()

        if service_status.lower() == 'enabled':
            disable_code, disable_output = disable_service(self._service_file, root, custom_env)

            if disable_code != 0:
                self._log.error(f"Could not disable '{self._service_file}'")
                return False

            self._log.info(f"{self._service_file} stopped and disabled")

        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                self._log.error(f"Could not remove file '{file_path}'")
                return False

            self._log.info(f"'{file_path}' removed")

        return True
