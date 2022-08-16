"""IO Operations."""


import io
import struct
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


def convert_bin_stl_to_ascii(path: Path) -> Path:
    data = path.read_bytes()
    out = io.StringIO()

    header = data[:80]

    # Length of Surfaces
    bin_faces = data[80:84]
    faces = struct.unpack("I", bin_faces)[0]

    out.write(f"solid {path.stem}")

    for x in range(0, faces):
        out.write("facet normal ")

        xc = data[84 + x * 50 : (84 + x * 50) + 4]
        yc = data[88 + x * 50 : (88 + x * 50) + 4]
        zc = data[92 + x * 50 : (92 + x * 50) + 4]

        out.write(str(struct.unpack("f", xc)[0]) + " ")
        out.write(str(struct.unpack("f", yc)[0]) + " ")
        out.write(str(struct.unpack("f", zc)[0]) + "\n")

        out.write(" outer loop\n")
        for y in range(1, 4):
            out.write("  vertex ")

            xc = data[84 + y * 12 + x * 50 : (84 + y * 12 + x * 50) + 4]
            yc = data[88 + y * 12 + x * 50 : (88 + y * 12 + x * 50) + 4]
            zc = data[92 + y * 12 + x * 50 : (92 + y * 12 + x * 50) + 4]

            out.write(str(struct.unpack("f", xc)[0]) + " ")
            out.write(str(struct.unpack("f", yc)[0]) + " ")
            out.write(str(struct.unpack("f", zc)[0]) + "\n")

        out.write(" endloop\n")
        out.write("endfacet\n")

    out.write(f"endsolid {path.stem}\n")

    path.write_text(out.getvalue())
    out.close()
    return path


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
