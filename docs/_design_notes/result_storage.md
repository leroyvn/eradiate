# Raw result storage, caching and the result data structure

Where the spectral loop writes, what survives a crash, and what the user gets
back. Companion to [`spectral_loop.md`](spectral_loop.md), which defines the
loop and the frame protocol this note stores the output of. Read that one first.

## Requirements

From the redesign brief, with the answer each one gets here:

| # | Requirement | Answer |
|---|---|---|
| 1 | Build the final structure first, populate it during the loop | `RawStore`, allocated from `RawLayout` before iteration 1 |
| 2 | Optional drive cache, crash-recoverable | Same store, different backend; completion mask written after data |
| 3 | Predict what remains to be computed | `LoopPlan` (in [`spectral_loop.md`](spectral_loop.md)) reads the completion mask |
| 4 | Grow the cache gradually, or preallocate? | Declare the full logical shape; let physical space grow per chunk |
| 5 | Raw Mitsuba bitmaps stay reachable for debugging | Reconstructed on demand from the store; two opt-in retention modes on top |
| 6 | Caching must not slow down fast loops | Write-behind chunk buffer; per-iteration cost is a `memcpy` in all modes |
| 7 | Result is a `DataTree`, not `dict[str, Dataset]` | Yes — with the version consequences spelled out below |

## The store

**Proposed.**

One store per run. Groups mirror the final result tree, so the raw store and the
processed result have the same shape and the same measure keys:

```
/                       run attrs: fingerprint, eradiate version, mode,
│                       kernel version, root seed, backend id, creation time
├── _plan/              the iteration table — the run's index
│   ├── w        (si)   float64  [nm]
│   ├── g        (si)   float64  — CKD only
│   ├── bin_index(si)   int32    — CKD only
│   ├── spp      (si)   int64
│   ├── active   (si, n_measures)  bool   — which measures each iteration feeds
│   ├── walltime (si)   float32  [s]      — filled as the loop runs
│   └── done     (si)   uint8               the completion mask
└── {measure_id}/
    ├── radiance (si, y_index, x_index[, stokes])  float32
    ├── m2       (si, …)                            float32  — if requested
    └── coords: y_index, x_index, vza, vaa, …       (written once, at creation)
```

`_plan/done` is the only authority on what has been computed. Everything else —
resumption, the effective loop length, the ETA — reads from it.

### One protocol, three backends

```python
class RawStore(Protocol):
    @classmethod
    def create(cls, layout: RawLayout, plan: LoopPlan, path=None) -> RawStore: ...
    @classmethod
    def open(cls, path, fingerprint: str) -> RawStore: ...

    def frame(self, i: int) -> Frame: ...     # writable views at index i
    def commit(self, i: int) -> None: ...     # honours the checkpoint policy
    def flush(self) -> None: ...
    @property
    def done(self) -> np.ndarray: ...         # (n_total,) bool
    def to_datatree(self, lazy: bool = False) -> xr.DataTree: ...
```

- **`MemoryStore`** — the default, and what a run with no cache gets. Plain
  NumPy arrays; `commit` sets a bit. No I/O, no dependencies.
- **`ZarrStore`** — the recommended cache. Chunk-per-checkpoint-block,
  uncompressed by default. Chunks materialize on write, region writes are
  native, and each chunk is an independent object, which is what makes partial
  results readable and eventually makes parallel writers possible.
- **`NetCDFStore`** — the fallback, and the one that needs no new dependency:
  `netcdf4` is already in `dependencies` (`pyproject.toml:26`). Written through
  the `netCDF4` library directly with chunked (never contiguous) variables and
  slice assignment; xarray's `to_netcdf` has no region-write mode, so it is not
  in this path.

The choice is deliberately not baked in. `netcdf4` being an existing hard
dependency is what makes it the fallback; Zarr's chunk semantics are what make
it the recommendation. See "Version and dependency consequences" for why the
order is not reversed.

### Why caching costs nothing when it is on

**Proposed**, and this is requirement 6.

The loop never writes to the storage layer directly. It writes into a
**write-behind buffer** holding one chunk — `K` consecutive iterations' worth of
every variable — and the buffer is flushed to the backing store when it fills,
or when the checkpoint policy fires, whichever comes first.

Per iteration, therefore, all three backends do exactly the same thing: one
`np.copyto` into a NumPy buffer. The difference is a whole-chunk write every `K`
iterations, on a chunk sized to be worth writing (target ≈ 1–4 MiB). For a
fast loop — DISORT flux-only, microseconds per solve — `K` is large, flushes are
rare and the cache is invisible in the profile. For a slow loop — Mitsuba at
10⁵ spp — a flush per iteration would be invisible anyway.

