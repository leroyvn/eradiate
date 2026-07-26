# Mono Variant Wavelength Support: Design Notes

> **Superseded.** Condensed into [`../kernel_interface.md`](../kernel_interface.md),
> §"Wavelength handling". This copy retains the full C++ excerpts and the key-files
> reference. Kept for reference; not maintained.

## Context

This document summarizes findings from an exploration of Mitsuba's codebase
(eradiate-mitsuba) to assess the feasibility of introducing wavelength
information in monochromatic variants. The goal is to support plugins like
`measured` (measured BSDF) in mono mode, and more broadly to allow spectrum
plugins to evaluate at a specific wavelength rather than assuming
panchromaticity.

## Current State of Mono Variants

In monochromatic mode:

- `Spectrum` type is `Color<Float, 1>` — a single scalar value.
- `Wavelength` type is `Color<Float, 0>` — **zero-sized, no wavelength data**.
- `sample_wavelength()` is a no-op returning `{ {}, 1.f }`.
- Rays and interactions carry zero-sized `wavelengths` fields.
- Spectral data is converted to grayscale via `luminance()` in
  `Properties::get_texture_impl()` (panchromatic assumption).

Defined in `include/mitsuba/core/traits.h`.

## Current Eradiate Workaround

Eradiate bypasses the panchromatic assumption by pre-evaluating all spectral
quantities at the target wavelength on the Python side. The render loop iterates
over `KernelContext` objects (one per wavelength). Spectral values are computed
in Python and injected as uniform scalars into the Mitsuba scene via the
parameter update system.

Only two Eradiate-specific C++ plugins (`ocean_legacy`, `ocean_grasp`) receive a
raw wavelength value as a plugin property (`m_wavelength`). This per-plugin
property approach is functional but impractical to scale.

## Proposed Design: Global `set_wavelength()`

### Mechanism

Introduce a process-wide global wavelength value following the Logger /
FileResolver pattern (static variable + free getter/setter with
`MI_EXPORT_LIB`):

- **Header** (`include/mitsuba/core/spectrum.h`):

  ```cpp
  extern MI_EXPORT_LIB void set_wavelength(float wavelength);
  extern MI_EXPORT_LIB float wavelength();
  ```

- **Implementation** (`src/core/spectrum.cpp`):

  ```cpp
  static float __wavelength = 0.f;  // 0 = unset
  void set_wavelength(float wavelength) { __wavelength = wavelength; }
  float wavelength() { return __wavelength; }
  ```

- **Python binding**: Exposed as `mi.set_wavelength()` / `mi.wavelength()`.

### Properties

- Process-wide, not thread-local (consistent with all other Mitsuba global
  state).
- Opt-in: plugins that don't read it continue with panchromatic behavior.
- A value of 0 (or similar sentinel) signals "unset".
- Called once per spectral iteration in Eradiate's render loop, before
  `mi.render()`.

### Compatibility with Panchromatic Default

The global wavelength does **not** change the default mono behavior. Plugins
that don't opt in continue to work panchromatically. This creates a semantic
split within mono mode (some plugins panchromatic, others monochromatic at a
specific wavelength), but this is acceptable because Eradiate controls the full
scene construction and never relies on Mitsuba's built-in spectral-to-mono
conversion.

## Application: `measured` BSDF Plugin

### Current Limitation

The `measured` plugin (`src/bsdfs/measured.cpp`) explicitly rejects mono mode in
its constructor (line 108-113). It checks `is_spectral_v<Spectrum>` and throws
if false.

### How It Works in Spectral Mode

Spectral data is stored as a 5D array `[phi_i, theta_i, wavelength, grid_y,
grid_x]` in a `Marginal2D<Float, 3, true>`. At evaluation time, for each
spectral channel:

```cpp
Float params_spec[3] = { phi_i, theta_i, si.wavelengths[i] };
spec[i] = m_spectra.eval(sample, params_spec, active);
```

The `Marginal2D` interpolation engine is variant-agnostic — it just takes float
parameters and interpolates.

