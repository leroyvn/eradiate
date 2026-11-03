# Test suite review: handover

Date: 2026-11-03. Branch at time of review: `fix/spherical-particlephase-fill`
(commit `cae0c78a`).

## Scope and method

Goal: identify tests that do not carry their weight (redundant, trivial, or
unable to fail) and only add maintenance cost.

- Small unit test files were read in full by hand. An AST script flagged tests
  with no assertion or with truthiness/isinstance-only assertions.
- Larger files (`tests/01_unit` files over ~200 lines, all of `tests/02_system`
  and `tests/03_regression`) were reviewed by six read-only subagents.
- No tests were run. All findings come from reading test and source code.
  Items marked **(verified)** were checked directly against the source during
  the review. "Cannot fail" claims not marked as verified should be confirmed
  with a quick mutation check (break the code under test, confirm the test
  still passes) before acting on them.

All paths below are relative to `tests/` unless stated otherwise.

## Summary

| Action                                          | Test functions removed |
| ----------------------------------------------- | ---------------------- |
| Delete outright: small files (first pass)       | 33                     |
| Delete outright: larger files                   | 45                     |
| Merge / parametrize (N tests into 1 counts N-1) | ~70                    |
| **Total**                                       | **~150 of 886 (~16%)** |

- The bug fixes in section 1 remove no tests.
- The system/regression changes in section 4 reduce parametrisation and spp,
  not function counts; that is where most of the runtime saving is.
- Collected pytest items drop by much more than the function count, because
  many deleted tests are parametrized over `modes_all` / `modes_all_double`.
  Run `pytest --collect-only -q | tail -1` before and after to get the exact
  figure.
- The ~70 merge estimate is the least certain figure, especially the ~15 from
  the `test_convert.py` class duplication.

## 1. Bugs: tests that cannot catch what they claim

Fix these regardless of the cleanup.

- `01_unit/radprops/test_array.py:39,61` **(verified)**: `sigma_a =
  array_radprofile.eval_sigma_s(...)`. `eval_sigma_a` is never tested on
  non-zero data; the `sigma_a` assert repeats the `sigma_s` one. Call
  `eval_sigma_a`.
- `01_unit/radprops/test_particles.py:747` `test_default_matches_interp_spectral`
  and `:891` `test_unresampled_matches_raw_union` **(verified)**:
  `eval_phase(resample_mu=False)` returns `_eval_phase_interp_spectral(w)`
  directly (`src/eradiate/radprops/_particles.py:977-980`), so both tests
  compare a function with itself. Delete.
- `01_unit/radprops/test_particles.py:755`
  `test_resample_mu_false_is_unresampled_union`: `<= 2*n_iangle` (6) also passes
  for resampled output; the union has exactly 3 points. Assert
  `mu_out.shape[0] == 3`.
- `01_unit/radprops/test_particles.py:943` `TestEvalPmom.test_zero_scattering`:
  the `or values[:, 0].sum() == 0.0` half is already guaranteed by the preceding
  `assert_array_equal`. Assert `nleg == 0` if that is the guarantee, or drop the
  line.
- `01_unit/data/test_convert.py:355` `test_explicit_nmom_passthrough` and `:580`
  `test_ndarray_nmom_stored_verbatim_per_point`: the `nmom` values passed equal
  the inferred non-NaN count, so an implementation ignoring `nmom` still passes.
  Pass values that differ from the inferred count, or delete.
- `01_unit/data/test_convert.py:815` `test_phase_consistent_with_mu`: phase is
  constant (isotropic), so a mis-ordered phase still passes. Use a
  non-symmetric phase in `_make_aer_v1`.
- `02_system/test_heterogeneous_atmosphere_flags.py:61`:
  `assert np.all(eradiate.run(exp) > 0.0)` evaluates `bool(Dataset)`, which only
  checks that data variables exist (a subagent confirmed with a negative-valued
  Dataset). Select `.radiance.values` and add a physical expectation (e.g.
  no-scattering case darker than default), or delete. There is also a
  `# TODO: Recycle this test` at line 27.
