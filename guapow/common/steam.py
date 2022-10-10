import re

RE_STEAM_CMD = re.compile(r'^.+\s+SteamLaunch\s+AppId\s*=\s*\d+\s+--\s+(.+)')
