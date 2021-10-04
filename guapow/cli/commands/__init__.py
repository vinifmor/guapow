from typing import Dict

from guapow.cli.commands.optimizer import *
from guapow.cli.commands.profile import *
from guapow.cli.commands.watcher import *


def map_commands(logger: Logger) -> Dict[str, CLICommand]:
    res = {}

    for c in CLICommand.__subclasses__():
        instance = c(logger)
        res[instance.get_command()] = instance

    return res
