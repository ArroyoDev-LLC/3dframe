import math
from typing import TYPE_CHECKING, Any, Dict, List

import attr
import solid as sp
import sympy as S
import solid.utils as sutils
from loguru import logger
from euclid3 import Point3 as EucPoint3
from euclid3 import Vector3 as EucVector3
from pydantic import BaseModel

from threedframe import utils
from threedframe.config import config
from threedframe.scad.interfaces import LabelMeta

if TYPE_CHECKING:
    from ..models import MeshData, MeshFace
    from .interfaces import FixtureMeta


class LabelParams(BaseModel):
    content: str
    halign: str = "center"
    valign: str = "center"
    depth: float = 1.5
    size: float = config.label_size
    width: float = config.label_width
    center: bool = True


@attr.s(auto_attribs=True, kw_only=True)
class FixtureLabel(LabelMeta):
    fixtures: List["FixtureMeta"] = ...
    target: "FixtureMeta" = ...
    meshes: Dict[str, "MeshData"] = ...

    @property
    def target_mesh(self) -> "MeshData":
        return self.meshes[self.target.params.label]

    @property
    def smallest_face(self) -> "MeshFace":
        return min(self.target_mesh.faces, key=lambda f: f.area)

    @property
    def other_meshes(self) -> Dict[str, "MeshData"]:
        _meshes = {k: v for k, v in self.meshes.items() if k != self.target.params.label}
        return _meshes

    def find_clear_face(self) -> "MeshFace":
        nearest_origin_face = self.target_mesh.faces[0]
        other_centers = [m.absolute_midpoint for m in self.other_meshes.values()]
        current_optimal_face = nearest_origin_face
        for face in self.target_mesh.faces:
            gt_optimal = face.area > current_optimal_face.area
            # this filter prevents labels from ending up on the ends.
            gt_min_area = face.area > math.ceil(self.smallest_face.area)
            if gt_optimal and gt_min_area:
                # ensure the taxicab distance ( Σ{x-dist, y-dist} ) is at least a fixture away.
                other_boundaries = [
                    face.centroid_point.taxicab_distance(f) > config.fixture_size
                    for f in other_centers
                ]
                logger.info("Fixture label face boundary checks: {}", other_boundaries)
                if all(other_boundaries):
                    current_optimal_face = face
                    break
        return current_optimal_face

    def do_transform(self, obj: sp.OpenSCADObject) -> sp.OpenSCADObject:
        label_face = self.find_clear_face()

        # now that we have found an appropriate face, find the center of it to place the label.
        face_midpoint = utils.find_center_of_gravity(
            *label_face.sympy_vertices, label_face.missing_rect_vertex
        )
        logger.info("Fixture label face area: {}", label_face.area)
        face_midpoint = EucPoint3(*tuple(face_midpoint))
        obj = sutils.transform_to_point(
            obj,
            dest_point=face_midpoint,
            dest_normal=label_face.normal_vector.reflect(label_face.normal_vector),
            src_normal=self.target.params.vector_from_origin,
        )
        return obj


@attr.s(auto_attribs=True, kw_only=True)
class CoreLabel(LabelMeta):
    core_data: Dict[str, Any]

    def get_optimal_face_midpoint(self) -> S.Point:
        face_verts = self.core_data["face_verts"]
        face_verts = [S.Point(*v) for v in face_verts]
        face_midpoint = utils.find_center_of_gravity(*face_verts)
        return face_midpoint

    def do_transform(self, obj: sp.OpenSCADObject) -> sp.OpenSCADObject:
        face_midpoint = self.get_optimal_face_midpoint()
        face_midpoint = EucPoint3(*tuple(face_midpoint))
        face_norm = EucVector3(*self.core_data["face_norm"])
        obj = sutils.transform_to_point(
            obj, dest_point=face_midpoint, dest_normal=face_norm.reflect(face_norm)
        )
        return obj
