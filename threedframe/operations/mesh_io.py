"""IO Operations."""


from pathlib import Path

import attrs
import open3d as o3d

from threedframe.utils import SerializableMesh


def write_mesh(path: Path, mesh: o3d.geometry.TriangleMesh) -> Path:
    o3d.io.write_triangle_mesh(str(path.absolute()), mesh)
    return path


def read_mesh(path: Path) -> o3d.geometry.TriangleMesh:
    mesh = o3d.io.read_triangle_mesh(str(path.absolute()), enable_post_processing=True)
    return mesh


@attrs.define
class ReadMeshOperation:
    def operate(self, path: Path) -> o3d.geometry.TriangleMesh:
        return read_mesh(path)


@attrs.define
class WriteMeshOperation:
    path: Path

    def operate(self, mesh: o3d.geometry.TriangleMesh) -> Path:
        return write_mesh(self.path, mesh)


@attrs.define
class SerializeMeshOperation:
    def operate(self, mesh: o3d.geometry.TriangleMesh) -> SerializableMesh:
        return SerializableMesh(mesh)
