from hypothesis import given
from hypothesis import strategies as st
from solid.solidpython import OpenSCADObject

import threedframe.models
from threedframe.models import MeshData, MeshFace, MeshPoint, ModelEdge, ModelVertex

st_ModelVertex = st.builds(
    ModelVertex,
    label=st.one_of(st.none(), st.one_of(st.none(), st.text())),
    edges=st.just([]) | st.deferred(lambda: st.lists(st_ModelEdge)),
)

st_MaybeVertex = st.one_of(st.none(), st_ModelVertex)

st_ModelEdge = st.builds(
    ModelEdge,
    joint_vertex=st.none() | st_ModelVertex,
    target_vertex=st.none() | st_ModelVertex,
)


@given(
    scad_object=st.builds(OpenSCADObject),
    inspect_object=st.builds(OpenSCADObject),
    inner_object=st.builds(OpenSCADObject),
    model_edge=st_ModelEdge,
    model_vertex=st_ModelVertex,
    dest_point=st.tuples(st.floats(), st.floats(), st.floats()),
    dest_normal=st.tuples(st.floats(), st.floats(), st.floats()),
    inspect_data=st.builds(dict),
    inspect_mesh=st.one_of(st.none(), st.builds(MeshData)),
)
def test_fuzz_JointFixture(
    scad_object,
    inspect_object,
    inner_object,
    model_edge,
    model_vertex,
    dest_point,
    dest_normal,
    inspect_data,
    inspect_mesh,
):
    threedframe.models.JointFixture(
        scad_object=scad_object,
        inspect_object=inspect_object,
        inner_object=inner_object,
        model_edge=model_edge,
        model_vertex=model_vertex,
        dest_point=dest_point,
        dest_normal=dest_normal,
        inspect_data=inspect_data,
        inspect_mesh=inspect_mesh,
    )


@given(
    vertices=st.lists(
        st.builds(
            MeshPoint,
            normal=st.one_of(
                st.none(),
                st.one_of(st.none(), st.tuples(st.floats(), st.floats(), st.floats())),
            ),
        )
    ),
    faces=st.lists(
        st.builds(
            MeshFace,
            centroid=st.one_of(
                st.none(),
                st.one_of(st.none(), st.tuples(st.floats(), st.floats(), st.floats())),
            ),
            normal=st.one_of(
                st.none(),
                st.one_of(st.none(), st.tuples(st.floats(), st.floats(), st.floats())),
            ),
        )
    ),
)
def test_fuzz_MeshData(vertices, faces):
    threedframe.models.MeshData(vertices=vertices, faces=faces)


@given(
    fidx=st.integers(),
    vertex_indices=st.lists(st.integers()),
    normal=st.one_of(st.none(), st.tuples(st.floats(), st.floats(), st.floats())),
    area=st.floats(),
    centroid=st.one_of(st.none(), st.tuples(st.floats(), st.floats(), st.floats())),
)
def test_fuzz_MeshFace(fidx, vertex_indices, normal, area, centroid):
    threedframe.models.MeshFace(
        fidx=fidx,
        vertex_indices=vertex_indices,
        normal=normal,
        area=area,
        centroid=centroid,
    )


@given(
    vidx=st.integers(),
    point=st.tuples(st.floats(), st.floats(), st.floats()),
    normal=st.one_of(st.none(), st.tuples(st.floats(), st.floats(), st.floats())),
)
def test_fuzz_MeshPoint(vidx, point, normal):
    threedframe.models.MeshPoint(vidx=vidx, point=point, normal=normal)


@given(
    num_vertices=st.integers(),
    num_edges=st.integers(),
    vertices=st.dictionaries(
        keys=st.integers(),
        values=st_ModelVertex,
    ),
)
def test_fuzz_ModelData(num_vertices, num_edges, vertices):
    threedframe.models.ModelData(num_vertices=num_vertices, num_edges=num_edges, vertices=vertices)


@given(
    eidx=st.integers(),
    length=st.floats(),
    joint_vidx=st.integers(),
    joint_vertex=st_MaybeVertex,
    target_vidx=st.integers(),
    target_vertex=st_MaybeVertex,
    vector_ingress=st.tuples(st.floats(), st.floats(), st.floats()),
)
def test_fuzz_ModelEdge(
    eidx, length, joint_vidx, joint_vertex, target_vidx, target_vertex, vector_ingress
):
    threedframe.models.ModelEdge(
        eidx=eidx,
        length=length,
        joint_vidx=joint_vidx,
        joint_vertex=joint_vertex,
        target_vidx=target_vidx,
        target_vertex=target_vertex,
        vector_ingress=vector_ingress,
    )


@given(
    vidx=st.integers(),
    edges=st.lists(st_ModelEdge),
    point=st.tuples(st.floats(), st.floats(), st.floats()),
    point_normal=st.tuples(st.floats(), st.floats(), st.floats()),
    label=st.one_of(st.none(), st.text()),
)
def test_fuzz_ModelVertex(vidx, edges, point, point_normal, label):
    threedframe.models.ModelVertex(
        vidx=vidx, edges=edges, point=point, point_normal=point_normal, label=label
    )
