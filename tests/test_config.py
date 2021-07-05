import pytest
from pytest import approx

from threedframe.config import _Config

# at 0.69 scale
computed_vals = [
    (
        "support_size",
        17.53,
    ),
    (
        "core_size",
        35.56,
    ),
    (
        "fixture_shell_thickness",
        3.0,
    ),
    (
        "fixture_length",
        38.1,
    ),
    (
        "fixture_size",
        20.54,
    ),
    ("fixture_hole_size", 17.55),
    (
        "label_size",
        7.15,
    ),
    (
        "label_width",
        16.65,
    ),
]


@pytest.mark.parametrize("attr,expect", computed_vals)
def test_config(attr: str, expect: float):
    c = _Config(SUPPORT_SCALE=0.69)
    assert getattr(c, attr) == approx(expect, rel=1e-2)
