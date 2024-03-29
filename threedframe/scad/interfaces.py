from __future__ import annotations

import abc
from typing import TYPE_CHECKING, List, Type, TypeVar, Callable, Iterator, Optional
from pathlib import Path

import attrs
import open3d as o3d
from loguru import logger
from euclid3 import Point3 as EucPoint3
from pydantic import BaseModel
from codetiming import Timer
from typing_extensions import ParamSpec
from solid.core.object_base import OpenSCADObject

from threedframe import utils
from threedframe.config import config
from threedframe.constant import Constants

if TYPE_CHECKING:
    from .label import LabelParams
    from ..models import ModelVertex
    from .fixture import FixtureTag, FixtureParams

T = TypeVar("T")
P = ParamSpec("P")


def scad_timer(f: Callable[P, T]) -> Callable[P, T]:
    def inner(*args: P.args, **kwargs: P.kwargs) -> T:
        inst = args[0]
        if not isinstance(inst, ScadMeta):
            raise TypeError("First argument must be a typeof ScadMeta.")
        cls_name = inst.__class__.__name__.lower()
        f_name = f.__name__
        timer = Timer(name=f"build>{cls_name}>{f_name}", logger=logger.trace)
        timer.start()
        result = f(*args, **kwargs)
        timer.stop()
        return result

    return inner


