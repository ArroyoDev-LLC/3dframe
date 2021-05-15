"""3DFrame configuration."""

import contextlib
from typing import Any, Optional
from pathlib import Path

import solid
from pydantic import BaseSettings, validator
from pydantic.fields import PrivateAttr

from threedframe.unit import Unit, UnitMM

__all__ = ["config"]

ROOT = Path(__file__).parent


@contextlib.contextmanager
def quiet_solid():
    """Monkey patch solidpython print statements.

    The errors are known and accommodated for,
    so just ignore them.

    """
    solid.objects.print = lambda *args: None
    solid.solidpython.print = lambda *args: None
    yield
    # undo monkey patch.
    solid.objects.print = print
    solid.solidpython.print = print


class _Config(BaseSettings):
    # OpenSCAD Poly Segments
    SEGMENTS: int = 48
    # OpenSCAD Libraries.
    LIB_DIR: Path = ROOT / "lib"
    MCAD_DIR: Path = LIB_DIR / "MCAD"
    DOTSCAD_DIR: Path = LIB_DIR / "dotSCAD"

    _mcad: Optional[Any] = PrivateAttr(None)
    _dotSCAD: Optional[Any] = PrivateAttr(None)

    @validator("LIB_DIR", "MCAD_DIR", "DOTSCAD_DIR")
    def validate_libs(cls, v: Path) -> Path:
        if not v.exists():
            raise ValueError(f"Missing library: {v}")
        return v

    @validator("MCAD_DIR")
    def validate_mcad(self):
        with quiet_solid():
            self._mcad = solid.import_scad(str(self.MCAD_DIR))

    @validator("DOTSCAD_DIR")
    def validate_mcad(self):
        with quiet_solid():
            self._dotSCAD = solid.import_scad(str(self.DOTSCAD_DIR))

    @property
    def mcad(self):
        return self._mcad

    @property
    def dotSCAD(self):
        return self._dotSCAD

    # Model Params
    GAP: UnitMM = UnitMM(0.02)  # 3dPrinting fudge factor.
    CORE_SIZE: Unit = UnitMM(1.4).inches
    SUPPORT_SIZE: Unit = UnitMM(0.69).inches
    FIXTURE_WALL_THICKNESS: Unit = UnitMM(6)
    FIXTURE_HOLE_SIZE: Unit = SUPPORT_SIZE + GAP
    FIXTURE_SIZE: Unit = FIXTURE_HOLE_SIZE + FIXTURE_WALL_THICKNESS


config = _Config()
