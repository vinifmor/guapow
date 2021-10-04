import getpass
import os
from argparse import Namespace
from logging import Logger
from pathlib import Path

from guapow.cli.command import CLICommand
from guapow.common.profile import get_profile_dir
from guapow.service.optimizer.profile import OptimizationProfile, CPUSettings, ProcessSettings, IOSchedulingClass, \
    GPUSettings, CompositorSettings


class GenerateProfile(CLICommand):

    CMD = 'gen-profile'
    PROFILES = {'default', 'media', 'game', 'steam'}

    @classmethod
    def generate_default(cls, path: str) -> OptimizationProfile:
        profile = OptimizationProfile.empty(path)
        profile.cpu = CPUSettings(performance=True)
        profile.process = ProcessSettings(None)
        profile.process.nice.level = -1
        profile.process.io.ioclass = IOSchedulingClass.BEST_EFFORT
        profile.process.io.nice_level = 0
        return profile

    @classmethod
    def generate_media(cls, path: str) -> OptimizationProfile:
        profile = cls.generate_default(path)
        profile.process.nice.level = -4
        return profile

    @classmethod
    def generate_game(cls, path: str) -> OptimizationProfile:
        profile = cls.generate_media(path)
        profile.gpu = GPUSettings(performance=True)
        profile.compositor = CompositorSettings(off=True)
        profile.process.nice.watch = True  # some games change their nice level during initialization, so it is better to keep monitoring
        return profile

    @classmethod
    def generate_steam(cls, path: str) -> OptimizationProfile:
        profile = cls.generate_game(path)
        profile.steam = True
        return profile

    def __init__(self, logger: Logger):
        super(GenerateProfile, self).__init__(logger)

    def add(self, commands: object):
        cmd = commands.add_parser('gen-profile', help='It generates template profiles. Options: {}'.format(', '.join(self.PROFILES)))
        cmd.add_argument('name', choices=self.PROFILES, help="Profile name", type=str)

    def get_command(self) -> str:
        return self.CMD

    def run(self, args: Namespace) -> bool:
        profile_name = args.name
        prof_dir = get_profile_dir(os.getuid(), getpass.getuser())
        profile_path = f'{prof_dir}/{profile_name}.profile'

        if os.path.exists(profile_path):
            self._log.error(f"Profile file '{profile_path}' already exists")
            return False

        self._log.info(f"Generating profile '{profile_name}'")

        try:
            Path(prof_dir).mkdir(parents=True, exist_ok=True)
        except OSError:
            self._log.error(f"Could not make directory '{prof_dir}'")
            return False

        profile = eval(f"self.generate_{profile_name}('{profile_path}')")

        try:
            with open(profile_path, 'w+') as f:
                f.write(profile.to_file_str())

            self._log.info(f'Profile file generated: {profile_path}')
            return True
        except OSError:
            self._log.error(f"Could not generate profile file '{profile_path}'")
            return False
