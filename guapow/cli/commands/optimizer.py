from argparse import Namespace
from logging import Logger

from guapow import __app_name__
from guapow.cli.command import CLICommand
from guapow.cli.commands.service import ServiceInstaller, ServiceUninstaller

OPTIMIZER_SERVICE_FILE = f'{__app_name__}-opt.service'


class InstallOptimizer(CLICommand):

    CMD = 'install-optimizer'

    def __init__(self, logger: Logger):
        super(InstallOptimizer, self).__init__(logger)
        self._installer = ServiceInstaller(service_cmd=OPTIMIZER_SERVICE_FILE.split('.service')[0],
                                           service_file=OPTIMIZER_SERVICE_FILE,
                                           requires_root=True,
                                           logger=logger)

    def add(self, commands: object):
        commands.add_parser(self.CMD, help="It installs and enables the optimizer service (root level) [requires 'systemd' and 'systemctl' installed]")

    def get_command(self) -> str:
        return self.CMD

    def run(self, args: Namespace) -> bool:
        return self._installer.install()


class UninstallOptimizer(CLICommand):

    CMD = 'uninstall-optimizer'

    def __init__(self, logger: Logger):
        super(UninstallOptimizer, self).__init__(logger)
        self._uninstaller = ServiceUninstaller(service_file=OPTIMIZER_SERVICE_FILE, requires_root=True, logger=logger)

    def add(self, commands: object):
        commands.add_parser(self.CMD, help="It disables and uninstalls the optimizer service (root level) [requires 'systemd' and 'systemctl' installed]")

    def get_command(self) -> str:
        return self.CMD

    def run(self, args: Namespace) -> bool:
        return self._uninstaller.uninstall()
