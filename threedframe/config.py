"""3DFrame configuration."""

from pathlib import Path

import solid
from pydantic import BaseSettings, validator

from threedframe.unit import Unit, UnitMM

__all__ = ["config"]

ROOT = Path(__file__).parent


class _Config(BaseSettings):
    # OpenSCAD Poly Segments
    SEGMENTS: int = 48
    # OpenSCAD Libraries.
    LIB_DIR: Path = ROOT / "lib"
    MCAD_DIR: Path = LIB_DIR / "MCAD"
    DOTSCAD_DIR: Path = LIB_DIR / "dotSCAD"

    @validator("LIB_DIR", "MCAD_DIR", "DOTSCAD_DIR")
    def validate_libs(cls, v: Path) -> Path:
        if not v.exists():
            raise ValueError(f"Missing library: {v}")
        # Monkey patch solidpython print statements.
        # (the errors are known and accommodated for)
        solid.objects.print = lambda *args: None
        solid.solidpython.print = lambda *args: None
        solid.import_scad(str(v))
        # undo monkey patch.
        solid.objects.print = print
        solid.solidpython.print = print
        return v

    # Model Params
    GAP: UnitMM = UnitMM(0.02)  # 3dPrinting fudge factor.
    CORE_SIZE: Unit = UnitMM(1.4).inches
    SUPPORT_SIZE: Unit = UnitMM(0.69).inches
    FIXTURE_WALL_THICKNESS: Unit = UnitMM(6)
    FIXTURE_HOLE_SIZE: Unit = SUPPORT_SIZE + GAP
    FIXTURE_SIZE: Unit = FIXTURE_HOLE_SIZE + FIXTURE_WALL_THICKNESS


config = _Config()
