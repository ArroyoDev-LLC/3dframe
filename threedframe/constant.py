"""3DFrame Constants."""

from enum import Enum

import sympy as S
from euclid3 import Point3 as EucPoint3


class Constants(float, Enum):
    TAU = 6.2831853071  # 2*PI
    MM = 1
    INCH = 25.4 * MM


class PlanarConstants(Enum):
    ORIGIN = (
        0,
        0,
        0,
    )

    @property
    def as_sympy(self):
        return S.Point(*self.value)

    @property
    def as_euclid(self):
        return EucPoint3(*self.value)
