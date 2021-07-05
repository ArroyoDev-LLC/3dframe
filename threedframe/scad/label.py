import math
from enum import IntEnum
from typing import TYPE_CHECKING, Any, Dict, List, Tuple, Union, Optional
from functools import cached_property

import attr
import solid as sp
import sympy as S
import solid.utils as sutils
from loguru import logger
from euclid3 import Line3 as EucLine3
from euclid3 import Point3 as EucPoint3
from euclid3 import Vector3 as EucVector3
from pydantic import Field, BaseModel, PrivateAttr

from threedframe import utils
from threedframe.config import config
from threedframe.scad.interfaces import LabelMeta

from ..models import MeshData, MeshFace
from .interfaces import FixtureMeta

if TYPE_CHECKING:
    from pydantic.typing import DictStrAny


class LabelParams(BaseModel):
    content: Union[str, Tuple[str, str, str]]
    halign: str = "center"
    valign: str = "center"
    depth: float = 1.5
    size: float = Field(default_factory=lambda: config.label_size)
    width: float = Field(default_factory=lambda: config.label_width)
    center: bool = True


class FixtureLabelPosition(IntEnum):
    ORIGIN = 0
    CENTER = 1
    TAIL = 2


class FixtureLabelParams(LabelParams):
    fixtures: List[FixtureMeta] = ...
    target: FixtureMeta = ...
    meshes: Dict[str, MeshData] = ...
    position: FixtureLabelPosition = FixtureLabelPosition.ORIGIN

    _midpoint: Optional[S.Point] = PrivateAttr(default=None)
    _target_face: Optional[MeshFace] = PrivateAttr(default=None)

    class Config:
        keep_untouched = (cached_property,)
        arbitrary_types_allowed = True

    def dict(self, **kws) -> "DictStrAny":
        base_kws = dict(exclude={"fixtures", "target", "meshes", "position"})
        base_kws.update(kws)
        return super().dict(**base_kws)

    @property
    def target_label(self) -> str:
        return self.target.params.target_vertex.label

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

    @property
    def label_init_point(self) -> EucPoint3:
        """Label starting coordinates."""
        return EucPoint3(0, config.label_size, 0)

    @property
    def midpoint_euc(self) -> Optional[EucPoint3]:
        return utils.euclidify(self.midpoint) if self.midpoint else None

    @property
    def destination_offset(self) -> Optional[EucPoint3]:
        """Point offset to translate label right 'under the skin' of the fixture."""
        coords = [-config.fixture_shell_thickness / 4] * 3
        if self.target_face:
            return EucPoint3(*coords) * self.target_face.normal_vector
        return None

    @property
    def destination_point(self) -> Optional[EucPoint3]:
        if self.target_face and self.destination_offset:
            return self.midpoint_euc.copy() + self.destination_offset.copy()

    @property
    def midpoint(self) -> Optional[S.Point3D]:
        if not self._midpoint and self.target_face is not None:
            # now that we have found an appropriate face, find the center of it to place the label.
            self._midpoint = utils.find_center_of_gravity(
                *self.target_face.sympy_vertices, self.target_face.missing_rect_vertex
            )
        return self._midpoint

    @property
    def target_face(self) -> Optional["MeshFace"]:
        if not self._target_face:
            self._target_face = self.find_clear_face()
        return self._target_face

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


@attr.s(auto_attribs=True, kw_only=True)
class FixtureLabel(LabelMeta):
    params: FixtureLabelParams = ...

    def do_transform(self, obj: sp.OpenSCADObject) -> sp.OpenSCADObject:
        logger.debug(
            "Translating label from face midpoint {} to destination {}.",
            self.params.midpoint_euc,
            self.params.destination_point,
        )

        trans_params = dict(
            dest_point=self.params.destination_point,
            dest_normal=-self.params.target_face.normal_vector,
            src_up=self.params.target_face.normal_vector,
            src_point=self.params.label_init_point,
        )
        logger.info(
            "[{sl}@{tl}] Transforming to ({dest_point}) w/ normal @ ({dest_normal} | rnd: {dest_normal_rnd})",
            sl=self.params.target.params.source_vertex.label,
            tl=self.params.target_label,
            **trans_params,
            dest_normal_rnd=self.params.target_face.rounded_normal_vector.copy(),
        )
        logger.debug(
            {
                **trans_params,
                "direction_to_origin": self.params.target.params.direction_to_origin,
            }
        )
        obj = sutils.transform_to_point(obj, **trans_params)

        if -self.params.target_face.normal_vector == sutils.UP_VEC:
            obj = utils.rotate_about_pt(obj, -90, 0, self.params.destination_point)
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


class FixtureLabelDebug(FixtureLabel):
    def create_arrow(
        self, euc_line: Union[EucVector3, EucLine3], color: str, rad: int = 5
    ) -> sp.OpenSCADObject:
        if not self.params.destination_point:
            raise RuntimeError("No destination point available!")
        return sp.translate(self.params.destination_point)(
            sutils.draw_segment(euc_line, endless=True, arrow_rad=rad, vec_color=color)
        )

    def do_transform(self, obj: sp.OpenSCADObject) -> sp.OpenSCADObject:
        obj = super().do_transform(obj)
        colors = utils.rand_color_generator()
        axis = self.params.target.params.direction_to_origin.cross(
            -self.params.target_face.normal_vector
        )
        obj += self.create_arrow(axis, color=next(colors))
        obj += self.create_arrow(self.params.target_face.normal_vector, color=next(colors), rad=3)
        return obj
