"""3dframe model models."""
import string
from typing import Dict, List, Tuple, Iterator

from pydantic import Field, BaseModel


class ModelEdge(BaseModel):
    """Computed edge info."""

    # Edge index.
    eidx: int
    # Edge length.
    length: float
    # Joint vertex index.
    joint_vidx: int
    # Target vertex index.
    target_vidx: int
    # Vector FROM target vertex into joint.
    vector_ingress: Tuple[float, float, float]

    @property
    def length_in(self) -> float:
        """Length in inches."""
        return self.length / 25.4


class ModelVertex(BaseModel):
    """Computed Vertex info."""

    # Vertex index.
    vidx: int
    # Edge map.
    edges: List[ModelEdge]
    # Vertex Point.
    point: Tuple[float, float, float]
    # Vertex Point normal.
    point_normal: Tuple[float, float, float]
    # Generated label for vertex.
    label: str = Field(default_factory=lambda: next(MODEL_LABELS))


def label_generator() -> Iterator[str]:
    """Generates labels for vertices.

    Yields: 'AA', 'AB', 'AC'...'ZW', 'ZY', 'ZZ'

    """
    base_charmap = iter(string.ascii_uppercase)
    _label_charmap = iter(string.ascii_uppercase)
    _base_label = None
    while True:
        if not _base_label:
            _base_label = next(base_charmap)
        try:
            label = next(_label_charmap)
        except StopIteration:
            try:
                _base_label = next(base_charmap)
            except StopIteration:
                break
            _label_charmap = iter(string.ascii_uppercase)
            label = next(_label_charmap)
        yield f"{_base_label}{label}"


class ModelData(BaseModel):
    """Computed model info."""

    # Total number of vertices in model.
    num_vertices: int
    # Total number of edges in model.
    num_edges: int
    # Vertices.
    vertices: Dict[int, ModelVertex]

    def get_edge_target_vertex(self, edge: "ModelEdge") -> "ModelVertex":
        """Retrieve an edges target vertex."""
        vertex = self.vertices[edge.target_vidx]
        return vertex


MODEL_LABELS = label_generator()
