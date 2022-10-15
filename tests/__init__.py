import asyncio
import os
from typing import Iterable, Optional, Any, List

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
RESOURCES_DIR = f'{TESTS_DIR}/resources'


class AnyInstance(object):
    def __init__(self, instance_class: type):
        self._class = instance_class

    def __eq__(self, other):
        return other is not None and isinstance(other, self._class)

    def __repr__(self):
        return f'<ANY_{self._class.__name__}>'


class AsyncIterator:
    def __init__(self, seq: Iterable):
        self.iter = iter(seq)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.iter)
        except StopIteration:
            raise StopAsyncIteration


class MockedAsyncCall:
    def __init__(self, results: List[Any], await_time: Optional[float] = None):
        self._results = results
        self._iterable = iter(results)
        self._await_time = await_time if isinstance(await_time, (int, float)) and await_time > 0 else None

    async def call(self, *args, **kwargs) -> Any:
        if self._await_time:
            await asyncio.sleep(self._await_time)

        return next(self._iterable, self._results[-1])
