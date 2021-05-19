"""3dframe joint models."""

from typing import Dict, Tuple, Optional

from solid import OpenSCADObject
from pydantic import BaseModel

from threedframe.models.mesh import MeshData, analyze_scad
from threedframe.models.model import ModelEdge, ModelVertex


class JointFixture(BaseModel):
    """Joint Fixture item."""

    # OpenSCAD Object.
    scad_object: OpenSCADObject
    # OpenSCAD inspection object (no hollow).
    inspect_object: OpenSCADObject
    # Inner fixture Object (the inner shell).
    inner_object: OpenSCADObject
    # Edge item of fixture.
    model_edge: ModelEdge  # Vertex item of fixture.
    model_vertex: ModelVertex
    # Destination point of fixture.
    dest_point: Tuple[float, float, float]
    # Destination normal of fixture.
    dest_normal: Tuple[float, float, float]
    # Inspect data (deprecated)
    inspect_data: Dict
    # Mesh Data of inspect object.
    inspect_mesh: Optional[MeshData] = None

    class Config:
        arbitrary_types_allowed = True

    def analyze(self):
        self.inspect_mesh = analyze_scad(self.inspect_object)