- `02_system/test_albedo.py:152` **(verified)**: the `canopy_constant` case uses
  `{"type": "directional", "zenith": 0.0}`, making it identical to
  `canopy_directional`. Constant illumination is never tested for
  `CanopyExperiment`. Change to `{"type": "constant"}`.
- `02_system/test_atmosphere_rpv.py:720` `test_rpv_vs_lambertian`
  **(verified)**: `ert_seed_state` is a separate `SeedState(0)`
  (`src/eradiate/testing/fixtures/__init__.py:121`), not the root seed state.
  `ert_seed_state.reset()` has no effect because `eradiate.run(exp)` is not
  passed `seed_state=ert_seed_state`. The homogeneous-atmosphere case compares
  two independent MC runs. Pass the seed state; then exact equality is
  possible. The no-atmosphere case duplicates
  `ext/mitsuba/src/eradiate_plugins/tests/bsdfs/test_rpv.py::test_eval_diffuse`.
- `02_system/test_atmosphere_rpv.py:305` `make_figure`: `select_orientation(...,
  "forward")` is hard-coded, so the "backward" panel plots forward data. The
  `name` parameter of `where_azimuth` / `select_orientation` is unused.
- `02_system/test_mdistant_insitu.py:122`: `filename` is only defined when
  `plot_figures` is set; a real failure without `--plot` raises `NameError`
  instead of showing the assertion message.
- `01_unit/pipelines/test_engine_core.py:199-200` `test_execute_lazy_evaluation`:
  `"c" not in executed` is always true ("c" is an untracked lambda). Drop the
  line or track "c".
- `01_unit/scenes/test_loader.py:19` **(verified)**: module-level
  `eradiate.set_mode("mono")` runs at import and changes the active mode for
  every module collected afterwards. Use the `mode_mono` fixture.
- `01_unit/scenes/biosphere/test_core.py:16` and `test_discrete.py:37`
  `tempfile_spheres`: data looks copy-pasted (file named `tempfile_leaves.txt`;
  first row `8.864 9.040 1.878` does not match the other rows starting with
  `0.100`). Fix while moving the fixture (see section 3).
- `01_unit/scenes/measure/test_target.py:106` `test_target_rectangle`: no
  parameter case is an exception, so the `pytest.raises` branch never runs (and
  its `return` sits after the raising call). Drop the branch.
- `01_unit/scenes/shapes/test_buffermesh.py:33`
  `test_buffermesh_construct_trafo_warning`: `pytest.raises(Warning)` only works
  because `pytest.toml` sets `filterwarnings = ["error"]`. Use
  `pytest.warns(UserWarning, match="to_world")`.
- `01_unit/scenes/test_loader.py:709` `test_transformation`: identity matrix, so
  the translation column is never exercised. Use a matrix with a translation.

## 2. Delete outright

### 2.1 Dead files, fixtures and dependencies

- `01_unit/scenes/phase/test_blend.py`: empty file.
- `01_unit/pipelines/conftest.py` **(verified)**: fixtures `results_mono`,
  `results_mono_spp`, `results_ckd` have no consumer in `src/`, `tests/` or
  `docs/`. Delete the whole file.
- `01_unit/pipelines/test_engine_integration.py`: overlaps `test_engine_core.py`
  with weaker asserts. Delete, or keep only `test_full_postprocessing_workflow`
  as an xarray smoke test (4 of 5 tests removed).
  - `test_basic_workflow`, `test_full_postprocessing_workflow`: check dims only,
    on random data.
  - `test_mode_dependent_pipeline`: tests a Python `if` in a local builder.
  - `test_parallel_branches`: duplicates `test_execute_no_outputs_computes_leaves`
    and never checks values.
  - `test_workflow_with_metadata_tracking`: reimplements
    `get_nodes_by_metadata` by iterating `_nodes`.
- `02_system/test_kernel_render_benchmark.py:69` `test_mi_render_rebuild`: no
  assertion; docstring claims result equality with the previous test but never
  compares; carries `# TODO: Recycle this test`.
- `02_system/test_maximum_scene_size.py:99`: `json_metadata["metrics"]` block has
  no consumer (CI in `.github/workflows/ci.yml` never passes `--json-report`).
  It is the only use of `pytest-json-report` (`pyproject.toml:91`,
  **verified**). Remove the block and the dependency.
