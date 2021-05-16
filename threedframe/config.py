"""3DFrame configuration."""

import shutil
import contextlib
from typing import Any, Optional
from pathlib import Path

import solid
from pydantic import BaseSettings, validator
from pydantic.fields import PrivateAttr

from threedframe.constant import Constants

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
    TMP_DIR: Path = Path("/tmp/") / "threedframe"
    LIB_DIR: Path = ROOT / "lib"
    MCAD_DIR: Path = LIB_DIR / "MCAD"
    DOTSCAD_DIR: Path = LIB_DIR / "dotSCAD" / "src"

    _mcad: Optional[Any] = PrivateAttr(None)
    _dotSCAD: Optional[Any] = PrivateAttr(None)

    @validator("LIB_DIR", "MCAD_DIR", "DOTSCAD_DIR")
    def validate_libs(cls, v: Path) -> Path:
        if not v.exists():
            raise ValueError(f"Missing library: {v}")
        return v

    @validator("TMP_DIR", pre=True)
    def validate_tmp_dir(cls, v: Path) -> Path:
        if v.exists():
            shutil.rmtree(v, ignore_errors=True)
        v.mkdir()
        return v

    def create_lib_dir(self, lib_dir: Path):
        """Create library directory.

        Copies given lib to /tmp/ directory to
        simplify previewing generated models on host.

        """
        rel_dir = lib_dir.relative_to(self.LIB_DIR)
        target_dir = self.TMP_DIR / rel_dir
        target_dir.mkdir(parents=True)
        shutil.copytree(lib_dir, target_dir, dirs_exist_ok=True)
        return target_dir

    def setup_libs(self):
        mcad = self.create_lib_dir(self.MCAD_DIR)
        dotscad = self.create_lib_dir(self.DOTSCAD_DIR)
        with quiet_solid():
            self._mcad = solid.import_scad(str(mcad))
            self._dotSCAD = solid.import_scad(str(dotscad))

    @property
    def mcad(self):
        if not self._mcad:
            self.setup_libs()
        return self._mcad

    @property
    def dotSCAD(self):
        if not self._dotSCAD:
            self.setup_libs()
        return self._dotSCAD

    # Model Params
    GAP: float = 0.02  # 3dPrinting fudge factor.
    CORE_SIZE: float = 1.4 * Constants.INCH
    SUPPORT_SIZE: float = 0.69 * Constants.INCH
    FIXTURE_WALL_THICKNESS: float = 6.0
    FIXTURE_HOLE_SIZE: float = SUPPORT_SIZE + GAP
    FIXTURE_SIZE: float = FIXTURE_HOLE_SIZE + FIXTURE_WALL_THICKNESS


config = _Config()
