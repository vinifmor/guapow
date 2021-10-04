import re
from re import Pattern
from typing import Optional

re_any_operator = re.compile(r'\*+')


def map_any_regex(word: str) -> Optional[Pattern]:
    if word:
        if has_any_regex(word):
            return map_only_any_regex(word)
        else:
            return re.compile(r'^{}$'.format(re.escape(word)))


def has_any_regex(word: str) -> bool:
    return '*' in word if word else False


def map_only_any_regex(word: str) -> Optional[Pattern]:
    escaped_word = re.escape(re_any_operator.sub('@', word))
    return re.compile(r'^{}$'.format(escaped_word.replace('@', '.+')))


def strip_file_extension(cmd: str) -> Optional[str]:
    if cmd:
        return '.'.join(cmd.split('.')[0:-1])

