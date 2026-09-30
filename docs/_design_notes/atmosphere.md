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
| `top`, `bottom` on every component | fields on `particle_aot` only; derived from the data elsewhere |
| `MolecularAtmosphere` / `"molecular"` | `MolecularComponent` / `"molecular"` |
| `MolecularAtmosphere.absorption_database` | `MolecularComponent.properties` |
| `ParticleLayer` / `"particle_layer"` | `ParticleAOTComponent` / `"particle_aot"` |
| `particle_properties`, `tau_ref`, `distribution` | `properties`, `aot_ref`, `density` |
| `ParticleDistribution` (undefined) | `VerticalDensity` + subclasses |

v2 is a new API: no deprecation aliases. The table above, extended with the v1 names in
the archived proposal (§9), is input for a v1-to-v2 migration guide, not for code.

## Unifying observation

**Settled.** Every component is a **profile** (state variables over space) plus
**properties** (a map from state to optical properties). The component types differ by
how much of the optics the user supplies directly:

| Component | profile | properties |
|---|---|---|
| molecular | p, T, x_i (thermophysical profile) | absorption database + Rayleigh |
| particle, state-driven | amount, reff, veff (or rh, ...) | single-scattering table indexed by (w, state) |
| particle, AOT-driven | none: τ(w_ref) and a vertical shape | table indexed by w |
| particle, extinction-driven | none: σ_t(w, x, y, z), ϖ(w, x, y, z) | phase function only |

## Nomenclature

**Settled.**

| Term | Meaning |
|---|---|
| component | Named constituent of a heterogeneous atmosphere. Contributes σ_t, ϖ and a phase function on the evaluation grid. |
| `profile` | Dataset of state variables over space, 1D (z) or 3D (x, y, z), dense or sparse. |
| `properties` | Lookup table mapping (w, state variables) to optical properties. |
| state variable | Profile variable used as an index into `properties` (reff, veff, rh, ...). Identified by name, never hardcoded. |
| amount variable | Profile variable scaling the per-unit-amount extinction (mass or number concentration). |
| `density` | Normalised vertical shape of the particle number in a `particle_aot` component. Replaces "distribution", which now collides with particle *size* distributions. |

Type ids name the **input data**, not the spatial extent: `molecular`, `particle_aot`,
`particle_extinction`, `particle_state`. Class names mirror type ids with a
`Component` suffix (`particle_aot` → `ParticleAOTComponent`); the dict interface is the
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
    ├── ParticleAOTComponent            "particle_aot"
    ├── ParticleExtinctionComponent     "particle_extinction"
    └── ParticleStateComponent          "particle_state"   name-agnostic core
        └── ParticlePSDComponent        "particle_psd"     preset: state (reff, veff)
