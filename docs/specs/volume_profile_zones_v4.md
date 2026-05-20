# Volume Profile Zones V4

## Purpose

This document defines the next execution-research slice after raw profile accounting and smoothed profile geometry.

V4 does not emit traps yet. It defines how profile state becomes a compact internal zone model that can later be translated into `StructuralTrapSignal`.

The design goal is to preserve the existing separation of concerns:

- raw profile provides deterministic accounting anchors
- smoothed profile provides geometric structure candidates
- zone extraction combines those two layers into explicit, testable structural hypotheses
- signal emission remains a later step

## Why V4 Exists

V3 established two clean surfaces inside `VolumeProfileDetector`:

- raw accounting via `point_of_control()` and `value_area()`
- smoothed geometry via HVN and LVN extraction

That is enough to describe acceptance and shape, but not enough to decide which regions are structurally actionable.

Without an intermediate zone layer, the detector would have to jump directly from profile summaries to order-facing signal objects. That would collapse accounting, interpretation, and execution intent into one step and make later debugging ambiguous.

## Scope

V4 covers:

1. a minimal `VolumeProfileZone` schema
2. deterministic eligibility rules for a small number of zone archetypes
3. a test matrix for converting profile state into zones

V4 does not cover:

- `StructuralTrapSignal` emission
- coordinator deployment policy
- execution-side sizing changes
- live trap invalidation rules derived from profile zones

## Non-Goals

- do not encode full trading logic inside zone extraction
- do not let smoothed geometry overwrite raw accounting anchors
- do not create overlapping zone families just to increase coverage
- do not optimize zone rules for fill count before they are falsifiable in tests

## Model Statement

V4 introduces an explicit zone layer between profile state and trap intent.

At a high level:

- raw profile defines where volume was accepted
- smoothed profile defines local structural concentrations and voids
- zone extraction accepts only combinations that satisfy both layers
- later signal logic can react to price interaction with those zones

The resulting architecture is:

1. raw profile
2. smoothed profile
3. nodes
4. acceptance anchors
5. eligible zones
6. future trap translation

## Acceptance Anchors

V4 treats the following as deterministic acceptance anchors derived from the raw profile:

- `POC`: highest-volume raw price bin
- `VAH`: upper bound of the raw value area
- `VAL`: lower bound of the raw value area

These anchors are accounting outputs, not interpretive geometry.

## Structure Candidates

V4 treats the following as interpretive structure candidates derived from the smoothed profile:

- `HVN`: locally prominent high-volume node
- `LVN`: locally prominent low-volume node

These candidates express shape, not audited volume totals.

## Internal Zone Schema

V4 introduces a compact internal model such as:


```python
@dataclass(frozen=True)
class VolumeProfileZone:
    symbol: str
    zone_id: str
    zone_kind: str
    directional_bias: str
    lower_bound: float
    upper_bound: float
    reference_price: float
    source_levels: Mapping[str, float]
    metadata: Mapping[str, float | str | bool]
```


### Required Semantics

- `zone_kind`
  - allowed initial values: `value_edge_rejection`, `poc_reversion`, `void_through_value`
- `directional_bias`
  - allowed initial values: `long_reversion`, `short_reversion`
- `lower_bound` and `upper_bound`
  - explicit interaction range for later price tests
- `reference_price`
  - the anchor that best represents the zone thesis
- `source_levels`
  - must record the raw and smoothed components that justified the zone
- `metadata`
  - may store distances, adjacency facts, and confirmation flags, but not execution instructions

## Eligibility Rules

V4 should start with three zone archetypes only.

### 1. Value-Edge Rejection Zone

Intent:

- represent failed acceptance outside value followed by return into value

Long variant:

- latest interaction probes below `VAL`
- a subsequent finalized bar closes back inside value
- `VAL` becomes the reference acceptance edge
- optional strengthening condition: an `LVN` or `HVN` sits within a configurable proximity band around `VAL`

Short variant:

- latest interaction probes above `VAH`
- a subsequent finalized bar closes back inside value
- `VAH` becomes the reference acceptance edge
- optional strengthening condition: an `LVN` or `HVN` sits within a configurable proximity band around `VAH`

Minimum deterministic rule:

- no zone is created from a simple touch of `VAH` or `VAL`
- the zone requires both breach and re-entry confirmation

Suggested bounds:

- zone spans from the breached value edge to the confirming return region
- for a minimal implementation, bounds may be the edge price plus or minus one bin on the acceptance side

### 2. POC Reversion Zone

Intent:

- represent displacement away from accepted value that fails and rotates back toward the highest accepted price row

Long variant:

- price stretches materially below `POC`
- subsequent finalized action rejects lower prices and rotates upward
- `POC` is the reference acceptance magnet

Short variant:

