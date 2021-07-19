from typing import TYPE_CHECKING, List, Type, Iterator, Optional

import attr
import solid as sp
import sympy as S
import solid.extensions.bosl2.std as bosl2
from loguru import logger

from threedframe import utils
from threedframe.config import config
from threedframe.scad.interfaces import JointMeta, LabelMeta

from .core import Core
from .label import CoreLabel, FixtureLabel
from .fixture import Fixture, FixtureParams

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
        self, fixture: "Fixture", fixtures: Optional[List["Fixture"]] = None
    ) -> List["Fixture"]:
        """Retrieve list of fixtures that are sibling to the given."""
        group = fixtures or self.fixtures
        if group is None and not self.has_fixtures:
            raise RuntimeError("Fixtures have not been computed yet!")
        return [f for f in group if f.name != fixture.name]

    @Timer(name="build>compute_fixture_meshes", logger=logger.trace)
    def compute_fixture_meshes(
        self, fixtures: List["Fixture"]
    ) -> List[Tuple[str, utils.SerializableMesh, FixtureMeshType]]:
        tasks = []
        for f in fixtures:
            tasks += [(f, FixtureMeshType.HOLE), (f, FixtureMeshType.SHELL)]
        with Pool() as pool:
            _fixtures = list(pool.starmap(Fixture.serialize_mesh, tasks))
        return _fixtures

    @Timer(name="build>find_fixture_intersections", logger=logger.trace)
    def find_fixture_intersections(self, fixtures: List["Fixture"]) -> Dict[str, Set]:
        # Set of other fixtures that intersect K's support hole..
        fixtures_states: Dict[str, Set] = dict()

        for fa, fb in itertools.combinations(fixtures, r=2):
            fixtures_states.setdefault(fa.name, set())
            fixtures_states.setdefault(fb.name, set())
            if fa.does_intersect_other_support(fb):
                fixtures_states[fb.name].add(fa.name)
            if fb.does_intersect_other_support(fa):
                fixtures_states[fa.name].add(fb.name)
        logger.trace("fixture intersect states: {}", fixtures_states)
        return fixtures_states

    def construct_fixtures(self) -> List["FixtureMeta"]:
        params = self.build_fixture_params()
        fixtures = [
            self.fixture_builder(params=p, label_builder=self.fixture_label_builder) for p in params
        ]

        # precompute meshes in parallel for time.
        meshes = self.compute_fixture_meshes(fixtures)
        for fname, mesh, mesh_type in meshes:
            fix = next((f for f in fixtures if f.name == fname))
            fix.meshes[mesh_type] = mesh.to_open3d(do_compute=True)

        _fixtures: Dict[str, "Fixture"] = {f.name: f for f in fixtures}
        _fixtures_names = set(list(_fixtures.keys()))
        init_intersections = self.find_fixture_intersections(list(_fixtures.values()))
        _intersecting_fixtures = [_fixtures[k] for k, v in init_intersections.items() if any(v)]
        logger.warning("intersecting fixtures: {}", [f.name for f in _intersecting_fixtures])

        while True:
            intersections = self.find_fixture_intersections(_intersecting_fixtures)
            inter_by_all = [any(ib) for ib in intersections.values()]
            logger.warning("remaining intersections: {} {}", intersections, inter_by_all)
            if not any(inter_by_all):
                break
            for fname, intersected_by in intersections.items():
                fix = _fixtures[fname]
                if any(intersected_by):
                    logger.warning("[{}] intersected by: {}", fix.name, intersected_by)
                    fix.extend_fixture_base(1)
                    _fixtures[fix.name] = fix

        return list(_fixtures.values())

    def build_fixtures(self) -> "Joint":
        for fix in self.construct_fixtures():
            logger.info("building [{}]", fix.name)
            fix.assemble()
            self.fixtures.append(fix)
        return self

    def build_core(self) -> "Joint":
        core = self.core_builder(fixtures=self.fixtures)
        core.assemble()
        self.core = core
        return self

    def assemble(self):
        self.build_fixtures().build_core()
        self.scad_object = self.core.scad_object.copy() + [f.scad_object for f in self.fixtures]
        # ensure we cleanup any potential overlapped corners and such.
        self.scad_object = bosl2.diff("fixture_hole", "fixture_base")(self.scad_object)


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
            self.scad_object += sp.color(c=f_color, alpha=0.4)(fix.scad_object)
