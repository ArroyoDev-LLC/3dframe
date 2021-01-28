# -*- coding: utf-8 -*-

"""Gathers all vectors + angels from blender model."""
import os
import pickle
from math import atan2, pi
from pathlib import Path
from pprint import pprint
from typing import Dict

import bmesh
import bpy
from mathutils import Quaternion, Vector

from threedframe.utils import ModelInfo

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


obj_data = bpy.data.objects["CyberTruck"].data
vertex_map: Dict[int, list] = {}

bm = bmesh.from_edit_mesh(obj_data)
bm.verts.ensure_lookup_table()
bm.edges.ensure_lookup_table()

model_info = ModelInfo(num_edges=len(bm.edges), num_vertices=len(bm.verts))

for vert in bm.verts:
    rel_origin = vert.co
    vertex_map.setdefault(vert.index, list())
    for edge in vert.link_edges:
        other_vert = edge.other_vert(vert)
        relative_vector: Vector = other_vert.co - rel_origin
        vertex_map[vert.index].append(
            (
                edge.index,
                edge.calc_length(),
                (relative_vector.x, relative_vector.y, relative_vector.z),
            )
        )

pprint(vertex_map)
pprint(vertex_map[5])

model_data_map = {"info": model_info, "data": vertex_map}

data_out = Path(os.getenv("THREEDFRAME_OUT"))

print(f"Computed: {model_info.num_edges} edges | {model_info.num_vertices} vertices")

pickled = pickle.dumps(model_data_map)
data_out.write_bytes(pickled)