### Required Changes

1. **Constructor**: Remove the `is_spectral_v` gate to allow mono mode to load
   spectral `.bsdf` files.
2. **`eval()` and `sample()`**: Use `mitsuba::wavelength()` instead of
   `si.wavelengths[i]` when `is_monochromatic_v<Spectrum>`.
3. No changes needed to data loading or the `Marginal2D` setup.

## Application: Spectrum Plugins

### Plugins That Could Benefit

| Plugin      | Data                      | Interpolation                  | Current mono behavior    |
|-------------|---------------------------|--------------------------------|--------------------------|
| `regular`   | Regularly-spaced samples  | Linear, O(1)                   | Not implemented (throws) |
| `irregular` | Irregularly-spaced samples| Linear + binary search, O(log n)| Not implemented (throws) |
| `blackbody` | Temperature parameter     | Analytic (Planck's law)        | Not implemented (throws) |
| `srgb`      | 3 polynomial coefficients | Analytic (Jakob 2019 model)    | Returns luminance        |
| `d65`       | Delegates to `regular`    | Via `regular`                  | Expands to `uniform`     |

### Caching Strategy

Since the global wavelength changes only once per spectral iteration (not per
ray), spectrum plugins can cache the interpolated value:

```cpp
mutable ScalarFloat m_cached_wavelength = 0.f;
mutable ScalarFloat m_cached_value = 0.f;

UnpolarizedSpectrum eval(...) const override {
    if constexpr (is_monochromatic_v<Spectrum>) {
        ScalarFloat wl = mitsuba::wavelength();
        if (wl != m_cached_wavelength) {
            m_cached_value = /* interpolate at wl */;
            m_cached_wavelength = wl;
        }
        return m_cached_value;
    } else if constexpr (is_spectral_v<Spectrum>) {
        // existing spectral code path
    }
}
```

This avoids per-ray interpolation costs entirely — the per-ray cost becomes a
float comparison + cached value return.

### Impact on Eradiate

This would simplify Eradiate's architecture:

- `regular` and `irregular` spectrum plugins could be used directly in mono mode
  with their full spectral data, instead of being pre-evaluated in Python and
  replaced with `uniform`.
- The Python-side `SceneParameter` lambdas that evaluate spectra at each
  wavelength could be eliminated for these cases.
- Scene construction becomes simpler: pass spectral data to Mitsuba and let it
  handle wavelength evaluation internally.

## Key Files Reference

- Variant/traits: `include/mitsuba/core/traits.h`
- Spectrum global state: `include/mitsuba/core/spectrum.h`, `src/core/spectrum.cpp`
- Global state patterns: `src/core/logger.cpp`, `src/core/fresolver.cpp`
- Python bindings: `src/python/alias.cpp`, `src/core/python/`
- Measured BSDF: `src/bsdfs/measured.cpp`
- Spectrum plugins: `src/spectra/{uniform,regular,irregular,blackbody,srgb,d65}.cpp`
- Interpolation: `include/mitsuba/core/distr_1d.h`, `include/mitsuba/core/distr_2d.h`
- Eradiate mode system: `src/eradiate/_mode.py`
- Eradiate render loop: `src/eradiate/kernel/_render.py`
- Eradiate kernel dict: `src/eradiate/kernel/_kernel_dict.py`
- Eradiate ocean plugins: `src/eradiate/scenes/bsdfs/_ocean_legacy.py`, `_ocean_grasp.py`

## Open Questions

- Should `set_wavelength()` trigger variant change callbacks or be independent?
- Should plugins error when mono mode is used without `set_wavelength()` being
  called, or fall back to panchromatic behavior?
- Should `ocean_legacy` and `ocean_grasp` be migrated from the per-plugin
  `m_wavelength` property to the global `set_wavelength()` mechanism?
- Should `Properties::get_texture_impl()` be updated to evaluate at the global
  wavelength instead of integrating to luminance when `set_wavelength()` is set?
