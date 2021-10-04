from argparse import ArgumentParser, Namespace
from typing import Iterable

from guapow import __app_name__, __version__
from guapow.cli.command import CLICommand


def read(commands: Iterable[CLICommand]) -> Namespace:
    parser = ArgumentParser(prog=__app_name__, description=f"Utility commands for {__app_name__}")
    parser.add_argument('-v', '--version', action='version', version=f'%(prog)s {__version__}')

    sub_parsers = parser.add_subparsers(dest='command', help='Available commands')

    for c in commands:
        c.add(sub_parsers)

    return parser.parse_args()
