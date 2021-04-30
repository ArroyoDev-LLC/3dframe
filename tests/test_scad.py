from pathlib import Path

import pytest
from snapshottest.file import FileSnapshot

from threedframe import joint


@pytest.mark.parametrize("vertices", [(1,), (2,), (3,)])
def test_scad_render(test_data: Path, snapshot, vertices):
    in_data = test_data / "computed.pkl"
    assert in_data.exists()
    joint.generate(in_data, vertices=vertices, render=False, keep=True)
    render_dir = joint.ROOT.parent / "renders"
    out_path = render_dir / "joint-v1.scad"
    assert out_path.exists()
    snapshot.assert_match(FileSnapshot(str(out_path)))
