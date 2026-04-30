import re

UNDERLINE_START = '\033[4m'
UNDERLINE_END = '\033[24m'

RED_START = '\033[31m'
RED_END = '\033[39m'

ESC_SEQ_REGEX = re.compile('\033' + r'\[(\d+(;\d+)*)?[a-zA-Z]')
def screenlen(x: str) -> int:
    return len(re.sub(ESC_SEQ_REGEX, '', x))

def underline(s: str) -> str:
    return f'{UNDERLINE_START}{s}{UNDERLINE_END}'

def red(s: str) -> str:
    return f'{RED_START}{s}{RED_END}'

