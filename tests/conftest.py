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

def pytest_collection_modifyitems(session: pytest.Session, config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption('--run-slow'):
        # --run-slow given in cli: do not skip slow tests
        return

    skip_slow = pytest.mark.skip(reason='need --run-slow option to run')
    for item in items:
        if 'slow' in item.keywords:
            item.add_marker(skip_slow)
