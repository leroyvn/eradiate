# Architecture

The v2 object model and the invariants it rests on. Read this first: every other design
note assumes the layer split described here.

*Consolidated from [`archive/two.md`](archive/two.md) and
[`archive/two_assessment.md`](archive/two_assessment.md).*

## What v1 got right

**Settled.** These are kept as they are; they bound the refactor.

- **The 1D solver configuration syntax.** `AtmosphereExperiment` and its dict-based
  configuration are good. v2 keeps the shape of that interface, and changes what
  happens underneath.
- **Mode and variant selection.** The `eradiate.set_mode()` mechanism, encoding Mitsuba
  variant, spectral method, precision and polarization, carries over.
- **Pint-based unit handling.** Units stay pervasive and stay Pint. What changes is the
  machinery that validates them at the configuration boundary (see
  [`configuration_layer.md`](configuration_layer.md)).

Everything else is open to change.

## The layer split

**Settled** in principle, **Open** in its details (see the last section).

v2 separates *what is simulated* from *what computes it*:

```
      configuration                      backend
   ┌───────────────────┐          ┌────────────────────────┐
   │ Experiment        │          │ Backend                │
   │  geometry         │          │  validate(exp)         │
   │  atmosphere       │  ──────► │  process(exp, meas)    │ ──► xr.DataTree
   │  surface          │          │  postprocess(exp,meas) │
   │  illumination     │          │                        │
   │  measurements     │          │  MitsubaBackend        │
   └───────────────────┘          │  (others: 1D solvers)  │
    Pydantic, inert,              └────────────────────────┘
    serializable                   owns all radiometric state
```

The configuration layer (`eradiate.two.core`) holds no kernel state and knows nothing
about Mitsuba. A backend consumes a configuration and produces results. `Backend.run`
is `validate` → `process` → `postprocess`.

The motivation is 1D scenes: a two-stream or discrete-ordinate solver should consume
the same `AtmosphereExperiment` description without a rendering kernel anywhere in
sight. 3D scenes only ever run through Mitsuba.

## Object model rules

Three rules, each extracted from a concrete failure or duplication in the prototype.

### Configuration objects are inert

**Settled.** A configuration object validates its inputs, evaluates its own physics
(a spectrum knows how to evaluate itself at a spectral index), and serializes. It never
holds a kernel object, a kernel parameter path, or anything else a backend owns. This
is what makes a second backend possible at all.

### Kernel objects are thin wrappers

**Settled.** A kernel-side object wraps a Mitsuba object and delegates *evaluation* to
its configuration counterpart. It adds the kernel object and the update protocol,
nothing else.

The prototype violated this: `two/kernel/spectra.py` reimplemented interpolation that
`two/core/spectrum.py` already provides, producing two parallel spectrum hierarchies.
Observe what the kernel class actually does — it loads a `uniform` plugin and registers
a lambda that evaluates the configuration spectrum at the current spectral index. That
is one class, not a hierarchy:

```python
class KernelSpectrum(SceneObject):
    def __init__(self, spectrum: core.BaseSpectrum, quantity):
        super().__init__(
            {"type": "uniform", "value": 0.0},
            {"value": lambda ctx: float(spectrum.eval(ctx.si).m_as(uck.get(quantity)))},
        )
```

Consequence: adding a configuration spectrum type requires no kernel-side code. The
same treatment applies to materials once more than `diffuse` exists.

### Composition is generic

**Settled.** Kernel objects form a tree (a material owns a reflectance spectrum, a
medium owns a phase function). Updating a node must update its children.

The prototype solved this per class: `Material.updating_children()` plus an overridden
`update()`, existing solely to reach one spectrum. Two TODOs left in
`two/kernel/scene.py` asked for the general version. Do it once: `SceneObject` carries a
`children` list, and a single traversal with a `visited` set walks it. That removes the
override, the double-update-of-shared-objects problem, and the missing-children problem
in one change.

## The spectral loop

**Superseded** by [`spectral_loop.md`](spectral_loop.md) and
[`result_storage.md`](result_storage.md), which develop the loop driver, the
driver/backend contract, raw result storage and optional drive caching in full. The
summary below is kept because it states the sample count allocation rule, which those
notes carry over unchanged.

**Proposed.** The loop iterates over a `SpectralGrid`, building a `KernelContext` per
spectral index, and drives the update protocol described in
[`kernel_interface.md`](kernel_interface.md).

Sample count allocation, which v1 gets wrong:

- **Uniform or delta SRF** — apply the requested SPP to each wavelength (mono) or each
  bin (CKD).
- **Band SRF** — apply the requested SPP to the whole band, and distribute it over the
  spectral grid pro rata of each bin's weight in the final measurand.

The second rule is the one that matters for cost: a band measurement should not cost
`n_bins × spp`.

## Open questions

**The second backend.** `Backend` is a three-method abstract interface with exactly one
implementation, itself incomplete. Which solver is the second one — a two-stream code,
a libRadtran-style solver, something else? Its requirements decide whether
`process` / `postprocess` is the right seam. An abstraction designed against a single
implementation is how abstractions end up wrong; resolve this before hardening the
interface.

**Who owns the spectral loop.** *Answered — see
[`spectral_loop.md`](spectral_loop.md), "Who owns what".* The proposal is the shared
driver: it owns iteration, sample count allocation, storage, checkpointing and progress;
the backend owns only a layout declaration and a per-iteration `solve`. The original
question follows. The prototype implies backend-side ownership
(`MitsubaBackend._setup_spectral`). That duplicates the SPP-distribution logic above in
every backend. The alternative is a shared driver that owns the loop and calls into the
backend per spectral index. Decide before the second backend exists, not after.

**Measurement modelling.** `BaseMeasurement` is an empty registry stub. Measurements
are where the spectral loop, the sensor, and the post-processing pipeline meet, so this
question is entangled with both of the above.
