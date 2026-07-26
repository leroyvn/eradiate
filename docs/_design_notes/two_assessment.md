# Assessment of the `two` prototype

*Status as of 2026-07-26, branch `two` (8 commits ahead of `main`, 4421 lines added,
all additive — no v1 code modified).*

This note records what the `eradiate.two` experiments have taught us, so the design of
the next iteration can be settled before more code is written. It complements
[`two.md`](two.md), which lists the intended evolutions; this document reports on what
was actually built and what it revealed.

## 1. What exists

| Layer | Modules | Tech | Status |
|---|---|---|---|
| `two/core/` — configuration | `spectrum`, `material`, `surface`, `illumination`, `atmosphere`, `measurement`, `experiment` | Pydantic v2 + hand-rolled `Registry` | partially working |
| `two/kernel/` — Mitsuba | `scene_object`, `scene`, `spectra`, `materials`, `backend` | attrs + Mitsuba objects | working prototype |
| `two/backend.py` | `Backend` ABC: `validate` / `process` / `postprocess` / `run` | — | interface only |
| `two/repr_html.py`, `two/units_formatting.py` | 498 lines | attrs + Pydantic HTML repr | works, off the critical path |

Supporting material: four playground notebooks (`playgrounds/two/`) exercising the
kernel layer, and three design notes (`two.md`, `feature_mono_wavelength.md`,
`testing_framework.md`, `refactoring_class_machinery.md`).

## 2. Does it run

**Tests** — 11 pass, 2 fail. Both failures are stale expectations, not design problems:

- `tests/two/kernel/test_scene_object.py:25` expects a `_mi_object` field; the attribute
  was renamed to `_object` and the test was not updated.
- `tests/two/kernel/test_scene.py:42` asserts that `_OBJECT_TYPES_TO_SECTIONS` and
  `_SECTIONS_TO_OBJECT_TYPES` are mutual inverses. They are not: the former keys on
  `"material"`, the latter emits `"bsdf"`. The ID prefix is therefore `02_bsdf_*` while
  the lookup key is `material`. The invariant the test asserts is genuinely broken.

**Imports**

- `eradiate.two.core` imports cleanly.
- `eradiate.two.kernel.backend` **fails to import**:
  - `core/experiment.py`: `SphericalShellGeometry.planet_radius: pint.Quantity` with no
    `arbitrary_types_allowed` in the model config →
    `PydanticSchemaGenerationError`.
  - `core/experiment.py:21`: `BaseGeometry` referenced before its definition at line 28.
  - `kernel/backend.py`: `Experiment` used in four signatures, never imported.
- `ParticleLayer` builds but cannot be instantiated: `ParticleProperties` and
  `ParticleDistribution` are undefined (`PydanticUserError: not fully defined`).
- `model_dump()` works; **`model_dump_json()` fails** with
  `PydanticSerializationError: Unable to serialize unknown type: pint.Quantity`.

**Summary**: the kernel layer is exercised end-to-end (scene construction, spectral
update loop, notebook demos). The configuration layer is a sketch. The two never meet —
`MitsubaBackend._setup_global` is the only bridge, and the module it lives in does not
import.

## 3. Lessons

### 3.1 `SceneObject` is the right primitive

Colocating the Mitsuba object, an updater mapping, and a cached `mi.traverse` result
works well. `test_scene.py:49-71` establishes the property that matters:
`SceneObject` instances behave as pointers, so updating a "floating" object propagates
into the scene without going through the scene-level parameter tree. Early
instantiation (as opposed to dict templates) delivers what `two.md` asked for. Keep this
design.

### 3.2 Floating updates skip `parameters_changed`

`test_scene.py:73-111` documents the counterpart: parameter updates issued from a
floating object do **not** trigger a BVH / kd-tree rebuild. This is harmless for spectra
and textures, and silently wrong for geometry. `Scene.parameters_changed()` exists but
nothing calls it.

*Next iteration*: tag updaters as geometry-affecting or not; have `Scene.update` call
`parameters_changed()` once at the end of a traversal in which any geometry updater
fired.

### 3.3 Child updates are per-class boilerplate

`Material.updating_children()` plus its `update()` override exist solely to recurse into
the `reflectance` spectrum. The two TODOs at `kernel/scene.py:168-169` ask for precisely
what a generic mechanism would provide.

*Next iteration*: give `SceneObject` a `children: list[SceneObject]` attribute and
implement a single traversal with a `visited` set. This removes the `Material` override,
the double-update-of-shared-objects TODO, and the update-children TODO in one change.

### 3.4 The spectrum hierarchy is duplicated across layers

`core/spectrum.py` provides `UniformSpectrum`, `InterpolatedSpectrum` and
`SolarIrradianceSpectrum`, each with `eval_mono` / `eval_ckd` / `integral`.
`kernel/spectra.py` reimplements `InterpolatedSpectrum` — including the interpolation
itself — on top of `SceneObject`.

