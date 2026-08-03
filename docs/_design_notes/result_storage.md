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
| 8 | Reruns may differ for users; developers keep reproducibility | Seed is pure in loop state, `run_seed` fixed or fresh per run, always recorded |

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
- the Eradiate and kernel versions.

The run seed is deliberately *not* part of the hash; it is stored as its own
attribute and handled by the rules below.

`RawStore.open` refuses a mismatch. `resume="force"` overrides it for the case
where the user knows the difference is cosmetic; nothing else does.

## Seeding

**Proposed**, and a correctness prerequisite for caching rather than an
optimization.

Seeds are currently drawn from a sequential stream: `mi_render` calls
`seed_state.next()` once per sensor per iteration
(`src/eradiate/kernel/_render.py:453`). A run resumed at iteration `k` draws
different seeds than an uninterrupted one, so a resumed run is neither
reproducible nor a faithful continuation of the run it claims to continue. Two
separate concerns hide in that single stream; the design separates them.

**Within a run, the seed is a pure function of loop state.**

```python
seed = np.random.SeedSequence(
    entropy=run_seed, spawn_key=(iteration_index, sensor_index)
).generate_state(1)[0]
```

No stream position is involved, so iteration `i` gets the same seed whether it
runs first, last, or after a resume. `SeedState` gains a `derive(*key)` method
for this; `next()` stays for the callers that legitimately want a stream
(`numpy_default_rng`). One welcome side effect: `SeedState.reset()` calls that
exist only to rewind the stream between paired runs — for instance
`tests/02_system/test_compare_canopy_atmosphere.py:113` — stop being necessary.

**Across runs, `run_seed` decides whether results repeat.** The mechanism
already exists and does not need inventing: the `rng_seed` setting is either an
integer (packaged default `42`, `src/eradiate/config/eradiate.toml:30`) or the
string `"random"`, which seeds from OS entropy. What changes is that the
*effective* run seed — the configured integer, or the entropy actually drawn —
is **recorded**: in the store's root attrs, and in the provenance attrs of the
result tree.

That serves both audiences without a compromise between them:

- a developer runs with a fixed `rng_seed` and gets identical results across
  runs, resumes and machines (modulo kernel non-determinism), which is what the
  regression suites already rely on;
- a user running with `rng_seed = "random"` gets a different Monte Carlo
  realisation on every run — which is what a Monte Carlo run should look like —
  and can still replay any particular one exactly by passing the recorded
  integer back.

Whether the packaged default should flip from `42` to `"random"` is a separate
call this design does not need to make. The regression suites pass their own
`SeedState` explicitly (`ert_seed_state`,
`src/eradiate/test_tools/fixtures/__init__.py:124`), so the default and the test
contract are already decoupled. Recorded provenance is the prerequisite either
way: flipping the default before results carry their seed would turn every
surprising result into an unreproducible one.

**Resumption always adopts the stored `run_seed`**, including under `"random"`.
Regenerating entropy mid-run would splice two different streams into one result.
If the user explicitly requests an integer seed differing from the stored one,
the resume is refused rather than silently reinterpreted; under `"random"` the
stored value is adopted without comment. This is why the seed sits outside the
fingerprint hash: it is reused, not compared.

## Concurrency

**Proposed. Single writer.** A lock file in the cache directory, holding pid and hostname,
refused politely if held. Concurrent writers to one cache are out of scope until
the parallel-iteration question in [`spectral_loop.md`](spectral_loop.md) is
settled.

## The raw store is kept whole

**Decided.** The store holds every iteration for the lifetime of the run. Peak
memory (or drive occupancy) is `plan.nbytes_raw`, and post-loop aggregation
reads the store once.

The alternative — releasing each CKD bin's raw slots as soon as the bin's last
quadrature node lands, since the plan iterates bin-major — was considered and
rejected. It would cut peak memory by roughly the quadrature size, but it costs
the two things the rest of this design is built on: raw data available after the
fact for debugging, and the ability to re-aggregate without re-running the
solver. It also makes the completion mask per bin instead of per iteration,
which complicates the one mechanism that has to stay simple. Not implemented,
and not planned.

Note that in mono mode the question is moot in any case: there is no
aggregation, so the raw array *is* the result array.

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
for an in-memory run it is the store's arrays themselves.

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
- **That means dropping Python 3.9 — decided.** Eradiate currently declares
  `requires-python = ">=3.9,<3.14"` (`pyproject.toml:12`) and `xarray>=2023`
  (`pyproject.toml:39`). The lockfile shows what that costs: the `py39`
  environment resolves to **xarray 2024.7.0**, i.e. the last release before
  DataTree, while every other environment gets 2025.6.1 or 2026.2.0. There is no
  version of xarray that has `DataTree` and runs on 3.9. The `dev` environment
  is already py310 (`pyproject.toml:230`), and py39 exists only to prove a
  production environment resolves (`pyproject.toml:236-238`). Python 3.9 is also
  past end of life, so the drop costs nothing that is still supported anyway.
- **Floors — decided:** `requires-python = ">=3.10,<3.14"`, `xarray>=2024.11`,
  matching what `eradiate-disort` already ships. **The floor stops at 3.10**;
  nothing in this design justifies 3.11, which is why the Zarr backend is
  optional rather than required (next-but-one bullet).
  *Verify before committing:* whether DataTree coordinate inheritance semantics
  (which changed after the initial release) require a higher xarray floor for
  the root-level shared coordinates described above; if so, raise the xarray
  floor to the first release where they settled rather than working around them.
  Raising the *Python* floor to get there is not on the table.
- **NetCDF I/O for a `DataTree`** writes one netCDF group per node and needs a
  recent `netcdf4` or `h5netcdf`. *Verify* the exact minimum for
  `DataTree.to_netcdf` / `xr.open_datatree` with the `netcdf4` engine before
  pinning.
- **Zarr is a new, optional dependency — decided.** It appears nowhere in the
  current lockfile, and it belongs in an extra (`eradiate[cache]`), never in
  `dependencies`. *Verify:* zarr-python 3.x requires Python ≥ 3.11, above the
  3.10 floor. If that holds, the Zarr backend is gated on 3.11+ (with zarr 2.18
  as an alternative on 3.10) and Eradiate itself stays installable on 3.10
  without it. This is exactly why `NetCDFStore`, on the already-required
  `netcdf4`, is the backend that must always work: no cache feature may make a
  Python version or a new dependency mandatory.
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
    raw_dtype="float32",
    debug_bitmaps=None,        # None | "keep" | "write:<dir>"
    seed=None,                 # int | "random" | None → the rng_seed setting
)
```

`seed` is a per-run override of the `rng_seed` setting; the effective value is
recorded in the results either way (see "Seeding"). On resume it is checked
against the stored seed, not applied over it.

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

**Should the packaged `rng_seed` default flip to `"random"`?** See "Seeding".
The design works either way and does not depend on the answer; it only requires
that the effective seed be recorded first.

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
