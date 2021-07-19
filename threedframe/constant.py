"""3DFrame Constants."""

from enum import Enum

import numpy as np
import sympy as S
from euclid3 import Point3 as EucPoint3
from euclid3 import Vector3 as EucVector3


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

    # Left -> Towards X-
    LEFT = (-1, 0, 0)
    # Right -> Towards X+
    RIGHT = (1, 0, 0)
    # Front/Forward -> Towards Y-
    FORWARD = (0, 1, 0)
    # Back/Behind -> Y+
    BACK = (0, -1, 0)
    # Bottom/Down/Below -> Towards Z-
    DOWN = (0, 0, -1)
    # Top/Up/Above -> Towards Z+
    UP = (0, 0, 1)

    @property
    def as_arr(self) -> List[int]:
        return list(self.value)

    @property
    def as_nparray(self) -> "np.ndarray":
        return np.array(self.as_arr, dtype=np.float64)

    @property
    def as_sympy(self) -> S.Point3D:
        return S.Point(*self.value).copy()

    @property
    def as_euclid(self) -> Union[EucPoint3, EucVector3]:
        if self == PlanarConstants.ORIGIN:
            return EucPoint3(*self.value).copy()
        return EucVector3(*self.value).copy()


