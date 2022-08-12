"""Flatten a given mesh.

 Translate the min bound of a given mesh to 0.
"""


import copy
from typing import Any

import attrs
import numpy as np
import open3d as o3d
import numpy.typing as npt

from threedframe.utils import SerializableMesh


@attrs.define
class FlatOperation:
    def _compute_translation(self, vertices: npt.ArrayLike) -> np.ndarray[Any, np.float64]:
        verts = np.asarray(vertices, dtype=np.float64)
        min_vert = verts.min(axis=0)
        relative_translation = np.zeros((1, 3), dtype=np.float64) - min_vert
        return relative_translation

    def _translate_mesh(self, mesh: o3d.geometry.TriangleMesh) -> o3d.geometry.TriangleMesh:
        trans = self._compute_translation(mesh.vertices)
        return mesh.translate(trans.reshape(3, 1))

    def operate(self, mesh: SerializableMesh) -> SerializableMesh:
        new_mesh = copy.deepcopy(mesh.to_open3d())
        return SerializableMesh(self._translate_mesh(new_mesh))
