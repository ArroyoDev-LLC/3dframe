from typing import TYPE_CHECKING, Type, Tuple, Iterator

import attr
import solid as sp

from threedframe.models.mesh import MeshData, analyze_scad
from threedframe.scad.interfaces import JointMeta, LabelMeta

from .core import Core
from .label import LabelParams, FixtureLabel
from .fixture import Fixture, SolidFixture, FixtureParams

if TYPE_CHECKING:
    from .interfaces import CoreMeta, FixtureMeta


@attr.s(auto_attribs=True)
class Joint(JointMeta):
    fixture_builder: Type["FixtureMeta"] = Fixture
    fixture_label_builder: Type["LabelMeta"] = FixtureLabel
    core_builder: Type["CoreMeta"] = Core
    # core_label_builder: Type['LabelMeta'] = ...

    def build_fixture_params(self) -> Iterator[FixtureParams]:
        for edge in self.vertex.edges:
            params = FixtureParams(source_edge=edge, source_vertex=self.vertex)
            yield params

    def build_fixtures(self) -> Iterator["FixtureMeta"]:
        for params in self.build_fixture_params():
            fix = self.fixture_builder(params=params)
            fix.assemble()
            yield fix

    def build_fixture_meshes(self) -> Iterator[Tuple[str, "MeshData"]]:
        for fix in self.fixtures:
            solid_fix = SolidFixture(params=fix.params)
            solid_fix.assemble()
            yield fix.params.label, analyze_scad(solid_fix.scad_object)

    def build_labeled_fixtures(self) -> Iterator["FixtureMeta"]:
        for fixture in self.fixtures:
            label_params = LabelParams(content=fixture.params.label)
            label_obj = self.fixture_label_builder(
                params=label_params, fixtures=self.fixtures, target=fixture, meshes=self.meshes
            )
            label_obj.assemble()
            fixture.scad_object -= label_obj.scad_object
            yield fixture

    def build_core(self) -> "CoreMeta":
        core = self.core_builder(fixtures=self.fixtures, meshes=self.meshes)
        core.assemble()
        return core

    def assemble(self):
        self.fixtures = list(self.build_fixtures())
        self.meshes = {k: v for k, v in self.build_fixture_meshes()}
        self.core = self.build_core()
        self.fixtures = list(self.build_labeled_fixtures())
        scad_objects = [self.core.scad_object] + [f.scad_object for f in self.fixtures]
        self.scad_object = sp.union()(*scad_objects)
