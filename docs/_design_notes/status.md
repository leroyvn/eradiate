# Status and roadmap

**Living document.** Reflects branch `two` as of **2026-07-26**. The health section
below is measured, not reasoned about — re-run the checks and rewrite it rather than
trusting it. The design files it references
([`architecture.md`](architecture.md), [`configuration_layer.md`](configuration_layer.md),
[`kernel_interface.md`](kernel_interface.md)) change far more slowly.

*Consolidated from [`archive/two_assessment.md`](archive/two_assessment.md) and
[`archive/two.md`](archive/two.md).*

## What exists

Branch `two`, 8 commits ahead of `main`, 4421 lines added, all additive — no v1 code
modified.

| Layer                                         | Modules                                                                                      | Tech                     | State                        |
| --------------------------------------------- | -------------------------------------------------------------------------------------------- | ------------------------ | ---------------------------- |
| `two/core/` — configuration                   | `spectrum`, `material`, `surface`, `illumination`, `atmosphere`, `measurement`, `experiment` | Pydantic v2 + `Registry` | partial                      |
| `two/kernel/` — Mitsuba                       | `scene_object`, `scene`, `spectra`, `materials`, `backend`                                   | attrs + Mitsuba objects  | working prototype            |
| `two/backend.py`                              | `Backend` ABC                                                                                | —                        | interface only               |
| `two/repr_html.py`, `two/units_formatting.py` | HTML repr for attrs and Pydantic objects                                                     | 498 lines                | works, off the critical path |

Also: four playground notebooks under `playgrounds/two/` exercising the kernel layer.

The kernel layer runs end to end — scene construction, spectral update loop, notebook
demos. The configuration layer is a sketch. **The two never meet**:
`MitsubaBackend._setup_global` is the only bridge, and its module does not import.

## Health

Measured 2026-07-26 with `pixi run -e dev`.

**Tests** — `pytest tests/two`: 11 passed, 2 failed. Both failures are stale
expectations, not design problems.

- `tests/two/kernel/test_scene_object.py:25` — expects a `_mi_object` field; renamed to
  `_object`.
- `tests/two/kernel/test_scene.py:42` — asserts `_OBJECT_TYPES_TO_SECTIONS` and
  `_SECTIONS_TO_OBJECT_TYPES` are mutual inverses. They are not (`"material"` versus
  `"bsdf"`). The invariant is genuinely broken; see
  [`kernel_interface.md`](kernel_interface.md).

**Imports**

- `eradiate.two.core` — clean.
- `eradiate.two.kernel.backend` — **fails**. Three causes:
  `core/experiment.py` `SphericalShellGeometry.planet_radius: pint.Quantity` without
  `arbitrary_types_allowed`; `BaseGeometry` referenced at `core/experiment.py:21` before
  its definition at line 28; `Experiment` used in four signatures of
  `kernel/backend.py` and never imported.
- `ParticleLayer` — builds, cannot be instantiated: `ParticleProperties` and
  `ParticleDistribution` are undefined.

**Serialization** — `model_dump()` works; `model_dump_json()` raises
`PydanticSerializationError: Unable to serialize unknown type: pint.Quantity`.

**Coverage gaps** — no tests for the configuration layer at all: no validation tests, no
registry dispatch tests, no serialisation round-trip.

## Roadmap

Ordered. Each item has an acceptance criterion, so "done" is checkable.

1. **Fix the seam.** `core/experiment.py` (forward reference, `arbitrary_types_allowed`)
   and `kernel/backend.py` imports.
   *Done when* `import eradiate.two.kernel.backend` succeeds. Nothing downstream is
   testable before this.
2. **`QuantityField` annotated type** ([`configuration_layer.md`](configuration_layer.md)).
   *Done when* every configuration class round-trips through
   `model_validate(model_dump_json(...))` with units preserved, and the per-field
   `field_validator` boilerplate is gone.
3. **Collapse the kernel spectra and materials into thin wrappers**
   ([`architecture.md`](architecture.md)).
   *Done when* `two/kernel/spectra.py` contains no evaluation logic and adding a
   configuration spectrum type requires no kernel-side change.
4. **Generic child traversal and geometry-aware `parameters_changed`**
   ([`kernel_interface.md`](kernel_interface.md)).
   *Done when* `Material.updating_children` is gone, shared objects update once, and a
   geometry updater provably triggers exactly one rebuild per context.
5. **One vertical slice.** `AtmosphereExperiment` → `MitsubaBackend.process` → one
   measurement, mono mode, diffuse surface, directional illumination.
   *Done when* it produces a `DataTree` and the result is compared against v1 for the
   same configuration. This is the first artefact that validates the backend split —
   nothing in the branch validates it today.
6. **Tests.** Fix the two stale ones; add configuration-layer coverage (validation,
   registry dispatch, JSON round-trip).
   *Done when* `pytest tests/two` is green and the configuration layer has non-zero
   coverage.

Items 2 and 3 are independent of each other and both precede 5.

## Deferred, tracked elsewhere

- **Spectral loop and result storage redesign** — see
  [`spectral_loop.md`](spectral_loop.md) and [`result_storage.md`](result_storage.md).
  Not started. It intersects roadmap item 5 (the vertical slice): the slice is the first
  thing that would exercise the loop driver and the `DataTree` output, so decide whether
  it is built on the new design or on a throwaway loop before starting it. Independent
  of items 1–4.
- **Documentation** — user manual reorganization, wider tutorial coverage, and porting
  the numerical methods document (ATBD) to Sphinx. Not blocked by anything above.
- **Testing, regression and benchmarking framework** — see
  [`testing_framework.md`](testing_framework.md). Item 6 above is the minimum for v2
  development; that note describes the target.
- **`repr_html.py` / `units_formatting.py`** — 498 lines of HTML repr written before an
  experiment runs. Works, generic over attrs and Pydantic. Leave it; do not extend it
  until the configuration/backend seam is settled.
