from enum import IntEnum
from typing import TYPE_CHECKING, Any, Dict, Union

import attr
import solid as sp
import sympy as S
import solid.extensions.bosl2 as bosl2
import solid.extensions.legacy.utils as sutils
from euclid3 import Line3 as EucLine3
from euclid3 import Point3 as EucPoint3
from euclid3 import Vector3 as EucVector3
from pydantic import Field, BaseModel
from solid.core.object_base import OpenSCADObject

from threedframe import utils
from threedframe.config import config
from threedframe.scad.interfaces import LabelMeta, FixtureMeta

if TYPE_CHECKING:
    from pydantic.typing import DictStrAny


class LabelParams(BaseModel):
    content: str
    halign: str = "center"
    valign: str = "center"
    depth: float = 1.5
    size: float = Field(default_factory=lambda: config.label_size)
    char_width: float = Field(default_factory=lambda: config.label_char_width)
    center: bool = True

    @property
    def width(self):
        if len(self.content) <= 2:
            return self.char_width * len(self.content)
        return self.char_width * 2

    def dict(self, **kws) -> "DictStrAny":
        base_kws = dict(exclude={"char_width"})
        base_kws.update(kws)
        base = super().dict(**base_kws)
        base.setdefault("width", self.width)
        return base


class FixtureLabelPosition(IntEnum):
    ORIGIN = 0
    CENTER = 1
    TAIL = 2


class FixtureLabelParams(LabelParams):
    target: FixtureMeta = ...
    position: FixtureLabelPosition = FixtureLabelPosition.ORIGIN

    class Config:
        arbitrary_types_allowed = True

    @property
    def tag(self) -> str:
        return self.target.params.labels_tag


@attr.s(auto_attribs=True, kw_only=True)
class FixtureLabel(LabelMeta):
    params: FixtureLabelParams

    @property
    def name(self):
        return f"Label[{self.params.target.name}]"

    def create_base(self) -> OpenSCADObject:
        return bosl2.text3d(
            self.params.content,
            size=self.params.size,
            anchor=bosl2.CENTER,
            h=1.5 / 2,
            font="OpenSans:style=ExtraBold",
            _tags=self.params.tag,
        )

    def do_transform(self, obj: OpenSCADObject) -> OpenSCADObject:
        res = sp.resize(self.params.width, 0, 1.5 / 2)
        return res(obj)


@attr.s(auto_attribs=True, kw_only=True)
class CoreLabel(LabelMeta):
    core_data: Dict[str, Any]

    @property
    def name(self):
        return "CoreLabel"

    def get_optimal_face_midpoint(self) -> S.Point:
        face_verts = self.core_data["face_verts"]
        face_verts = [S.Point(*v) for v in face_verts]
        face_midpoint = utils.find_center_of_gravity(*face_verts)
        return face_midpoint

    def do_transform(
        self, obj: sp.core.object_base.OpenSCADObject
    ) -> sp.core.object_base.OpenSCADObject:
        face_midpoint = self.get_optimal_face_midpoint()
        face_midpoint = EucPoint3(*tuple(face_midpoint))
        face_norm = EucVector3(*self.core_data["face_norm"])
        obj = sutils.transform_to_point(
            obj, dest_point=face_midpoint, dest_normal=face_norm.reflect(face_norm)
        )
        return obj


class FixtureLabelDebugArrows(FixtureLabel):
    def create_arrow(
        self, euc_line: Union[EucVector3, EucLine3], color: str, rad: int = 5
    ) -> sp.core.object_base.OpenSCADObject:
        if not self.params.destination_point:
            raise RuntimeError("No destination point available!")
        return sp.translate(self.params.destination_point)(
            sutils.draw_segment(euc_line, endless=True, arrow_rad=rad, vec_color=color)
        )

    def do_transform(
        self, obj: sp.core.object_base.OpenSCADObject
    ) -> sp.core.object_base.OpenSCADObject:
        obj = super().do_transform(obj)
        colors = utils.rand_color_generator()
        axis = self.params.target.params.direction_to_origin.cross(
            -self.params.target_face.normal_vector
        )
        obj += self.create_arrow(axis, color=next(colors))
        obj += self.create_arrow(self.params.target_face.normal_vector, color=next(colors), rad=3)
        return obj
