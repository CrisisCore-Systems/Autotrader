"""Runtime compatibility patches for third-party libraries."""

from __future__ import annotations

import inspect
from typing import ForwardRef

_forward_ref_evaluate = getattr(ForwardRef, "_evaluate", None)
if _forward_ref_evaluate is not None:
    signature = inspect.signature(_forward_ref_evaluate)
    param = signature.parameters.get("recursive_guard")
    if param is not None and param.default is inspect._empty:
        def _forward_ref_eval_compat(self, globalns, localns, type_params=None, *, recursive_guard=None):
            if recursive_guard is None:
                recursive_guard = set()
            return _forward_ref_evaluate(self, globalns, localns, type_params, recursive_guard=recursive_guard)

        ForwardRef._evaluate = _forward_ref_eval_compat  # type: ignore[attr-defined]