- `01_unit/pipelines/test_logic.py:207-213`: commented-out
  `test_00_run_experiment`.

### 2.2 Construction-only smoke tests

Each only asserts `Cls(**kwargs)` is truthy, or checks the type of a converted
default, while a neighbouring test already builds the same object and loads it
via `check_scene_element`. Where the smoke test has a `kwargs` parametrisation,
move it onto the kernel-dict test (as `scenes/bsdfs/test_ocean_grasp.py` and
`test_hapke.py` already do).

- BSDFs:
  - `01_unit/scenes/bsdfs/test_black.py:7` `test_black_constructor`
  - `test_checkerboard.py:13` `test_checkerboard_construct`
  - `test_ocean_legacy.py:23` `test_ocean_legacy_construct`
  - `test_ocean_mishchenko.py:22` (misnamed `test_ocean_legacy_construct`)
  - `test_rpv.py:26` `test_rpv_construct`
  - `test_rtls.py:26` (misnamed `test_rpv_construct`)
  - `test_lambertian.py:14` `test_lambertian_construct`
  - `test_maignan.py:16` `test_maignan_construct`
- `01_unit/scenes/integrators/test_path_tracers.py:31`
  `test_path_tracers_construct` (5 classes x 2 kwargs x all modes; the next test
  loads the same kwargs)
- Shapes, `*_construct_trafo`:
  - `01_unit/scenes/shapes/test_rectangle.py:27`
  - `test_sphere.py:26`
  - `test_cuboid.py:30`
  - `test_filemesh.py:70`
- Spectra / illumination:
  - `01_unit/scenes/spectra/test_air_scattering_coefficient.py:12`
  - `01_unit/scenes/illumination/test_constant.py:9`
  - `01_unit/scenes/illumination/test_directional.py:16`
  - `01_unit/scenes/illumination/test_astro_object.py:16`
- Experiments:
  - `01_unit/experiments/test_canopy.py:15` `test_canopy_experiment_construct_default`
  - `01_unit/experiments/test_atmosphere.py:38`
    `test_atmosphere_experiment_construct_illuminations`
  - `01_unit/experiments/test_canopy.py:83` `test_canopy_experiment_real_life`
  - `01_unit/experiments/test_dem.py:150` `test_dem_experiment_run_basic`
    (only `isinstance(exp.results, dict)`; `test_core.py:117` covers the type)
- Atmosphere:
  - `01_unit/scenes/atmosphere/test_particle_ms_component.py:71` `test_construct`
  - `test_particle_ot.py:88` `test_construct_noargs`
  - `test_particle_ot.py:114` `test_construct_attrs`
  - `test_particle_ot.py:136` `test_altitude_units`
  - `test_particle_extinction_component.py:74` `test_phase_spec_instance`
  - `test_particle_profile.py:46` `TestConstruction.test_valid_dataset`
  - `test_particle_profile.py:285` `TestResample.test_output_dataset_valid`
    (cannot fail: `_resample_impl` already returns a validated `ParticleProfile`)
  - `test_heterogeneous.py:375` `test_heterogeneous_blend_switches`
- Biosphere:
  - `01_unit/scenes/biosphere/test_core.py:34` `test_instanced_canopy_element_create`
  - `test_tree_abstract.py:36` `test_abstract_tree_instantiate`
  - `test_discrete.py:107` `test_discrete_canopy_instantiate`
  - `test_leaf_cloud.py:116` `test_leaf_cloud_radii` (function is `np.full`)
- Spectral:
  - `01_unit/spectral/test_response.py:11` `TestUniformSRF.test_construct`
  - `test_response.py:31` `TestDeltaSRF.test_construct_from_array`
  - `01_unit/spectral/test_ckd_quad.py:5` `test_ckd_quad_config_construct`

### 2.3 Checks of defaults, stored attributes or private state

- `01_unit/test_config.py:24` `test_settings`
- `01_unit/test_rng.py:6` `test_seed_state_construct`, `:36` `test_seed_state_rng`
- `01_unit/testing/test_regression.py:39` `test_instantiate`, `:47`
  `test_instantiate_fail` (attrs mandatory-argument check)
