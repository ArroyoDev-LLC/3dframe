from typing import Optional

import attr
import solid.extensions.bosl2.std as bosl2

from threedframe.scad.interfaces import CoreMeta


@attr.s(auto_attribs=True)
class Core(CoreMeta):
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

    def assemble(self):
        self.scad_object = bosl2.hulling("fix_fillet")(*[f.scad_object for f in self.fixtures])
