from pathlib import Path

from threedframe.scad import JointDirector, JointDirectorParams


def test_joint_render(test_data: Path):
    in_data = test_data / "computed.json"
    assert in_data.exists()
    params = JointDirectorParams(model=in_data, vertices=[1])
    director = JointDirector(params=params)
    director.assemble()
