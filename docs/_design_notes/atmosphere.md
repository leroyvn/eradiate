# Atmosphere components

How a v2 atmosphere is described in the configuration layer: the container, the
component types, their inputs, and the spatial grid they are evaluated on. See
[`configuration_layer.md`](configuration_layer.md) for the Pydantic machinery this
relies on.

*Consolidated from [`archive/atmosphere_proposal/`](archive/atmosphere_proposal/),
written on 2026-09-30 for v1 on branch `partfield_review` and retargeted to v2. The
archived proposal holds the diagnosis of the v1 classes (`ParticleEnsemble`,
`ParticleField`, `ParticleFieldPhaseFunction`), which exist on `partfield_review` only,
and a runnable sketch of the state-driven evaluation (`hierarchy.py`).*

## What changes from the current prototype

`two/core/atmosphere.py` today has `Atmosphere.components: list[AtmosphereComponent]`,
a base component carrying `top`, `bottom`, `has_absorption`, `has_scattering`, and two
components, `MolecularAtmosphere` and `ParticleLayer`. `ParticleLayer` cannot be
instantiated (see [`status.md`](status.md)). This note replaces that sketch:

| Current (`two/core`) | Replacement |
|---|---|
| `Atmosphere.components: list` | `HeterogeneousAtmosphere.components: dict[str, AtmosphereComponent]` |
| `top`, `bottom` on every component | fields on `particle_ot` only; derived from the data elsewhere |
| `MolecularAtmosphere` / `"molecular"` | `MolecularComponent` / `"molecular"` |
| `MolecularAtmosphere.absorption_database` | `MolecularComponent.properties` |
| `ParticleLayer` / `"particle_layer"` | `ParticleOTComponent` / `"particle_ot"` |
| `particle_properties`, `tau_ref`, `distribution` | `properties`, `ot_ref`, `density` |
| `ParticleDistribution` (undefined) | `VerticalDensity` + subclasses |

v2 is a new API: no deprecation aliases. The table above, extended with the v1 names in
the archived proposal (§9), is input for a v1-to-v2 migration guide, not for code.

