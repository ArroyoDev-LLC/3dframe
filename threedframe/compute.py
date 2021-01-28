# -*- coding: utf-8 -*-

"""Gathers all vectors + angels from blender model."""
from typing import Tuple, Dict, Iterable, List, Optional
from pprint import pprint
import pickle
from enum import Enum
import pdb
import vg
from mathutils import Matrix, Vector, Quaternion, Euler
from pathlib import Path
from bpy import context
from math import degrees, atan2, pi
import bmesh
from bmesh.types import BMVert, BMEdge


import numpy as np
import bpy


class Direction(Enum):
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    BACK = "BACK"
    FORWARD = "FORWARD"
    UP = "UP"
    DOWN = "DOWN"


up = Vector((0, 0, 1))
forward = Vector((0, 1, 0))
right = Vector((1, 0, 0))


class PlanarVectors(Enum):
    FORWARD = (0, 1, 0)
    BACK = (0, -1, 0)
    LEFT = (-1, 0, 0)
    RIGHT = (1, 0, 0)
    UP = (0, 0, 1)
    DOWN = (0, 0, -1)

    # def as_vector(self):
    #     return Vector(self.value)
    #
    # @property
    # def x(self):
    #     return PlanarVectors.RIGHT.as_vector()
    #
    # @property
    # def y(self):
    #     return PlanarVectors.FORWARD.as_vector()
    #
    # @property
    # def z(self):
    #     return PlanarVectors.UP.as_vector()


def unit_vector(vector):
    """ Returns the unit vector of the vector.  """
    return vector / np.linalg.norm(vector)


def angle_between(v1, v2):
    """Returns the angle in radians between vectors 'v1' and 'v2'::

    >>> angle_between((1, 0, 0), (0, 1, 0))
    1.5707963267948966
    >>> angle_between((1, 0, 0), (1, 0, 0))
    0.0
    >>> angle_between((1, 0, 0), (-1, 0, 0))
    3.141592653589793
    """
    v1_u = unit_vector(v1)
    v2_u = unit_vector(v2)
    return np.arccos(np.clip(np.dot(v1_u, v2_u), -1.0, 1.0))


def serialize_vector(vec) -> Tuple[int, int, int]:
    """Turns Blender `Vector` object into a tuple for numpy processing."""
    print(vec)
    return vec.x, vec.y, vec.z


def angle_direction(v1, v2):
    offset_x = v1.x - v2.x
    offset_y = v1.y - v2.y
    offset_z = v1.z - v2.z

    max_offset = max([offset_x, offset_y, offset_z], key=lambda x: abs(x))
    print("max offset:", max_offset)

    if max_offset == offset_x:
        return Direction.RIGHT if offset_x < 0 else Direction.LEFT

    if max_offset == offset_y:
        return Direction.FORWARD if offset_x < 0 else Direction.BACK

    if max_offset == offset_z:
        return Direction.UP if offset_x < 0 else Direction.DOWN


def get_vertex(vidx):
    vert = obj_data.vertices[vidx]
    return vert, serialize_vector(vert.co)


def get_angle(quat, a, c):
    M = quat.invert().to_matrix().to_4x4()

    a = (M @ a).xy.normalized()
    c = (M @ c).xy.normalized()
    rads = pi - atan2(a.cross(c), a.dot(c))
    return rads


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
    # axis_r = axis.copy()
    # print(axis)
    quat: Quaternion = axis.rotation_difference(up)
    M = quat.to_matrix().to_4x4()

    a = (M @ a).xy.normalized()
    c = (M @ c).xy.normalized()
    return pi - atan2(a.cross(c), a.dot(c))


    # quat_for = axis.rotation_difference(forward)
    # quat_right = axis.rotation_difference(right)

    # rads_3 = []
    # for q in [quat, quat_for, quat_right]:
    #     rads_3.append(get_angle(q, a, c))

    # return tuple(rads_3)

    # mat = quat.copy().to_euler()

    # m = np.asmatrix(list(M))
    # return (
    #     pi - atan2(a.cross(c), a.dot(c)),
    #     # quat.to_axis_angle(),
    #     quat.copy().normalized().to_euler("XYZ").freeze(),
    # )


obj_data = bpy.data.objects["CyberTruck"].data
vertex_map: Dict[int, list] = {}

