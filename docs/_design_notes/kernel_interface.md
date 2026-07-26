# Kernel interface

How v2 talks to Mitsuba: object lifetime, the update protocol, and wavelength handling.
See [`architecture.md`](architecture.md) for the layer split this sits inside.

*Consolidated from [`archive/two.md`](archive/two.md),
[`archive/two_assessment.md`](archive/two_assessment.md) and
[`archive/feature_mono_wavelength.md`](archive/feature_mono_wavelength.md).*

## Early instantiation

**Settled.** v1 builds a scene by assembling a nested `KernelDict` template and calling
`mi.load_dict()` once at the end. v2 instantiates Mitsuba objects as scene elements are
created, and assembles the scene from live objects.

Two reasons: memory (a large template duplicates data that the kernel object already
holds), and accessibility (an instantiated object can be inspected, evaluated and
updated before a scene exists).

The property that makes this work, verified in `tests/two/kernel/test_scene.py:49-71`:
Mitsuba objects are reference-counted, so a wrapper holds a pointer. Updating an object
that has been inserted into a scene propagates into that scene, and the same object may
be referenced from several places without being copied.

## `SceneObject`

**Settled.** The prototype's central abstraction, and it earns its place: a Mitsuba
object, a mapping of scene parameter paths to update callables, and a cached
`mi.traverse()` result.

```python
SceneObject(
    {"type": "uniform", "value": 0.0},          # dict or live mi.Object
    {"value": lambda ctx: eval_at(ctx.si)},     # path -> f(KernelContext) -> value
)
```

`update(ctx)` evaluates every updater against a `KernelContext` and pushes the results
through the cached `SceneParameters`. Coordinating updates through a single context
object is what makes the spectral loop a loop over contexts rather than a loop over
special cases.

Extension required by [`architecture.md`](architecture.md): a `children` list plus one
generic traversal with a `visited` set, replacing per-class `update()` overrides.

## `Scene` and parameter paths

**Settled** in structure, **Proposed** in naming.

`Scene` groups scene objects into ordered sections (phase functions, media, materials,
shapes, emitters) and builds the `mi.Scene` from them. Insertion rewrites Mitsuba object
IDs, so IDs are not a reliable handle — the Python-side dicts are. Parameter paths,
however, are built from those IDs and *are* user-visible:

```
02_bsdf_lambertian.reflectance.value
```

The `02` is currently the index of `materials` in `Scene._SECTIONS`. Reordering that
list silently changes every path a user has written down and every path stored in a
regression reference. The prefix should be a **fixed string per section**, not a
positional index. Determinism is the goal; ordering is not the way to get it.

The prototype also disagrees with itself here: `_OBJECT_TYPES_TO_SECTIONS` keys on
`"material"` while `_SECTIONS_TO_OBJECT_TYPES` emits `"bsdf"`. Pick one vocabulary.

## The update protocol, and its trap

**Settled** as a rule, **Proposed** as an implementation.

`tests/two/kernel/test_scene.py:73-111` establishes the behaviour that has to be
designed around:

| Update issued through                          | BVH / kd-tree rebuild |
| ---------------------------------------------- | --------------------- |
| Scene-level `SceneParameters`, by assignment   | yes                   |
| Scene-level `SceneParameters`, in place (`+=`) | **no**                |
| A floating object's own `SceneParameters`      | **no**                |
| `mi_scene.parameters_changed()`                | yes                   |

Since `SceneObject.update()` goes through the object's own parameters, geometry updates
never trigger a rebuild. This is harmless for spectra and textures — the overwhelming
majority of updates — and silently wrong for geometry.

Rule: **updaters declare whether they affect geometry.** `Scene.update()` runs the
traversal, and if any geometry-affecting updater fired, calls `parameters_changed()`
once at the end. One rebuild per context at most, and never a missed one.

## Wavelength handling

### Baseline

**Settled** — this is what the prototype does today, and it works.

