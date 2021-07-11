import attr
import solid.extensions.bosl2.std as bosl2

from threedframe.scad.interfaces import CoreMeta


@attr.s(auto_attribs=True)
class Core(CoreMeta):
    def assemble(self):
        self.scad_object = bosl2.hulling("fix_fillet")(*[f.scad_object for f in self.fixtures])
