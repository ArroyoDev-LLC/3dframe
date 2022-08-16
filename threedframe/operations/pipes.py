"""Operation Pipes."""
from __future__ import annotations

from typing import Union, TypeVar, Protocol, runtime_checkable
from collections import deque

import attrs
from loguru import logger

import threedframe.operations as op

TargetT = TypeVar("TargetT")


@runtime_checkable
class Operation(Protocol[TargetT]):
    def operate(self, mesh: TargetT) -> TargetT:
        ...


@attrs.define
class OperationPipeline:
    operations: deque[Union[Operation, OperationPipeline]] = attrs.field(factory=deque)

    def add_ops(self, *ops: Union[Operation[TargetT], OperationPipeline]) -> OperationPipeline:
        self.operations.extend(ops)
        return self

    def apply(self, target: TargetT) -> TargetT:
        result = target
        for op in self.operations:
            if isinstance(op, OperationPipeline):
                result = op.apply(result)
            elif isinstance(op, Operation):
                logger.info("applying operation: {!r}", op)
                result = op.operate(result)
            else:
                raise TypeError(f"Expected Operation or OperationPipeline object, got: {op}")
        return result


OrientPipeline = OperationPipeline().add_ops(
    op.RepairOperation(),
    op.FlatOperation(),
    op.OptimalOrientOperation(),
)

OrientMeshFilePipeline = lambda path: OperationPipeline().add_ops(
    op.ReadMeshOperation(), op.SerializeMeshOperation(), OrientPipeline, op.WriteMeshOperation(path)
)
