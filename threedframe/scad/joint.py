from __future__ import annotations

import os
import time
import itertools
from typing import Set, Dict, List, Type, Iterator, Optional
from functools import partial
from multiprocessing import Pool

import attrs
import solid as sp
from loguru import logger

from threedframe import utils
from threedframe.models import ModelVertex
from threedframe.scad.core import CoreParams, CoreContext
from threedframe.scad.context import Context, BuildFlag
from threedframe.scad.fixture import (
    Fixture,
    FixtureMesh,
    FixtureParams,
    FixtureContext,
    FixtureMeshType,
)
from threedframe.scad.interfaces import JointMeta, FixtureMeta, JointParamsMeta, scad_timer


@attrs.define
class JointContext(Context["JointParams"]):
    context: Context
    strategy: Type[JointMeta]

    fixture_context: FixtureContext = attrs.field(default=None)
    core_context: CoreContext = attrs.field(default=None)

    @property
    def flags(self) -> BuildFlag:
        return self.context.flags

    @classmethod
    def from_build_context(cls, ctx: Context) -> JointContext:
        strategy = Joint
        child_ctx = cls(context=ctx, strategy=strategy)
        fixture_ctx = FixtureContext.from_build_context(child_ctx)
        core_ctx = CoreContext.from_build_context(child_ctx)
        child_ctx.fixture_context = fixture_ctx
        child_ctx.core_context = core_ctx
        return child_ctx

    def build_strategy(self, params: JointParams) -> JointMeta:
        inst = self.strategy(params, context=self)
        return inst

    def assemble(self, params: JointParams) -> JointMeta:
        inst = self.build_strategy(params)
        inst.assemble()
        return inst


class JointParams(JointParamsMeta):
    vertex: ModelVertex


@attrs.define
class Joint(JointMeta):
    context: JointContext

    def build_fixture_params(self) -> Iterator[FixtureParams]:
        for edge in self.params.vertex.edges:
            params = FixtureParams(source_edge=edge, source_vertex=self.params.vertex)
            yield params

    @scad_timer
    def get_sibling_fixtures(
        self, fixture: "Fixture", fixtures: Optional[List["Fixture"]] = None
    ) -> List["Fixture"]:
        """Retrieve list of fixtures that are sibling to the given."""
        group = fixtures or self.fixtures
        if group is None and not self.has_fixtures:
            raise RuntimeError("Fixtures have not been computed yet!")
        return [f for f in group if f.name != fixture.name]

    @scad_timer
    def compute_fixture_meshes(
        self, fixtures: List["Fixture"], *mesh_types: FixtureMeshType
    ) -> Dict[str, FixtureMeta]:
        fixtures_by_name = {f.name: f for f in fixtures}
        proc_count = min(len(fixtures) * 2, os.cpu_count() or 4)
        logger.info("using {} processes for mesh pool.", proc_count)
        with Pool(processes=proc_count, maxtasksperchild=1) as pool:
            tasks = []

            def on_mesh(fixture_name: str, mesh_result: FixtureMesh):
                """collect task results and store by fixture name."""
                logger.info("recieved mesh result: {}", mesh_result)
                o3d_mesh = mesh_result.mesh.to_open3d(do_compute=True)
                fixtures_by_name[fixture_name].meshes[mesh_result.mesh_type] = o3d_mesh

            for fix in fixtures:
                tasks += [
                    pool.apply_async(
                        self.context.fixture_context.serialize_mesh,
                        (fix, mt),
                        callback=partial(on_mesh, fix.name),
                        error_callback=logger.error,
                    )
                    for mt in mesh_types
                ]

            while True:
                time.sleep(0.5)
                readies = [t for t in tasks if t.ready()]
                logger.info(readies)
                logger.info(f"{len(readies)}/{len(tasks)} tasks complete.")
                if all([t.ready() for t in tasks]):
                    logger.success("done")
                    break

        return fixtures_by_name

    @scad_timer
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

    @scad_timer
    def construct_fixtures(self) -> List["FixtureMeta"]:
        params = self.build_fixture_params()
        fixtures = [self.context.fixture_context.build_strategy(params=p) for p in params]

        # precompute meshes in parallel for time.
        fixtures_by_name = self.compute_fixture_meshes(
            fixtures, FixtureMeshType.HOLE, FixtureMeshType.SHELL
        )
        fixtures = list(fixtures_by_name.values())

        _fixtures = fixtures_by_name
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
        core_params = CoreParams(fixtures=self.fixtures)
        self.core = self.context.core_context.assemble(core_params)
        return self

    @scad_timer
    def assemble(self):
        self.build_fixtures().build_core()
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
        fix = next(iter(self.construct_fixtures()))
        fix.scad_object = fix.create_base()
        fix.scad_object = fix.do_extrude(fix.scad_object)
        trans_fix_scad = fix.do_transform(fix.scad_object.copy())
        self.scad_object = fix.scad_object + ~trans_fix_scad


class JointFixturesOnly(Joint):
    def assemble(self):
        self.build_fixtures().build_core()
        color_gen = utils.rand_color_generator()
        f_color = next(color_gen)
        self.scad_object = sp.color(c=f_color, alpha=0.4)(self.fixtures[0].scad_object)
        for fix in self.fixtures[1:]:
            f_color = next(color_gen)
            self.scad_object += sp.color(c=f_color, alpha=0.4)(fix.scad_object)
