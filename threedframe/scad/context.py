from __future__ import annotations

from enum import Flag, auto
from typing import TYPE_CHECKING, Optional, Protocol, runtime_checkable

if TYPE_CHECKING:
    pass


class BuildFlag(Flag):
    CORE = auto()
    FIXTURES = auto()

    CORE_LABEL = auto()
    FIXTURE_LABEL = auto()

    LABELS = CORE_LABEL | FIXTURE_LABEL

    JOINT = CORE | FIXTURES | LABELS


@runtime_checkable
class Context(Protocol):
    context: Optional[Context]

    @property
    def flags(self) -> BuildFlag:
        ...

    @classmethod
    def from_build_context(cls, ctx: Context):
        ...