bm = bmesh.from_edit_mesh(obj_data)

for vert in bm.verts:
    rel_origin = vert.co
    vertex_map.setdefault(vert.index, list())
    for edge in vert.link_edges:
        other_vert = edge.other_vert(vert)
        relative_vector: Vector = other_vert.co - rel_origin
        vertex_map[vert.index].append((edge.index, edge.calc_length(), (relative_vector.x, relative_vector.y, relative_vector.z)))

# for f in bm.faces:
#     edges = f.edges[:]
#     print("Face", f.index, "Edges:", [e.index for e in edges])
#     edges.append(f.edges[0])
#     edge_map: Iterable[Tuple[BMEdge, BMEdge]] = zip(edges, edges[1:])
#
#     for e1, e2 in edge_map:
#         # verts: Iterable[BMVert] = set(e1.verts).intersection(e2.verts)
#         corner_vert = b = set(e1.verts).intersection(e2.verts).pop()
#         a = edge_angle(e1, e2, f.normal)
#         # if axis:
#         #     axis = serialize_vector(axis)
#
#         vertex_map.setdefault(corner_vert.index, list())
#         vertex_map[corner_vert.index].append((e1.index, e2.index, degrees(a), f.index))
        # print(verts)

        # for vert in e1.verts:
        # vertex_map.setdefault(vert.index, set())
        # vertex_map[vert.index].add(e1.index, degrees(angle))

        # for vert in verts:
        #     vertex_map.setdefault(vert.index, set())
        #     vertex_map[vert.index].add((e1.index, e2.index, degrees(angle), axis, e1.calc_length()))

# pprint(vertex_map)
# pprint(vertex_map[5])
# pprint(59)
# pprint(vertex_map[59])
# pprint(78)
# pprint(vertex_map[78])
pprint(vertex_map)
pprint(vertex_map[5])

# pprint('E105:')
# for key, entry in vertex_map.items():
#     for item in entry:
#         if item[0] == 105 or item[1] == 105:
#             pprint(key)
#             pprint(item)


ROOT = Path(__file__).parent
data_out = ROOT / "cyber_joints.pkl"

pickled = pickle.dumps(vertex_map)
data_out.write_bytes(pickled)


# for e in obj_data.edges:
#     add_vertex(e.vertices[0], e.vertices[1])
#     v1 = normalize_vector(obj_data.vertices[e.vertices[0]].co)
#     v2 = normalize_vector(obj_data.vertices[e.vertices[1]].co)
#     vec_indices = [e.vertices[0], e.vertices[1]]
#     angle_deg = np.rad2deg(angle_between(v1, v2))
#     print(f"E{e.index}: {e.vertices[0]} <--> {e.vertices[1]} @ {angle_deg}")
# print('Edge',e.index,'connects vertices',e.vertices[0],'and',e.vertices[1],'at angle:', np.rad2deg(angle_between(v1, v2)))


# for f in obj_data.polygons:
#     print('Face',f.index,'uses vertices', end=' ')
#     for fv in f.vertices:
#         print(fv, end=', ')

# pprint(vertex_map)
#
# # pprint(0)
# # pprint(vertex_map[0])
# # pprint(35)
# # pprint(vertex_map[35])
#
# pprint(0)
# pprint(vertex_map[0])
# pprint(1)
# pprint(vertex_map[1])
#
# pprint(5)
# pprint(vertex_map[5])
#
# vert1, vert1co = get_vertex(5)
# vert2, vert2co = get_vertex(2)
#
# v1_u = unit_vector(vert1co)
# v2_u = unit_vector(vert2co)
#
# v1_np = np.array(vert1co)
# v2_np = np.array(vert2co)
#
# print('Vert 1:', vert1co, v1_np)
# print('Vert 2:', vert2co, v2_np)
# print('VG Angle between:', vg.angle(np.array(vert1co), np.array([0, 1, 0])))
# print('VG Normalized Angle between:', vg.angle(np.array(v1_u), np.array(v2_u), assume_normalized=True, look=vg.basis.x))
# print('VG Signed Normalized Angle between:', vg.signed_angle(np.array(v1_u), np.array(v2_u), vg.basis.x))
# print('Angle Between:', angle_between(vert1co, vert2co))
