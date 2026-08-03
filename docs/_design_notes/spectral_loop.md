# The spectral loop

How the spectral loop is driven, what it produces, and who owns which part of it.
This note supersedes the "The spectral loop" section of
[`architecture.md`](architecture.md) and answers its "Who owns the spectral loop"
open question. Storage, caching and the shape of the final data structure are in
[`result_storage.md`](result_storage.md); the two notes were written together and
only make sense together.

Scope: the driver and the per-iteration contract. Applies to the Mitsuba backend
and, unchanged in structure, to the CDISORT backend in
[`eradiate-disort`](https://github.com/eradiate/eradiate-disort), where Mitsuba
bitmaps are replaced by NumPy arrays read out of `nanodisort.DisortState`.

## What is wrong today

**Measured**, on `main` (v1) as of 2026-08-03. File references are to v1 because
that is where the working implementation lives; the v2 prototype has not reached
this code path yet.

The loop and the post-processing pipeline are separated by a dictionary of
Mitsuba bitmaps, and everything expensive follows from that.

1. **Every bitmap of the run is alive at once.** `mi_render`
   (`src/eradiate/kernel/_render.py:379`) returns
   `dict[si_hashable, dict[sensor_id, mi.Bitmap]]`, and `Experiment.process`
   (`src/eradiate/experiments/_core.py:730`) re-splits each of them into
   per-measure dicts stored on `Measure.mi_results`. Nothing is ever released
   until `clear()` is called.

2. **Post-processing rebuilds the data structure one iteration at a time.**
   `gather_bitmaps` (`src/eradiate/pipelines/logic.py:589`) creates, *per
   spectral index*: one `DataArray` for `spp`, one for the bitmap (via
   `bitmap_to_dataarray`, which builds five coordinate arrays), one
   `expand_dims` copy, and one more of each if variance is on. It then calls
   `xr.combine_by_coords` once over the whole list. For a full-spectrum CKD run
   (order 10³ bins × up to 16 quadrature points) that is order 10⁵ short-lived
   xarray and NumPy objects, followed by an alignment over 10⁴ objects.

3. **The bitmap is copied at least three times** on its way to the result array:
   `mi.Bitmap(film.bitmap())` in `mi_render`, `np.array(bmp, dtype="float64")`
   in `bitmap_to_dataarray` (also doubling the footprint — the film's component
   format is `float32`), and the `expand_dims` copy.

4. **CKD aggregation iterates in Python over every pixel.**
   `aggregate_ckd_quad` (`src/eradiate/pipelines/logic.py:147`) loops over bins
   and, inside, over `itertools.product` of all non-spectral dimensions. The
   comment at line 150 explains why it was written that way; the answer is not
   to index differently but not to loop at all.

5. **A run cannot be resumed.** State lives only in process memory. A crash — or
   a walltime limit on a cluster — at iteration 15 999 of 16 000 costs the whole
   run.

The redesign addresses 1–5 with one change of shape: **allocate the final
storage before the loop starts and have the loop write into it**, then make the
optional persistence of that storage a property of where it was allocated rather
than a separate mechanism.

## Shape of the new design

**Proposed.**

```
 plan(exp)      ─►  LoopPlan       iteration table, per-measure activity,
                                   spp per iteration, sizes, cached mask,
                                   effective (remaining) length, cost estimate
                        │
 allocate()     ─►  RawStore       dense arrays, one flat spectral axis,
                                   one group per measure  (memory | on drive)
                        │
      ┌─────────────────┴──────────────────────────────┐
      │  for i, ctx in plan.remaining():               │
      │      frame = store.frame(i)   # writable views │
      │      backend.solve(ctx, frame)  # writes here  │
      │      store.commit(i)          # checkpoint pol.│
      └─────────────────┬──────────────────────────────┘
                        │
 postprocess()  ─►  label → aggregate → derive  ─►  xr.DataTree
```

Three properties fall out of it:

- The loop allocates nothing per iteration. The backend writes into views of
  arrays that already exist.
- Whether those arrays live in RAM or on drive is one constructor argument. The
  per-iteration code path is identical either way (see the write-behind buffer
  in [`result_storage.md`](result_storage.md)).
- Post-processing starts from one dense array per variable per measure. Its cost
  stops depending on the iteration count in any Python-object sense.

## The flat spectral axis

**Proposed.** This is the load-bearing decision; several others follow from it.

Raw arrays carry a single spectral dimension `si`, of length equal to the number
of loop iterations, and *not* the `(w, g)` product used today. `w`, `g` and the
bin index are non-dimension coordinates along `si`:

```
radiance          (si, y_index, x_index[, stokes])   float32
w                 (si,)                              float64   [nm]
g                 (si,)                              float64   — CKD only
bin_index         (si,)                              int32     — CKD only
spp               (si,)                              int64
```

Rationale, in order of weight:

- **No padding waste.** CKD quadrature is adaptive: `CKDSpectralGrid.walk_quads`
  yields a per-bin quadrature whose node count varies. A dense `(w, g)` array
  must be sized at `max(ng)` and NaN-filled elsewhere — today's
  `combine_by_coords` produces exactly that, as does `stacked_data` in
  `eradiate-disort` (`src/eradiate_disort/_pipeline.py:129`, an explicit
  `np.full(..., np.nan)`). The flat axis holds exactly the points that were
  computed.
- **Resumption is index-based.** Iteration `i` ↔ slot `i` ↔ one entry in the
  completion mask. No coordinate lookup, no partial-bin bookkeeping.
- **Aggregation becomes a segmented reduction.** The plan guarantees bin-major,
  ascending iteration order (v1 already sorts contexts that way,
  `src/eradiate/experiments/_core.py:622`), so the CKD quadrature is
  `np.add.reduceat` over `si` with per-node weights — one vectorized call
  replacing the nested Python loop of point 4 above.
- **Mono mode collapses to the trivial case.** `si` *is* the wavelength axis;
  the raw array *is* the final array. Nothing to aggregate, nothing to copy.

The `(w, g)` view is recoverable — it is a reshape when the quadrature is
uniform and a `groupby` otherwise — but it is not the storage layout.

## The frame protocol

**Proposed.** The contract between the driver and any backend.

```python
@dataclass(frozen=True)
class VarSpec:
    dims: tuple[str, ...]      # trailing dims, excluding the leading "si"
    shape: tuple[int, ...]
    dtype: np.dtype            # float32 by default; see result_storage.md
    attrs: dict                # units, long_name, …

@dataclass(frozen=True)
class RawLayout:
    # measure id -> variable name -> spec
    variables: dict[str, dict[str, VarSpec]]
    coords: dict[str, VarSpec]      # per-measure coordinate arrays (vza, …)
    attrs: dict                     # channel names, pixel format, backend id


class LoopBackend(Protocol):
    def layout(self, exp, plan: LoopPlan) -> RawLayout: ...
    def setup_global(self, exp, plan: LoopPlan) -> None: ...
    def setup_spectral(self, ctx: KernelContext) -> None: ...
    def solve(self, ctx: KernelContext, frame: Frame) -> None: ...
```

`Frame` is a mapping from `(measure_id, var_name)` to a writable NumPy view into
the store at index `i`. Three rules make the whole thing work:

1. `solve` **must** fill every variable the layout declares as active for that
   iteration, and **must not** allocate result arrays — it writes into the views
   it is given.
2. `solve` never touches xarray. Coordinates, units and metadata come from
   `layout()` and are applied once, after the loop.
3. `layout()` is called before allocation and must be exact. Everything the
   driver needs to size the store — film resolution, Stokes and moment channels,
   number of optical depth levels — is known then.

### Mitsuba mapping

`solve` becomes: update parameters, `mi.render(...)`, then copy the film into
the frame. The copy is direct and single:

```python
img = np.asarray(sensor.film().bitmap(), copy=False)   # (h, w, c) float32
np.copyto(frame[mid, "radiance"], img[..., channel_index])
```

Channel selection uses an index map computed once in `setup_global` from the
integrator flags, replacing the per-iteration `Bitmap.split()` and pixel-format
conversion in `Experiment.process` (`src/eradiate/experiments/_core.py:735-742`).
Stokes components and the second moment become declared trailing axes of the
layout rather than separate bitmaps in a dict. Net effect per iteration: three
copies and a dict of `mi.Bitmap` objects become one `np.copyto`.

The `mi.Bitmap` objects themselves are no longer retained — see "Raw bitmaps
stay reachable" in [`result_storage.md`](result_storage.md), which is a
requirement, not an afterthought.

### CDISORT mapping

`eradiate-disort` is already close: `_collect_results`
(`src/eradiate_disort/_backend.py:373`) builds a dict of nine freshly allocated
NumPy arrays per iteration, and `stacked_data` re-stacks them afterwards. Under
the frame protocol both disappear:

```python
def solve(self, ctx, frame):
    self._state.solve()
    ds = self._state
    for name in self._fields:                # rfldir, rfldn, flup, …
        frame[self._mid, name][:] = getattr(ds, name)
    if self._has_radiance:
        frame[self._mid, "uu"][:] = ds.uu
```

`layout()` there is a function of `ntau`, `numu`, `nphi` and the measure table —
all fixed after `_setup_global`, which is where they are computed today. The
DISORT backend's `_setup_spectral` / `_solve` split maps onto
`setup_spectral` / `solve` with no change of meaning.

One wrinkle, already documented in that repository's `CLAUDE.md`: `ntau` is only
known after `compute_measures_info`, which depends on the spectrally varying
optical depth. `ds.allocate()` therefore happens on the first iteration. The
layout needs `ntau` *before* the first iteration, so `plan()` must evaluate the
merged `utau` for the reference spectral context — one extra evaluation, once
per run, and it makes the "allocate exactly once, before any assignment" rule an
invariant of the driver instead of a `first_call` flag.

## The run plan

**Proposed.** `LoopPlan` is what makes "how much is left to compute" answerable,
and it is cheap to build — it needs the spectral grids and the measure table,
nothing from the kernel.

```python
plan = backend.plan(exp)          # or SpectralLoop.plan(exp, cache=...)

plan.n_total          # iterations in the full loop
plan.n_cached         # iterations already present and flagged done in the cache
plan.n_remaining      # effective loop length
plan.measures         # per measure: active iteration mask, film shape, bytes
plan.nbytes_raw       # total raw storage the run needs
plan.nbytes_remaining # what is still to be written
plan.eta              # None, or an estimate — see below
```

`repr` prints the table; `_repr_html_` gives the notebook version. `plan()` is
also the natural place to fail early: with `nbytes_raw` in hand, the driver
checks free space on the cache device before allocating anything and refuses a
run that cannot finish, rather than dying at 90 %.

**Estimating the remaining cost.** Three sources, in increasing order of
reliability:

- *Static proxy* — `Σ_i spp_i × n_pixels` for Mitsuba, `n_iterations × nlyr ×
  nstr²` (or similar) for DISORT. Comparable across configurations of the same
  scene; useless in seconds.
- *Calibration* — time the first `k` iterations and extrapolate over the
  remaining ones, weighted by the static proxy so that a band SRF with unequal
  per-iteration sample counts extrapolates correctly.
- *Recorded timings* — the store keeps `walltime (si)` alongside the data
  (a few bytes per iteration). On resume, the ETA for the remaining iterations
  comes from measurements of *this* configuration on *this* machine.

The estimate is reported as an estimate. Absorption-database I/O, first-touch
page faults and CKD bins with wildly different quadrature sizes all break naive
extrapolation; the calibration weighting handles the third and nothing handles
the first two except saying so.

## Sample count allocation

**Proposed**, carried over unchanged from [`architecture.md`](architecture.md)
and given a home in the plan:

- Uniform or delta SRF — the requested `spp` applies to each wavelength (mono)
  or each bin (CKD).
- Band SRF — the requested `spp` applies to the *whole band*, distributed over
  the grid pro rata of each bin's weight in the final measurand.

The consequence for this note is that `spp` varies per iteration, so it is a
column of the plan's iteration table and a coordinate of the raw store, and it
participates in the ETA weighting above. It must be persisted in the cache: a
resumed run that recomputes `spp` from a changed SRF would silently mix sample
counts, which is what the run fingerprint (see
[`result_storage.md`](result_storage.md)) exists to prevent.

## Progress reporting

**Proposed.** Small, but it is the visible face of the plan.

- The progress bar's total is `n_remaining`, not `n_total`; the description
  states how many iterations were skipped as cached, so a resumed run does not
  look like a shorter run.
- The bar updates the recorded per-iteration walltime, which feeds both the ETA
  and the next run's estimate.
- Checkpoint flushes are visible in the description (`⤓` marker or similar) so
  that IO stalls are attributable.
- The existing gating on `config.settings.progress` and `ProgressLevel` is kept.

## What this does to post-processing

**Proposed.** The pipeline stops being where the data structure is built and
becomes only where physics is applied.

| Today | After |
|---|---|
| `gather_bitmaps` — O(n_iterations) xarray objects, then `combine_by_coords` | deleted |
| — | `label_raw` — wraps the store's dense arrays in `DataArray`s and attaches coordinates and metadata; O(1) in iteration count |
| `aggregate_ckd_quad` — Python loop over bins × pixel product | segmented weighted reduction over `si` (`np.add.reduceat`); one call per variable |
| `moment2_to_variance`, `apply_spectral_response`, `compute_bidirectional_reflectance`, `compute_albedo`, `radiosity`, `degree_of_linear_polarization` | unchanged — already array-level |

The variance path needs the same treatment as the mean: the CKD variance
aggregation weights by `w²` (`src/eradiate/pipelines/logic.py:157-163`), which
is the same `reduceat` with squared weights.

`Pipeline` (the DAG engine) is not in question here. What changes is the input
contract of its first node: `bitmaps` (a dict of `mi.Bitmap`) becomes `raw` (a
group of dense arrays plus a coordinate table). In v1 this can be done without
touching the DAG's shape by keeping the node name and making it a pass-through;
in v2 the node is simply not there.

**Acceptance criterion.** A benchmark under `benchmarks/` that post-processes a
recorded raw store for a CKD run of ≥ 10³ iterations, run against both
implementations. The claim to be checked is that post-processing time becomes
proportional to the data volume rather than to the iteration count; state the
measured ratio in `status.md` rather than predicting it here.

## Who owns what

**Proposed.** This is the answer to the open question in
[`architecture.md`](architecture.md).

**The driver** (`SpectralLoop`, backend-agnostic, one implementation) owns:
iteration order, sample count allocation, the store and its lifetime,
checkpointing, resumption, the plan and the ETA, progress reporting, and the
final labelling of raw arrays.

**The backend** owns: `layout()`, global and per-iteration setup, and `solve()`.
It sees one spectral index and a set of writable views at a time. It never
decides how many iterations there are, never allocates result storage, and never
touches xarray.

That split is what stops the SPP-distribution and caching logic from being
duplicated in every backend — the concrete failure mode the open question was
worried about. It also gives the second backend a much smaller surface to
implement: `eradiate-disort` under this protocol is `layout()` plus a ten-line
`solve()`.

## Open questions

**Batched and parallel iterations.** Mitsuba renders sensors sequentially inside
one context; DISORT solves are independent and embarrassingly parallel across
spectral indices. The frame protocol is compatible with a worker pool — frames
are indexed and disjoint — but commit ordering, the completion mask and the
progress bar all assume sequential completion. Decide before, not after,
somebody wraps the loop in a `ThreadPoolExecutor`.

**Streaming aggregation as the default.** If raw data is dropped as soon as its
bin is fully aggregated, peak memory becomes the size of the *final* result plus
one bin's worth of raw. Section "Two population modes" of
[`result_storage.md`](result_storage.md) develops this; whether it should be the
default, or an option for large runs, depends on how often raw data is actually
wanted after the fact.

**Where the measure ↔ sensor mapping lives.** v1 resolves it in
`Experiment.contexts` (`src/eradiate/experiments/_core.py:595`) against a live
Mitsuba scene, which means the plan cannot be built before `init()`. For the
plan to be a pre-flight artefact, the mapping has to come from the configuration
layer instead. This is entangled with the "Measurement modelling" open question
in [`architecture.md`](architecture.md).

**`spp` override placement.** `run(exp, spp=...)` currently overrides every
measure's sample count. With per-iteration allocation, an override is a scaling
factor on the distribution, not a value — the API should say which.