- price stretches materially above `POC`
- subsequent finalized action rejects higher prices and rotates downward
- `POC` is the reference acceptance magnet

Minimum deterministic rule:

- require a configurable minimum distance from `POC` before a zone becomes eligible
- require reclaim or directional rejection evidence, not only proximity

Suggested bounds:

- zone spans the reclaim region between the rejection pivot and the first accepted bin back toward `POC`

### 3. Void-Through-Value Zone

Intent:

- represent failed traversal through a thin-volume region that could not establish new acceptance

Long variant:

- an `LVN` sits near `VAL` or between two `HVN` anchors below or around value
- price enters the thin region, fails to continue lower, and closes back toward thicker acceptance

Short variant:

- an `LVN` sits near `VAH` or between two `HVN` anchors above or around value
- price enters the thin region, fails to continue higher, and closes back toward thicker acceptance

Minimum deterministic rule:

- require a real `LVN` relationship, not just a wide empty-looking range
- require adjacency either to a value edge or between identifiable `HVN` boundaries

Suggested bounds:

- zone spans the `LVN` price and the nearest acceptance boundary it failed to clear

## Adjacency And Proximity Rules

To keep V4 narrow, adjacency should be explicit and deterministic.

Recommended initial rules:

- a node is adjacent to `VAH`, `VAL`, or `POC` if it lies within `adjacency_bins` bins or `adjacency_bps` basis points
- if both bin-based and bps-based thresholds are implemented, both thresholds must be recorded in metadata
- if multiple candidate nodes satisfy the same condition, choose the nearest by absolute distance
- if absolute distance ties, choose the lower-price node

These rules preserve deterministic behavior that matches the existing POC and value-area tie-break philosophy.

## Public API Boundary

V4 should add an internal zone-construction seam before `detect()` emits anything.

Example shape:


```python
def extract_zones(self, finalized_bars: Sequence[Dict[str, Any]]) -> List[VolumeProfileZone]:
    ...
```


Expected behavior:

- `extract_zones(...)` updates or reuses the current profile state
- `detect(...)` may call `extract_zones(...)`, but in V4 it should still return `[]`
- tests in this slice should validate zone construction only

## Test Matrix

V4 is not valid without explicit zone-construction tests.

Minimum required tests:

- no zones are emitted when there is insufficient profile state
- value-edge rejection long zone requires breach below `VAL` and confirmed close back inside value
- value-edge rejection short zone requires breach above `VAH` and confirmed close back inside value
- touching `VAH` or `VAL` without re-entry confirmation does not produce a zone
- POC reversion zone requires minimum displacement from `POC`
- POC reversion zone is rejected when price stays near `POC` without a meaningful stretch
- void-through-value zone requires an `LVN` that is adjacent to a value edge or bracketed by `HVN` anchors
- void-through-value zone is rejected when the thin region is not tied to a legitimate `LVN`
- when multiple candidate nodes qualify, nearest-node selection is deterministic
- when nearest-node distance ties, lower-price selection wins
- `detect(...)` still returns `[]` in V4 even if `extract_zones(...)` finds valid zones

## Output Requirements

Each extracted zone should record enough provenance to explain why it exists.

Minimum zone output fields:

- `zone_kind`
- `directional_bias`
- `lower_bound`
- `upper_bound`
- `reference_price`
- raw acceptance anchors used
- smoothed nodes used
- proximity or adjacency measurements used
- confirmation facts used to qualify the zone

This is required so later signal translation can be debugged without re-deriving the profile state by hand.

## Recommended Implementation Order

### Slice 1: Zone Schema And Extraction Hook

Goal:

- add `VolumeProfileZone`
- add `extract_zones(...)`
- keep `detect(...)` non-emitting

Validation target:

- deterministic zone construction tests only

### Slice 2: Value-Edge And POC Zones

Goal:

- implement the two acceptance-led archetypes first

Validation target:

- focused tests for breach, re-entry, displacement, and tie-break behavior

### Slice 3: Void-Through-Value Zones

Goal:

- add the first geometry-led archetype that still references acceptance anchors

Validation target:

- focused tests for LVN adjacency and failed traversal behavior

## Decision Standard

V4 should only continue if zone construction remains easier to inspect than direct signal emission would have been.

Success for this specification does not mean profitable traps. Success means:

- accounting anchors remain deterministic
- geometry remains interpretive but explicit
- zone eligibility is reproducible
- signal emission is still isolated from the profile-to-zone translation layer

## Initial Recommendation

Implement `VolumeProfileZone` and `extract_zones(...)` first, with `value_edge_rejection` and `poc_reversion` as the initial archetypes.

Those are the cheapest discriminating cases because they rely most directly on the raw acceptance anchors that are already validated, while still forcing the new zone abstraction to prove its value before trap emission begins.

