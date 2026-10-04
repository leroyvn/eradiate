# Dev fix branch task list

*This document can be edited by an AI agent.*

This is the list of codebase cleanup tasks. When relevant, dev instructions
must be updated. At the end of the work on that branch, we should have clear
coding guidelines that a combination of linter, CI and agent should be able to
enforce.

Tasks with an asterisk have an explanation section that has the task name as its
title.

This document must be deleted once the work on this branch is completed.

**Tooling**

- [ ] Make the codebase REUSE compliant.
- [ ] Make the codebase Repo Review compliant.
- [ ] Align tooling with other Eradiate subprojects (*e.g.* eradiate-disort).
- [ ] Enforce linting, formatting, type checking with prek in CI.

**Coding hygiene**

- [x] Make linter more aggressive.
- [x] Make a full linter pass.
- [x] Remove all absolute imports at module top level from the codebase.
- [x] Remove aliases to the `typing` module (*e.g.* `import typing as t`).
- [x] Remove aliases to the `numpy.typing` module (`import numpy.typing as npt`).
- [x] Switch to attrs modern API.
- [x] Enforce Python 3.10+ typing annotations.
- [x] Move all compatibility shims to a `compat` module.
- [x] Pint hygiene: apply relevant Pint usage guidelines.
- [ ] Delete the `dev` environment.
- [ ] Add ty type checking to prek.

**Refactoring**

- [ ] Hunt unnecessary Numpy array copies (using `np.array()` instead of `np.asarray()`).
- [ ] Review raised exceptions for their type, and fix it if inappropriate.
- [ ] Refactor the features of the `srf_tools` module into the `SRF` classes.
- [ ] Issue a deprecation warning for DEM classes (decision: delete them?).
- [ ] Rename `test_tools` to `testing`; keep a compatibility alias with deprecation warning.
- [ ] Review full test suite: delete useless tests, refactor all tests into classes.
- [ ] Rewrite post-processing pipeline tests (make them cleaner, nicer to follow and debug).
- [ ] Benchmark makeover: switch from ASV to pytest-benchmark, following the pattern in other Eradiate repos.
- [ ] Tutorial makeover: turn into smoke tests, sync with Jupytext.
- [ ] Data validation: Remove Cerberus prototype, add Pandera validation (requires Python 3.10+).
- [ ] Upgrade to Pintext (requires Python 3.10+).

**Documentation**

- [ ] Rewrite user manual.
- [ ] Update developer guide (concise dev guide, more consistent dev notes, good practices guide).
- [ ] Add AI instructions (including AGENTS.md).
