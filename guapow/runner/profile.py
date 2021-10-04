from logging import Logger
from typing import Optional, Dict, Tuple

import aiofiles

from guapow.common.model import ProfileFile, ScriptSettings
from guapow.common.model_util import FileModelFiller
from guapow.common.profile import StopProcessSettings
from guapow.common.profile import get_profile_dir, get_default_profile_name


class RunnerProfile(ProfileFile):

    FILE_MAPPING = {'proc.env': ('environment_variables', dict, None)}

    def __init__(self, path: Optional[str], environment_variables: Optional[dict]):
        super(RunnerProfile, self).__init__(path)
        self.before_scripts = ScriptSettings(node_name='scripts.before')
        self.environment_variables = environment_variables
        self.stop = StopProcessSettings('stop.before', None)

    def get_file_mapping(self) -> Dict[str, Tuple[str, type, Optional[object]]]:
        return self.FILE_MAPPING

    def is_valid(self) -> bool:
        if super(RunnerProfile, self).is_valid():
            return True

        return bool(self.environment_variables)

    def setup_valid_properties(self):
        if self.before_scripts:
            self.before_scripts.run_as_root = False

    @classmethod
    def empty(cls, path: Optional[str] = None) -> "RunnerProfile":
        return cls(path, None)


class RunnerProfileReader:

    def __init__(self, model_filler: FileModelFiller, logger: Logger):
        self._model_filler = model_filler
        self._log = logger

    async def read_valid(self, user_id: int, user_name: str, profile: str, add_settings: Optional[str] = None) -> Optional[RunnerProfile]:
        profile_path = f'{get_profile_dir(user_id, user_name)}/{profile}.profile'
        self._log.info(f"Reading runner profile file '{profile_path}'")

        async with aiofiles.open(profile_path) as f:
            profile_str = (await f.read()).strip()

        if not profile_str:
            self._log.warning(f"No properties defined in runner profile file '{profile_path}'")
            return

        instance = RunnerProfile.empty()
        self._model_filler.fill_profile(profile=instance, profile_str=profile_str, profile_path=profile_path, add_settings=add_settings)
        instance.setup_valid_properties()

        if instance.is_valid():
            return instance

        self._log.warning(f"No valid runner profile properties found in file '{profile_path}'")

    async def read_available(self, user_id: int, user_name: str, profile: Optional[str], add_settings: Optional[str] = None) -> Optional[RunnerProfile]:
        if profile:
            try:
                return await self.read_valid(user_id=user_id, user_name=user_name, profile=profile, add_settings=add_settings)
            except FileNotFoundError as e:
                self._log.warning(f"Runner profile file '{e.filename}' not found")

        try:
            return await self.read_valid(user_id=user_id, user_name=user_name, profile=get_default_profile_name(), add_settings=add_settings)
        except FileNotFoundError as e:
            self._log.warning(f"Runner profile file '{e.filename}' not found")

    def map_valid_config(self, config: str) -> Optional[RunnerProfile]:
        instance = RunnerProfile.empty()
        self._model_filler.fill_profile(profile=instance, profile_str='\n'.join(config.split(' ')), profile_path=None)
        instance.reset_invalid_nested_members()
        instance.setup_valid_properties()

        if instance.is_valid():
            return instance
        else:
            self._log.error(f'Invalid configuration defined: {config}')