v1 (`eradiate.scenes.atmosphere`, with PR #632) already implements most of this note
and serves as the reference implementation. Deprecated aliases mentioned below exist in
v1 only, until 2.0.0.

## Unifying observation

**Settled.** Every component is a **profile** (state variables over space) plus
**properties** (a map from state to optical properties). The component types differ by
how much of the optics the user supplies directly:

| Component | profile | properties |
|---|---|---|
| molecular | p, T, x_i (thermophysical profile) | absorption database + Rayleigh |
| particle, state-driven | amount, reff, veff (or hum, ...) | single-scattering table indexed by (w, state) |
| particle, OT-driven | none: τ(w_ref) and a vertical shape | table indexed by w |
| particle, extinction-driven | none: σ_t(w, x, y, z), ϖ(w, x, y, z) | phase function only |

## Nomenclature

**Settled.**

| Term | Meaning |
|---|---|
| component | Named constituent of a heterogeneous atmosphere. Contributes σ_t, ϖ and a phase function on the evaluation grid. |
| `profile` | Dataset of state variables over space, 1D (z) or 3D (x, y, z), dense or sparse. |
| `properties` | Lookup table mapping (w, state variables) to optical properties. |
| state variable | Profile variable used as an index into `properties` (reff, veff, hum, ...). Identified by name, never hardcoded. |
| amount variable | Profile variable scaling the per-unit-amount extinction (mass or number concentration). |
| OT | Optical thickness. |
| `density` | Normalised vertical shape of the particle number in a `particle_ot` component. Replaces "distribution", which now collides with particle *size* distributions. |

Type ids name the **input data**, not the spatial extent: `molecular`, `particle_ot`,
`particle_extinction`, `particle_state`, `particle_ms`. Class names mirror type ids with
a `Component` suffix (`particle_ot` → `ParticleOTComponent`); the dict interface is the
concise entry point.

## Class hierarchy

**Proposed.** Not implemented in v2.

```
Atmosphere (ABC)                                 atmosphere_registry
├── HomogeneousAtmosphere          "homogeneous"
└── HeterogeneousAtmosphere        "heterogeneous"  components: dict[str, AtmosphereComponent]

AtmosphereComponent (ABC)          atmosphere_component_registry
│                                  has_absorption, has_scattering; no geometry
├── MolecularComponent             "molecular"
└── ParticleComponent (ABC)        force_polarized_phase
    ├── ParticleOTComponent             "particle_ot"
    ├── ParticleExtinctionComponent     "particle_extinction"
    └── ParticleStateComponent          "particle_state"   name-agnostic core
        └── ParticleMSComponent         "particle_ms"      preset: state (reff, veff),
                                                           amount mass_concentration
```

Both registries already exist in `two/core/atmosphere.py`; dispatch goes through the
`Object`-level mechanism of [`configuration_layer.md`](configuration_layer.md).

Supporting classes, internal to the particle components:

| Class | Role |
|---|---|
| `ParticleProperties` | Single-scattering table indexed by (w, *state_dims); `state_dims` may be empty |
| `ParticleProfile` | Profile dataset, dense or sparse, arbitrary variables; resampling method per variable |
| `VerticalDensity` + `UniformDensity`, `ExponentialDensity`, `GaussianDensity`, `ArrayDensity`, `InterpolatorDensity` | 1D vertical shapes for `particle_ot`. v1 keeps `ParticleDistribution` and its subclasses as deprecated aliases |

`MolecularComponent` does not use them. Its `profile` is the existing
`AtmosphericProfile` (Joseki, later Skytherm) and its `properties` an AxsDB
`AbsorptionDatabase`; format validation and resampling of the thermophysical profile
stay with those libraries. Molecular and particle components share field *names*, not
field types.

### Responsibilities

- **`HeterogeneousAtmosphere`** holds the components and `scale`. Component names must
  be valid identifiers, since a backend derives object ids from them.
- **`AtmosphereComponent`** evaluates its own physics, as configuration objects do
  ([`architecture.md`](architecture.md)): `eval_sigma_t(si, grid)`,
  `eval_sigma_s(si, grid)`, `eval_albedo(si, grid)`, `bottom`/`top`. It stores no
  geometry and is evaluated on the grid it is given. Its phase function is a
  configuration object; the backend turns it into a kernel phase function.
- **Backend** (`MitsubaBackend`): builds the media, the kernel ids
  (`f"{atmosphere_id}_{name}"`), the per-component phase plugins
  (`ParticlePhaseFunction`, `GriddedParticlePhaseFunction`) and their mixture
  (`MultiPhaseFunction`, weighted by σ_s per component). None of these appear in the
  configuration layer.
- **`AtmosphereExperiment`** validates the shapes of component inputs against its
  geometry's grid, in a `model_validator(mode="after")`. The container cannot do it: in
  v2 the geometry belongs to the experiment, not the atmosphere.

### Component fields

| Component | Fields |
|---|---|
| `molecular` | `profile`, `properties`, `rayleigh_depolarization`, `error_handler_config` |
| `particle_ot` | `bottom`, `top`, `density`, `ot_ref`, `w_ref` (all scalar), `properties` (state-free table) |
| `particle_extinction` | `sigma_t`, `albedo` (dims exactly `w`, `x`, `y`, `z`), `w_out_of_bounds` (`"raise"` or `"extrapolate"`, default `"raise"`), `phase` (required) |
| `particle_state` | `profile`, `properties` (table with 0 to 2 state dims), `amount` (optional), `state_variables` (optional mapping), `phase` (optional) |
| `particle_ms` | as `particle_state`; `amount` defaults to `mass_concentration`, `state_variables` to `{"reff": "reff", "veff": "veff"}`; `properties` must have state dims `(reff, veff)` |

Plus `has_absorption`, `has_scattering` on every component and `force_polarized_phase`
on particle components. Scalar quantities (`bottom`, `top`, `ot_ref`, `w_ref`) use the
`QuantityField` annotated types. v1 accepts `particle_properties`, `tau_ref` and
`distribution` as deprecated aliases of `properties`, `ot_ref` and `density`.

`particle_extinction` takes `phase` rather than `properties`: a table's `ext`/`ssa`
would be silently ignored, so the field name must not suggest otherwise. `phase` has the
same meaning on every particle component: the phase function used for the component.
It is required on `particle_extinction`, which has no table to build one from. On
`particle_state` it is optional and, when set, replaces the phase function built from
`properties`. `phase` accepts a phase function spec (`{"type": "hg", "g": 0.85}`) or a state-free table
reference. This requires a phase function type family in the configuration layer,
which does not exist yet.

`particle_ot` rejects per-column OT: `ot_ref`, `bottom` and `top` are scalars. That case
is `particle_extinction` with σ_t computed by the user; if needed, a
`ParticleExtinctionComponent.from_ot()` helper covers it later.

## Serialisation of component data

**Settled**, following the reference rule of
[`configuration_layer.md`](configuration_layer.md).

`profile`, `properties`, `sigma_t` and `albedo` serialise as references: a dataset
identifier or a file path. An in-memory `xr.Dataset`/`xr.DataArray` is accepted as a
convenience for interactive work, but the resulting configuration does not serialise:
`model_dump_json()` raises and tells the user to write the data to disk and pass the
path. Embedding user arrays in the JSON form is ruled out.

## Dict interface

**Proposed.**

```python
atmosphere = {
    "type": "heterogeneous",
    "components": {
        "molecular": {
            "type": "molecular",
            "profile": {"identifier": "afgl_1986-us_standard"},  # joseki.make() kwargs
            "properties": "monotropa",
        },
        "aerosols": {
            "type": "particle_ot",
            "bottom": {"value": 0.0, "units": "km"},
            "top": {"value": 2.0, "units": "km"},
            "density": {"type": "exponential", "rate": 5.0},
            "ot_ref": 0.2,
            "w_ref": {"value": 550.0, "units": "nm"},
            "properties": "govaerts_2021-continental",
        },
        "smoke": {
            "type": "particle_extinction",
            "sigma_t": "smoke_sigma_t.nc",
            "albedo": "smoke_albedo.nc",
            "phase": {"type": "hg", "g": 0.7},
        },
        "cloud": {
            "type": "particle_ms",
            "profile": "les-ppr_ms_v1.nc",
            "properties": "watercloud-prt_ms_v1.nc",
        },
    },
}
```

Shorthand: a bare component dict given as an atmosphere is wrapped in a
single-component container named after its type, so `{"type": "molecular"}` keeps
working. This keeps the shape of the v1 interface, as
[`architecture.md`](architecture.md) requires. The wrapping rule lives in the
`Atmosphere` dispatch.

## State-driven evaluation

**Proposed.** Sketch and self-check in `archive/atmosphere_proposal/hierarchy.py`.

1. **State dimensions** are the dimensions of `properties.ext` other than `w`: e.g.
   `(reff, veff)`, `(hum,)`, or `()`. More than two raise at validation (`ValueError`),
   until the kernel phase plugin is generalised.
2. **Binding.** `state_variables: dict[str, str]` maps each table dimension to a
   profile variable; same name by default.
3. **Amount.** `amount` names the profile variable scaling `ext`. If unset, the
   component picks, among variables not bound to a state dimension, the unique one for
   which `amount × ext` is an inverse length. Zero or several matches raise.
4. **Evaluation.** Resample the profile onto the evaluation grid, interpolate `ext`
   and `ssa` linearly in (w, state) per voxel; `σ_t = amount · ext`, `ϖ = ssa`. State
   values outside the table range are clamped to its edges.
5. **Phase.** No state dimension: spatially constant phase function. One or two: the
   backend builds a gridded phase lookup (the kernel plugin interpolates bilinearly;
   one dimension is padded with a degenerate axis).

Presets (`particle_ms` only, for now) fix the binding and required variables, add unit
checks and carry the documentation. They contain no evaluation code.

## Data formats

**Settled.** This answers the particle part of the "Data formats" question in
[`configuration_layer.md`](configuration_layer.md). The specs are in
`docs/data/formats/prt.rst`, `ppr.rst` and `aer.rst`.

| Format | Content |
|---|---|
| `prt_core_v1` | State-free single-scattering table. Extensions add state dimensions after `w`, each with a strictly increasing coordinate carrying units; `ext` is then extinction per unit amount. |
| `prt_ms_v1` | `prt_core_v1` with state dimensions `(reff, veff)`. |
| `prt_hum_v1` | `prt_core_v1` with state dimension `(hum,)`. |
| `ppr_core_v1` | Particle profile. Coordinates `x_edges`/`y_edges`/`z_edges` (strictly increasing cell edges; x and y both in length or both in angle units). Data variables dense, dims `(z, y, x)`, names free, with units. |
| `ppr_ms_v1` | `ppr_core_v1` with `reff`, `veff` and `mass_concentration`. |
| `aer_core_v2`, `aer_v1` | Deprecated, superseded by `prt_core_v1`. |
| extinction input | NetCDF holding one DataArray with a `units` attribute. Dims exactly `w`, `x`, `y`, `z`. `w` may be size 1 and is interpolated linearly; outside its range `w_out_of_bounds` applies (`"extrapolate"` holds the edge value, so size-1 + `"extrapolate"` means spectrally constant). |

The sparse profile layout of the archived proposal is dropped.

## Spatial grid

**Proposed.** Adopted from the v1 grid foundation on `partfield_review` (`grid.py`), as
a configuration-layer object.

The geometry (`PlaneParallelGeometry`, `SphericalShellGeometry`) exposes a
`SpatialGrid`; components are evaluated on it.

```
SpatialGrid (ABC)
├── CartesianGrid       plane-parallel geometry
└── SphericalGrid       spherical-shell geometry
```

Members follow one axis-prefixed scheme for x, y and z alike: `{x,y,z}_edges`,
`{x,y,z}_centers`, `n_{x,y,z}_edges`, `n_{x,y,z}_cells`, `{x,y,z}_cell_size`,
`{x,y,z}_extent`. In `SphericalGrid` the x and y quantities are angles (azimuth,
colatitude), so generic code must not assume length units for them. No aliases: the
older names (`levels`, `layers`, `layer_height`, `n_levels`, `azimuths`,
`colatitudes`, ...) are not carried over.

Constructors are keyword-only (`x_edges`, `y_edges`, `z_edges`). Named factories
(`from_extent_and_resolution`, ...) are kept where they read well.

## Open questions

- **Resampling accuracy.** Nearest-neighbour z resampling (v1) does not conserve the
  column optical thickness. `ParticleProfile` picks a method per variable:
  overlap-weighted (conservative) averaging for the amount variable, so τ is
  preserved; amount-weighted averaging for state variables, since a plain volume
  average of reff gives the wrong optics. Undecided: conservative by default or opt-in
  (accuracy against cost). Decide before `ppr_core_v1` is frozen.
- **Mitsuba-specific medium settings.** v1 puts `force_majorant`,
  `extremum_resolution` and `use_mis` on the container. They are majorant-grid and
  sampling settings that only `MitsubaBackend` reads. Configuration fields, or backend
  options? Tied to the measurement/backend questions in
  [`architecture.md`](architecture.md).
- **1D backends.** `particle_extinction` and `particle_state` accept 3D data that a 1D
  solver cannot consume. Rejection belongs in `Backend.validate`; whether a 1D backend
  should instead accept horizontally uniform 3D inputs is undecided.
- **Phase function configuration.** `particle_extinction.phase` needs a phase
  function type family (registry, `hg`, tabulated) in `two/core`, which does not exist.
