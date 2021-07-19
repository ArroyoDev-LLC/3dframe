"""3dframe model models."""
import string
import itertools
from typing import Dict, List, Tuple, Iterator, Optional

from pydantic import Field, BaseModel, validator


class ModelEdge(BaseModel):
    """Computed edge info."""

    # Edge index.
    eidx: int
    # Edge length.
    length: float
    # Joint vertex index.
    joint_vidx: int
    joint_vertex: Optional["ModelVertex"]
    # Target vertex index.
    target_vidx: int
    target_vertex: Optional["ModelVertex"]
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
    label: Optional[str] = Field(default_factory=lambda: next(MODEL_LABELS))

    @validator("label")
    def validate_label(cls, v: str):
        if not v or not isinstance(v, str):
            return next(MODEL_LABELS)
        return v

    def __hash__(self):
        return hash(self.vidx)

    def __eq__(self, other):
        return self.vidx == other.vidx


def label_generator() -> Iterator[str]:
    """Generates labels for vertices.

    Yields: 'AA', 'AB', 'AC'...'ZW', 'ZY', 'ZZ'

    """
    for group_label, item_label in itertools.cycle(
        itertools.product(string.ascii_uppercase, repeat=2)
    ):
        yield f"{group_label}{item_label}"


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

    def get_vidx_by_label(self, label: str) -> Optional[int]:
        """Resolve vertex index by label.

        Args:
            label: alpha label of vertex.

        Returns:
            Vertex index if found. None otherwise.

        """
        vert = next((v for v in self.vertices.values() if v.label.lower() == label.lower()), None)
        if vert:
            return vert.vidx


ModelVertex.update_forward_refs()
ModelEdge.update_forward_refs()
MODEL_LABELS = label_generator()
