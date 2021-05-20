from typing import TYPE_CHECKING, Any, Dict, Type, Union, Iterator, Optional, Sequence
from pathlib import Path

import attr
from loguru import logger
from pydantic import BaseModel, validator, parse_file_as

from threedframe import utils
from threedframe.models import ModelData
from threedframe.scad.joint import Joint

from ..config import config

if TYPE_CHECKING:
    from .interfaces import CoreMeta, JointMeta, LabelMeta, FixtureMeta


class JointDirectorParams(BaseModel):
    joint_builder: Optional[Type["JointMeta"]] = Joint
    fixture_builder: Optional[Type["FixtureMeta"]] = None
    fixture_label_builder: Optional[Type["LabelMeta"]] = None
    core_builder: Optional[Type["CoreMeta"]] = None
    core_label_builder: Optional[Type["LabelMeta"]] = None

    vertices: Optional[Sequence[int]] = None
    model: Union[Path, "ModelData"]

    @validator("model")
    def validate_model_data(cls, v: Union[Path, "ModelData"], values: Dict[str, Any]) -> ModelData:
        if isinstance(v, Path):
            v = parse_file_as(ModelData, v)
        verts = values["vertices"]
        if verts is not None:
            # scoped vertices down to requested by params.
            _new_verts = {k: v for k, v in v.vertices.items() if k in verts}
            v.vertices = _new_verts
        return v


@attr.s(auto_attribs=True)
class JointDirector:
    params: JointDirectorParams

    @property
    def builder_params(self) -> Dict[str, Any]:
        _build_params = self.params.dict(
            exclude={"model", "vertices"}, exclude_none=True, exclude_unset=True
        )
        return _build_params

    def build_joints(self) -> Iterator["JointMeta"]:
        for vertex in self.params.model.vertices.values():
            logger.info("Building joint for vertex: {}", vertex.vidx)
            joint = self.params.joint_builder(
                vertex=vertex,
                **self.builder_params,
            )
            joint.assemble()
            yield joint

    def assemble(self):
        logger.info("Constructing joint objects for {} vertices.", len(self.params.model.vertices))
        logger.debug("Director builders: {}", self.builder_params)
        joints = list(self.build_joints())
        for joint in joints:
            file_name = f"joint-v{joint.vertex.vidx}.scad"
            out_dir = config.RENDERS_DIR / file_name
            utils.write_scad(joint.scad_object, out_dir, segments=config.SEGMENTS)