Two knobs, both with defaults that should not need touching:

- `checkpoint_every` — iterations between flushes (default: derived from the
  chunk size).
- `checkpoint_interval` — seconds between flushes (default ≈ 30 s), so that a
  slow loop checkpoints on time rather than on count.

A flush is: write the data chunk → `fsync` → write the `done` bits for those
iterations → `fsync`. In that order, always. It costs one extra sync per
checkpoint and it is what makes the mask trustworthy.

## Grow gradually, or allocate the drive space up front?

**Proposed** — this is requirement 4, and the answer is "both, at different
levels".

**Declare the full logical shape at creation. Let the physical space grow.**

- *Zarr* makes this free: array creation writes metadata only, and a chunk that
  has never been written simply does not exist — reads return the fill value.
  Growth is per chunk, in the order the loop runs.
- *NetCDF-4/HDF5* does the same **provided the variables are chunked**. HDF5
  allocates chunked datasets incrementally; a contiguous-layout dataset is
  allocated in full at creation. So: always chunk, never contiguous. Fixed
  dimensions are preferable to unlimited ones — the length is known from the
  plan, and fixed dimensions keep the layout predictable.

Preallocating the whole file up front buys exactly one thing: an early `ENOSPC`
instead of a late one. That is worth having, and it is cheaper to get from the
plan: `plan.nbytes_raw` compared against the free space on the target device
before the store is created, refusing the run with an actionable message. An
explicit `preallocate=True` (write every chunk once at creation) stays available
for the case where the filesystem is shared and the guarantee has to be
physical, not advisory — it costs one full-size write and is off by default.

Growth also has a reporting benefit: the on-drive size of a partial run is
proportional to progress, so `du` is a progress indicator that survives the
process dying.

## Crash recovery

**Proposed.**

**The completion mask is separate from the data and written after it.** A chunk
that was being written when the process died has no `done` bits, so those
iterations are simply recomputed. There is no attempt to detect a torn chunk by
inspecting its contents — that is where formats like this go wrong. The
ordering, plus the `fsync` pair, is the whole recovery mechanism.

**The run fingerprint.** Resuming into a cache written by a different
configuration is the failure this design most needs to prevent, because it is
silent. The store's root attrs carry a hash over:

- the serialized experiment configuration (v2's Pydantic `model_dump_json` makes
  this exact; v1 needs a stable serialization of the measure and atmosphere
  fields, which is the weaker link),
- the mode id, spectral grids and CKD quadrature configuration,
- the `RawLayout` (shapes, dtypes, variable names),
- the Eradiate and kernel versions,
- the root seed.

`RawStore.open` refuses a mismatch. `resume="force"` overrides it for the case
where the user knows the difference is cosmetic; nothing else does.

**Determinism across a resume — a required change.** Seeds are currently drawn
from a sequential stream: `mi_render` calls `seed_state.next()` once per sensor
per iteration (`src/eradiate/kernel/_render.py:453`). A run resumed at iteration
`k` would draw different seeds than an uninterrupted one, so a resumed run is
not reproducible and, worse, differs from the run it claims to continue. The
seed must become a pure function of the iteration index:

```python
seed = counter_based(root_seed, iteration_index, sensor_index)
```

with `root_seed` stored in the cache. This is a small change to `SeedState` use
and it is a correctness prerequisite for caching, not an optimization.

**Single writer.** A lock file in the cache directory, holding pid and hostname,
refused politely if held. Concurrent writers to one cache are out of scope until
the parallel-iteration question in [`spectral_loop.md`](spectral_loop.md) is
settled.

## Two population modes

**Proposed.** The memory result depends on whether raw data is kept.