Note what the kernel class actually does: it loads `{"type": "uniform", "value": 0.5}`
and registers `lambda ctx: float(self._eval_kernel(ctx.si))`. Every kernel spectrum is a
uniform plugin driven by a Python-side evaluation. One class therefore suffices:

```python
class KernelSpectrum(SceneObject):
    def __init__(self, spectrum: core.BaseSpectrum, quantity):
        super().__init__(
            {"type": "uniform", "value": 0.0},
            {"value": lambda ctx: float(spectrum.eval(ctx.si).m_as(uck.get(quantity)))},
        )
```

No parallel hierarchy, no duplicated interpolation, and a new configuration spectrum
type requires no kernel-side code at all. The same treatment applies to materials once
more than `diffuse` exists.

### 3.5 Pint × Pydantic is the unsolved problem

This is the issue that decides whether the configuration layer works at all. Current
state:

- `ConfigDict(arbitrary_types_allowed=True)` repeated in six classes.
- A `field_validator(mode="before")` per quantity field, each re-doing `ensure_units`.
- Unit-versus-quantity compatibility checked ad hoc in `model_validator(mode="after")`;
  `spectrum.py` contains two near-identical ~30-line blocks.
- No JSON serialisation whatsoever.

Since serialisation/deserialisation is the stated reason to adopt Pydantic, this is the
primary gap. It calls for one annotated type, written once:

```python
Wavelength = Annotated[pint.Quantity, QuantityField(quantity="wavelength")]
```

with `__get_pydantic_core_schema__` performing coercion and the compatibility check, and
a serialiser emitting `{"value": ..., "units": ...}`. That single object also implements
the `two.md` item on retiring the `<field>_units` dict syntax, and it replaces roughly
150 lines currently spread across `spectrum`, `illumination`, `surface` and
`atmosphere`.

### 3.6 The registry is justified; its boilerplate is not

Pydantic's native discriminated unions require a closed union. Backend-registered types
require an open one, so the hand-rolled `Registry` plus wrap-validator dispatch is the
correct call. But the identical six-line `_dispatch` classmethod is copy-pasted into
seven classes.

*Next iteration*: fold the dispatch into the `Object` base class via `__init_subclass__`,
with the registry declared as a class attribute. The per-module noise disappears.

### 3.7 Scene IDs leak section ordering into parameter paths

Parameter paths look like `02_bsdf_lambertian.reflectance.value`. The `02` is the index
of `materials` within `Scene._SECTIONS`. Reordering that list silently changes every path
a user has written down, and every path stored in a regression reference.

The prefix exists to make paths deterministic, which is right. Make it a fixed string per
section rather than a positional index.

### 3.8 Premature work

498 lines of HTML repr machinery exist before a single experiment runs. The code works
and is generic over attrs and Pydantic. It is polish on an API that will change; leave it
in place, do not extend it until the configuration/backend seam is settled.

## 4. Recommended order of work

1. **Fix the seam.** `core/experiment.py` (geometry forward reference,
   `arbitrary_types_allowed`) and `kernel/backend.py` imports. Nothing downstream is
   testable until `MitsubaBackend` imports.
2. **Implement the `QuantityField` annotated type** (§3.5). This blocks serialisation,
   which is the point of the Pydantic migration. Do it before writing more configuration
   classes.
3. **Collapse the kernel spectra and materials into thin wrappers** over `core` objects
   (§3.4).
4. **Generic child traversal and geometry-aware `parameters_changed`** in `SceneObject` /
   `Scene` (§3.2, §3.3).
5. **Complete one vertical slice**: `AtmosphereExperiment` → `MitsubaBackend.process` →
   one measurement, mono mode, diffuse surface, directional illumination. This is the
   smallest artefact that validates the backend split, and nothing in the branch
   validates it today.
6. **Tests**: fix the two stale ones; add configuration-layer coverage (validation,
   registry dispatch, JSON round-trip). There is currently none.

## 5. Open questions

- **Backend split.** `Backend` is a three-method ABC with a single, incomplete
  implementation. What is the *second* backend (1D two-stream? a libRadtran-style
  solver?)? Its requirements determine whether `process` / `postprocess` is the right
  seam. Designing an abstraction against one implementation is how abstractions end up
  wrong.
- **Measurement and the spectral loop.** `BaseMeasurement` is an empty registry stub.
  Does the spectral loop live in the backend or in a shared driver? The current sketch
  implies backend-side (`_setup_spectral`), which would duplicate the SPP-distribution
  logic described in `two.md` in every backend.
- **Mono wavelength support.** The global `set_wavelength()` proposed in
  `feature_mono_wavelength.md` removes the "pre-evaluate everything in Python"
  constraint that `KernelSpectrum` is built around. If it lands, updaters shrink
  drastically. Decide before locking the updater protocol.
