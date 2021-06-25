from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Type, Union, Optional, Sequence
from pathlib import Path
from multiprocessing import Pool

import attr
import psutil
from loguru import logger
from pydantic import BaseModel, validator, parse_file_as
from codetiming import Timer

from threedframe import utils
from threedframe.models import ModelData, ModelVertex
from threedframe.scad.joint import Joint

from ..config import config

if TYPE_CHECKING:
    from .interfaces import CoreMeta, JointMeta, LabelMeta, FixtureMeta


class RenderFileType(str, Enum):
    STL = "stl"
    PNG = "png"

    @property
    def _scad_args(self):
        return {
            RenderFileType.STL: ["--export-format=binstl"],
            RenderFileType.PNG: ["--autocenter", "--viewall", "--render=full", "--projection=p"],
        }

    @property
    def scad_args(self):
        return self._scad_args[self]


class JointDirectorParams(BaseModel):
    joint_builder: Optional[Type["JointMeta"]] = Joint
    fixture_builder: Optional[Type["FixtureMeta"]] = None
    fixture_label_builder: Optional[Type["LabelMeta"]] = None
    core_builder: Optional[Type["CoreMeta"]] = None
    core_label_builder: Optional[Type["LabelMeta"]] = None

    vertices: Optional[Sequence[int]] = None
    render: bool = False
    render_file_type: Optional[RenderFileType] = RenderFileType.STL
    model: Union[Path, "ModelData"]
    overwrite: bool = False

    @staticmethod
    def _resolve_edge_relations(
        model: "ModelData", vertices: Dict[int, "ModelVertex"]
    ) -> "ModelData":
        _vertices = {}
        for vidx, vertex in vertices.items():
            edges = []
            for edge in vertex.edges:
                if vidx == edge.joint_vidx:
                    target = model.get_edge_target_vertex(edge)
                    logger.info(
                        "mapped vertex[{}] -> edge[{}] -> vertex[{}]", vidx, edge.eidx, target.vidx
                    )
                    edges.append(edge.copy(update=dict(joint_vertex=vertex, target_vertex=target)))
            _vertices[vidx] = vertex.copy(update=dict(edges=edges))
        return model.copy(update=dict(vertices=_vertices))

    @validator("model")
    def validate_model_data(cls, v: Union[Path, "ModelData"], values: Dict[str, Any]) -> ModelData:
        if isinstance(v, Path):
            v: ModelData = parse_file_as(ModelData, v)
        verts = values["vertices"]
        if verts is not None:
            # scoped vertices down to requested by params.
            _new_verts = {k: v for k, v in v.vertices.items() if k in verts}
            v = cls._resolve_edge_relations(v, _new_verts)
        return v


@attr.s(auto_attribs=True)
class JointDirector:
    params: JointDirectorParams

    @property
    def builder_params(self) -> Dict[str, Any]:
        _build_params = self.params.dict(
            exclude={"model", "vertices", "joint_builder", "render", "render_file_type"},
            exclude_none=True,
            exclude_unset=True,
        )
        return _build_params

    @logger.catch(reraise=True)
    def build_joint(self, vertex: "ModelVertex") -> Optional["JointMeta"]:
        scad_path = self.get_joint_file_path(vertex.vidx)
        if not self.params.overwrite and scad_path.exists() and self.params.render:
            logger.warning(f"Joint for vertex: {vertex.vidx} already exists, skipping to render...")
            return self.render_joint(scad_path)
        logger.info("Building joint for vertex: {}", vertex.vidx)
        joint = self.params.joint_builder(
            vertex=vertex,
            **self.builder_params,
        )
        joint.assemble()
        self.write_joint(joint)
        return joint

    def get_joint_file_path(self, vidx: int) -> Path:
        file_name = f"joint-v{vidx}.scad"
        out_path = config.RENDERS_DIR / file_name
        return out_path

    def write_joint(self, joint: "JointMeta"):
        out_path = self.get_joint_file_path(joint.vertex.vidx)
        utils.write_scad(joint.scad_object, out_path, segments=config.SEGMENTS)
        if self.params.render:
            self.render_joint(out_path)

    def render_joint(self, scad_path: Path):
        out_path = scad_path.with_suffix(f".{self.params.render_file_type}")
        logger.success("Writing mesh -> {}", out_path)
        proc = utils.openscad_cmd(
            *self.params.render_file_type.scad_args, "-o", str(out_path), str(scad_path)
        )
        for line in iter(proc.stderr.readline, b""):
            outline = line.decode().rstrip("\n")
            logger.debug("[OpenSCAD]: {}", outline)

    @Timer(logger=logger.success)
    def assemble(self):
        logger.info("Constructing joint objects for {} vertices.", len(self.params.model.vertices))
        logger.debug("Director builders: {}", self.builder_params)
        verts = self.params.model.vertices.values()
        for vert in verts:
            self.build_joint(vert)


class ParallelJointDirector(JointDirector):
    @Timer(logger=logger.success)
    def assemble(self):
        logger.info("Constructing joint objects for {} vertices.", len(self.params.model.vertices))
        logger.debug("Director builders: {}", self.builder_params)
        workers = psutil.cpu_count()
        verts = self.params.model.vertices.values()
        with Pool(processes=workers) as pool:
            list(pool.imap_unordered(self.build_joint, verts))
