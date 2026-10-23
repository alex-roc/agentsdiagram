"""From "old text, new text" to the smallest set of line edits (for LSP ``TextEdit``s) and diffs."""

from __future__ import annotations

import difflib
from dataclasses import dataclass


@dataclass(frozen=True)
class LineEdit:
    """Replace lines ``[start, end)`` (0-based) with ``text``."""

    start: int
    end: int
    text: str


def line_edits(before: str, after: str) -> list[LineEdit]:
    a = before.splitlines(keepends=True)
    b = after.splitlines(keepends=True)
    edits: list[LineEdit] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag != "equal":
            edits.append(LineEdit(i1, i2, "".join(b[j1:j2])))
    return edits


def unified_diff(rel: str, before: str | None, after: str) -> str:
    lines = difflib.unified_diff(
        (before or "").splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile="/dev/null" if before is None else f"a/{rel}",
        tofile=f"b/{rel}",
    )
    return "".join(line if line.endswith("\n") else line + "\n" for line in lines)
