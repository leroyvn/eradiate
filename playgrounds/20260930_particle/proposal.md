# Atmosphere components: nomenclature, dict interface, class hierarchy

Status: draft proposal, 2026-09-30, branch `partfield`.
Companion files: `interface.py` (dict examples), `hierarchy.py` (class
skeletons and the state-driven evaluation sketch).

## 1. Diagnosis

Problems in the current branch, most structural first:

1. **Components are atmospheres.** `MolecularAtmosphere`, `ParticleEnsemble`
   and `ParticleField` derive from `AbstractHeterogeneousAtmosphere`. They
   therefore carry `id`, `geometry`, `scale`, `force_majorant` and
   `extremum_resolution`. The container then forbids some of these (the
   validators reject `scale`) and overwrites others (`update()` replaces
   `geometry` and `id`). One consequence showed up while writing
   `playgrounds/scratch.py`: a component validates its `(n_x, n_y)` arrays
   against its *own* default geometry before the container replaces it, so
   the user must pass the same geometry to every component.
2. **The container has one slot per component kind.** `molecular_atmosphere`
   is a single slot, `particle_ensembles` is a list, and `particle_field` is a
   single slot with no dict converter. Each new component kind needs a new
   slot, a new converter and a new branch in `components`.
3. **`ParticleEnsemble` accepts two input models.** The first is an
   AOT-driven layer: scalar `tau_ref` at `w_ref`, spread over
   [`bottom`, `top`] by a 1D vertical distribution. The second is a per-column
   variant with `(n_x, n_y)` values for `tau_ref`/`bottom`/`top` and a 3D
   `ArrayParticleDistribution`. The second is gridded extinction, but it is
   written as a normalised shape times a column optical thickness.
4. **`ParticleProperties` switches type on dataset shape.**
   `has_size_distribution` tests for `reff`/`veff` dimensions.
   `ParticleEnsemble` requires `False` and `ParticleField` requires `True`,
   so the class stands for two types. `reff`/`veff` are also hardcoded as the
   only possible extra dimensions.
5. **`ParticleProfile` hardcodes variable names** (`reff`, `veff`,
   `mass_concentration`). This rules out other parametrizations such as
   humidity-dependent aerosols.
6. **`ParticleFieldPhaseFunction` is named after its only consumer**, not
   after what it does (per-voxel phase lookup in state-variable space). Its
   fields (`r_eff_volume`, `v_eff_grid`, ...) repeat the reff/veff hardcoding.
7. **"Distribution" is ambiguous.** `ParticleDistribution` is the vertical
   shape of the particle number fraction. Now that particle *size*
   distributions (reff/veff) are in the codebase, the name is misleading.
8. **Field names are inconsistent**: `particle_properties` in
   `ParticleEnsemble` vs `properties` in `ParticleField`.

## 2. Unifying observation

Every component can be described as a **profile** plus a set of
**properties**:

| Component | profile (state in space) | properties (state → optics) |
|---|---|---|
| molecular | p, T, x_i (thermoprops) | absorption database + Rayleigh |
| particle, state-driven | amount, reff, veff (or rh, ...) | single-scattering table indexed by (w, state) |
| particle, AOT-driven | none: user gives τ(w_ref) and a vertical shape | table indexed by w (spectral shape of ext, ssa, phase) |
| particle, extinction-driven | none: user gives σ_t(w, x, y, z), ϖ(w, x, y, z) | phase only |

The draft's `profile`/`properties` pair therefore becomes the general
vocabulary. The AOT and extinction components are the cases where the user
supplies some or all of the optics directly.

## 3. Nomenclature

| Term | Meaning |
|---|---|
| component | Named constituent of a heterogeneous atmosphere. It contributes σ_t, ϖ and a phase function on the render grid. |
| `profile` | Dataset of state variables over space: 1D (z) or 3D (x, y, z), stored dense or sparse. |
| `properties` | Lookup table mapping (w, state variables) to optical properties. |
| state variable | Profile variable used as an index into `properties` (reff, veff, rh, ...). Identified by name, not hardcoded. |
| amount variable | Profile variable that scales the per-unit-amount extinction: mass or number concentration. |
| `density` | Normalised vertical shape of the particle number in a `particle_aot` component. Replaces "distribution" (see §1.7). |

Type ids name the **input data**, not the spatial extent: `molecular`,
`particle_aot`, `particle_extinction`, `particle_state`. `particle_state`
names the path from position to optics: space → state variables → table.
Class names mirror type ids: type id `particle_aot` gives class `ParticleAOTComponent`.
The `Component` suffix is kept even though it makes names long: the dict
interface is the concise entry point.

## 4. Class hierarchy

