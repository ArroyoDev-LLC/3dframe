from typing import List, Callable

from threedframe.scad import JointDirector

DirectoryFactoryType = Callable[[List[int]], JointDirector]
