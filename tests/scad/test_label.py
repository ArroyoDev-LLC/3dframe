# This test code was written by the `hypothesis.extra.ghostwriter` module
# and is provided under the Creative Commons Zero public domain dedication.

from hypothesis import given
from hypothesis import strategies as st

import threedframe.scad.label

# TODO: replace st.nothing() with an appropriate strategy


@given(
    scad_object=st.none(),
    params=st.just(Ellipsis),
    fixtures=st.just(Ellipsis),
    target=st.just(Ellipsis),
    meshes=st.just(Ellipsis),
)
def test_fuzz_FixtureLabel(scad_object, params, fixtures, target, meshes):
    threedframe.scad.label.FixtureLabel(
        scad_object=scad_object,
        params=params,
        fixtures=fixtures,
        target=target,
        meshes=meshes,
    )


@given(
    content=st.text(),
    halign=st.text(),
    valign=st.text(),
    depth=st.floats(),
    size=st.floats(),
    width=st.floats(),
    center=st.booleans(),
)
def test_fuzz_LabelParams(content, halign, valign, depth, size, width, center):
    threedframe.scad.label.LabelParams(
        content=content,
        halign=halign,
        valign=valign,
        depth=depth,
        size=size,
        width=width,
        center=center,
    )
