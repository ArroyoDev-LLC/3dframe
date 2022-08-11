from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Type, Union, TypeVar, Optional, Sequence
from pathlib import Path
from multiprocessing import Pool

import attrs
import open3d as o3d
import psutil
from loguru import logger
from pydantic import BaseModel, validator
from codetiming import Timer

from threedframe import utils
from threedframe.config import config
from threedframe.models import ModelData, ModelVertex
from threedframe.constant import RenderFileType
from threedframe.scad.joint import JointParams, JointContext
from threedframe.scad.context import Context, BuildFlag

if TYPE_CHECKING:
    from .interfaces import ScadMeta, JointMeta

ModelT = TypeVar("ModelT", Path, ModelData)
ScadT = TypeVar("ScadT", bound="ScadMeta")


@attrs.define
class DirectorContext:
    context: Context
    strategy: Type[JointDirector]

    joint_context: Context = attrs.field(default=None)

    @property
    def flags(self) -> BuildFlag:
        return self.context.flags

    @classmethod
    def from_build_context(cls, ctx: Context) -> DirectorContext:
        strategy = JointDirector
        child_ctx = cls(context=ctx, strategy=strategy)
        joint_ctx = JointContext.from_build_context(child_ctx)
        child_ctx.joint_context = joint_ctx
        return child_ctx

    def build_strategy(self, params: JointDirectorParams) -> JointDirector:
        inst = self.strategy(params=params, context=self)
        return inst

    def assemble(self, params: JointDirectorParams) -> JointDirector:
        inst = self.build_strategy(params)
        inst.assemble()
        return inst


class JointDirectorParams(BaseModel):
    vertices: Optional[Sequence[Union[int, str]]] = None
    render: bool = False
    render_file_type: Optional[RenderFileType] = RenderFileType.STL
    model: ModelData
    overwrite: bool = False

    @classmethod
    def from_model_path(cls, path: Path, **kwargs) -> JointDirectorParams:
        model = ModelData.from_source(path)
        return cls(model=model, **kwargs)

    @staticmethod
    @Timer("build>resolve_edge_relations", logger=logger.trace)
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

    @validator("model", always=True)
    def validate_model_data(cls, v: Union[Path, "ModelData"], values: Dict[str, Any]) -> ModelData:
        v = ModelData.from_source(v)
        verts = values["vertices"]
        resolve_verts = v.vertices
        if verts is not None:
            _verts = []
            for vl in verts:
                if not str(vl).isnumeric():
                    _verts.append(v.get_vidx_by_label(vl))
                else:
                    _verts.append(int(vl))
            # scoped vertices down to requested by params.
            resolve_verts = {k: v for k, v in v.vertices.items() if k in _verts}
        v = cls._resolve_edge_relations(v, resolve_verts)
        return v


@attrs.define
class JointDirector:
    context: DirectorContext
    params: JointDirectorParams
    joints: Dict["ModelVertex", "JointMeta"] = attrs.field(factory=dict)
    scad_paths: Dict["ModelVertex", Path] = attrs.field(factory=dict)
    render_paths: Dict["ModelVertex", Path] = attrs.field(factory=dict)

    def vertex_by_idx_or_label(self, v: Union[int, str]) -> "ModelVertex":
        """Resolve vertex obj from vidx or label."""
        vidx = self.params.model.get_vidx_by_label(v)
        vidx = vidx if vidx is not None else int(vidx)
        return self.params.model.vertices[vidx]

    def create_joint(self, vertex: Union[int, "ModelVertex"]) -> "JointMeta":
        """Create joint object to be assembled."""
        vert = vertex if isinstance(vertex, ModelVertex) else self.params.model.vertices[vertex]
        joint_params = JointParams(vertex=vert)
        self.joints[vert] = self.context.joint_context.assemble(joint_params)
        return self.joints[vert]

    @Timer("build>joint", logger=logger.success)
    @logger.catch(reraise=True)
    def build_joint(self, vertex: "ModelVertex") -> Optional["JointMeta"]:
        logger.info("Building joint for vertex: {}", vertex.vidx)
        joint = self.create_joint(vertex=vertex)
        joint.assemble()
        self.write_joint(joint)
        return joint

    @Timer("build>write joint", logger=logger.success)
    def write_joint(self, joint: "JointMeta"):
        out_path = config.RENDERS_DIR / f"{joint.file_name}.scad"
        utils.write_scad(joint.scad_object, out_path, header=config.scad_header)
        self.scad_paths[joint.vertex] = out_path
        if self.params.render:
            return self.render_joint(joint)

    @Timer("build>render joint", logger=logger.success)
    def render_joint(self, joint: "JointMeta"):
        out_path = config.RENDERS_DIR / f"{joint.file_name}.{self.params.render_file_type}"
        self.render_paths[joint.vertex] = out_path
        logger.success("Writing mesh -> {}", out_path)
        proc = utils.openscad_cmd(
            *self.params.render_file_type.scad_args,
            "--enable=all",
            "-o",
            str(out_path),
            str(self.scad_paths[joint.vertex]),
        )
        for line in iter(proc.stderr.readline, b""):
            outline = line.decode().rstrip("\n")
            logger.debug("[OpenSCAD]: {}", outline)

    def preview_joint(self, vertex: "ModelVertex"):
        rnd_path = self.render_paths[vertex]
        mesh: o3d.geometry.TriangleMesh = o3d.io.read_triangle_mesh(
            str(rnd_path),
            enable_post_processing=True,
            print_progress=True,
        )
        mesh.compute_vertex_normals()
        mesh.compute_triangle_normals()
        o3d.visualization.draw([mesh], show_ui=True)

    @Timer("build", logger=logger.success)
    def assemble(self):
        logger.info("Constructing joint objects for {} vertices.", len(self.params.model.vertices))
        logger.debug("Director context: {}", self.context)
        verts = self.params.model.vertices.values()
        for vert in verts:
            self.build_joint(vert)


class ParallelJointDirector(JointDirector):
    @Timer("build", logger=logger.success)
    def assemble(self):
        logger.info("Constructing joint objects for {} vertices.", len(self.params.model.vertices))
        logger.debug("Director context: {}", self.context)
        workers = psutil.cpu_count()
        verts = self.params.model.vertices.values()
        chunk_size = len(verts) // workers
        if len(verts) <= workers:
            chunk_size = 1
        logger.info("parallel chunk size: ({} // {}) = {}", len(verts), workers, chunk_size)
        with Pool(processes=workers) as pool:
            list(pool.imap_unordered(self.build_joint, verts, chunksize=chunk_size))
