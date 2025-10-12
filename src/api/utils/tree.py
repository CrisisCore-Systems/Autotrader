"""Helper utilities for working with execution trees."""

from __future__ import annotations

from typing import Any, Dict


def serialize_tree_node(node: Any) -> Dict[str, Any]:
    """Serialize a TreeNode-like object to a dictionary structure.

    Args:
        node: Node with ``key``, ``title``, ``description``, optional ``outcome`` and
            ``children`` attributes.

    Returns:
        Recursive dictionary capturing the essential node data.
    """

    serialized = {
        "key": getattr(node, "key", ""),
        "title": getattr(node, "title", ""),
        "description": getattr(node, "description", ""),
        "outcome": None,
        "children": [],
    }

    outcome = getattr(node, "outcome", None)
    if outcome:
        serialized["outcome"] = {
            "status": getattr(outcome, "status", None),
            "summary": getattr(outcome, "summary", None),
            "data": getattr(outcome, "data", {}) if hasattr(outcome, "data") else {},
        }

    children = getattr(node, "children", [])
    serialized["children"] = [serialize_tree_node(child) for child in children]

    return serialized
