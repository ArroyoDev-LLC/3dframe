"""Repair Operation"""

import copy

import attrs
import open3d as o3d

from threedframe.utils import SerializableMesh


def prepare_mesh(self, mesh: o3d.geometry.TriangleMesh) -> o3d.geometry.TriangleMesh:
    if not mesh.has_vertex_normals():
        mesh.compute_vertex_normals()
    if not mesh.has_triangle_normals():
        mesh.compute_triangle_normals()
    return mesh


def repair_mesh(self, mesh: o3d.geometry.TriangleMesh) -> o3d.geometry.TriangleMesh:
    new_mesh = self._prepare_mesh(copy.deepcopy(mesh))
    new_mesh.remove_duplicated_vertices()
    new_mesh.remove_unreferenced_vertices()
    new_mesh.remove_duplicated_triangles()
    new_mesh.remove_degenerate_triangles()
    new_mesh.remove_non_manifold_edges()
    return new_mesh


@attrs.define
class RepairOperation:
    def operate(self, mesh: SerializableMesh) -> SerializableMesh:
        _mesh = repair_mesh(mesh.to_open3d())
        return SerializableMesh(_mesh)