```
Atmosphere (ABC)                                  [unchanged]
├── HomogeneousAtmosphere          "homogeneous"   [unchanged]
└── HeterogeneousAtmosphere        "heterogeneous" container, holds components: dict[str, AtmosphereComponent]

AtmosphereComponent (ABC)          no id, no geometry; evaluated on a grid passed by the container
├── MolecularComponent             "molecular"
└── ParticleComponent (ABC)        has_absorption, has_scattering, force_polarized_phase
    ├── ParticleAOTComponent            "particle_aot"
    ├── ParticleExtinctionComponent     "particle_extinction"
    └── ParticleStateComponent          "particle_state"         name-agnostic core
        └── ParticlePSDComponent        "particle_psd"           preset: state (reff, veff)
```

Supporting classes:

| Class | Role | Current name |
|---|---|---|
| `ParticleProperties` | Single-scattering table indexed by (w, *state_dims); `state_dims` may be empty | same name; `has_size_distribution`/`reff`/`veff` replaced by `state_dims`/`state_coords` |
| `ParticleProfile` | Profile dataset, dense or sparse, arbitrary variables | same name, generalised |
| `ParticlePhaseFunction` | Phase function indexed by w only (spatially uniform) | unchanged |
| `GriddedParticlePhaseFunction` | Phase function looked up per voxel from state variables (1 or 2 state dimensions) | `ParticleFieldPhaseFunction` |
| `VerticalDensity` + `UniformDensity`, `ExponentialDensity`, `GaussianDensity`, `ArrayDensity`, `InterpolatorDensity` | 1D vertical shapes for `particle_aot` | `ParticleDistribution` + subclasses (the 3D array support is removed) |

I kept `ParticleProperties` and `ParticleProfile` as names. Their problems
were the hardcoded dimension and variable names, not the class names, and
the field names `properties`/`profile` now match them.

### 4.1 Responsibilities

- **`HeterogeneousAtmosphere`** owns `id`, `geometry`, `scale`,
  `force_majorant`, `extremum_resolution` and `use_mis`. It validates the
  shapes of component inputs against its geometry (fixes §1.1). It sums
  σ_t and σ_s over components and mixes the phase functions with
  `MultiPhaseFunction` (unchanged). The kernel id of each component is
  `f"{atmosphere.id}_{name}"`, so names must be valid identifiers.
- **`AtmosphereComponent`** implements `eval_sigma_t(si, grid)`,
  `eval_sigma_s(si, grid)`, `eval_albedo(si, grid)`, `phase(geometry)`,
  `eval_mfp(ctx, grid)` and `bottom`/`top`. It stores no geometry.
- **`ParticleComponent`** holds the absorption/scattering switches and the
  polarized-phase flag, which are shared by the three particle kinds.

### 4.2 Component fields

| Component | Fields |
|---|---|
| `molecular` | `profile` (thermoprops, 1D or 3D), `properties` (absorption database), `rayleigh_depolarization`, `has_absorption`, `has_scattering`, `error_handler_config` |
| `particle_aot` | `bottom`, `top`, `density`, `aot_ref`, `w_ref` (all scalar), `properties` (state-free table) |
| `particle_extinction` | `sigma_t`, `albedo` (DataArray, dims ⊆ (w, x, y, z)), `phase` (phase function spec, or state-free table from which only the phase is used) |
| `particle_state` | `profile`, `properties` (table with state dims), `amount` (optional), `state_variables` (optional mapping) |
| `particle_psd` | same fields as `particle_state`; `amount`/`state_variables` fixed by the preset |

`particle_extinction` takes `phase` rather than `properties` because only the
phase function is used. A table's `ext`/`ssa` would be silently ignored, so
the field name should not suggest otherwise. `phase` accepts any
`PhaseFunction` spec (`{"type": "hg", "g": 0.85}`), or a dataset/keyword
converted to `ParticlePhaseFunction`.

`particle_aot` does not support per-column AOT (`aot_ref` as a 2D array);
`particle_extinction` covers that case with σ_t computed by the user. If
per-column AOT is needed later, it will be added as a helper
(`ParticleExtinctionComponent.from_aot(...)`), not by making `particle_aot`
accept arrays.

## 5. Dict interface

