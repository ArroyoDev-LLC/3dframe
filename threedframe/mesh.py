#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""3dframe pymesh interactions."""

import pymesh  # noqa
import json
import sys
from pathlib import Path

MODELS = Path("/models")


def load_mesh(path: Path) -> "threedframe.lib.PyMesh.python.Mesh.Mesh":
    mesh = pymesh.load_mesh(str(path))
    mesh.add_attribute("face_area")
    mesh.add_attribute("face_normal")
    mesh.enable_connectivity()
    return mesh


def inspect_core(core_path: Path, joint_path: Path, out_path: Path):
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

    out_path.write_text(
        json.dumps(
            dict(
                face_verts=max_face_verts,
                face_norm=max_face_normal,
                common_verts=list(common_verts),
            )
        )
    )
    print("Done!")


def collect_verts(mesh_path: Path, out_path: Path):
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
    out_path.write_text(
        json.dumps(
            dict(verts=face_vertices, verts_by_face=verts_by_face, norms_by_face=norms_by_face)
        )
    )


if __name__ == "__main__":
    CMD = sys.argv[1]
    if CMD == "inspect_core":
        core_path = MODELS / sys.argv[2].strip()
        joint_path = MODELS / sys.argv[3].strip()
        out_path = MODELS / sys.argv[4].strip()
        inspect_core(core_path, joint_path, out_path)

    if CMD == "collect_verts":
        mesh_path = MODELS / sys.argv[2].strip()
        out_path = MODELS / sys.argv[3].strip()
        collect_verts(mesh_path, out_path)
