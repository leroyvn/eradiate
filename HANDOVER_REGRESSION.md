# Handover — regression testing refactor

**Branch:** `claude/regression-testing-refactor-p1tliq` (pushed)
**Commit:** `dc31090` — *Tests: Decouple regression data management from statistical testing*
**Base:** `7876e70` (same as `fix_regression_testing`)

## What changed

Three layers, cleanly separated:

| Layer | Location | Responsibility |
|---|---|---|
| Statistics + charts | `src/eradiate/test_tools/regression.py` | Criteria only. No I/O, no pytest. |
| Reference data management | `src/eradiate/test_tools/fixtures/_regression.py` (new) | Lookup, regeneration, artefacts, `--plot` gating, report routing. |
| Call sites | `tests/03_regression/**` | One `dataset_regression.check(...)` per case. |

### Key API

```python
# statistical layer — pure comparator, holds a criterion not the data
outcome = ZTest(0.05, variable="radiance").evaluate(result, reference)
fig, axes = test.plot(result, reference, outcome)

# data management
dataset_regression.check(result, ZTest(0.05, variable="radiance"),
                         basename="het01_brfpp_ref")
dataset_regression.check(result, [t1, t2], basename="rami4atm/case-ref")  # shared reference
dataset_regression.reference_path("eovolpath_surface_ref")               # existence probe
```

### The read/write split (the crux)

`pytest_regressions.common.perform_regression_check` takes `datadir` and
`original_datadir` as **independent** arguments. Reads resolve against
`datadir` (a `LazyDataDir` we root at the resolver's location), writes go to
`original_datadir`. That is what makes the file resolver and reference
regeneration coexist:

* **Reads:** `fresolver.resolve("tests/regression_test_references")`.
* **Writes:** `$ERADIATE_SOURCE_DIR/resources/data/tests/regression_test_references/`
  (the eradiate-data submodule), overridable with `--reference-dir`.

Writing back to a resolved path would be a real bug, not just untidy:
`AssetManager` installs files as **symlinks into its unpack cache**
(`_asset_manager.py:294-296`).

### Flags

* `--update-references` → **removed**. Use `--force-regen` / `--regen-all`.
* The strict guard from `67086b0` is preserved: a missing reference fails and
  writes nothing unless a regen flag is passed.
* `--reference-dir` → **new** (overrides both read and write locations).
* `--plot`, `--artefact-dir` → unchanged.

### Reference file names are unchanged

No eradiate-data file needs renaming. `basename` reproduces the existing stems
(`het01_brfpp_ref`, `rpv_afgl1986_brfpp_ref`, `rami4atm/<case>-ref`, …).

## Verified here ✅

Environment used: `uv venv .venv --python 3.12`, `uv pip install -e ".[recommended]" --group test`,
plus `eradiate-mitsuba>=0.5,<0.6` (PyPI kernel) and `pytest-regressions`.
`ERADIATE_SOURCE_DIR=/home/user/eradiate`.

* `pytest tests/01_unit/test_tools` → **48 passed** (26 statistical + 18 fixture + 4 report).
* Full suite **collects** cleanly: 2271 tests.
* Manual end-to-end of the regeneration workflow against a scratch reference dir:
  missing → guard fails and writes nothing; `--force-regen` → creates + fails;
  rerun → passes; perturb → fails, reference untouched; `--force-regen` →
  rewrites, fails; rerun → passes.
* `--plot` routing: bootstrap emits `<basename>.png` (no-reference chart);
  comparison emits `<basename>-<variable>.png`; nothing lands in the reference dir.
* Reference dir resolution in dev mode resolves to the submodule for both read
  and write.
* `ruff check` and `ruff format --check` clean across `src/` and `tests/`.

## NOT verified here ❌ — needs your dev setup

1. **`tests/03_regression/**` never ran.** The `resources/data` submodule is not
   checked out in this container and the simulations need the kernel build +
   data assets. This is the main thing to confirm. Suggested sequence:

   ```bash
   git submodule update --init resources/data
   pixi run test-regression-report          # or:
   pytest tests -m regression --plot --artefact-dir <dir>
   git -C resources/data status --porcelain # must stay EMPTY on a passing run
   ```

   Then exercise regeneration on one case and check the diff is sane:

   ```bash
   pytest tests/03_regression/romc/test_het01.py --force-regen --plot
   git -C resources/data diff --stat
   git -C resources/data checkout .         # discard
   ```

2. **`tests/02_system/test_regression_framework.py`** (type I/II error self-check)
   — adapted to `evaluate()` but not executed; it renders a RAMI4ATM scene.
   `pytest tests/02_system/test_regression_framework.py -m slow`

3. **`pixi.lock` is NOT refreshed.** `pixi.sh` is blocked by this container's
   network policy, so I could not install pixi. Run `pixi lock` (or
   `pixi install`) to pick up the new `pytest-regressions>=2.11` entry added to
   `[dependency-groups].test` in `pyproject.toml`.
   *Not a CI blocker:* `.github/actions/prepare-ci/action.yml:21` installs with
   `pip install .[recommended] --group test`, so CI gets the dependency from
   `pyproject.toml` directly. It only affects `pixi run …` locally.

4. **Docs build** (`make -C docs html`) not run — needs the `docs` env. I did
   verify every symbol referenced from `docs/reference_api/test_tools.rst` is
   importable (`DatasetRegressionFixture`, `RegressionTestOutcome`, …).

5. **Robot report run** (`pytest -p robotframework --plot`) not exercised.
   Report routing goes through the unchanged `ReportLogger`, and the fixture
   unit tests cover the message/fragment flow with a spy, but the Robot backend
   itself was not driven.

## Things worth a second opinion

* **`dim` aggregation direction.** `RegressionTest.METRIC_LOWER_IS_BETTER`
  decides which slice is "worst" (max for RMSE, min for p-values). Only
  `RMSETest(dim="w")` is used in production today (ocean); the `ZTest` path is
  covered by a unit test only.
* **Ocean tests are now stricter in effect than the old code was in shape** —
  same criterion (per-wavelength RMSE ≤ 1e-6), but one chart instead of N, with
  `w` mapped to hue. If a wavelength fails you get `details["worst w"]`.
* **`test_ocean_grasp_open_atm` used to hard-code `plot=False`.** It now follows
  `--plot` like everything else. If that was deliberate (e.g. the chart is
  unreadable for that case), it needs restoring.
* **`session_timestamp` and `ocean_grasp_wavelength` are now unused** but left
  in place — they are public-ish test helpers and removing them is beyond this
  change.
* Two `RegressionTest` docstring TODOs from `7876e70` were resolved implicitly
  by the rewrite (`_plot_noref` styling, `_diagnostic_plotter` placement); the
  "missing ref variance might be intentional" TODO in `ZTest` was dropped as a
  comment but the behaviour (warn + conservative fallback) is unchanged.

## Resuming

Everything is committed and pushed; nothing is left in the working tree. The
throwaway `.venv/` in the repo root is self-ignoring (`uv` writes
`.venv/.gitignore` containing `*`) and can be deleted.
