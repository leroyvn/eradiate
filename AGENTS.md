# AGENTS.md

Eradiate is a Monte Carlo radiative transfer model for Earth observation, built
on the Mitsuba 3 renderer (Python package with a C++ kernel).

The developer documentation in `docs/` is the reference for working on this
codebase. Read the relevant page before starting a task; this file only
indexes it.

## Common commands

```shell
pixi run test-quick   # Tests, skipping 'slow' and 'regression' markers
pixi run test         # Full test suite
pixi run pytest ...   # Any pytest invocation
pixi run lint         # Ruff linter
pixi run kernel-build # Compile the kernel after changing its source
```

pytest is configured in `pytest.toml` and turns warnings into errors.

## Source layout

- `src/eradiate/`: Python package
  - `scenes/`: scene elements (atmosphere, surfaces, BSDFs, illumination,
    measures, integrators, biosphere)
  - `experiments/`: experiment classes assembling scenes and running them
  - `radprops/`: atmospheric radiative property profiles
  - `spectral/`: spectral dimension data structures
  - `kernel/`: interface to the Mitsuba kernel (kernel dictionaries, rendering)
  - `pipelines/`: post-processing pipeline
  - `data/`: data file management
  - `config/`, `cli/`, `xarray/`, `util/`, `notebook/`: configuration,
    command-line interface, xarray accessors, utilities, notebook support
  - `testing/`: pytest plugin, fixtures, regression test framework
- `tests/`: `01_unit`, `02_system`, `03_regression`
- `resources/data`: data submodule
- `docs/`: documentation; `docs/tutorials` is a submodule
- `benchmarks/`: benchmarks

## Kernel source layout (`ext/mitsuba/`)

The radiometric kernel code (fork of Mitsuba 3) is in the `ext/mitsuba` *
submodule. Do not read or edit it unless necessary or instructed to.
Eradiate-specific code is concentrated in a few places; the rest follows
upstream Mitsuba.

- `src/eradiate_plugins/`: Eradiate plugins, one directory per plugin type
  (`bsdfs`, `emitters`, `extremum`, `integrators`, `media`, `phase`,
  `sensors`, `shapes`, `volumes`); tests in `src/eradiate_plugins/tests/`
- `include/mitsuba/eradiate/`: headers for Eradiate plugins
- `src/<plugin type>/`, `include/mitsuba/{core,render}/`: upstream Mitsuba
  plugins and core library
- `src/python/`: Python bindings and the `mitsuba` Python package
- `docs_eradiate/`: kernel documentation (plugin reference, build guide)
- `build/`: build directory; `build/mitsuba.conf` selects compiled variants

Kernel tests run with pytest using `ext/mitsuba/pyproject.toml`, *e.g.*
`pixi run pytest ext/mitsuba/src/eradiate_plugins/tests`. They require a
compiled kernel (`pixi run kernel-build`).

## Developer guide (`docs/developer_guide/`)

| Task | Page |
| --- | --- |
| Pixi environments and tasks, pre-commit, submodules | `setup/workflow.rst` |
| Development installation, kernel compilation | `setup/install.rst` |
| Updating source, submodules and kernel | `setup/update.rst` |
| Writing library code (principles, style) | `conventions/code.rst` |
| Pint and unit handling | `conventions/units.rst` |
| xarray and caching | `conventions/data.rst` |
| Docstrings, `attrs` field documentation | `conventions/docstrings.rst` |
| Deprecating or removing a feature | `conventions/deprecations.rst` |
| Licensing, REUSE, third-party files | `conventions/licensing.rst` |
| Running and writing tests, fixtures, reports | `how_to/testing.rst` |
| Regression tests and references | `how_to/regression_tests.rst` |
| Building and editing the documentation | `how_to/documentation.rst` |
| Adding a scene element class | `how_to/scene_element.rst` |
| Registering a class to a factory | `how_to/factory_registration.rst` |
| Lazy imports and the public API | `how_to/lazy_imports.rst` |
| Benchmarking and profiling | `how_to/benchmark_profile.rst` |
| Managing dependencies | `maintainer/dependencies.rst` |
| Making a release | `maintainer/release.rst` |

## Design notes (`docs/design_notes/`)

Each note lists its status and the source files it describes. Read the note
before changing those files; a note with status `Outdated` does not match the
code.

| Component | Note |
| --- | --- |
| Scene elements and kernel dictionary generation | `scene_generation.rst` |
| Factories and dictionary-based configuration | `factories.rst` |
| Atmosphere and surface shape positioning | `atmosphere_geometry.rst` |
| Post-processing pipeline engine | `pipeline_engine.rst` |

## Missing content

Sections still to be written are marked with a `.. admonition:: To be written`
block. Do not invent rules where such a block stands; ask instead. If you
cannot ask (non-interactive session), follow the patterns of the surrounding
code and report the gap in your summary.