@attrs.define
class ScadMeta(abc.ABC):
    scad_object: Optional[OpenSCADObject] = attrs.field(default=None, init=False, repr=False)

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Human friendly and per-joint unique name."""
        raise NotImplementedError

    @property
    def file_name(self) -> str:
        """Name of output file if rendered out."""
        return self.name

    @scad_timer
    def render_scad(self, path: Optional[Path] = None) -> Path:
        """Renders `OpenSCADObject` to scad file."""
        _path = path or config.RENDERS_DIR / f"{self.file_name}.scad"
        utils.write_scad(self.scad_object, _path, header=config.scad_header)
        return _path

    @scad_timer
    def compute_mesh(self, obj: Optional[OpenSCADObject] = None) -> o3d.geometry.TriangleMesh:
        """Compute o3d triangle mesh from given scad object."""
        with utils.TemporaryScadWorkspace() as renderer:
            renderer.add_scad(obj or self.scad_object, name="mesh")
            renderer.render()
            mesh: o3d.geometry.TriangleMesh = o3d.io.read_triangle_mesh(
                str(renderer.renders["mesh"])
            )
            mesh.compute_vertex_normals()
            mesh.compute_triangle_normals()
            mesh.remove_duplicated_vertices()
            return mesh

    @abc.abstractmethod
    def assemble(self):
        raise NotImplementedError


@attrs.define
class FixtureMeta(ScadMeta, abc.ABC):
    params: "FixtureParams" = attrs.field(repr=False)

    _extrusion_height: Optional[float] = attrs.field(default=None, init=False)

    @property
    def extrusion_height(self) -> float:
        """Allow override of extrusion height."""
        if self._extrusion_height:
            return self._extrusion_height
        return self.params.extrusion_height

    @extrusion_height.setter
    def extrusion_height(self, value: float):
        self._extrusion_height = value

    @property
    def name(self) -> str:
        return f"{self.params.source_label}@{self.params.target_label}"

    @property
    def file_name(self) -> str:
        return "-".join([self.params.source_label, self.params.target_label])

    @abc.abstractmethod
    def create_base(self) -> OpenSCADObject:
        raise NotImplementedError

    @abc.abstractmethod
    def do_extrude(self, obj: OpenSCADObject) -> OpenSCADObject:
        raise NotImplementedError

    @abc.abstractmethod
    def do_transform(self, obj: OpenSCADObject) -> OpenSCADObject:
        raise NotImplementedError

    @property
    def hole_length(self) -> float:
        """Resulting length of empty space in fixture for support."""
        return self.params.extrusion_height - config.fixture_shell_thickness

    @property
    def support_endpoint(self) -> EucPoint3:
        """Actual point of the fixture-support meeting wall."""
        return self.point_at_distance(self.extrusion_height - self.hole_length)

    @property
    def target_face_endpoint(self) -> EucPoint3:
        """Actual point at the tip of the fixture."""
        return self.point_at_distance(self.extrusion_height)

    @property
    def final_edge_offset(self) -> float:
        """Offset from midpoint to support-fixture wall."""
        return self.params.midpoint.distance(self.support_endpoint)

    @property
    def final_edge_length(self) -> float:
        """Final support/edge cut length."""
        return self.params.adjusted_edge_length - self.final_edge_offset

    @property
    def final_edge_length_label(self) -> str:
        """Final support/edge length label."""
        length_in = self.final_edge_length / Constants.INCH
        val = str(round(length_in, 1))
        return val.rstrip(".0")

    def point_at_distance(self, dist: float) -> EucPoint3:
        """Point along fixture axis `dist` away from fixture midpoint."""
        a: EucPoint3 = self.params.midpoint.copy()
        b: EucPoint3 = self.params.midpoint.copy()
        # b is maximum distance away fixture could be.
        b.set_length(self.params.max_avail_extrusion_height)
        v = a + (dist * (b - a).normalized())
        return EucPoint3(*v.as_arr())

    def copy(self, **kws):
        return self.__class__(params=self.params, **kws)

    def distance_to(self, other: "FixtureMeta", at: Optional[float] = None) -> float:
        """Distance (in mm) from this to `other`.

        By default, utilizes the midpoint of the receiving end
        of each fixture.
        Alternatively, a distance can be specified with `at.`

        """
        _at = at or self.extrusion_height
        oth_at = at or other.extrusion_height
        return self.point_at_distance(_at).distance(other.point_at_distance(oth_at))

    @scad_timer
    def assemble(self):
        obj = self.create_base()
        obj = self.do_extrude(obj)
        obj = self.do_transform(obj)
        self.scad_object = obj


class CoreParametersBase(BaseModel, abc.ABC):
    fixtures: list["FixtureMeta"]

    class Config:
        arbitrary_types_allowed = True

    @property
    @abc.abstractmethod
    def fixture_tags(self) -> dict[FixtureTag, str]:
        ...


@attrs.define
class CoreMeta(ScadMeta, abc.ABC):
    params: CoreParametersBase

    @abc.abstractmethod
    def assemble(self):
        raise NotImplementedError


@attrs.define
class LabelMeta(ScadMeta, abc.ABC):
    params: "LabelParams" = attrs.field(repr=False)

    def create_base(self) -> OpenSCADObject:
        _params = self.params.dict()
        label = _params.pop("content")
        return utils.label_size(label, **_params)[0]

    @abc.abstractmethod
    def do_transform(self, obj: OpenSCADObject) -> OpenSCADObject:
        raise NotImplementedError

    @scad_timer
    def assemble(self):
        obj = self.create_base()
        obj = self.do_transform(obj)
        self.scad_object = obj


class JointParamsMeta(BaseModel, abc.ABC):
    vertex: "ModelVertex"

    class Config:
        arbitrary_types_allowed = True


@attrs.define
class JointMeta(ScadMeta, abc.ABC):
    core: "CoreMeta" = attrs.field(init=False)
    fixtures: List["FixtureMeta"] = attrs.field(init=False, default=[])
    solid_fixtures: List["FixtureMeta"] = attrs.field(init=False, default=[])

    params: JointParamsMeta

    @property
    def vertex(self) -> "ModelVertex":
        """Backwards compat."""
        return self.params.vertex

    @property
    def name(self) -> str:
        return f"Joint[{self.vertex.label}]"

    @property
    def file_name(self) -> str:
        return f"joint-{self.vertex.label}"

    @property
    def has_fixtures(self) -> bool:
        return any(self.fixtures)

    @property
    def has_solid_fixtures(self) -> bool:
        return any(self.solid_fixtures)

    @abc.abstractmethod
    def build_fixture_params(self) -> Iterator["FixtureParams"]:
        raise NotImplementedError

    @abc.abstractmethod
    def construct_fixtures(self) -> Iterator[FixtureMeta]:
        raise NotImplementedError

    @abc.abstractmethod
    def build_fixtures(self) -> Type["JointMeta"]:
        raise NotImplementedError

    @abc.abstractmethod
    def build_core(self) -> "CoreMeta":
        raise NotImplementedError
