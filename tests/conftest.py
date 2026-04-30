import sys
from pathlib import Path
import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        '--run-slow',
        action='store_true',
        default=False,
        help='Run slow tests',
    )

    parser.addoption(
        '--run-very-slow',
        action='store_true',
        default=False,
        help='Run very slow tests',
    )

def pytest_collection_modifyitems(session: pytest.Session, config: pytest.Config, items: list[pytest.Item]) -> None:
    skip_slow = pytest.mark.skip(reason='need --run-slow option to run')
    skip_very_slow = pytest.mark.skip(reason='need --run-very-slow option to run')
    for item in items:
        if 'slow' in item.keywords and not config.getoption('--run-slow'):
            item.add_marker(skip_slow)
        if 'veryslow' in item.keywords and not config.getoption('--run-very-slow'):
            item.add_marker(skip_very_slow)

