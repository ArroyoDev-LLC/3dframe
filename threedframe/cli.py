#!/usr/bin/env python3

"""Console script for 3DFrame."""
from enum import Enum
from typing import List, Optional
from pathlib import Path

import typer
from devtools import debug

from threedframe.config import config  # noqa

config.setup_solid()  # noqa

import threedframe.utils
from threedframe.scad import JointDirector, JointDirectorParams, ParallelJointDirector
from threedframe.scad.core import CoreDebugCubes
from threedframe.scad.joint import (
    SolidFixture,
    JointLabelDebug,
    JointCoreOnlyDebug,
    JointSingleFixtureDebug,
)
from threedframe.scad.label import FixtureLabelDebugArrows
from threedframe.scad.fixture import FixtureLabelDebug


class BuildStrategy(str, Enum):
    CORE_ONLY = "debugCoreOnly"
    CORE_VERTICES = "debugCoreVertices"
    FIXTURE_LABELS = "debugFixLabels"
    FIXTURE_LABELS_ARROWS = "debugFixLabelsArrows"
    SINGLE_FIXTURE = "debugSingleFixture"
    PARALLEL = "parallel"

    @property
    def _builders(self):
        return {
            BuildStrategy.CORE_ONLY: {"joint_builder": JointCoreOnlyDebug},
            BuildStrategy.CORE_VERTICES: {
                "fixture_builder": SolidFixture,
                "core_builder": CoreDebugCubes,
            },
            BuildStrategy.FIXTURE_LABELS: {
                "joint_builder": JointLabelDebug,
                "fixture_builder": FixtureLabelDebug,
            },
            BuildStrategy.FIXTURE_LABELS_ARROWS: {
                "joint_builder": JointLabelDebug,
                "fixture_label_builder": FixtureLabelDebugArrows,
            },
            BuildStrategy.SINGLE_FIXTURE: {"joint_builder": JointSingleFixtureDebug},
            BuildStrategy.PARALLEL: {"director": ParallelJointDirector},
        }

    @property
    def builders(self):
        return self._builders[self]


app = typer.Typer(name="3dframe")


def parse_vertices(vertices: List[str]):
    if not len(vertices):
        return None
    _verts = []
    for v in vertices:
        if "-" in v:
            rng = [int(i) for i in v.split("-")]
            final = rng.pop(-1)
            rng.append(final + 1)
            for pv in range(*rng):
                _verts.append(int(pv))
        else:
            _verts.append(int(v))
    return _verts


@app.command()
def generate(
    model_path: Path = typer.Argument(
        ..., exists=True, file_okay=True, dir_okay=False, help="Path to data computed from model."
    ),
    vertices: Optional[List[str]] = typer.Option(
        None, "-v", "--vertices", callback=parse_vertices, help="Vertices to render."
    ),
    build_mode: Optional[BuildStrategy] = typer.Option(
        None, "-b", "--build-mode", help="Optional debug mode to utilize."
    ),
    render: Optional[bool] = typer.Option(
        False, "-r", "--render", help="Render mesh.", is_flag=True
    ),
    render_format: Optional[str] = typer.Option("stl", "-f", "--format", help="Render file type."),
    scale: Optional[float] = typer.Option(1.0, "-s", "--scale", help="Support size scale."),
    dump_config: Optional[bool] = typer.Option(
        False, "-d", "--dump-config", help="Dump generated config.", is_flag=True
    ),
    no_cache: Optional[bool] = typer.Option(
        False, "--no-cache", help="Disable caching.", is_flag=True
    ),
):
    """Generate joint model from given vertices."""
    if not vertices:
        typer.confirm("Are you sure you want to render ALL vertices?", abort=True)
        vertices = None  # indicates all in director params.
    config.SUPPORT_SCALE = scale
    if no_cache:
        config.set_solid_caching(False)
    params = JointDirectorParams(
        model=model_path, vertices=vertices, render=render, render_file_type=render_format
    )
    director_cls = JointDirector
    if build_mode is not None:
        builders = build_mode.builders.copy()
        director_cls = builders.pop("director", director_cls)
        params = JointDirectorParams(
            model=model_path,
            vertices=vertices,
            render=render,
            render_file_type=render_format,
            **builders,
        )
    director = director_cls(params=params)
    vert_count = "all" if vertices is None else len(vertices)
    if dump_config:
        debug(config)
        debug(config.computed_values)
        debug(params)
        return
    typer.secho(
        f"Building joints for {vert_count} vertices.", bold=True, fg=typer.colors.BRIGHT_WHITE
    )
    director.assemble()


@app.command()
def compute(model_path: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False)):
    """Compute vertices/edge data from blender model."""
    model_path = Path(model_path)
    script_path = Path(__file__).parent / "compute.py"
    assert script_path.exists(), "Failed to find script path."
    data_path = model_path.with_suffix(".json")
    threedframe.utils.exec_blender_script(Path(model_path), script_path, data_path)
    print("[bold green]✔ Done!")
    print(f"[bold white]Data written to: [cyan]{data_path.absolute()}")


@app.command()
def setup_host_libs():
    """Setup SCAD libraries on host for previewing renders in openSCAD."""
    config.setup_libs()


@app.callback()
def main():
    """3dframe CLI Entrypoint."""


if __name__ == "__main__":
    app()
