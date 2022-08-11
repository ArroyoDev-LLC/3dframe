from typing import Any

import attrs
import solid as sp

from threedframe.scad.interfaces import ScadMeta


@attrs.define
class NoOpScad(ScadMeta):
    context: Any = attrs.field(default=None)
    params: Any = attrs.field(default=None)

    @property
    def name(self):
        return "NOOP"

    def assemble(self):
        self.scad_object = sp.union()
