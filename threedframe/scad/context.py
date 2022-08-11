from __future__ import annotations

from enum import Flag, auto
from typing import TYPE_CHECKING, TypeVar, Optional, Protocol, runtime_checkable

import attrs

if TYPE_CHECKING:
    pass


class BuildFlag(Flag):
    CORE = auto()
    FIXTURES = auto()

    CORE_LABEL = auto()
    FIXTURE_LABEL = auto()

    LABELS = CORE_LABEL | FIXTURE_LABEL

    JOINT = CORE | FIXTURES | LABELS


ParamsT = TypeVar("ParamsT", contravariant=True)
T = TypeVar("T")


@runtime_checkable
class Context(Protocol[ParamsT]):
    context: Optional[Context]

    @property
    def flags(self) -> BuildFlag:
        ...

    @classmethod
    def from_build_context(cls, ctx: Context) -> Context:
        ...

    def build_strategy(self, params: ParamsT) -> T:
        ...

    def assemble(self, params: ParamsT) -> T:
        ...


@attrs.define
class BuildContext:
    build_flags: BuildFlag = attrs.field(default=BuildFlag.JOINT)

    @property
    def flags(self) -> BuildFlag:
        return self.build_flags
