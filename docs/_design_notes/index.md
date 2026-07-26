# Eradiate v2 — design notes

Working documents for the design of the next iteration of Eradiate, prototyped in
`src/eradiate/two/`. Audience: developers working on v2. These files are not part of
the Sphinx build.

## Files

| File | Contents | Stability |
|---|---|---|
| [`architecture.md`](architecture.md) | Layer split, object model rules, spectral loop | Stable design |
| [`configuration_layer.md`](configuration_layer.md) | Pydantic configuration layer, units, serde, data formats | Stable design |
| [`kernel_interface.md`](kernel_interface.md) | Mitsuba interface, update protocol, wavelength handling | Stable design |
| [`status.md`](status.md) | Prototype state and ordered roadmap | **Living** — expected to go stale |

Read `architecture.md` first; it states the layer split every other file assumes.
`status.md` is the only file that answers "what should I work on now"; the other three
answer "what is this supposed to look like, and why".

## Section markers

Every section of the three design files carries one of:

- **Settled** — decided, and the prototype backs it. Change it only with a reason
  recorded here.
- **Proposed** — a concrete design that has not been implemented or validated.
- **Open** — a question with no answer yet. Do not build on it without deciding first.

## Out of scope

These notes cover v2 architecture only. Also in this directory, unrelated and
unmaintained by the above:

- [`testing_framework.md`](testing_framework.md) — specification for a pytest-based
  testing, regression and benchmarking framework. Applies to v1 and v2 alike.
- [`refactoring_class_machinery.md`](refactoring_class_machinery.md) — plan for the v1
  attrs field-documentation and stub-generation machinery. Note that it targets paths
  under `ext/eradiate/` and a uv/taskipy workflow, neither of which matches this
  repository; and that the v2 configuration layer replaces `documented()` with
  Pydantic. Its relevance needs a separate decision.

Published developer documentation lives in `docs/developer_guide/`; nothing here is
published.

## Archive

The `archive/` directory holds the superseded notes these files were consolidated from.
They are kept because they contain detail dropped in condensing, and are not
maintained.

- [`two.md`](archive/two.md) — the original v2 wishlist: what to keep from v1, what to
  change.
- [`two_assessment.md`](archive/two_assessment.md) — audit of the `two` prototype
  (2026-07-26), with the per-test narrative that led to the rules in
  `kernel_interface.md`.
- [`feature_mono_wavelength.md`](archive/feature_mono_wavelength.md) — feasibility study
  for wavelength support in Mitsuba's mono variants, with full C++ excerpts and a
  key-files reference.
