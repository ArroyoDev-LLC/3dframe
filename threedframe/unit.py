"""3DFrame units.

TODO: This is incomplete (and unused). In future,
use this as a base for all units.

"""
from typing import Union

import attr

from threedframe.constant import Constants


@attr.s(auto_attribs=True)
class Unit:
    value: Union[int, float]

    @property
    def inches(self):
        return Constants.INCH
