from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import attr
import numpy as np
import solid
import solid.extensions.bosl2 as bosl2

from threedframe.utils import distance3d
from threedframe.scad.interfaces import CoreMeta, scad_timer

if TYPE_CHECKING:
    import numpy as np
    import open3d as o3d


@attr.s(auto_attribs=True)
class Core(CoreMeta):
    verts: list[float] = attr.ib(default=[])

    @property
    def source_label(self) -> Optional[str]:
        if any(self.fixtures):
            return self.fixtures[0].params.source_label

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
        for fixture in self.fixtures:
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


@attr.s(auto_attribs=True)
class CoreDebugVertices(Core):
    def assemble(self):
        super().assemble()
        self.scad_object += bosl2.move_copies(self.verts)(solid.color("red")(solid.sphere(1)))
