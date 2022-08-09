from __future__ import annotations

from typing import TYPE_CHECKING

import attrs
from rich import get_console
from rich.tree import Tree

if TYPE_CHECKING:
    from codetiming import Timer  # type: ignore
    from rich.console import Console, RenderResult, ConsoleOptions  # type: ignore
    from codetiming._timers import Timers  # type: ignore


@attrs.define
class TimerReport:
    timer: Timer
    console: Console = attrs.field(factory=get_console)

    @property
    def timers(self) -> Timers:
        return self.timer.timers

    def make_tree(self) -> Tree:
        root = Tree("Times")
        # sort timers by depth such that output resembles:
        # > [(0, "other"), (0, "one"), (1,"one>two"), (2,"one>two>three")]
        timer_names = sorted(
            [(len(k.split(">")) - 1, k) for k in self.timers.keys()], key=lambda k: k[0]
        )
        branches = dict()

        for _, name in timer_names:
            _time = self.timers[name]
            leaf_name = name.split(">")[-1]
            parent_name = name.split(">")[:-1][-1] if ">" in name else leaf_name
            entry = f"{leaf_name} - {_time}"

            if parent_name == leaf_name:
                branches[leaf_name] = root.add(entry)
                continue

            try:
                # parent name is assured defined due to earlier depth sort (if it has a timer)
                branches[leaf_name] = branches[parent_name].add(entry)
            except KeyError:
                # if it does not have a timer, use grandparent or root.
                grandparent = name.split(">")[-3]
                branches[parent_name] = branches[grandparent].add(parent_name)
                branches[leaf_name] = branches[parent_name].add(entry)

        return root

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        yield self.make_tree()
