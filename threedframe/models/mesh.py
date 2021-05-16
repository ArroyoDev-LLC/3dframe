"""3dframe mesh models."""

import itertools
from typing import List, Tuple, Optional

import sympy as S
from solid import OpenSCADObject, union
from euclid3 import Point3, Vector3
from pydantic import Field, BaseModel
from pydantic.fields import PrivateAttr

from threedframe import mesh as meshutil
from threedframe.utils import (
    TemporaryScadWorkspace,
    find_center_of_gravity,
    find_missing_rect_vertex,
)


class MeshPoint(BaseModel):
    """Mesh Point."""

    # Vertex Index.
    vidx: int
    # 3D Coordinate of point.
    point: Tuple[float, float, float]
    # Point normal.
    normal: Optional[Tuple[float, float, float]]
    # Parent Mesh Data.
    _parent: Optional["MeshData"] = PrivateAttr(default=None)

    @property
    def faces(self) -> List["MeshFace"]:
        return [f for f in self._parent.faces if self.vidx in f.vertex_indices]

    @property
    def as_euclid(self) -> Point3:
        return Point3(*self.point)

    @property
    def as_sympy(self) -> S.Point3D:
        return S.Point3D(*self.point)

    @property
    def as_vector(self) -> Vector3:
        return Vector3(*self.point)

    @property
    def normal_vector(self) -> Vector3:
        return Vector3(*self.normal)


class MeshFace(BaseModel):
    """Mesh Face."""

    # Face Index.
    fidx: int
    # Vertices that makeup face.
    vertex_indices: List[int]
    # Face normal.
    normal: Optional[Tuple[float, float, float]]
    # Face area.
    area: float
    # Vector representing face centroids.
    centroid: Optional[Tuple[float, float, float]]
    # Parent Mesh Data.
    _parent: Optional["MeshData"] = PrivateAttr(default=None)

    @property
    def vertices(self) -> List[MeshPoint]:
        return [v for v in self._parent.vertices if v.vidx in self.vertex_indices]

    @property
    def sympy_vertices(self) -> List[S.Point3D]:
        return [p.as_sympy for p in self.vertices]

    @property
    def euclid_vertices(self) -> List[Point3]:
        return [p.as_euclid for p in self.vertices]

    @property
    def as_sympy_plane(self) -> S.Plane:
        return S.Plane(*self.sympy_vertices, normal_vector=self.normal)

    @property
    def missing_rect_vertex(self) -> S.Point3D:
        points_perms = itertools.permutations(self.sympy_vertices, 3)
        least_dist = None
        least_dist_point = None
        for perm in points_perms:
            midp = find_missing_rect_vertex(*perm)
            dist = self.centroid_point.distance(midp)
            if least_dist is None or least_dist > dist:
                least_dist = dist
                least_dist_point = midp
        return least_dist_point

    @property
    def midpoint_by_canberra(self) -> S.Point3D:
        fp_1 = self.vertices[0].as_sympy
        fp_2 = max(self.sympy_vertices, key=lambda p: fp_1.canberra_distance(p))
        return fp_1.midpoint(fp_2)

    @property
    def normal_vector(self) -> Vector3:
        return Vector3(*self.normal)

    @property
    def centroid_point(self) -> S.Point3D:
        return S.Point3D(*self.centroid)


class MeshData(BaseModel):
    """Mesh Analysis Data."""

    # Vertices of mesh.
    vertices: List[MeshPoint]
    # Faces of mesh.
    faces: List[MeshFace]

    def __init__(self, **data):
        super().__init__(**data)
        for vert in self.vertices:
            vert._parent = self
        for face in self.faces:
            face._parent = self

    @classmethod
    def from_dict(cls, data):
        vertices = data.get("vertices", [])
        faces = data.get("faces", [])
        verts = [MeshPoint(**v) for v in vertices]
        fces = [MeshFace(**f) for f in faces]
        return cls(vertices=verts, faces=fces)

    def calc_absolute_midpoint(self):
        face_mps = []
        for face in self.faces:
            face_mps.append(find_center_of_gravity(*face.sympy_vertices, face.missing_rect_vertex))
        return find_center_of_gravity(*face_mps)


def analyze_scad(obj: OpenSCADObject) -> "MeshData":
    scad_obj = [("target", union()(obj), "stl")]
    with TemporaryScadWorkspace(scad_objs=scad_obj) as tmpdata:
        tmp_path, tmp_files = tmpdata
        data = meshutil.analyze_mesh(tmp_files[0][-1])
        return MeshData.from_dict(data)
