from typing import TYPE_CHECKING, Any, Dict, List, Type, Tuple, Iterator

import attr
import solid as sp

from threedframe import mesh as meshutil
from threedframe import utils
from threedframe.models.mesh import MeshData, analyze_scad
from threedframe.scad.interfaces import JointMeta, LabelMeta

from .core import Core
from .label import CoreLabel, LabelParams, FixtureLabel
from .fixture import Fixture, SolidFixture, FixtureParams

if TYPE_CHECKING:
    from .interfaces import CoreMeta, FixtureMeta


@attr.s(auto_attribs=True)
class Joint(JointMeta):
    fixture_builder: Type["FixtureMeta"] = Fixture
    fixture_label_builder: Type["LabelMeta"] = FixtureLabel
    core_builder: Type["CoreMeta"] = Core
    core_label_builder: Type["LabelMeta"] = CoreLabel

    def build_fixture_params(self) -> Iterator[FixtureParams]:
        for edge in self.vertex.edges:
            params = FixtureParams(source_edge=edge, source_vertex=self.vertex)
            yield params

    def build_fixtures(self) -> Iterator["FixtureMeta"]:
        for params in self.build_fixture_params():
            fix = self.fixture_builder(params=params, label_builder=self.fixture_label_builder)
            fix.assemble()
            yield fix

    def build_fixture_meshes(self) -> Iterator[Tuple["FixtureMeta", "MeshData"]]:
        for fix in self.fixtures:
            solid_fix = SolidFixture(params=fix.params)
            solid_fix.assemble()
            yield solid_fix, analyze_scad(solid_fix.scad_object)

    def build_core(self) -> "CoreMeta":
        core = self.core_builder(fixtures=self.fixtures, meshes=self.meshes)
        core.assemble()
        # ensure core-facing joint is hollowed out.
        for solid_fix in self.solid_fixtures:
            overlap = core.scad_object.copy() * solid_fix.scad_object.copy()
            core.scad_object -= overlap
        return core

    def build_core_joint_mesh(self, solid_fixtures: List["FixtureMeta"]) -> Dict[str, Any]:
        inspect_core = self.core.scad_object.copy()
        inspect_solid_with_core = [self.core.scad_object.copy()] + [
            f.scad_object for f in solid_fixtures
        ]
        inspect_solid_with_core = sp.union()(*inspect_solid_with_core)
        scad_objs = [
            (
                "core",
                sp.union()(inspect_core),
                "stl",
            ),
            (
                "solid_joints",
                inspect_solid_with_core,
                "stl",
            ),
        ]
        with utils.TemporaryScadWorkspace(scad_objs=scad_objs) as tmpdata:
            tmp_path, tmp_files = tmpdata
            core_files = tmp_files[0]
            joint_files = tmp_files[1]
            data = meshutil.inspect_core(core_files[-1], joint_files[-1])
        return data

    def build_core_label(self, core_data: Dict[str, Any]) -> "CoreMeta":
        core_label_params = LabelParams(content=self.vertex.label)
        core_label = self.core_label_builder(params=core_label_params, core_data=core_data)
        core_label.assemble()
        self.core.scad_object -= core_label.scad_object
        return self.core

    def assemble(self):
        self.fixtures = list(self.build_fixtures())
        solid_fixture_meshes = list(self.build_fixture_meshes())
        self.solid_fixtures: List["FixtureMeta"] = [f[0] for f in solid_fixture_meshes]
        self.meshes = {k.params.label: v for k, v in solid_fixture_meshes}
        self.core = self.build_core()
        core_inspect_data = self.build_core_joint_mesh(self.solid_fixtures)
        self.core = self.build_core_label(core_inspect_data)
        scad_objects = [self.core.scad_object] + [f.scad_object for f in self.fixtures]
        self.scad_object = sp.union()(*scad_objects)


class JointCoreOnlyDebug(Joint):
    def assemble(self):
        super().assemble()
        self.scad_object = self.core.scad_object


class JointLabelDebug(Joint):
    def assemble(self):
        super().assemble()
        self.scad_object = sp.union()(*[~f.scad_object for f in self.fixtures])


class JointSingleFixtureDebug(JointLabelDebug):
    def build_fixture_params(self) -> Iterator[FixtureParams]:
        edge = self.vertex.edges[1]
        params = FixtureParams(source_edge=edge, source_vertex=self.vertex)
        yield params

    def assemble(self):
        self.fixtures = list(self.build_fixtures())
        self.scad_object = self.fixtures[0].scad_object
