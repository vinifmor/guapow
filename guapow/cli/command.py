from abc import ABC, abstractmethod
from argparse import Namespace
from logging import Logger


class CLICommand(ABC):

    @abstractmethod
    def __init__(self, logger: Logger):
        self._log = logger

    @abstractmethod
    def add(self, commands: object):
        pass

    @abstractmethod
    def get_command(self) -> str:
        pass

    @abstractmethod
    def run(self, args: Namespace) -> bool:
        pass