**Direct** (`raw="keep"`, the default today's behaviour maps onto). The raw store
holds every iteration. Peak memory (or drive) is `plan.nbytes_raw`. Post-loop
aggregation reads it once. This is what debugging, variance work and any
re-aggregation with a different quadrature need.

**Streaming** (`raw="stream"`). Because the plan iterates bin-major, a CKD bin
is complete when its last quadrature node lands. The driver can then aggregate
that bin immediately into the final array and release the raw slots. Peak memory
becomes *the size of the final result plus one bin's raw data* — for a
16-point quadrature, a 16× reduction on the dominant term. Resume granularity
becomes the bin rather than the iteration, and the completion mask is per bin.

Streaming is exact, not approximate: it is the same weighted sum evaluated
incrementally. What it costs is the ability to look at raw data afterwards, and
the ability to re-run aggregation without re-running the solver. In mono mode
the distinction vanishes — there is no aggregation, so the raw array *is* the
result array.

Which one should be the default is an open question (see below); the design
supports both because they are the same code with a different release policy.

## Raw bitmaps stay reachable

**Proposed** — requirement 5, and the reason it needs its own section is that
"keep the bitmaps" and "stop keeping the bitmaps" have to both be true.

A `mi.Bitmap` is a pixel buffer plus a pixel format plus channel names. All
three are recoverable: the buffer is a slice of the store, and the other two are
written into the store's attrs by `layout()`. So the default is **reconstruction
on demand**, which costs nothing when nobody asks:

```python
bmp = store.bitmap(i, measure="measure")     # -> mi.Bitmap over the stored slice
```

`mi.Bitmap` already accepts a NumPy array with an explicit pixel format — v1
does exactly this in `Experiment.process`
(`src/eradiate/experiments/_core.py:712`).

On top of that, two opt-in retention modes for the cases reconstruction cannot
serve — a bug *inside* Mitsuba's film handling, or a crash before the store is
written:

- `debug_bitmaps="keep"` — retain the live `mi.Bitmap` objects, keyed by
  `(iteration, sensor)`. This is exactly today's behaviour and today's memory
  cost, now explicit and opt-in.
- `debug_bitmaps="write:<dir>"` — dump one OpenEXR per iteration and sensor.
  Survives the process, readable by Mitsuba tooling, and the natural choice when
  the thing being debugged is a crash.

Both default to off. `Measure.mi_results` gets a deprecation shim that
reconstructs from the store, so existing debugging code and the three tests that
touch it (`tests/01_unit/pipelines/conftest.py:25,68`,
`tests/01_unit/pipelines/test_logic.py:122`) keep working during the transition.

**Dtype.** Store raw data as `float32` — the film's component format is
`float32` (`src/eradiate/scenes/measure/_core.py:227`), so today's
`bitmap_to_dataarray(..., dtype="float64")` doubles the footprint to store
zeros. Accumulate in `float64` during aggregation, where it matters. `raw_dtype`
is configurable for anyone who disagrees about a specific run.

## What this costs, in bytes

Arithmetic, not measurements. `n` = iterations, `p` = pixels per iteration,
`c` = extra channels (Stokes, moment), 4 bytes per value.

| Case | n | p | c | raw size |
|---|---|---|---|---|
| Principal plane, `MultiDistantMeasure` 91×1, full-spectrum CKD | 8 000 | 91 | 1 | 2.9 MB |
| Hemispherical 64×64, same spectral grid | 8 000 | 4 096 | 1 | 131 MB |
| …with Stokes (4) and second moment (×2) | 8 000 | 4 096 | 8 | 1.05 GB |
| DISORT radiance, 32 μ × 10 τ × 36 φ | 8 000 | 11 520 | 1 | 369 MB |

Two things follow. First, for the small-film cases that dominate everyday use,
raw storage was never the memory problem — the per-iteration xarray object churn
was (see [`spectral_loop.md`](spectral_loop.md), "What is wrong today"). Second,
for the wide-film cases the current `float64` raw plus intermediate copies is
roughly 3× the table above, which is where runs actually fail.

## The result data structure

**Proposed** — requirement 7.

`Experiment.results` becomes an `xr.DataTree`:

```
/                          run attrs: convention, source, history, references
├── {measure_id}/          the processed dataset — radiance, brf, irradiance, …
│   └── raw/               optional; the raw store, lazily backed when cached
└── {measure_id_2}/
```

Shared coordinates (`w`, `sza`, `saa`) sit at the root and are inherited by the
children, which is the feature that makes a tree better than a dict here: today
every measure's `Dataset` carries its own copy of the spectral coordinate and
the solar angles.

The `raw/` child is where the debugging story and the caching story meet: when a
drive cache was used, it is opened lazily and costs nothing to carry around;
when the run was in-memory with `raw="keep"`, it is the arrays themselves; with
`raw="stream"` it is absent.

**Migration.** `results[measure_id]` keeps working — `DataTree.__getitem__`
returns a node, and `.to_dataset()` gets the `Dataset` back. `run()`'s return
value changes from `Dataset | dict[str, Dataset]` to `DataTree`, which is a
breaking change for every downstream script and needs a release note, a
migration paragraph in the user guide, and probably one release where a
`results_dict` property exists for people who cannot move yet.

## Version and dependency consequences

**Measured where stated; the rest flagged for verification.**

- **`xr.DataTree` requires xarray ≥ 2024.10** (the release that merged
  `datatree` into xarray). In practice the floor used in the ecosystem is
  slightly higher: `eradiate-disort` — which already returns a `DataTree` —
  declares `xarray>=2024.11` and `requires-python = ">=3.10,<3.14"`
  (`eradiate-disort/pyproject.toml:7-8`).
- **That means dropping Python 3.9.** Eradiate currently declares
  `requires-python = ">=3.9,<3.14"` (`pyproject.toml:12`) and `xarray>=2023`
  (`pyproject.toml:39`). The lockfile shows what that costs: the `py39`
  environment resolves to **xarray 2024.7.0**, i.e. the last release before
  DataTree, while every other environment gets 2025.6.1 or 2026.2.0. There is no
  version of xarray that has `DataTree` and runs on 3.9. The `dev` environment
  is already py310 (`pyproject.toml:230`), and py39 exists only to prove a
  production environment resolves (`pyproject.toml:236-238`), so the practical
  cost of the drop is low.
- **Proposed floors:** `requires-python = ">=3.10,<3.14"`, `xarray>=2024.11`.
  *Verify before committing:* whether DataTree coordinate inheritance semantics
  (which changed after the initial release) require a higher floor for the
  root-level shared coordinates described above; if so, raise to the first
  release where they settled rather than working around them.
- **NetCDF I/O for a `DataTree`** writes one netCDF group per node and needs a
  recent `netcdf4` or `h5netcdf`. *Verify* the exact minimum for
  `DataTree.to_netcdf` / `xr.open_datatree` with the `netcdf4` engine before
  pinning.
- **Zarr is a new, optional dependency** — it appears nowhere in the current
  lockfile. It belongs in an extra (`eradiate[cache]`), not in
  `dependencies`. *Verify:* zarr-python 3.x requires Python ≥ 3.11, which is
  above the proposed 3.10 floor. If that holds, the Zarr backend is gated on
  3.11+ (with zarr 2.18 as an alternative on 3.10) — which is precisely why
  `NetCDFStore` and not `ZarrStore` is the fallback that must always work.
- **Dask is not required.** It is needed only to make the `raw/` group lazy over
  a cached store, and only then. Keep it optional; do not let the storage design
  acquire a dask dependency by accident.

## Configuration surface

**Proposed.** Run-level arguments, with settings-file defaults through the
existing `eradiate.config` (dynaconf) mechanism:

```python
eradiate.run(
    exp,
    cache="runs/s2a_full",     # None (default) → MemoryStore
    cache_format="zarr",       # "zarr" | "netcdf"; default: zarr if available
    resume=True,               # False → refuse to reuse a populated cache
    checkpoint_interval=30.0,  # seconds
    raw="keep",                # "keep" | "stream"
    raw_dtype="float32",
    debug_bitmaps=None,        # None | "keep" | "write:<dir>"
)
```

`eradiate.plan(exp, cache=...)` returns the `LoopPlan` without running anything,
so "how long will this take and is there room for it" is answerable before
committing a cluster job.

## Transfer to the CDISORT backend

**Proposed.** Nothing in this note is Mitsuba-specific except the bitmap
reconstruction, which has no analogue there because the intermediate is already
a NumPy array.

What `eradiate-disort` gains: `_collect_results`'s nine allocations per
iteration disappear (`src/eradiate_disort/_backend.py:373`); `stacked_data`'s
NaN-padded dense `(w, g)` array disappears with the flat spectral axis
(`src/eradiate_disort/_pipeline.py:129`); `_pipeline.py` keeps only its
per-measure dataset builders, which are the part that is actually about DISORT.
Its `aggregated_data` node already delegates to Eradiate's
`aggregate_ckd_quad`, so it inherits the vectorized reduction for free.

What it must provide: `layout()` from `ntau`/`numu`/`nphi` and the measure
table, and the pre-loop evaluation of the merged `utau` discussed in
[`spectral_loop.md`](spectral_loop.md).

Its own `requires-python` is already `>=3.10` and its xarray floor already
`>=2024.11`, so the version consequences above cost it nothing.

## Open questions

**Does the cache hold raw or aggregated data?** Raw allows exact resumption and
re-aggregation; aggregated is up to 16× smaller in CKD and enough for most
resumed runs. The streaming mode makes this a real choice rather than a
trade-off to agonize over, but the default has to be picked.

**Does `raw/` ship inside an exported NetCDF result?** Including it makes the
result self-describing and possibly enormous; excluding it makes exported results
non-reproducible without a re-run. Probably: excluded by default, one flag.

**Cache portability.** Is a cache expected to move between machines and Eradiate
versions? The fingerprint currently says no — any version change invalidates it.
That is safe and possibly too strict for a cache that took a day to fill.

**Multi-process writers.** Zarr's per-chunk objects make this nearly free at the
storage level, but the plan, the completion mask and the lock all assume one
writer. Tied to the parallel-iteration question in
[`spectral_loop.md`](spectral_loop.md).
