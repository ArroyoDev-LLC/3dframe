# -*- coding: utf-8 -*-
# snapshottest: v1 - https://goo.gl/zC4yUc
from __future__ import unicode_literals

from snapshottest import Snapshot
from snapshottest.file import FileSnapshot

snapshots = Snapshot()

snapshots["test_scad_render 1"] = FileSnapshot("snap_test_scad/test_scad_render 1.scad")

snapshots["test_scad_render[vertices0] 1"] = FileSnapshot(
    "snap_test_scad/test_scad_render[vertices0] 1.scad"
)

snapshots["test_scad_render[vertices1] 1"] = FileSnapshot(
    "snap_test_scad/test_scad_render[vertices1] 1.scad"
)

snapshots["test_scad_render[vertices2] 1"] = FileSnapshot(
    "snap_test_scad/test_scad_render[vertices2] 1.scad"
)
