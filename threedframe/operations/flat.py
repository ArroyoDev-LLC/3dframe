"""Flatten a given mesh.

 Translate the min bound of a given mesh to 0.
"""


from typing import Any

import attrs
import numpy as np
import numpy.typing as npt


@attrs.define
class FlatOperation:
    def _compute_translation(self, vertices: npt.ArrayLike) -> np.ndarray[Any, np.float64]:
        verts = np.asarray(vertices, dtype=np.float64)
        min_vert = np.min(axis=0)
        relative_translation = np.zeros((1, 3), dtype=np.float64) - min_vert
        return verts + relative_translation

    def operate(self, vertices: npt.ArrayLike) -> np.ndarray[Any, np.float64]:
        return self._compute_translation(vertices)