- `01_unit/scenes/atmosphere/test_particle_state_component.py:74`
  `test_state_dims` (pure delegation), `:78` `test_amount_selected_automatically`
  (private `_amount`, covered by `test_eval_sigma_t_albedo`)
- `01_unit/pipelines/test_engine_core.py`:
  - `:48` `test_add_single_node`
  - `:55` `test_add_node_with_dependencies`
  - `:85` `test_add_node_with_description`
  - `:91` `test_add_node_with_metadata`
  - `:477` `test_adds_source_and_child_nodes`
  - `:553` `test_child_depends_on_source`
- `01_unit/scenes/phase/test_particles.py:93` `test_eval_impl` (object identity
  from private `_eval_impl`; the `cache_by_id` decorator is tested in
  `util/test_misc.py`)
- Debatable: `01_unit/scenes/atmosphere/test_particle_ms_component.py:292`
  `test_phase_rebuilds_on_each_access` asserts `ms.phase is not ms.phase`, i.e.
  absence of caching. Delete unless that behaviour is an intended guarantee.

### 2.4 Superseded or duplicated by another test

- `01_unit/scenes/atmosphere/test_integration_3d.py:37` `test_gridded_empty`
  duplicates `test_heterogeneous.py:40` `test_heterogeneous_empty`.
- `01_unit/pipelines/test_engine_core.py`:
  - `:78` duplicates `test_engine_virtual_inputs.py:35`
  - `:306` superseded by `:321`
  - `:676` covered by node "c" in `:624`
- `01_unit/pipelines/test_engine_virtual_inputs.py`:
  - `:60` superseded by `:223`
  - `:87` duplicates `:242`
  - `:218` and `:235` duplicate `:74`
- `01_unit/radprops/test_particles.py`:
  - `:491` duplicates `:742`
  - `:846` duplicates `:426`; add `make_size_distribution_dataset` to the
    parametrisation at `:422` instead
  - `:992` duplicates `:914`; parametrize `test_clip` over `pp` / `pp_single`
- `01_unit/data/test_convert.py:995` `test_produces_reff_veff_dimensions`,
  implied by `:1000` and `:1005`.
- `01_unit/scenes/atmosphere/test_particle_ms_component.py`:
  - `:273` `test_phase_returns_particle_phase`, inherited from
    `ParticleStateComponent` and tested in `test_particle_state_component.py:96`
    (add an `"ms"` entry to `CASES` there; unverified that
    `make_state_properties_dataset` accepts `{reff, veff}`)
  - `:302` `test_eval_phase_data_matches_grid_evals`, re-implements private
    `_eval_phase_data`; tested at `test_particle_state_component.py:113`
  - `:329` `test_template_and_params_phase_keys`; merge the `_params_phase` keys
    into the state `test_template_phase` (`:125`)
  - `:596-598`, `:631-638` inside `test_multi_reff_veff_ws`; trim to the
    sigma_t/albedo numerical checks
- Both-switches-disabled triplicate: `test_particle_ms_component.py:191`,
  `test_particle_extinction_component.py:128` and the `"none"` case of
  `test_particle_ot.py:571 test_switches` all hit
  `ParticleComponent._switch_validator`
  (`src/eradiate/scenes/atmosphere/_particle_component.py:96`). Keep the
  extinction one.
- `01_unit/scenes/atmosphere/test_heterogeneous.py:359` `test_heterogeneous_scale`
  (slow): the scale emission is shared code
  (`src/eradiate/scenes/atmosphere/_core.py:802`), also tested in
  `test_particle_ot.py:266` and `test_molecular_atmosphere.py:61`. Keep the OT
  one; drop the scale assert in the molecular test.

## 3. Merge or parametrize

### Experiments

These are copy-pasted across experiment classes and exercise shared code in
`src/eradiate/experiments/_helpers.py`. Merge each into
`01_unit/experiments/test_experiment_common.py`, parametrized over the class.

- `*_construct_measures`: `test_atmosphere.py:66`, `test_canopy.py:22`,
  `test_canopy_atmosphere.py:25`, `test_dem.py:27`
