"""3DFrame units.

TODO: This is incomplete (and unused). In future,
use this as a base for all units.

"""

import operator
from enum import Enum
from typing import Union, ClassVar
from functools import partial

from threedframe.constant import Constants


class UnitTypes(str, Enum):
    MM = "mm"
    INCH = "inches"


class Unit:
    _rich_ops = [
        "__lt__",
        "__ge__",
        "__gt__",
        "__ge__",
        "__eq__",
        "__ne__",
        "__truediv__",
        "__floordiv__",
        "__add__",
        "__mul__",
        "__mod__",
        "__matmul__",
        "__pow__",
        "__sub__",
    ]
    unit_type: ClassVar[UnitTypes]

    def __new__(cls, *args, **kwargs):
        obj = object.__new__(cls)
        for op in cls._rich_ops:
            setattr(cls, op, partial(cls._do_comp, getattr(operator, op), obj))
        return obj

    def __init__(self, value: Union[int, float]):
        self.value = value

    def __repr__(self):
        return f"{self.__class__.__name__}(value={self.value})"

    @property
    def inches(self):
        raise NotImplementedError

    @property
    def mm(self):
        raise NotImplementedError

    @staticmethod
    def _do_comp(op, a, b):
        if oth_conv := getattr(b, a.unit_type):
            return op(a.value, oth_conv.value)
        return op(a.value, oth_conv.value)

    def __abs__(self):
        return self.__class__(abs(self.value))

    def __neg__(self):
        return self.__class__(-self.value)

    def __pos__(self):
        return self.__class__(+self.value)


class UnitMM(Unit):
    unit_type = UnitTypes.MM

    @property
    def inches(self) -> Unit:
        return UnitInch(self.value / Constants.INCH)

    @property
    def mm(self) -> Unit:
        return self


class UnitInch(Unit):
    unit_type = UnitTypes.INCH

    @property
    def inches(self) -> Unit:
        return self

    @property
    def mm(self) -> Unit:
        return UnitMM(self.value * Constants.INCH)
