# Atmosphere interface redesign: tasks

Decisions from user (2026-09-30):

- `particle_extinction`: sigma_t and albedo fully user-supplied (spectral
  dependence included); properties supply the phase function only
- Container: nested `components` dict under `{"type": "heterogeneous", ...}`
- State-driven family (`particle_state`): arbitrary state variables over a
  name-agnostic core; only the PSD preset (`particle_psd`) for now
  (2026-10-01)
- Backward compatibility: deprecation aliases for names released on main
  only; branch-only names and formats (`prt_v1`, `ppr_v1`) are amended or
  replaced without alias (2026-10-01)
- Keep the `Component` class suffix; the dict interface is the concise entry
  point (2026-10-01)
- No per-column AOT; if needed later, add a
  `ParticleExtinctionComponent.from_aot()` helper (2026-10-01)

Tasks:

- [x] Survey current classes (ParticleEnsemble, ParticleField, ParticleProfile,
      ParticleProperties, ParticleFieldPhaseFunction, MolecularAtmosphere,
      HeterogeneousAtmosphere, ParticleDistribution) and main's interface
- [x] Resolve ambiguities with user
- [x] Write `proposal.md`: diagnosis, nomenclature, hierarchy, dict interface,
      data formats, deprecation aliases, open questions
- [x] Write `interface.py`: revised dict examples
- [x] Write `hierarchy.py`: class skeletons + name-agnostic state-driven
      evaluation sketch
- [x] Checkpoint commit (needs `git add -f`: `playgrounds/` is in
      `.git/info/exclude`; waiting on user)
