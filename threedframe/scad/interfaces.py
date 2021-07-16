import abc
from typing import TYPE_CHECKING, Dict, List, Type, Iterator, Optional
from pathlib import Path

import attr
from euclid3 import Point3 as EucPoint3
from solid.core.object_base import OpenSCADObject

from threedframe import utils
from threedframe.config import config
from threedframe.constant import Constants

if TYPE_CHECKING:
    from .label import LabelParams
    from ..models import MeshData, ModelVertex
    from .fixture import FixtureParams


@attr.s(auto_attribs=True)
class ScadMeta(abc.ABC):
    scad_object: Optional[OpenSCADObject] = None

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Human friendly and per-joint unique name."""
        raise NotImplementedError

    @property
    def file_name(self) -> str:
        """Name of output file if rendered out."""
        return self.name

    def render_scad(self, path: Optional[Path] = None) -> Path:
        """Renders `OpenSCADObject` to scad file."""
        _path = path or config.RENDERS_DIR / f"{self.file_name}.scad"
        utils.write_scad(self.scad_object, _path, header=config.scad_header)
        return _path

    @abc.abstractmethod
    def assemble(self):
        raise NotImplementedError


@attr.s(auto_attribs=True)
class FixtureMeta(ScadMeta, abc.ABC):
    params: "FixtureParams" = ...

    _extrusion_height: Optional[float] = attr.ib(None, init=False)

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

    def distance_to(self, other: "FixtureMeta", at: Optional[float] = None) -> float:
        """Distance (in mm) from this to `other`.

        By default, utilizes the midpoint of the receiving end
        of each fixture.
        Alternatively, a distance can be specified with `at.`

        """
        _at = at or self.extrusion_height
        oth_at = at or other.extrusion_height
        return self.point_at_distance(_at).distance(other.point_at_distance(oth_at))

    def assemble(self):
        obj = self.create_base()
        obj = self.do_extrude(obj)
        obj = self.do_transform(obj)
        self.scad_object = obj


@attr.s(auto_attribs=True)
class CoreMeta(ScadMeta, abc.ABC):
    fixtures: List["FixtureMeta"] = ...

    @abc.abstractmethod
    def assemble(self):
        raise NotImplementedError


@attr.s(auto_attribs=True)
class LabelMeta(ScadMeta, abc.ABC):
    params: "LabelParams" = ...

    def create_base(self) -> OpenSCADObject:
        _params = self.params.dict()
        label = _params.pop("content")
        return utils.label_size(label, **_params)[0]

    @abc.abstractmethod
    def do_transform(self, obj: OpenSCADObject) -> OpenSCADObject:
        raise NotImplementedError

    def assemble(self):
        obj = self.create_base()
        obj = self.do_transform(obj)
        self.scad_object = obj


@attr.s(auto_attribs=True)
class JointMeta(ScadMeta, abc.ABC):
    meshes: Dict[str, "MeshData"] = attr.ib(init=False, default={})
    core: "CoreMeta" = attr.ib(init=False)
    fixtures: List["FixtureMeta"] = attr.ib(init=False, default=[])
    solid_fixtures: List["FixtureMeta"] = attr.ib(init=False, default=[])

    fixture_builder: Type["FixtureMeta"] = ...
    fixture_label_builder: Type["LabelMeta"] = ...
    core_builder: Type["CoreMeta"] = ...
    core_label_builder: Type["LabelMeta"] = ...

    vertex: "ModelVertex" = ...

    @property
    def name(self) -> str:
        return f"Joint[{self.vertex.label}]"

    @property
    def file_name(self) -> str:
        return f"joint-v{self.vertex.label}"

    @property
    def has_fixtures(self) -> bool:
        return any(self.fixtures)

    @property
    def has_solid_fixtures(self) -> bool:
        return any(self.solid_fixtures)

    @property
    def has_meshes(self) -> bool:
        return any(self.meshes)

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
