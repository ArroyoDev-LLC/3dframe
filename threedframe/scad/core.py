from __future__ import annotations

from typing import TYPE_CHECKING, Type, Optional

import attrs
import numpy as np
import solid
import solid.extensions.bosl2 as bosl2
from boltons.dictutils import OMD

from threedframe.utils import distance3d
from threedframe.scad.label import LabelContext
from threedframe.scad.context import Context, BuildFlag
from threedframe.scad.interfaces import CoreMeta, CoreParametersBase, scad_timer

if TYPE_CHECKING:
    import numpy as np
    import open3d as o3d

    from threedframe.scad.interfaces import FixtureTag


@attrs.define
class CoreContext(Context[CoreParametersBase]):
    context: Context
    strategy: Type[CoreMeta]

    label_context: LabelContext = attrs.field(default=None)

    @property
    def flags(self) -> BuildFlag:
        return self.context.flags ^ BuildFlag.FIXTURE_LABEL

    @classmethod
    def from_build_context(cls, ctx: Context):
        strategy = Core
        child_ctx = cls(context=ctx, strategy=strategy)
        label_ctx = LabelContext.from_build_context(child_ctx)
        child_ctx.label_context = label_ctx
        return child_ctx

    def build_strategy(self, params: CoreParams) -> CoreMeta:
        inst = self.strategy(params=params, context=self)
        return inst

    def assemble(self, params: CoreParams) -> CoreMeta:
        strategy = self.build_strategy(params)
        strategy.assemble()
        return strategy


class CoreParams(CoreParametersBase):
    @property
    def fixture_tags(self) -> OMD[FixtureTag, str]:
        tags = OMD()
        for fixture in self.fixtures:
            tags.update_extend(fixture.params.tags)
        return tags


@attrs.define
class Core(CoreMeta):
    context: CoreContext
    params: CoreParams

    verts: list[float] = attrs.field(factory=list)

    @property
    def source_label(self) -> Optional[str]:
        if any(self.params.fixtures):
            return self.params.fixtures[0].params.source_label
        return None

    @property
    def name(self) -> str:
        source = self.source_label or "?"
        return f"Core[{source}]"

    @property
    def file_name(self) -> str:
        source = self.source_label or "?"
        return f"core-{source}"

    @scad_timer
    def assemble(self):
        origin = (0, 0, 0)
        # TODO: cleanup, optimize, and get rid of assertion.
        for fixture in self.params.fixtures:
            base_mesh: "o3d.geometry.TriangleMesh" = fixture.base_mesh
            base_mesh.remove_duplicated_vertices()
            min_bound, max_bound = base_mesh.get_min_bound(), base_mesh.get_max_bound()
            min_dist = distance3d(origin, min_bound)
            max_dist = distance3d(origin, max_bound)
            verts = np.asarray(base_mesh.vertices)
            inner_verts = []
            for v in verts.tolist():
                v_dist = distance3d(origin, v)
                if (round(v_dist) - round(min_dist)) < (round(max_dist) - round(v_dist)):
                    inner_verts.append(tuple(v))

            assert len(inner_verts) == 4
            self.verts.extend(inner_verts)
        self.scad_object = solid.polyhedron(self.verts, bosl2.hull3d_faces(self.verts))


@attrs.define
class CoreDebugVertices(Core):
    def assemble(self):
        super().assemble()
        self.scad_object += bosl2.move_copies(self.verts)(solid.color("red")(solid.sphere(1)))
