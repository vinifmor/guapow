from argparse import Namespace
from logging import Logger

from guapow import __app_name__
from guapow.cli.command import CLICommand
from guapow.cli.commands.service import ServiceInstaller, ServiceUninstaller

WATCHER_SERVICE_FILE = f'{__app_name__}-watch.service'


class InstallWatcher(CLICommand):

    CMD = 'install-watcher'

    def __init__(self, logger: Logger):
        super(InstallWatcher, self).__init__(logger)
        self._installer = ServiceInstaller(service_cmd=WATCHER_SERVICE_FILE.split('.service')[0],
                                           service_file=WATCHER_SERVICE_FILE, 
                                           requires_root=False,
                                           logger=logger)

    def add(self, commands: object):
        commands.add_parser(self.CMD, help="It installs and enables the watcher service (root or user level) [requires 'systemd' and 'systemctl' installed]")

    def get_command(self) -> str:
        return self.CMD

    def run(self, args: Namespace) -> bool:
        return self._installer.install()


class UninstallWatcher(CLICommand):

    CMD = 'uninstall-watcher'

    def __init__(self, logger: Logger):
        super(UninstallWatcher, self).__init__(logger)
        self._uninstaller = ServiceUninstaller(service_file=WATCHER_SERVICE_FILE, requires_root=False, logger=logger)

    def add(self, commands: object):
        commands.add_parser(self.CMD, help="It disables and uninstalls the watcher service (root or user level) [requires 'systemd' and 'systemctl' installed]")

    def get_command(self) -> str:
        return self.CMD

    def run(self, args: Namespace) -> bool:
        return self._uninstaller.uninstall()
