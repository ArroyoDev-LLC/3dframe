#!/usr/bin/env python3

"""Console script for 3DFrame."""
import sys
from pathlib import Path
from importlib import reload

import click
from rich import print

import threedframe.joint
import threedframe.utils


@click.group()
def main():
    """3dframe Cli Entrypoint."""


@main.command()
@click.option("-d", "--debug", is_flag=True, default=False, help="Enable debug mode.")
@click.option(
    "-r", "--render", is_flag=True, default=False, help="Render to .STL or provided file type."
)
@click.option("-k", "--keep", is_flag=True, default=False, help="Keep SCAD Files.")
@click.option("-w", "--watch", is_flag=True, default=False, help="Watch for changes.")
@click.option(
    "-f",
    "--file-type",
    default="stl",
    help="Exported file type.",
)
@click.argument(
    "model_data",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
)
@click.argument("vertices", type=str, nargs=-1)
def generate(model_data, vertices=tuple(), watch=False, *args, **kwargs):
    """Generate joint model from given vertex."""
    print(vertices)
    _verts = vertices
    if not any(vertices) and not vertices == tuple([0]) and not vertices == tuple(["0"]):
        print("[bold orange]No vertices were provided.")
        click.confirm("Would you like to render ALL vertices?", abort=True)
    else:
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
        click.confirm(f"Render {' '.join([str(i) for i in _verts])}?", abort=True)
    threedframe.joint.generate(Path(model_data), _verts, *args, **kwargs)
    if watch:

        def _on_modify():
            reload(threedframe.joint)
            reload(threedframe.utils)
            try:
                threedframe.joint.generate(Path(model_data), vertices, *args, **kwargs)
            except Exception as e:
                print(e)

        watcher = threedframe.utils.FileModifiedWatcher(_on_modify)
        watcher.run()


@main.command()
@click.argument(
    "model_path",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
)
def compute(model_path: Path):
    """Compute vertices/edge data from blender model."""
    model_path = Path(model_path)
    script_path = Path(__file__).parent / "compute.py"
    assert script_path.exists(), "Failed to find script path."
    data_path = model_path.with_suffix(".pkl")
    threedframe.utils.exec_blender_script(Path(model_path), script_path, data_path)
    print("[bold green]✔ Done!")
    print(f"[bold white]Data written to: [cyan]{data_path.absolute()}")


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
