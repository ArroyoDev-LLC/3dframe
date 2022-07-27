"""Gathers all vectors + angels from blender model."""
import os
from math import pi, atan2
from pprint import pprint
from typing import Dict
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector, Quaternion

from threedframe.models import ModelData, ModelEdge, ModelVertex

UP = Vector((0, 0, 1))


def edge_angle(e1, e2, face_normal):
    # Corner of 2 edges -> middle vert
    b = set(e1.verts).intersection(e2.verts).pop()
    # make b a 'new origin'
    a = e1.other_vert(b).co - b.co
    c = e2.other_vert(b).co - b.co
    a.negate()
    print(a, b, c)
    # axis of rotation normal to plane
    axis = a.cross(c).normalized()
    if axis.length < 1e-5:
        return pi, None  # inline vert

    if axis.dot(face_normal) < 0:
        axis.negate()
    quat: Quaternion = axis.rotation_difference(UP)
    M = quat.to_matrix().to_4x4()

    a = (M @ a).xy.normalized()
    c = (M @ c).xy.normalized()
    return pi - atan2(a.cross(c), a.dot(c))


obj_data = bpy.context.active_object.data
vertex_map: Dict[int, list] = {}

bm = bmesh.from_edit_mesh(obj_data)
bm.verts.ensure_lookup_table()
bm.edges.ensure_lookup_table()


vertices = {}
for vert in bm.verts:
    # Treat this vector as our new 'origin'
    rel_origin = vert.co
    vertex_map.setdefault(vert.index, list())
    joint_edges = []
    for edge in vert.link_edges:
        # Other vertex this edge is connected too.
        other_vert = edge.other_vert(vert)
        # Vector FROM other vertex coming INTO joint.
        relative_vector: Vector = other_vert.co - rel_origin

        edge_length = edge.calc_length()

        # TODO: use bpy.context.scene.unit_settings to be dynamic.
        # assuming scene is using imperial w/ LENGTH set to inches
        edge_length_mm = edge_length * 25.4

        edge_info = ModelEdge(
            eidx=edge.index,
            length=edge_length_mm,
            joint_vidx=vert.index,
            target_vidx=other_vert.index,
            vector_ingress=(
                relative_vector.x,
                relative_vector.y,
                relative_vector.z,
            ),
        )
        # Map of joint-side edges -> target vertices.
        joint_edges.append(edge_info)
        vertex_map[vert.index].append(
            (
                edge.index,
                edge_length_mm,
                (relative_vector.x, relative_vector.y, relative_vector.z),
            )
        )
    vert_normal = vert.normal
    vertex_info = ModelVertex(
        vidx=vert.index,
        edges=joint_edges,
        point=(
            vert.co.x,
            vert.co.y,
            vert.co.z,
        ),
        point_normal=(
            vert_normal.x,
            vert_normal.y,
            vert_normal.z,
        ),
    )
    vertices[vert.index] = vertex_info

model_info = ModelData(num_edges=len(bm.edges), num_vertices=len(bm.verts), vertices=vertices)

pprint(model_info)

data_out = Path(os.getenv("THREEDFRAME_OUT"))

print(f"Computed: {model_info.num_edges} edges | {model_info.num_vertices} vertices")

model_info_ser = model_info.json()
data_out.write_text(model_info_ser)
