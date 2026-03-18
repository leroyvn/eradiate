# Eradiate v2: Design Notes And Update Plan

This document collects the list of evolutions foreseen for Eradiate v2. Some
changes are extremely intrusive, while others can be implemented in Eradiate v1
without significantly breaking the interface.

## Things that work and we want to keep

- Configuration of the 1D solver: `AtmosphereExperiment` configuration syntax
  is fine, we can keep it
- Mode and variant selection
- Pint-based unit processing

## Things we need to change

- Separate configuration and radiometric backend (applies mostly for 1D scenes,
  3D scenes would only run through Mitsuba) → backend architecture
- Data formats:
  - New aerosol data format (derived from libRadtran)
  - New atmospheric database format
  - New atmospheric profile format
- Dict-based Mitsuba scene construction: Transition to early instantiation of
  objects to save up memory and make objects more accessible
- Mitsuba object wrapping: New `SceneObject` abstraction that colocates a Mitsuba
  object together with scene parameter updates
- Wavelength in the simulation: use spectral variant or add wavelength awareness
  to mono variant (second is less intrusive)
- Smarter sample count:
  - With uniform or delta SRF: Apply SPP to each wavelength (mono) or bin (CKD)
  - With band SRF: Apply SPP to whole band, distribute it on SRF pro rata of bin
    bin weight in final measurand
- Documentation: Reorganize user manual, increase tutorial coverage, port
  numerical methods document
  (~ATBD) to Sphinx
- LLVM variant support
- Material library / definitions
- Coordinate transformations
- Single-precision support
- Dict syntax for Pinttrs input: Deprecate `{"<field>": ..., "<field>_units": ...}`
  for units, and instead use `{"<field>": {"magnitude": ..., "value": ...}}`