- `*_construct_default` (geometry override check): `test_atmosphere.py:26`,
  `test_canopy_atmosphere.py:15`, `test_dem.py:17`
- `*_real_life`: `test_atmosphere.py:144`, `test_canopy_atmosphere.py:173`,
  `test_dem.py:94`
- `*_inconsistent_multiradiancemeter`: `test_canopy_atmosphere.py:249`,
  `test_dem.py:118`
- `*_run_detailed`: `test_atmosphere.py:195`, `test_canopy_atmosphere.py:214`,
  `test_dem.py:161`, `test_canopy.py:107` (3 marked slow, 2 docstrings say
  "outdated"). Keep the atmosphere one or parametrize it. `test_canopy.py:146`
  has an unreachable `else: raise UnsupportedModeError`.
- `test_canopy_atmosphere.py:41` normalize-measures: two copy-pasted blocks;
  parametrize over `atmosphere`. `test_dem.py:42`: drop the
  `HomogeneousAtmosphere` case (`DEMExperiment._normalize_measures` ignores the
  atmosphere).
- `test_atmosphere.py:171` `test_atmosphere_experiment_run_basic`: only an
  isinstance check. Keep only if the `particle_components` path matters, then
  assert finite positive radiance.

### Atmosphere

- `test_heterogeneous.py:70/97` (single mono/ckd) and `:124/142` (multi
  mono/ckd): parametrize over mode, atmosphere fixture via
  `request.getfixturevalue`.
- `test_particle_ot.py:185/212/239` (absorbing / scattering / general): one
  parametrized test.
- `test_particle_ot.py:274` `test_eval_radprops_format`: merge its
  `albedo`/`z_layer` asserts into `:290`.
- Convert passthrough/rejection: `test_particle_ms_component.py:75,99` and
  `test_particle_ot.py:95,109` all go through
  `atmosphere_factory.convert(value, allowed_cls=cls)`. One test parametrized
  over (cls, default type id).
- `test_molecular_atmosphere.py:26-42` `_find_nearest` /
  `_default_spectral_index` duplicate `test_heterogeneous.py:21-37`; move into a
  shared conftest.
- `test_molecular_atmosphere.py:154` `test_molecular_atmosphere_depolarization`:
  4 copy-pasted blocks; parametrize, drop the `isinstance(pint.Quantity)`.
- `test_molecular_atmosphere.py:45` `test_molecular_atmosphere_default_mono`:
  runs in all modes, `assert template.render(...)` can only fail by raising.
  Rename; consider `check_scene_element`.
- `test_particle_dist.py:183`: keep only the rejected-method checks,
  parametrized.

### Data / radprops

- `01_unit/data/test_convert.py`: `TestMakeAerCoreV2` (`:249`) and
  `TestMakePrtPsdV1` (`:441`) test `make_prt_core_v1` and `make_prt_ms_v1`, both
  thin wrappers over `make_prt_v1` (`src/eradiate/data/convert.py:378,418`).
  Parametrize the shared Check / Nangles / AutoPmom / Normalize cases over the
  builder, or keep the ms versions only. Rename the classes; docstrings at
  `:797`, `:822` cite the old `aer_v1_to_aer_core_v2`.
- `test_convert.py` small groups:
  - `:268/:277` raises-on-descending: parametrize over `check`; inline the
    single-use `mu_asc` fixture
  - `:323/:330` and `:534/:545`: parametrize `(nmom, expected)`
  - `:507/:514`: merge (identical input, second has no assert)
  - `:688/:695`: parametrize over the dimension
  - `:860/:868`: merge into one real-data smoke test
- `01_unit/radprops/test_particles.py:382/385` `test_shape` /
  `test_has_polarization`: replace with one test parametrized over `phamat` sizes
  1/4/6/other, or delete. `:296/:305`: merge.
- `01_unit/radprops/test_array.py:26/45`: parametrize.
- `01_unit/radprops/test_rayleigh_scattering.py:91/101`: parametrize over the
  function.

### Pipelines

- `test_engine_core.py`:
  - `:60/:531` method chaining: merge
  - `:227/:247` bypass: parametrize
  - `:261/:272` subgraph extraction: parametrize, assert via `list_nodes()`
  - `:648/:667` metadata: merge
  - `:731/:751` bypass inactive: merge
