# Handover — RAMI4ATM regression suite cleanup

Branch: `claude/rami4atm-regression-cleanup-fp3bo8` (pushed).
This file is a working note, not part of the deliverable: drop it before the
branch is merged.

## What landed

Three commits, in order:

| Commit | Subject |
| --- | --- |
| `d7226fe` | Pipelines: Add SRF-weighted variance output |
| `41e2ab2` | Tests: Rework the RAMI4ATM test case definitions |
| `2e0f3e5` | Tests: Compare radiance_srf in the RAMI4ATM regression suite |

(SHAs are from this container; they change if the branch is rebased.)

### 1. Pipeline — `<var>_srf_var`

`ZTest` keys its standard error on `<variable>_var`, and the pipeline built
`<var>_srf` but no variance for it, so no noise-aware comparison could be made
on a band-integrated quantity. `apply_spectral_response()` now takes an
`is_variance` flag, and `pipelines/definitions.py` adds a `<var>_srf_var` node
wherever `<var>_var` and `<var>_srf` both exist.

The coefficients of the SRF weighting were factored out into
`spectral_response_weights()`. This matters for correctness, not just tidiness:
`apply_spectral_response()` resamples onto the union of the data and SRF grids
with `method="nearest"`, which replicates one bin's estimate across several
nodes. Those replicas are perfectly correlated, so squaring the *node* weights —
the way `aggregate_ckd_quad()` legitimately does for its quadrature — would
understate the variance. Squaring the per-bin coefficients does not.

### 2. RAMI4ATM case definitions

`registry` (a dict of dicts) → `CASES`, a dict of `rami4atm.Case` objects
carrying ready-built `RegressionTest` instances. The defaults the test module
used to invent with `.get(...)` now live in the definitions, which is what makes
them usable outside pytest. Constructors return experiments only — the SRF
identifier they used to return alongside existed solely to hand-roll an
SRF-weighted variance.

Also: `benchmarks/benchmarks/bench_rami4atm.py` was importing
`create_rami4atm_hom00_bla_sd2s_m03_z30a000_brfpp`, which no longer existed —
the benchmark module could not import at all. It is now built on `CASES`.
`tests/03_regression/rami4atm/test_rami4atm_benchmark.py` was renamed to
`test_rami4atm.py` (it is a regression test *of* the RAMI4ATM benchmark
scenarios, not a benchmark).

`hom00_bla_a00s_m04_z30a000_brfpp` left `CASES`: it is an analytic check that a
black surface under an absorbing-only atmosphere returns zero, and keeping it in
the registry forced the test module to filter it back out by name. It still has
its own test, built through `create_toa()`.

### 3. Tested variable

RAMI4ATM criteria moved from `radiance` to `radiance_srf`.

## What could NOT be verified here, and why

This container has **no `eradiate` install, no Mitsuba kernel, no `pixi`, and an
empty `resources/data`** (the `eradiate-data` submodule is not checked out).
`python -c "import eradiate"` fails on `numpy`. So nothing that imports the
package was run.

Verified:

- `ruff check` and `ruff format --check` clean across `src`, `tests`,
  `benchmarks`.
- `python -m py_compile` on every modified module.
- No dangling references: `rg 'create_rami4atm|rami4atm\.registry|postprocess_boa_cases|test_rami4atm_benchmark'` is empty.
- **The pipeline refactor was validated numerically in isolation.** The pre- and
  post-change `apply_spectral_response()` were extracted with `ast`, executed
  against a stubbed SRF and synthetic CKD data, and compared: the mean is
  reproduced to a max relative deviation of **7.8e-16** at 1, 2, 16 and 30 bins,
  with identical name, attrs, dims and coords. The new unit test's assertions
  were mirrored in that harness and hold at every bin count. The harness is at
  `<scratchpad>/check_srf.py`; it is disposable, not part of the deliverable.

Not run, and needing a real environment:

```shell
pytest tests/01_unit/pipelines/test_logic.py          # new is_variance tests
pytest tests/03_regression/rami4atm --collect-only    # parametrisation
python -c "import benchmarks.benchmarks.bench_rami4atm"
pytest tests -m regression -k rami4atm --plot --artefact-dir <dir>
pytest tests/02_system/test_regression_framework.py
```

## Left pending — needs a run to resolve

1. **Framework self-check constants.**
   `tests/02_system/test_regression_framework.py` carries a `TODO`: the measured
   family p-values in the `BIAS` comment (0.03 → 0.05, 0.05 → 4e-4,
   0.10 → 3e-11) and the "~2 % per-pixel relative standard deviation" were
   measured on the per-bin `radiance` and no longer apply. Re-measure by running
   `pytest tests/02_system/test_regression_framework.py` and record the new
   numbers. The derivable part is already updated: n drops from 1216
   (76 viewing angles × 16 CKD bins) to 76, so the Šidák-corrected
   per-comparison level at `THRESHOLD = 1e-4` is ~1.3e-6, a rejection past
   ~4.85 sigma.

2. **RAMI4ATM Z-test thresholds** (`0.005`, and `0.05` for the m03 case, in
   `_toa_case`). Two effects push the same way and could produce false failures:
   the smaller n loosens the Šidák correction, so each pixel is easier to
   reject; and until references are regenerated the Z-test finds no
   `radiance_srf_var` in them, warns, and falls back to the result variance
   alone — conservative by up to √2. Regenerate the references first (below),
   then re-run before touching any threshold.

3. **Reference regeneration** — recommended, not required.

   ```shell
   pytest tests -m regression -k rami4atm --force-regen --plot \
       --artefact-dir <dir>
   git -C resources/data diff        # review, then commit in eradiate-data
   ```

   Why it is not required: the tested variables keep their names. `radiance_srf`
   is already in the TOA references (references are dumped whole), and the BOA
   references still hold `hdrf` and `bhr` under those names. Only the *archived
   auxiliary* variables of the BOA cases were renamed (`radiance_srf1/2`,
   `radiosity_srf3/4` → `radiance_target`, `radiance_white`,
   `radiosity_target`, `radiosity_white`, each with a `_var` sibling), and the
   references gain `radiance_srf_var`, which is what restores the full-precision
   Z-test.

## Known issues found but deliberately left alone

- **`bhr` cannot be charted.** `radiosity_srf` is summed over the film, so
  `bhr` is a scalar while the plotting code lays a variable out against `vza`.
  `RMSETest.plot()` on it will fail under `--plot`. This predates these commits
  (the old `postprocess_boa_cases` produced a scalar `bhr` too) and is not
  RAMI4ATM-specific — it belongs with the plotting code.
- **`radiosity` has no pipeline variance.** `postprocess_boa` derives one as the
  film-sum of `sector_radiosity_srf_var`, neglecting inter-pixel covariance, and
  says so in `_total_radiosity_var`. The alternative — a `radiosity_var`
  pipeline node — is a modelling decision worth making deliberately rather than
  as a side effect of this cleanup. Note that the code being replaced was worse:
  it stored a per-pixel array under a name suggesting a global scalar, and
  normalised the mean by the sum of the SRF weights but the variance by their
  sum of squares.
- **The BOA cases still use `RMSETest`.** `postprocess_boa` now emits `hdrf_var`
  and `bhr_var` that no criterion consumes; they are kept in the archived
  dataset because they are exactly what a future `ZTest` on `hdrf` would need.
- **Other suites still test `radiance`.** `spherical` and the CKD ocean case
  could move to `radiance_srf` for the same reason, now that the variance
  exists. Out of scope here.
- **`test_cases/ocean.py` has a `has_atmoshphere` typo** in its public
  signature. Untouched — not RAMI4ATM.
