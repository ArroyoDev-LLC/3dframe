import attr
import solid as sp
from solid import utils as sputils

from threedframe.config import config
from threedframe.scad.interfaces import FixtureMeta


@attr.s(auto_attribs=True)
class Fixture(FixtureMeta):
    def create_base(self) -> sp.OpenSCADObject:
        return sp.square(config.FIXTURE_SIZE, center=True)

    def do_extrude(self, obj: sp.OpenSCADObject):
        obj = config.dotSCAD.hollow_out.hollow_out(shell_thickness=3)(obj)
        obj = sp.linear_extrude(self.params.extrusion_height)(obj)
        return obj

    def do_transform(self, obj: sp.OpenSCADObject):
        obj = sputils.transform_to_point(
            obj, dest_point=self.params.midpoint, dest_normal=self.params.vector_from_origin
        )
        return obj


@attr.s(auto_attribs=True)
class SolidFixture(Fixture):
    def do_extrude(self, obj: sp.OpenSCADObject):
        obj = sp.linear_extrude(self.params.extrusion_height)(obj)
        return obj
