from typing import List
from pathlib import Path

import pytest

from threedframe.scad import JointDirector, JointDirectorParams

from .utils import DirectoryFactoryType

TESTS_ROOT = Path(__file__).parent
TESTS_DATA = TESTS_ROOT / "data"


@pytest.fixture
def test_data():
    assert TESTS_DATA.exists()
    return TESTS_DATA


@pytest.fixture
def director_factory(test_data: Path) -> DirectoryFactoryType:
    in_data = test_data / "computed.json"

    def _director_factory(vertices: List[int]) -> JointDirector:
        params = JointDirectorParams(model=in_data, vertices=vertices)
        return JointDirector(params=params)

    return _director_factory