```

Both registries already exist in `two/core/atmosphere.py`; dispatch goes through the
`Object`-level mechanism of [`configuration_layer.md`](configuration_layer.md).

Supporting classes, internal to the particle components:

| Class | Role |
|---|---|
| `ParticleProperties` | Single-scattering table indexed by (w, *state_dims); `state_dims` may be empty |
| `ParticleProfile` | Profile dataset, dense or sparse, arbitrary variables; resampling method per variable |
| `VerticalDensity` + `UniformDensity`, `ExponentialDensity`, `GaussianDensity`, `ArrayDensity`, `InterpolatorDensity` | 1D vertical shapes for `particle_aot` |

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
| `particle_aot` | `bottom`, `top`, `density`, `aot_ref`, `w_ref` (all scalar), `properties` (state-free table) |
| `particle_extinction` | `sigma_t`, `albedo` (dim `w` required, spatial dims ⊆ (x, y, z)), `w_out_of_bounds` (`"raise"` or `"extrapolate"`, default `"raise"`), `phase` |
| `particle_state` | `profile`, `properties` (table with state dims), `amount` (optional), `state_variables` (optional mapping) |
| `particle_psd` | as `particle_state`; `amount` and `state_variables` fixed by the preset |

Plus `has_absorption`, `has_scattering` on every component and `force_polarized_phase`
on particle components. Scalar quantities (`bottom`, `top`, `aot_ref`, `w_ref`) use the
`QuantityField` annotated types.

`particle_extinction` takes `phase` rather than `properties`: a table's `ext`/`ssa`
would be silently ignored, so the field name must not suggest otherwise. `phase`
accepts a phase function spec (`{"type": "hg", "g": 0.85}`) or a state-free table
reference. This requires a phase function type family in the configuration layer,
which does not exist yet.

`particle_aot` does not accept per-column AOT. That case is `particle_extinction` with
σ_t computed by the user; if needed, a `ParticleExtinctionComponent.from_aot()` helper
covers it later.

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
            "type": "particle_aot",
            "bottom": {"value": 0.0, "units": "km"},
            "top": {"value": 2.0, "units": "km"},
            "density": {"type": "exponential", "rate": 5.0},
            "aot_ref": 0.2,
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
            "type": "particle_psd",
            "profile": "les-ppr_v1.nc",
            "properties": "watercloud-prt_v1.nc",
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

1. **State dimensions** are the dimensions of `properties` other than `w`, `phamat`,
   `iangle`, `imom`: e.g. `(reff, veff)`, `(rh,)`, or `()`.
2. **Binding.** `state_variables: dict[str, str]` maps each table dimension to a
   profile variable; same name by default.
3. **Amount.** `amount` names the profile variable scaling `ext`. If unset, the
   component picks, among variables not bound to a state dimension, the unique one for
   which `amount × ext` is an inverse length. Zero or several matches raise.
4. **Evaluation.** Resample the profile onto the evaluation grid, interpolate `ext`
   and `ssa` in (w, state) per voxel; `σ_t = amount · ext`, `ϖ = ssa`.
5. **Phase.** No state dimension: spatially uniform phase. One or two: the backend
   builds a gridded phase lookup (the kernel plugin interpolates bilinearly; one
   dimension is padded with a degenerate axis). More than two: `NotImplementedError`
   until the kernel plugin is generalised.

Presets (`particle_psd` only, for now) fix the binding and required variables, add unit
checks and carry the documentation. They contain no evaluation code.

## Data formats

**Proposed.** This answers the particle part of the "Data formats" question in
[`configuration_layer.md`](configuration_layer.md). The specs live on
`partfield_review` (`docs/data/formats/aer.rst`, `docs/data/formats/profile.rst`), not on
`two`.

| Format | Content |
|---|---|
| `aer_core_v2` | State-free single-scattering table. Unchanged. |
| `prt_v1` | `aer_core_v2` plus state dimensions: any extra dimension is a state dimension with a coordinate carrying units. `ext` is extinction per unit amount. |
| `ppr_v1` | Particle profile. Required: `x_levels`/`y_levels`/`z_levels`, plus a sparse (`index` with `i_x`/`i_y`/`i_z`) or dense (`x`, `y`, `z`) layout. Other variables free, with units. |
| extinction input | NetCDF holding one DataArray with a `units` attribute. Dim `w` required (may be size 1), interpolated linearly; outside its range `w_out_of_bounds` applies (`"extrapolate"` holds the edge value, so size-1 + `"extrapolate"` means spectrally constant). Spatial dims ⊆ (x, y, z), missing ones broadcast; coordinates are cell centres. |

`prt_v1` and `ppr_v1` were never released, so they are amended in place rather than
versioned.

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

Members follow one axis-suffixed scheme for x, y and z alike: `edges_{x,y,z}`,
`cells_{x,y,z}` (centres), `n_edges_{x,y,z}`, `n_cells_{x,y,z}`,
`cell_size_{x,y,z}`, `extent_{x,y,z}`. In `SphericalGrid` the x and y quantities are
angles, so generic code must not assume length units for them. No aliases: the v1
names (`levels`, `layers`, `layer_height`, ...) are not carried over.

Constructors are keyword-only (`edges_x`, `edges_y`, `edges_z`). Named factories
(`make_onedim_from_levels`) are kept where they read well.

## Open questions

- **Resampling accuracy.** Nearest-neighbour z resampling (v1) does not conserve the
  column optical thickness. `ParticleProfile` picks a method per variable:
  overlap-weighted (conservative) averaging for the amount variable, so τ is
  preserved; amount-weighted averaging for state variables, since a plain volume
  average of reff gives the wrong optics. Undecided: conservative by default or opt-in
  (accuracy against cost). Decide before `ppr_v1` is finalised.
- **State out of table range** (e.g. reff beyond the tabulated range): clamp, raise, or
  treat the voxel as empty. The sketch yields NaN, then zero (empty voxel).
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
