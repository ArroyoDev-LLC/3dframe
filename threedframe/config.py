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
    # General Config.
    RENDERS_DIR: Path = Path("renders")

    @validator("RENDERS_DIR")
    def validate_renders_dir(cls, v: Path) -> Path:
        v.mkdir(exist_ok=True)
        return v

    ## Log Config
    LOG_BASE_FMT: str = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan>"

    # OpenSCAD Poly Segments.
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
        v.mkdir(exist_ok=True)
        return v

    def create_log_format(self, fmt: str):
        return self.LOG_BASE_FMT + fmt + " - <level>{message}</level>"

    def create_lib_dir(self, lib_dir: Path):
        """Create library directory.

        Copies given lib to /tmp/ directory to
        simplify previewing generated models on host.

        """
        rel_dir = lib_dir.relative_to(self.LIB_DIR)
        target_dir = self.TMP_DIR / rel_dir
        if target_dir.exists():
            return target_dir
        target_dir.mkdir(parents=True, exist_ok=True)
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

    GAP: float = 0.02  # 3dPrinting fudge factor.

    # Support dimension scale,
    SUPPORT_SCALE: float = 1.0

    # Multipliers applied to support size.
    CORE_SIZE_MULTIPLIER: float = 2.03
    FIXTURE_SHELL_THICKNESS_MULTIPLIER: float = 0.1712
    FIXTURE_LENGTH_MULTIPLIER: float = 2.1739
    LABEL_SIZE_MULTIPLIER: float = 0.408
    LABEL_WIDTH_MULTIPLIER: float = 0.612

    @property
    def computed_values(self):
        attrs = {
            "support_size",
            "core_size",
            "fixture_shell_thickness",
            "fixture_length",
            "fixture_size",
            "label_size",
            "label_width",
        }
        return {k: getattr(self, k) for k in attrs}

    @property
    def support_size(self) -> float:
        return self.SUPPORT_SCALE * Constants.INCH

    @property
    def core_size(self) -> float:
        return self.support_size * self.CORE_SIZE_MULTIPLIER

    @property
    def fixture_shell_thickness(self) -> float:
        return self.support_size * self.FIXTURE_SHELL_THICKNESS_MULTIPLIER

    @property
    def fixture_length(self) -> float:
        return self.support_size * self.FIXTURE_LENGTH_MULTIPLIER

    @property
    def fixture_size(self) -> float:
        return (self.support_size + self.GAP) + self.fixture_shell_thickness

    @property
    def fixture_hole_size(self) -> float:
        return self.support_size + self.GAP

    @property
    def label_size(self) -> float:
        return self.support_size * self.LABEL_SIZE_MULTIPLIER

    @property
    def label_width(self) -> float:
        return self.support_size * self.LABEL_WIDTH_MULTIPLIER


config = _Config()
