"""Plan and edit: change the code from the diagram (see docs/editing.md).

``plan_edit(root, request)`` analyses the project, finds the nodes named by ``request`` in the
current code and returns the new text of every file it touches. Nothing is written until
``Outcome.write()`` (CLI, ``serve``) or the editor applies the edits (VS Code, through LSP).
"""

from .doc import EditError
from .engine import EDITORS, Outcome, plan_edit
from .session import Change
from .textedit import LineEdit, line_edits, unified_diff

__all__ = ["EDITORS", "Change", "EditError", "LineEdit", "Outcome", "line_edits", "plan_edit", "unified_diff"]