```python
atmosphere = {
    "type": "heterogeneous",
    "geometry": {...},                   # optional, usually set by the experiment
    "extremum_resolution": (32, 32, 32),
    "components": {
        "molecular": {
            "type": "molecular",
            "profile": {"identifier": "afgl_1986-us_standard"},  # joseki.make() kwargs
            "properties": "monotropa",
        },
        "aerosols": {
            "type": "particle_aot",
            "bottom": 0.0 * ureg.km,
            "top": 2.0 * ureg.km,
            "density": {"type": "exponential", "rate": 5.0},
            "aot_ref": 0.2,
            "w_ref": 550.0 * ureg.nm,
            "properties": "govaerts_2021-continental",
        },
        "smoke": {
            "type": "particle_extinction",
            "sigma_t": sigma_t,             # xr.DataArray, dims ⊆ (w, x, y, z), units attr
            "albedo": albedo,               # xr.DataArray, same rules
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

Shorthand: a bare component dict passed as an atmosphere is wrapped in a
single-component container named after its type. `atmosphere={"type":
"molecular"}` (common on main) therefore keeps working. Components get their
own factory, `atmosphere_component_factory`, and `atmosphere_factory` keeps
the containers (`heterogeneous`, `homogeneous`) plus the wrapping rule.

See `interface.py` for complete examples.

## 6. State-driven family: name-agnostic core

`ParticleStateComponent` evaluates as follows (sketch in
`hierarchy.py`):

1. **State dimensions** are the dimensions of `properties` other than
   `w`, `phamat`, `iangle` and `imom`. For example, `(reff, veff)`,
   `(rh,)`, or `()`.
2. **Binding.** `state_variables: dict[str, str]` maps each table dimension
   to a profile variable. By default the names are the same.
3. **Amount.** `amount` names the profile variable that scales `ext`. If it
   is unset, the component picks the unique profile variable for which
   `amount × ext` has units of inverse length. Mass or number
   concentration is therefore selected from the units, not from the
   variable name. If zero or several variables match, the component raises
   an error.
4. **Evaluation.** The profile is resampled onto the render grid. Then `ext`
   and `ssa` are interpolated in (w, state) per voxel, and
   `σ_t = amount · ext` and `ϖ = ssa`.
5. **Phase.** With no state dimension, the component uses
   `ParticlePhaseFunction`. With 1 or 2 state dimensions, it uses
   `GriddedParticlePhaseFunction` (the kernel plugin interpolates
   bilinearly; a single dimension is padded with a degenerate second axis).
   With more than 2, it raises `NotImplementedError` until the kernel plugin
   is generalised.

Presets (currently only `particle_psd`) only fix
the binding and the required variables, add unit checks, and carry the
documentation for their parametrization. They contain no evaluation code.

## 7. Data formats

| Format | Change |
|---|---|
| `aer_core_v2` | Unchanged. It is the state-free case. |
| `prt_v1` (amended) | Any dimension beyond those of `aer_core_v2` is a state dimension and must have a coordinate with units. `ext` is extinction per unit amount (1/length per mass or number concentration). |
| `ppr_v1` (amended) | Required: `x_levels`/`y_levels`/`z_levels`, plus either a sparse layout (`index` dimension with `i_x`/`i_y`/`i_z`) or a dense layout (dimensions `x`, `y`, `z`). Other variables are free but must have units. |
| extinction input | `xr.DataArray` with a `units` attribute. Dims ⊆ (w, x, y, z); missing dims are broadcast. `w` is interpolated linearly; spatial coordinates are cell centres. |

`prt_v1` and `ppr_v1` were introduced on this branch and never released, so
they are amended in place (specs in `docs/data/formats/aer.rst` and
`docs/data/formats/profile.rst`) rather than versioned. Existing branch files
are regenerated if needed.

## 8. Deprecation aliases

Only names released on main get an alias. Names introduced on this branch
(`ParticleEnsemble`, `ParticleField`, `ParticleFieldPhaseFunction` and their
type ids) are replaced without alias.

| Old | New |
|---|---|
| `HeterogeneousAtmosphere(molecular_atmosphere=m)` | `components={"molecular": m}` |
| `HeterogeneousAtmosphere(particle_layers=[p0, p1])` | `components={"particle_layer_0": p0, ...}` |
| `MolecularAtmosphere(thermoprops=, absorption_data=)` | `MolecularComponent(profile=, properties=)` |
| `ParticleLayer` / `"particle_layer"` | `ParticleAOTComponent` / `"particle_aot"` |
| `tau_ref`, `distribution`, `particle_properties` | `aot_ref`, `density`, `properties` |
| `ParticleDistribution` + subclasses | `VerticalDensity` + subclasses |
| `atmosphere={"type": "molecular", ...}` | wrapped automatically (§5) |

## 9. Open questions

1. **Resampling accuracy.** `ParticleProfile` resamples z by
   nearest-neighbour lookup. This does not conserve the column optical
   thickness when the profile and render layers differ. Conservative
   (overlap-weighted) averaging of σ_t would preserve τ. This is an accuracy
   vs cost choice to make before `ppr_v1` is finalised.
2. **State out of table range** (e.g. reff beyond the tabulated range):
   clamp, raise, or treat the voxel as empty. The current branch behaviour
   should be checked and documented.
