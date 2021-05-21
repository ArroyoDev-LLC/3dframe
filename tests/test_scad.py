from pathlib import Path

import pytest

from threedframe import joint
from threedframe.scad import JointDirector, JointDirectorParams


@pytest.mark.parametrize("vertices", [(1,), (2,), (3,)])
def test_scad_render(test_data: Path, snapshot, vertices):
    in_data = test_data / "computed.json"
    assert in_data.exists()
    params = JointDirectorParams(model=in_data, vertices=[1])
    director = JointDirector(params=params)
    director.assemble()
    render_dir = joint.ROOT.parent / "renders"
    out_path = render_dir / "joint-v1.scad"
    assert out_path.exists()
    out_data = out_path.read_text()
    snapshot.assert_match(out_data, f"joint-{'-'.join((str(i) for i in vertices))}")
