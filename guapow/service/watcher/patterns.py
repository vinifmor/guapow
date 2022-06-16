import re
from enum import Enum
from logging import Logger
from re import Pattern
from typing import Optional, Set, Tuple, Dict, Collection

from guapow.common import steam
from guapow.common.util import map_only_any_regex, has_any_regex

RE_PYTHON_REGEX = re.compile(r'^r:(.+)$')


class RegexType(Enum):
    CMD = 0
    COMM = 1


class RegexMapper:

    BUILTIN_RE = {'__steam__': (steam.RE_STEAM_CMD, RegexType.CMD)}

    def __init__(self, cache: bool, logger: Logger):
        self._pattern_cache: Optional[dict] = None
        self._string_no_pattern_cache: Optional[Set[str]] = None

        if cache:
            self._pattern_cache, self._string_no_pattern_cache = {}, set()

        self._log = logger

    def get_cached_pattern(self, str_pattern: str) -> Optional[Pattern]:
        if self._pattern_cache is not None:
            return self._pattern_cache.get(str_pattern)

    def is_cached_as_no_pattern(self, string: str) -> bool:
        return string in self._string_no_pattern_cache if self._string_no_pattern_cache is not None else False

    def map(self, string: str) -> Optional[Tuple[Pattern, RegexType]]:
        builtin_pattern = self.BUILTIN_RE.get(string)

        if builtin_pattern:
            if builtin_pattern[1] == RegexType.CMD:
                return builtin_pattern[0], RegexType.CMD

            if builtin_pattern[1] == RegexType.COMM:
                return builtin_pattern[0], RegexType.COMM

            self._log.error(f"Unknown type of built-in pattern '{string}'. It will be ignored.")
            return

        if self.is_cached_as_no_pattern(string):
            return

        pattern = self.get_cached_pattern(string)
        cached = bool(pattern)

        if not cached:
            python_regex = RE_PYTHON_REGEX.findall(string)

            if python_regex:
                try:
                    pattern = re.compile('^{}$'.format(python_regex[0]))
                except re.error:
                    self._log.warning(f'Invalid Python regex mapping: {string}')
                    return

            elif has_any_regex(string):
                pattern = map_only_any_regex(string)
            else:
                pattern = None

        if pattern:
            type_ = RegexType.CMD if pattern.pattern[1] == '/' else RegexType.COMM

            if not cached and self._pattern_cache is not None:
                self._pattern_cache[string] = pattern

            return pattern, type_

        elif self._string_no_pattern_cache is not None:
            self._string_no_pattern_cache.add(string)

    def map_for_profiles(self, mapping: Dict[str, str]) -> Optional[Tuple[Dict[Pattern, str], Dict[Pattern, str]]]:
        """
        return: a tuple with two dictionaries: first with cmd patterns and second with comm patterns.
        """
        if mapping:
            cmd, comm = {}, {}

            for string, prof in mapping.items():
                string_mapping = self.map(string)

                if string_mapping:
                    pattern, type_ = string_mapping

                    if type_ == RegexType.CMD:
                        cmd[pattern] = prof
                    elif type_ == RegexType.COMM:
                        comm[pattern] = prof
                    elif type_:
                        self._log.error(f"Could not assign pattern ({string}) to profile ({prof}). "
                                        f"Unsupported {RegexType.__class__.__name__} ({type_})")
                    else:
                        self._log.error(f"No {RegexType.__class__.__name__} returned when mapping pattern ({string})"
                                        f" to profile ({prof})")

            return cmd, comm

    def map_collection(self, strings: Collection[str]) -> Optional[Dict[RegexType, Set[Pattern]]]:
        if strings:
            res: Dict[RegexType, Set[Pattern]] = {type_: None for type_ in RegexType}
            for string in strings:
                string_mapping = self.map(string)
                if string_mapping:
                    pattern, type_ = string_mapping

                    if type_:
                        patterns = res.get(type_)

                        if patterns is None:
                            patterns = set()
                            res[type_] = patterns

                        patterns.add(pattern)
                    else:
                        self._log.error(f"No {RegexType.__class__.__name__} returned when mapping pattern ({string})")

            return res
