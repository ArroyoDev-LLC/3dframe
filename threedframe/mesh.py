#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""3dframe pymesh interactions.

TODO: This module used to be hackily copied and executed in a pymesh container,
needs a lot of cleanup.

"""
try:
    import pymesh  # noqa
except ImportError:
    pymesh = None

from pathlib import Path
from functools import wraps

MODELS = Path("/models")


def check_pymesh(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not pymesh:
            raise RuntimeError("PyMesh library is not installed!")
        return func(*args, **kwargs)

    return wrapper


@check_pymesh
def load_mesh(path: Path) -> "threedframe.lib.PyMesh.python.Mesh.Mesh":
    mesh = pymesh.load_mesh(str(path))
    mesh, _ = pymesh.remove_duplicated_faces(mesh)
    mesh, _ = pymesh.remove_duplicated_vertices(mesh)
    mesh.add_attribute("face_area")
    mesh.add_attribute("face_normal")
    mesh.add_attribute("face_centroid")
    mesh.add_attribute("vertex_normal")
    mesh.enable_connectivity()
    return mesh


@check_pymesh
def inspect_core(core_path: Path, joint_path: Path, out_path=None):
    core_mesh = load_mesh(core_path)
    joint_mesh = load_mesh(joint_path)

    core_vertices = set([tuple(v) for v in core_mesh.vertices.tolist()])
    joint_vertices = set([tuple(v) for v in joint_mesh.vertices.tolist()])

    common_verts = core_vertices & joint_vertices
    print("Intersecting Vertices:", common_verts)

    face_areas = core_mesh.get_attribute("face_area").tolist()
    face_norms = core_mesh.get_face_attribute("face_normal").tolist()

    adj_face_areas = []

    for vert in common_verts:
        vidx = core_mesh.vertices.tolist().index(list(vert))
        adj_faces = core_mesh.get_vertex_adjacent_faces(vidx).tolist()
        for fidx in adj_faces:
            farea = face_areas[fidx]
            adj_face_areas.append((fidx, farea))

    print("Adjacent Face Areas:", adj_face_areas)
    max_face_idx, max_face_area = max(adj_face_areas, key=lambda k: k[1])

    print("Maximum face area:", max_face_idx, max_face_area)

    max_face_normal = face_norms[max_face_idx]
    max_face_vert_idxs = core_mesh.faces[max_face_idx]
    max_face_verts = [tuple(core_mesh.vertices[vx]) for vx in max_face_vert_idxs]

    print("Max face verts:", max_face_verts)
    print("Max face norm:", max_face_normal)
    return dict(
        face_verts=max_face_verts,
        face_norm=max_face_normal,
        common_verts=list(common_verts),
    )


@check_pymesh
def collect_verts(mesh_path: Path, out_path=None):
    mesh = load_mesh(mesh_path)
    face_norms = mesh.get_face_attribute("face_normal").tolist()
    verts_by_face = []
    norms_by_face = {}
    for fidx, face in enumerate(mesh.faces):
        fverts = [tuple(mesh.vertices[vi]) for vi in face]
        verts_by_face.append((fidx, fverts))
        norms_by_face[fidx] = face_norms[fidx]
    verts = [tuple(v) for v in mesh.vertices.tolist()]
    init_vert_adj_faces = mesh.get_vertex_adjacent_faces(0).tolist()
    first_face = mesh.faces[0]
    last_face = mesh.faces[-1]
    print(
        "First area:Last Area:",
        mesh.get_attribute("face_area")[0],
        mesh.get_attribute("face_area")[-1],
    )
    face_vertices = [tuple(mesh.vertices[vi]) for vi in first_face]
    last_vertices = [tuple(mesh.vertices[vi]) for vi in last_face]
    print("Face Vertices:", face_vertices)
    print("Init vert faces:", init_vert_adj_faces)
    print("Collected verts:", verts)
    print("Face areas:", mesh.get_attribute("face_area"))
    return dict(verts=face_vertices, verts_by_face=verts_by_face, norms_by_face=norms_by_face)


def iter_mesh_faces(mesh):
    face_norms = mesh.get_face_attribute("face_normal").tolist()
    face_areas = mesh.get_face_attribute("face_area").tolist()
    face_centroids = mesh.get_face_attribute("face_centroid").tolist()
    for fidx, face in enumerate(mesh.faces):
        normal = face_norms[fidx]
        area = face_areas[fidx]
        centroid = face_centroids[fidx]
        yield dict(
            fidx=fidx, vertex_indices=face.tolist(), normal=normal, area=area[0], centroid=centroid
        )


def iter_mesh_vertices(mesh):
    vertex_norms = mesh.get_vertex_attribute("vertex_normal").tolist()
    for vidx, vertex in enumerate(mesh.vertices):
        vert = tuple(vertex)
        vert_normal = vertex_norms[vidx]
        yield dict(vidx=vidx, point=vert, normal=vert_normal)


@check_pymesh
def analyze_mesh(mesh_path: Path, out_path=None):
    mesh = load_mesh(mesh_path)

    mesh_data = dict(faces=list(iter_mesh_faces(mesh)), vertices=list(iter_mesh_vertices(mesh)))
    return mesh_data
