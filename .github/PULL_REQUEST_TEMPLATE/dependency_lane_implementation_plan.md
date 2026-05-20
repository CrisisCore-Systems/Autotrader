---
title: "Dependency Lane Implementation Plan"
branch: dependency-lane-implementation-plan
scope: docs-only, no manifest or workflow changes
files:
  - docs/ci/dependency_lane_implementation_plan.md
---

This PR documents the implementation plan for dependency lane separation in CI and dependency governance. No requirements, pyproject, or workflow files are changed. No runtime, broker, or trading code is affected.

- Documents the rationale, file plan, candidate movements, CI job design, implementation sequence, and boundaries.
- Follows governance and architectural planning milestones.
- Hard boundary: No dependency, workflow, or allow-list changes in this PR.

Ready for review and merge as the final planning milestone before implementation.