- `test_engine_core.py:387` `test_clear_cache` asserts on `_cache`; rewrite with
  a call counter.
- `test_engine_core.py:581-582,594-595`: drop the `_nodes` membership lines.
- `test_engine_virtual_inputs.py:55,123,133` (missing-input error) and
  `:242,250,260,269` (bypass makes input unneeded): parametrize each group.
- `test_logic.py:43-56` `measure` / `srf` fixtures: reduce to
  `yield request.param` (dead `else` branches). `:515` `test_08_viewing_angles`:
  delete or check values.

### Measures, phase, spectra, spectral

- `01_unit/scenes/measure/test_multi_distant.py`:
  - `:82,125,168,204,238`: 5 azimuth-convention tests into one
  - delete the 5 `Cls()` raises-TypeError blocks (attrs mandatory field)
  - fix the comment at `:253`
- `01_unit/scenes/measure/test_distant.py:44/57`: parametrize over (cls,
  film_resolution).
- `01_unit/scenes/phase/test_multi.py:167/216`: merge into the parametrized test.
- `01_unit/scenes/phase/test_gridded_particle_phase_function.py:168/179` and
  `:184/190`: parametrize.
- `01_unit/scenes/phase/test_particles.py:77` `test_factory`: isinstance only;
  add `check_scene_element` or delete.
- `01_unit/spectral/test_index.py:8,14,22,70,78,88,96`: `convert` calls
  `from_dict`, which calls `new`; merge into one test over (entry point, mode).
- `01_unit/spectral/test_response.py:37/42` DeltaSRF eval: merge.
- `01_unit/spectral/test_grid.py:129`: drop the `arange` half (duplicates
  `test_ckd_spectral_grid_arange`); `:54`: inline the single-case parametrize.
- `01_unit/scenes/spectra/test_interpolated.py:101`: remove unused `units`
  parameter. `:186,263`: move into `test_interpolated_construct` as ValueError
  cases. `:196`: collapse dead mode branches.
- `01_unit/scenes/spectra/test_solar_irradiance.py:42` `test_construct`: reduce
  to the DataError case plus path/dataset inputs. `:85-89`: collapse dead
  branches.
- `01_unit/scenes/spectra/test_uniform.py:72-75`: drop the `float` type asserts
  (low priority).
- `01_unit/scenes/shapes/test_buffermesh.py:25`: drop the "correct" success
  case.
- `01_unit/util/test_misc.py:58-59` `test_deduplicate`: `preserve_order=False`
  returns `list(set(...))`; compare `sorted(...)`, drop the TODO.

### Kernel, testing, loader, biosphere, surface

- `01_unit/kernel/test_transform.py:9/41`: parametrize over (func, source
  vertices); fix the copied docstrings.
- `01_unit/kernel/test_render.py`: move the inline scene dict at `:57-78` /
  `:92-113` into `SCENE_DICTS`; share the scene between `:215` and `:278`; drop
  the redundant isinstance lines at `:132,194,265`; rename the misleading ids at
  `:186`; remove the dead `enumerate` at `:269`.
- `01_unit/testing/test_regression.py:343`: fold into `:287`, parametrized over
  the test class.
- `01_unit/testing/test_report.py:79`: drop the `logger._robot is stub` line.
  `:109` `test_smoke`: keep only if someone inspects the report by hand.
- `01_unit/scenes/test_loader.py:890` `TestGenerateName`: 6 static methods into
  one parametrized test. `:741,780,851`: extract the repeated
  `CanopyExperiment(...)` block.
- Biosphere: create `01_unit/scenes/biosphere/conftest.py` and move
  `tempfile_leaves` (`test_leaf_cloud.py:42`, `test_tree_abstract.py:18`,
  `test_discrete.py:24`), `tempfile_spheres` (`test_core.py:16`,
  `test_discrete.py:37`) and the OBJ cube (`test_tree_mesh.py:20`,
  `test_discrete.py:50`).
