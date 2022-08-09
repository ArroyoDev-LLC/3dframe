"""3DFrame configuration."""

from pathlib import Path

from pydantic import BaseSettings
from solid.config import config as SolidConfig
from solid.extensions.scad_interface import ScadInterface

from threedframe.constant import Constants

__all__ = ["config"]

ROOT = Path(__file__).parent


class _Config(BaseSettings):
    # General Config.
    RENDERS_DIR: Path = Path("renders")
    CI: bool = False

    # Log Config
    LOG_BASE_FMT: str = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan>"

    # OpenSCAD Poly Segments.
    SEGMENTS: int = 48

    def create_log_format(self, fmt: str):
        return self.LOG_BASE_FMT + fmt + " - <level>{message}</level>"

    def setup_solid(self):
        self.RENDERS_DIR.mkdir(exist_ok=True, parents=True)
        SolidConfig.enable_pickle_cache = not self.CI

    def set_solid_caching(self, enabled: bool = True):
        SolidConfig.enable_pickle_cache = enabled

    @property
    def scad_header(self) -> str:
        tmpl = "$fn = {c.SEGMENTS};"
        return tmpl.format(c=self)

    @property
    def scad_interface(self) -> ScadInterface:
        scad_int = ScadInterface()
        scad_int.additional_header_code(self.scad_header)
        scad_int.set_global_var("$preview", "false")
        return scad_int

    GAP: float = 0.02  # 3dPrinting fudge factor.

    # Support dimension scale,
    SUPPORT_SCALE: float = 1.0

    # Multipliers applied to support size.
    CORE_SIZE_MULTIPLIER: float = 2.03
    FIXTURE_SHELL_THICKNESS_MULTIPLIER: float = 0.3424
    FIXTURE_LENGTH_MULTIPLIER: float = 2.1739
    LABEL_SIZE_MULTIPLIER: float = 0.408
    LABEL_WIDTH_MULTIPLIER: float = 0.95

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

    @property
    def label_char_width(self) -> float:
        return self.label_width / 2

    @property
    def label_line_height(self) -> float:
        return self.fixture_length / 3.5

    class Config:
        env_prefix = "3DFRAME_"


config = _Config()
