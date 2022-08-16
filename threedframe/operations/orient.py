"""Auto Orient Operation."""

from __future__ import annotations

import copy
import tempfile
from pathlib import Path

import attrs
import open3d as o3d
from tweaker3 import FileHandler, MeshTweaker

from threedframe.utils import SerializableMesh
from threedframe.operations.mesh_io import convert_bin_stl_to_ascii


@attrs.define
class OptimalOrientOperation:
    def _prepare_mesh(self, mesh: o3d.geometry.TriangleMesh) -> list[list[int]]:
        tmp_file = tempfile.mktemp(suffix=".stl")
        mesh.compute_vertex_normals()
        mesh.compute_triangle_normals()
        o3d.io.write_triangle_mesh(tmp_file, mesh)
        convert_bin_stl_to_ascii(Path(tmp_file))
        fh = FileHandler.FileHandler()
        objs: list[dict[str, list[list[int]]]] = fh.load_mesh(tmp_file)
        _mesh = objs[0]["mesh"]
        Path(tmp_file).unlink()
        return _mesh

    def _orient_mesh(
        self, mesh: o3d.geometry.TriangleMesh, data: list[list[int]]
    ) -> o3d.geometry.TriangleMesh:
        tweak = MeshTweaker.Tweak(
            data, extended_mode=True, verbose=True, show_progress=True, min_volume=False
        )
        new_mesh = copy.deepcopy(mesh).rotate(tweak.matrix)
        return new_mesh

    def operate(self, mesh: SerializableMesh) -> SerializableMesh:
        _mesh = mesh.to_open3d()
        return SerializableMesh(self._orient_mesh(_mesh, self._prepare_mesh(_mesh)))
