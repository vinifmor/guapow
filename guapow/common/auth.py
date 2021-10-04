from typing import Optional

import aiofiles


def get_machine_id_path() -> str:
    return '/etc/machine-id'


async def read_machine_id() -> Optional[str]:
    try:
        async with aiofiles.open(get_machine_id_path()) as f:
            return (await f.read()).strip()
    except FileNotFoundError:
        return
