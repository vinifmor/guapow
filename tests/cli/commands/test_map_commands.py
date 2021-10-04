from unittest import TestCase
from unittest.mock import Mock

from guapow.cli.commands import map_commands, GenerateProfile, InstallOptimizer, UninstallOptimizer, InstallWatcher, \
    UninstallWatcher


class MapCommandsTest(TestCase):

    def test__must_return_all_CLICommand_subclasses(self):
        cmds = map_commands(Mock())

        exp_classes = {GenerateProfile, InstallOptimizer, UninstallOptimizer, InstallWatcher, UninstallWatcher}

        self.assertEqual(len(exp_classes), len(cmds))

        for cmd in cmds.values():
            self.assertIn(cmd.__class__, exp_classes)
