from typing import Tuple, Optional
from unittest.mock import Mock

from guapow.service.optimizer.win_compositor import WindowCompositor


class WindowCompositorMock(WindowCompositor):

    def __init__(self, enabled: bool = False):
        super(WindowCompositorMock, self).__init__(Mock())
        self._enabled = enabled
        self.enable_count = 0
        self.disable_count = 0

    def can_be_managed(self) -> Tuple[bool, Optional[str]]:
        return True, None

    def get_name(self) -> str:
        return 'mock'

    async def is_enabled(self, user_id: Optional[int], user_env: Optional[dict], context: dict) -> Optional[bool]:
        return self._enabled

    async def enable(self, user_id: Optional[int], user_env: Optional[dict], context: dict) -> bool:
        self._enabled = True
        self.enable_count += 1
        return True

    async def disable(self, user_id: Optional[int], user_env: Optional[dict], context: dict) -> bool:
        self.disable_count += 1
        self._enabled = False
        return True
