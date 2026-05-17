# Lane License Warning Report Design

## Purpose

Design a non-blocking CI warning layer for dependency lane license reports.

## Inputs

- runtime lane license report
- broker lane license report
- market-data lane license report
- mlops lane license report

## Output

A readable CI summary showing review-sensitive license findings per lane.

## Warning categories

- UNKNOWN
- GPL
- LGPL
- AGPL
- MPL
- Zope
- CNRI
- complex AND/OR expressions
- linking-exception expressions

## Behavior

The warning report must:

- parse lane artifact JSON
- group findings by lane
- print a readable summary
- upload or expose the summary
- never fail the build

## Non-enforcement statement

This design does not introduce a CI gate.

## Boundary

No requirements.txt changes.
No pyproject.toml changes.
No dependency movement.
No license allow-list changes.
No runtime behavior changes.
No trading behavior changes.
