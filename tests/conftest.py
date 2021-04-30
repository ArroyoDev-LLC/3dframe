from pathlib import Path

import pytest

TESTS_ROOT = Path(__file__).parent
TESTS_DATA = TESTS_ROOT / "data"


@pytest.fixture
def test_data():
    assert TESTS_DATA.exists()
    return TESTS_DATA
