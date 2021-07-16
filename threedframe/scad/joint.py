from typing import TYPE_CHECKING, List, Type, Iterator, Optional

import attr
import solid as sp
import sympy as S
import solid.extensions.legacy.utils as sutils
from loguru import logger

from threedframe import utils
from threedframe.config import config
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
        if group is None and not self.has_fixtures:
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
        processed = set()
        for fixture in fixtures:
            if processed.issuperset({fixture.name}):
                continue

            overlaps = list(self.find_overlapping_fixtures(fixture, fixtures))
            if not any(overlaps):
                yield fixture
                continue

            # check for variance in extrusion heights.
            ext_heights = {
                *[
                    f.extrusion_height
                    for f in (
                        fixture,
                        *overlaps,
                    )
                ]
            }
            if len(ext_heights) >= 2:
                siblings_by_height = sorted([fixture, *overlaps], key=lambda f: f.extrusion_height)
                constraining_fixture = siblings_by_height[0]
                logger.warning(
                    "[{}] constrained overlap adjustment made (height {} -> {})",
                    fixture.name,
                    fixture.extrusion_height,
                    constraining_fixture.extrusion_height,
                )
                fixture.extrusion_height = constraining_fixture.extrusion_height
                yield fixture
                continue

            # shortest -> longest
            siblings_by_edge_length = sorted(
                [fixture, *overlaps], key=lambda f: f.params.adjusted_edge_length
            )
            shortest_fixture = next(
                iter(self.get_sibling_fixtures(fixture, siblings_by_edge_length))
            )

            # Min clearance between fixture end-faces with a small buffer.
            minimum_clearance = config.fixture_size - config.fixture_shell_thickness * 1.15

            # Two points rep. the minimum and max height and resulting clearance distance.
            p1 = S.Point(
                fixture.extrusion_height, minimum_clearance - fixture.distance_to(shortest_fixture)
            )
            p2 = S.Point(
                shortest_fixture.params.max_avail_extrusion_height,
                minimum_clearance
                - shortest_fixture.distance_to(
                    fixture, at=shortest_fixture.params.max_avail_extrusion_height
                ),
            )

            # Create an eq. in terms height and the resulting clearance.
            slope = (p2.y - p1.y) / (p2.x - p1.x)
            x = S.symbols("x")
            f_height_to_clearance = (slope * x) + fixture.extrusion_height
            # Now solve for the minimum clearance.
            optimal_height = float(S.solve(S.Eq(minimum_clearance, f_height_to_clearance))[0])

            for adjusted in siblings_by_edge_length:
                logger.warning(
                    "[{}] overlap lengthen adjustment made (height {} -> {})",
                    adjusted.name,
                    adjusted.extrusion_height,
                    optimal_height,
                )
                adjusted.extrusion_height = optimal_height
                processed.add(adjusted.name)
                yield adjusted

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


class JointFixturesOnly(Joint):
    def assemble(self):
        self.build_fixtures()
        color_gen = utils.rand_color_generator()
        f_color = next(color_gen)
        self.scad_object = sp.color(c=f_color, alpha=0.4)(self.fixtures[0].scad_object)
        for fix in self.fixtures[1:]:
            f_color = next(color_gen)
            mp = fix.support_endpoint
            sph = sp.sphere(3)
            self.scad_object += sp.color(c=f_color, alpha=0.4)(fix.scad_object)
            self.scad_object += sp.color(c=f_color, alpha=0.6)(
                sutils.transform_to_point(
                    sph, dest_point=mp, dest_normal=fix.params.vector_from_origin
                )
            )