- `01_unit/scenes/biosphere/`:
  - `test_core.py:77`: assert instance positions, or delete
  - `test_leaf_cloud.py:83`: assert a minimum pairwise distance, or delete
  - `test_tree_abstract.py:53`: reuse the built tree; real assert for the dict
    case
  - `test_tree_abstract.py:115`: copy of `test_leaf_cloud.py:296` with no trunk
    asserts
  - `test_tree_mesh.py:131`: reduce to one TypeError plus the stl ValueError
  - `test_tree_mesh.py:159`: uses private `_template_*`; replace with
    `check_scene_element(MeshTree(...))`
  - `test_tree_mesh.py:195`: duplicate block
  - `test_discrete.py:120`: redundant `traverse`
  - `test_discrete.py:230`: private `_template_instances`
- `01_unit/scenes/surface/test_dem_surface.py:151` `test_mesh_from_dem`: dead
  spherical branch; split the raises case; match the warning text
  `"planet_radius"`. `:306-310`: duplicates `check_scene_element`.
- `01_unit/scenes/surface/test_central_patch.py:41`: split into a `noargs`
  raises test and one success test using `check_scene_element`; drop the two
  edges cases.
- `01_unit/scenes/test_core.py` and `test_loader.py` surface helpers: fine.
- `01_unit/test_srf_tools.py:57,72,101,130`: factor the repeated Dataset
  construction into a helper (low priority).
- `01_unit/scenes/atmosphere/test_molecular_atmosphere.py:196-239`: tests of
  private helpers in `eradiate.radprops._atmosphere`; keep, but move to
  `01_unit/radprops/`.

## 4. System and regression tests (Monte Carlo cost)

- `02_system/test_compare_canopy_atmosphere.py:15,153`: exact-equality checks of
  scene assembly over a 3x3 grid (9 x 2 renders each). Keep one parameter set,
  or compare kernel dicts in `01_unit`.
- `02_system/test_heterogeneous_atmosphere_expansion.py:9`: same issue (9 x 2
  renders); keep one case. `:147`: exp2 run without `spp=spp`.
- `02_system/test_mdistant_insitu.py:15`: 88 renders (11 spp values per
  offset, up to ~1M spp); only the last is asserted. Sweep only with `--plot`.
  Not marked slow.
- `02_system/test_basic.py:36`: `li in {0.1, 1, 10}` triples 5e5-spp renders;
  `test_irradiance_scaling` already checks linearity. Keep one `li`. `:32`,
  `:106-113`: commented-out `astro_object` case and branch.
- `02_system/test_irradiance_scaling.py:35`: the `datetime` parameter repeats
  `01_unit/scenes/spectra/test_solar_irradiance.py::test_datetime` and doubles
  renders. Drop it.
- `02_system/test_onedim_symmetry.py:69`: 1e6 spp for `atmosphere="none"`
  (deterministic); use spp=1 there and add `ert_seed_state` to the homogeneous
  case.
- "Lambertian, no atmosphere, BRF = rho" appears in
  `test_onedim_lambertian_brf.py`, `test_radiometric_accuracy[directional]`,
  `test_spectral_loop`, `test_ckd_basic` and `test_irradiance_scaling`. Merge
  into one parametrized test.
- `02_system/test_atmosphere_rpv.py:134`: relative azimuth is always 0; the
  `== 180.0` and `ValueError` branches of `select_brf` never run.
- Unit tests sitting in `02_system`:
  - `test_heterogeneous_atmosphere_parameter_id_consistency.py:8`: no render;
    move to `01_unit` and fix the docstring.
  - `test_kernel_render_benchmark.py:38` `test_mi_render`: 10,000-leaf canopy
    at 21 wavelengths x 100 spp to check dict keys. Move to `01_unit` with a
    trivial scene and 2 wavelengths.
- `03_regression/rami4atm/test_rami4atm.py:34` `hom00_bla_a00s_m04_z30a000`:
  analytic BRF = 0 with no reference, run at 160k spp. Use spp=1, move to
  `02_system`.
- `03_regression/rami4atm/test_rami4atm_gridded.py:100`: re-renders 6 1D
  references already rendered by `test_rami4atm`. Compare against stored
  `rami4atm/{case}-ref` via `dataset_regression`. Add a docstring.