In mono variants Mitsuba's `Wavelength` type is `Color<Float, 0>`: zero-sized, no
wavelength data. Spectral quantities are therefore evaluated **in Python** at the
current spectral index, and injected into the scene as uniform scalars through the
update protocol. Every kernel spectrum is a `uniform` plugin driven by an updater.

This is why the update protocol exists in its current form, and why `KernelSpectrum` is
a single class rather than a hierarchy.

### Proposed: a global `set_wavelength()` in Mitsuba

**Proposed.** A kernel change, not yet made. It would let plugins evaluate spectral data
themselves in mono mode.

Mechanism: process-wide state, following the existing Logger / FileResolver pattern.

```cpp
// include/mitsuba/core/spectrum.h
extern MI_EXPORT_LIB void set_wavelength(float wavelength);
extern MI_EXPORT_LIB float wavelength();
```

Exposed to Python as `mi.set_wavelength()` / `mi.wavelength()`, called once per spectral
iteration before `mi.render()`. Properties:

- Process-wide, not thread-local — consistent with all other Mitsuba global state.
- Opt-in: plugins that ignore it keep their panchromatic behaviour. This creates a
  semantic split within mono mode, acceptable because Eradiate controls scene
  construction end to end and never relies on Mitsuba's spectral-to-mono conversion.
- Sentinel value (0) means unset.
- `set_variant()` resets it to 0, via a variant change callback
  ([mitsuba3#1367](https://github.com/mitsuba-renderer/mitsuba3/pull/1367)), so a fresh
  variant keeps the panchromatic behaviour mono variants have today.

Because the value changes once per spectral iteration and not per ray, plugins cache:

```cpp
mutable ScalarFloat m_cached_wavelength = 0.f, m_cached_value = 0.f;
// in eval(): if (wl != m_cached_wavelength) { m_cached_value = interpolate(wl); ... }
```

Per-ray cost becomes a float comparison.

### Consequences for Eradiate

This is the reason the proposal matters here: it changes the shape of the update
protocol. `regular` and `irregular` spectrum plugins could carry their full spectral
data into the kernel instead of being pre-evaluated in Python and replaced by `uniform`.
The corresponding updaters — the bulk of them — disappear.

**Settle this before hardening the updater protocol.** Building the protocol first and
the kernel change second means rewriting every updater.

### Consumers

- **`measured` BSDF** — currently rejects mono mode outright (`is_spectral_v` gate in
  its constructor). Three changes: drop the gate; use `mitsuba::wavelength()` instead of
  `si.wavelengths[i]` in `eval()` and `sample()` when `is_monochromatic_v<Spectrum>`;
  nothing to change in data loading or the `Marginal2D` interpolation setup, which is
  variant-agnostic.
- **Spectrum plugins** — `regular`, `irregular` and `blackbody` currently throw in mono
  mode; `srgb` returns luminance; `d65` expands to `uniform`. All could evaluate at the
  global wavelength.
- **`ocean_legacy` / `ocean_grasp`** — the only Eradiate plugins receiving a wavelength
  today, via a per-plugin `m_wavelength` property. That approach does not scale:
  **decided** — both migrate to the global mechanism, and `m_wavelength` is dropped.
  This removes their wavelength parameter from the kernel dict and the updaters that
  set it.

## Deferred kernel work

**Open**, one line each — listed so they are not forgotten:

- **LLVM variant support.** Vectorized execution changes the cost model of per-context
  updates.
- **Single-precision support.** v1 is double-precision in practice.

## Open questions

From the feasibility study:

- Should plugins error when mono mode is used without `set_wavelength()` having been
  called, or fall back to panchromatic behaviour?
- Should `Properties::get_texture_impl()` evaluate at the global wavelength instead of
  integrating to luminance when a wavelength is set?

And the cross-cutting one, restated because it gates work elsewhere: the updater
protocol cannot be finalised until the `set_wavelength()` decision is made.
