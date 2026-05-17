# Package Metadata Cleanup Plan

## Trigger

Dependency lane license reports show the internal package `autotrader 0.1.0` as `UNKNOWN` across multiple lanes.

## Problem

The project package metadata does not currently provide enough license information for license-report tooling to classify the internal package cleanly.

## Goal

Add explicit package license metadata in a future implementation step so lane license reports no longer flag the internal package as UNKNOWN.

## Evidence

Observed UNKNOWN internal package metadata in:

- runtime lane
- broker lane
- market-data lane
- mlops lane

## Proposed metadata fields

Future implementation should review and update package metadata in `pyproject.toml`, including:

- license expression
- license file reference if applicable
- project authors/maintainers if missing
- package classifiers if used
- project URLs if useful

## Decision

Do not patch package metadata in this planning step.

Document the required cleanup first, then apply the metadata fix in a focused follow-up PR.

## Non-goals

- No dependency movement
- No license allow-list changes
- No workflow changes
- No runtime behavior changes
- No broker or strategy changes
- No trading automation changes

## Boundary

This plan does not change `requirements.txt`, `pyproject.toml`, workflows, runtime imports, broker code, strategy code, execution behavior, live ports, order sizing, or trading automation.