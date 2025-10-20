"""Tree-of-Thought execution scaffolding for the Hidden-Gem Scanner."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Literal, Optional

NodeStatus = Literal["success", "failure", "skipped"]


@dataclass
class NodeOutcome:
    """Represents the result of executing a tree node."""

    status: NodeStatus
    summary: str
    data: Dict[str, Any] = field(default_factory=dict)
    proceed: bool = True


@dataclass
class TreeNode:
    """Tree-of-Thought node with executable action and children."""

    key: str
    title: str
    description: str
    action: Optional[Callable[[Any], Optional[NodeOutcome]]] = None
    children: List["TreeNode"] = field(default_factory=list)
    outcome: Optional[NodeOutcome] = None

    def add_child(self, child: "TreeNode") -> "TreeNode":
        self.children.append(child)
        return child

    def run(self, context: Any) -> "TreeNode":
        proceed = True
        if self.action is not None:
            outcome = self.action(context)
            if outcome is None:
                outcome = NodeOutcome(status="success", summary="", data={}, proceed=True)
            self.outcome = outcome
            proceed = outcome.proceed
        if proceed:
            for child in self.children:
                child.run(context)
        else:
            for child in self.children:
                child.outcome = NodeOutcome(
                    status="skipped",
                    summary="Skipped due to parent outcome",
                    data={},
                    proceed=False,
                )
        return self

    def iter_nodes(self) -> Iterable["TreeNode"]:
        yield self
        for child in self.children:
            yield from child.iter_nodes()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "description": self.description,
            "outcome": None
            if self.outcome is None
            else {
                "status": self.outcome.status,
                "summary": self.outcome.summary,
                "data": self.outcome.data,
            },
            "children": [child.to_dict() for child in self.children],
        }
