import pytest

from threedframe.config import config

from ..utils import DirectoryFactoryType


@pytest.mark.parametrize("vertex", [1, 3, 42])
def test_fixture_length_less_than_support_length(
    director_factory: DirectoryFactoryType, vertex: int
):
    config.SUPPORT_SCALE = 0.69
    director = director_factory([vertex])
    verts = list(director.params.model.vertices.values())
    joint = director.params.joint_builder(vertex=verts[0], **director.builder_params)
    fixture_params = joint.build_fixture_params()
    for params in fixture_params:
        print(
            f"{params.source_label} [@ {params.adjusted_edge_length}] -> {params.target_label} => EH: {params.extrusion_height}"
        )
        assert params.extrusion_height * 2 < params.adjusted_edge_length


@pytest.mark.parametrize("vertex", [4])
def test_fixture_adjusted_length_lt_support_len(
    director_factory: DirectoryFactoryType, vertex: int
):
    config.SUPPORT_SCALE = 0.69
    director = director_factory([vertex])
    verts = list(director.params.model.vertices.values())
    joint = director.params.joint_builder(vertex=verts[0], **director.builder_params)

    for fix in joint.construct_fixtures():
        print(
            f"{fix.params.source_label} [@ {fix.params.adjusted_edge_length}] -> {fix.params.target_label} => EH: {fix.extrusion_height}"
        )
        assert fix.extrusion_height * 2 < fix.params.adjusted_edge_length