- `03_regression/atmospheres/test_rpv_afgl1986.py:15`,
  `test_rpv_afgl1986_continental.py:20`: close to RAMI4ATM `hom00_rpv_e00s_m04`
  / `hom00_rpv_ec2s_m04` (differences: SZA 20 vs 30 deg, 550 nm delta vs S2
  band 4, continental AOT 0.5 at 1-2 km). Drop unless the 550 nm delta SRF is
  deliberate.
- `03_regression/spherical/test_spherical.py:13`: no docstring.

## 5. Cosmetic

- Docstrings that do not match the code:
  - `02_system/test_atmosphere_rpv.py:633`: 11 angles / 10000 spp vs 14 /
    100000
  - `02_system/test_ckd_basic.py:28`: 10^6 spp vs 1000
  - `02_system/test_onedim_lambertian_brf.py:11`: 1001 angles vs 51; mentions
    the removed `OneDimSolverApp`
  - `02_system/test_maximum_scene_size.py`: sizes 1-1e9 vs 10-1e12
  - `02_system/test_compare_canopy_atmosphere.py:15`: 21 angles vs 13
  - `03_regression/ocean/test_ocean_grasp.py:67`: says coastal, is open ocean
- Unreachable `else: raise` branches:
  - `01_unit/scenes/atmosphere/test_heterogeneous.py:434`
  - `01_unit/scenes/atmosphere/test_particle_ot.py:622`
- Redundant `@pytest.mark.regression` (added automatically by
  `03_regression/conftest.py`):
  - `ocean/test_ocean_grasp.py:12,36,60`
  - `romc/test_het0{1,4,6}.py:16`
  - `rami4atm/*.py`
  - `spherical/test_spherical.py:11`
- Misnamed tests: `test_ocean_mishchenko.py` defines `test_ocean_legacy*`;
  `test_rtls.py` defines `test_rpv_construct`.
- Swapped ids: `01_unit/spectral/test_response.py:197`.
- `01_unit/radprops/test_particles.py:648-649`: `pytest.approx`; switch to
  `np.testing.assert_allclose`. `:946`: docstring describes development
  history.
- `01_unit/test_warp.py:32`: commented-out `check_vectorization` call.
- `01_unit/scenes/atmosphere/test_integration_3d.py:46,50`: commented-out
  spherical case.
- `01_unit/scenes/atmosphere/test_molecular_atmosphere.py:109`: leftover
  comment.
- Wrong comments: `test_interpolated.py:178`, `test_uniform.py:114`,
  `test_multi_distant.py:253`.

## Kept on purpose

These look weak but test real behaviour:

- `01_unit/test_import.py`: detects circular imports in eager mode.
- Regression tests without `assert`: they assert through the regression fixture.
- `01_unit/testing/test_regression*.py`: tests the statistical comparison code;
  `test_regression_fixture.py` had nothing to flag.
- `test_convert.py` "passes" tests paired with "raises" tests.
- Files the reviewers found clean:
  - `01_unit/scenes/measure/test_fisheye.py`, `test_distant_flux.py`
  - `01_unit/spectral/test_spp.py`
  - `01_unit/test_frame.py`, `test_grid.py`, `test_mode.py`
  - `01_unit/util/test_pmom.py`
  - `01_unit/scenes/atmosphere/test_homogeneous.py`
  - `01_unit/experiments/test_core.py`, `01_unit/scenes/test_core.py`
  - all conftests except `pipelines/conftest.py`
  - `02_system/test_spectral_loop.py`, `test_regression_framework.py`
  - `03_regression/integrators/*`, `03_regression/romc/*` (except decorators)

## Suggested order of work

1. Record the baseline: `pixi run pytest --collect-only -q | tail -1`.
2. Fix section 1 on its own branch; these are real test bugs and may surface
   real failures (`test_array.py`, `test_albedo.py`, `test_atmosphere_rpv.py`
   are the most likely).
3. Apply sections 2 and 3 per directory, one commit each, running the affected
   unit tests after each.
4. Apply section 4 separately; it changes what the system/regression suites
   check, so review it with whoever owns the regression references.
5. Re-run the collection count and compare with the baseline.

Use the default pixi environment (`pixi run pytest ...`, no `-e`).
