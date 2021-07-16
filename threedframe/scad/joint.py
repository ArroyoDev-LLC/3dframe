from typing import TYPE_CHECKING, List, Type, Iterator

import attr
import solid as sp
from loguru import logger

from threedframe.models.mesh import analyze_scad
from threedframe.scad.interfaces import JointMeta, LabelMeta

from .core import Core
from .label import CoreLabel, FixtureLabel
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

    def get_sibling_fixtures(
        self, fixture: "FixtureMeta", fixtures: Optional[List["FixtureMeta"]] = None
    ) -> List["FixtureMeta"]:
        """Retrieve list of fixtures that are sibling to the given."""
        group = fixtures or self.fixtures
        if not group or not self.has_fixtures:
            raise RuntimeError("Fixtures have not been computed yet!")
        return [f for f in group if f.name != fixture.name]

    def find_overlapping_fixtures(
        self, source: "FixtureMeta", fixtures: List["FixtureMeta"]
    ) -> Iterator["FixtureMeta"]:
        """Locate and yield fixtures that overlap with `source.`"""
        others = [f for f in fixtures if f.params.label != source.params.label]
        for other in others:
            angle_bet = source.params.angle_between(other.params)
            logger.info(
                "fixture angle between: [{}] <-> [{}] @ {}", source.name, other.name, angle_bet
            )
            if angle_bet <= 30:
                logger.warning(
                    "fixture [{}] overlaps with [{}] @ {} deg.", source.name, other.name, angle_bet
                )
                yield other

    def construct_fixtures(self) -> Iterator["FixtureMeta"]:
        params = self.build_fixture_params()
        fixtures = [
            self.fixture_builder(params=p, label_builder=self.fixture_label_builder) for p in params
        ]
        for fixture in fixtures:
            overlaps = list(self.find_overlapping_fixtures(fixture, fixtures))
            if any(overlaps):
                siblings_by_height = sorted([fixture, *overlaps], key=lambda f: f.extrusion_height)
                constraining_fixture = siblings_by_height[0]
                logger.warning(
                    "[{}] overlap adjustment made (height {} -> {})",
                    fixture.name,
                    fixture.extrusion_height,
                    constraining_fixture.extrusion_height,
                )
                fixture.extrusion_height = constraining_fixture.extrusion_height
            yield fixture

    def build_fixtures(self) -> "Joint":
        for fix in self.construct_fixtures():
            fix.assemble()
            self.fixtures.append(fix)
        return self

    def construct_fixture_mesh(self) -> Iterator["SolidFixture"]:
        for fix in self.fixtures:
            solid_fix = SolidFixture(params=fix.params)
            solid_fix.extrusion_height = fix.extrusion_height
            yield solid_fix

    def build_fixture_meshes(self) -> "Joint":
        for solid_fix in self.construct_fixture_mesh():
            solid_fix.assemble()
            self.solid_fixtures.append(solid_fix)
        for fix in self.fixtures:
            other_solids = self.get_sibling_fixtures(fix, fixtures=self.solid_fixtures)
            fix.scad_object -= [of.scad_object for of in other_solids]
        return self

    def analyze_fixture_meshes(self) -> "Joint":
        for solid_fix in self.solid_fixtures:
            mesh_analysis = analyze_scad(solid_fix.scad_object)
            self.meshes[solid_fix.params.label] = mesh_analysis
        return self

    def build_core(self) -> "Joint":
        core = self.core_builder(fixtures=self.fixtures, meshes=self.meshes)
        core.assemble()
        # ensure core-facing joint is hollowed out.
        for solid_fix in self.solid_fixtures:
            overlap = core.scad_object.copy() * solid_fix.scad_object.copy()
            core.scad_object -= overlap
        self.core = core
        return self

    def assemble(self):
        self.build_fixtures().build_fixture_meshes().analyze_fixture_meshes().build_core()
        self.scad_object = self.core.scad_object.copy() + [f.scad_object for f in self.fixtures]


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
        fix = next(self.construct_fixtures())
        fix.scad_object = fix.create_base()
        fix.scad_object = fix.do_extrude(fix.scad_object)
        trans_fix_scad = fix.do_transform(fix.scad_object.copy())
        self.scad_object = fix.scad_object + ~trans_fix_scad
