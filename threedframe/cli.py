#!/usr/bin/env python3

"""Console script for 3DFrame."""
from enum import Enum
from typing import TYPE_CHECKING, List, Optional
from pathlib import Path

import typer
from rich import print
from devtools import debug
from rich.tree import Tree
from rich.table import Table

from threedframe.config import config  # noqa

config.setup_solid()  # noqa

import threedframe.utils
from threedframe.scad import JointDirector, JointDirectorParams, ParallelJointDirector
from threedframe.scad.joint import (
    JointLabelDebug,
    JointFixturesOnly,
    JointCoreOnlyDebug,
    JointSingleFixtureDebug,
)
from threedframe.scad.label import FixtureLabelDebugArrows
from threedframe.scad.fixture import FixtureLabelDebug, FixtureSimpleDebug

if TYPE_CHECKING:
    from threedframe.scad.joint import Joint
    from threedframe.scad.interfaces import FixtureMeta


class BuildStrategy(str, Enum):
    CORE_ONLY = "debugCoreOnly"
    CORE_VERTICES = "debugCoreVertices"
    FIXTURE_LABELS = "debugFixLabels"
    FIXTURE_LABELS_ARROWS = "debugFixLabelsArrows"
    SINGLE_FIXTURE = "debugSingleFixture"
    SIMPLE_FIXTURES = "debugSimpleFixtures"
    PARALLEL = "parallel"

    @property
    def _builders(self):
        return {
            BuildStrategy.CORE_ONLY: {"joint_builder": JointCoreOnlyDebug},
            BuildStrategy.FIXTURE_LABELS: {
                "joint_builder": JointLabelDebug,
                "fixture_builder": FixtureLabelDebug,
            },
            BuildStrategy.FIXTURE_LABELS_ARROWS: {
                "joint_builder": JointLabelDebug,
                "fixture_label_builder": FixtureLabelDebugArrows,
            },
            BuildStrategy.SINGLE_FIXTURE: {"joint_builder": JointSingleFixtureDebug},
            BuildStrategy.SIMPLE_FIXTURES: {
                "joint_builder": JointFixturesOnly,
                "fixture_builder": FixtureSimpleDebug,
            },
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
            _verts.append(v)
    return _verts


ModelPathArg: Path = typer.Argument(
    ..., exists=True, file_okay=True, dir_okay=False, help="Path to data computed from model."
)
VerticesArg: Optional[List[str]] = typer.Option(
    None, "-v", "--vertices", callback=parse_vertices, help="Vertices to render."
)
ScaleArg: Optional[float] = typer.Option(1.0, "-s", "--scale", help="Support size scale.")


@app.command()
def generate(
    model_path=ModelPathArg,
    vertices: Optional[List[str]] = VerticesArg,
    build_mode: Optional[BuildStrategy] = typer.Option(
        None, "-b", "--build-mode", help="Optional debug mode to utilize."
    ),
    render: Optional[bool] = typer.Option(
        False, "-r", "--render", help="Render mesh.", is_flag=True
    ),
    render_format: Optional[str] = typer.Option("stl", "-f", "--format", help="Render file type."),
    scale: Optional[float] = ScaleArg,
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
def inspect(
    model_path=ModelPathArg,
    vertex: str = typer.Argument(..., help="Vertex to inspect."),
    scale: Optional[float] = ScaleArg,
):
    config.SUPPORT_SCALE = scale

    def create_fixture_table(fixture: "FixtureMeta"):
        tbl = Table("Ext. Height", "Cut Length", title=fixture.params.vidx_label)
        tbl.add_row(
            str(round(fixture.extrusion_height, 2)),
            f"{fixture.params.adjusted_edge_length_as_label} ({round(fixture.params.adjusted_edge_length, 2)})",
        )
        return tbl

    def create_fixture_target_table(root_fixture: "FixtureMeta", target: "FixtureMeta"):
        grid = Table.grid()
        grid.add_column()
        grid.add_column()
        grid.add_row(create_fixture_table(root_fixture), create_fixture_table(target))
        return grid

    tree = Tree(f"[bold green]Joint [white]{vertex}")
    fixtures_tree = tree.add("Fixtures")

    params = JointDirectorParams(model=model_path, vertices=(vertex,), render=False)
    director = JointDirector(params=params)
    target_vidx = params.model.get_vidx_by_label(vertex)
    target_vidx = target_vidx if target_vidx is not None else vertex
    joint = director.create_joint(vertex=target_vidx)
    sibling_joints = set()
    for fix_param in joint.build_fixture_params():
        sibling_joints.add(fix_param.target_vertex.vidx)

    new_verts = {*director.params.vertices} | sibling_joints
    new_params = JointDirectorParams(model=model_path, vertices=list(new_verts), render=False)
    director = JointDirector(params=new_params)
    target_vertex = director.params.model.vertices[target_vidx]

    joint_family = {}
    for vert in director.params.model.vertices.values():
        joint_family[vert.label] = director.create_joint(vertex=vert)
        joint_family[vert.label].fixtures = list(joint_family[vert.label].construct_fixtures())

    root_joint = joint_family[target_vertex.label]

    for fixture in root_joint.fixtures:
        fix_tree = fixtures_tree.add(label=f"[bold bright_white]{fixture.name}")
        target_vert_label = fixture.params.target_label
        target_joint = joint_family[target_vert_label]
        target_fixture = next(
            (
                f
                for f in target_joint.fixtures
                if f.params.target_label == fixture.params.source_label
            )
        )
        target_tree = fix_tree.add(
            label=f"[bold bright_yellow]From {fixture.params.source_label} -> {fixture.params.target_label}"
        )
        target_tree.add(create_fixture_target_table(fixture, target_fixture))

        siblings_tree = fix_tree.add(label=f"[bold bright_white]Fixture Siblings")
        siblings = [f for f in root_joint.fixtures if f.name != fixture.name]
        sib_grid = Table.grid()
        sib_tables = []
        for sib in siblings:
            sib_grid.add_column()
            sib_table = Table("Angle Bet.", title=sib.params.target_label)
            angle_bet = round(sib.params.angle_between(fixture.params), 2)
            angle_bet_r = str(angle_bet)
            if angle_bet < 30:
                angle_bet_r = f"[bold bright_red] :warning: {angle_bet_r}"
            sib_table.add_row(angle_bet_r)
            sib_tables.append(sib_table)
        sib_grid.add_row(*sib_tables)
        siblings_tree.add(sib_grid)

    print()
    print(tree)


@app.command()
def analyze(model_path: Path = ModelPathArg, scale: Optional[float] = ScaleArg):
    config.SUPPORT_SCALE = scale
    params = JointDirectorParams(model=model_path)
    director = JointDirector(params=params)

    invalid_joints = Table(
        "Joint",
        "Source Fix.",
        "Sibling Fix.",
        "Angle Bet.",
        title=f"[bold bright_red] :warning: Invalid Joints",
    )

    for vertex in director.params.model.vertices.values():
        joint: "Joint" = director.create_joint(vertex=vertex)
        joint.fixtures = list(joint.construct_fixtures())
        for fixture in joint.fixtures:
            siblings = joint.get_sibling_fixtures(fixture)
            for sib in siblings:
                angle_bet = round(sib.params.angle_between(fixture.params), 2)
                if angle_bet < 30:
                    invalid_joints.add_row(
                        fixture.params.vidx_label,
                        fixture.params.target_label,
                        sib.params.target_label,
                        str(angle_bet),
                    )

    print(invalid_joints)


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
def shell(
    model_path: Path = typer.Argument(
        ..., exists=True, file_okay=True, dir_okay=False, resolve_path=True
    ),
    scale: Optional[float] = ScaleArg,
    vertex: Optional[str] = typer.Argument(None, help="Vertex to inspect."),
    build: bool = typer.Option(False, "-b", "--build", help="Build Joint fixtures.", is_flag=True),
    preview: bool = typer.Option(
        False, "-p", "--preview", help="Preview fixture output mesh.", is_flag=True
    ),
):
    print("args:", model_path, scale, vertex)
    from traitlets.config import Config

    c = Config()
    exec_lines = [
        "from rich import inspect",
        "from pathlib import Path",
        "import solid as sp",
        "import open3d as o3d",
        "from threedframe.config import config",
        "config.setup_solid()",
        f"config.SUPPORT_SCALE = {scale}",
        "from threedframe.scad import *",
        f"params = JointDirectorParams(model=Path('{model_path}'))",
        "director = JointDirector(params=params)",
    ]
    if vertex:
        exec_lines.extend(
            [
                f"vidx = director.params.model.get_vidx_by_label('{vertex}')",
                f"vidx = vidx if vidx is not None else '{vertex}'",
                "vert = director.params.model.vertices[vidx]",
                "joint = director.create_joint(vert)",
            ]
        )
        if build:
            exec_lines.extend(
                [
                    "joint.build_fixtures()",
                    "[print(' - '.join([str(idx), f.name])) for idx, f in enumerate(joint.fixtures)]",
                ]
            )
        if preview:
            exec_lines.extend(
                [
                    "o = sp.union() + [f.scad_object for f in joint.fixtures]",
                    "om = joint.get_mesh(o)",
                    "o3d.visualization.draw_geometries([om])",
                ]
            )
    print("exec lines:", exec_lines)
    import IPython  # noqa

    c.InteractiveShellApp.exec_lines = exec_lines
    c.InteractiveShellApp.extensions.append("rich")
    IPython.start_ipython(argv=[], config=c)


@app.command()
def setup_host_libs():
    """Setup SCAD libraries on host for previewing renders in openSCAD."""
    config.setup_libs()


@app.callback()
def main():
    """3dframe CLI Entrypoint."""


if __name__ == "__main__":
    app()
