# Configuration layer

The user-facing description of a simulation: `eradiate.two.core`. Pydantic models, no
kernel state, fully serialisable. See [`architecture.md`](architecture.md) for where
this sits.

*Consolidated from [`archive/two.md`](archive/two.md) and
[`archive/two_assessment.md`](archive/two_assessment.md).*

## Why Pydantic

**Settled.** v1 uses attrs with `pinttrs` and a home-grown documentation layer. v2 moves
the configuration layer to Pydantic for two things: declarative validation, and
serialisation/deserialisation.

Serde is the acceptance criterion. A configuration that cannot round-trip through JSON
is not done, whatever else it validates. This bears repeating because the prototype
passes validation and fails serialisation (see below).

The kernel layer stays on attrs — it is internal, never serialised, and attrs is a
better fit for objects holding live Mitsuba pointers.

## Base class and open-world dispatch

**Settled** in mechanism, **Proposed** in form.

Every configuration type family (spectrum, material, surface, illumination, atmosphere
component, measurement) accepts `{"type": "...", ...}` dicts and resolves them to a
concrete class. Pydantic's native discriminated unions cannot express this: they need a
closed union, and backends register their own concrete types at import time. The
registry in `two/core/_factory.py` is therefore the right call, not an accident.

What is wrong is its ergonomics. Each base class carries an identical six-line
`_dispatch` wrap-validator, copy-pasted seven times:

```python
@model_validator(mode="wrap")
@classmethod
def _dispatch(cls, value, handler, info):
    if cls is not BaseSpectrum:
        return handler(value)
    return spectrum_registry.dispatch(value, handler, BaseSpectrum)
```

Fold it into the `Object` base via `__init_subclass__`, with the registry declared as a
class attribute. One implementation, no per-module boilerplate, and no opportunity to
paste the wrong base class name.

## Units and Pydantic

**Open — this is the central unsolved problem of the layer.**

Pint quantities are not Pydantic-native, and the prototype works around this per field:

- `ConfigDict(arbitrary_types_allowed=True)` repeated in six classes;
- one `field_validator(mode="before")` per quantity field, each re-doing `ensure_units`;
- quantity-compatibility checked ad hoc in `model_validator(mode="after")` —
  `spectrum.py` alone contains two near-identical ~30-line blocks;
- and no serialisation at all: `model_dump_json()` raises
  `Unable to serialize unknown type: pint.Quantity`.

That is roughly 150 lines of boilerplate across four modules, and it fails the
acceptance criterion.

The fix is one annotated type, written once:

```python
Wavelength = Annotated[pint.Quantity, QuantityField(quantity="wavelength")]

class InterpolatedSpectrum(BaseSpectrum):
    wavelengths: Wavelength
    values: SpectralValue  # units checked against the `quantity` field
```

`QuantityField.__get_pydantic_core_schema__` performs coercion of bare values to the
configuration units, checks compatibility against the declared physical quantity, and
installs a serialiser. Serialised form:

```json
{"value": 550.0, "units": "nm"}
```

This also settles a separate item: the `{"<field>": ..., "<field>_units": ...}` dict
syntax inherited from pinttrs is deprecated in v2, replaced by the nested form above.
One object, two problems.

Do this before writing more configuration classes. Every class written first is a class
to migrate afterwards.

## Serialisation contract

**Proposed.** A configuration must round-trip: `Experiment.model_validate(exp.model_dump())`
reconstructs an equivalent object, and the JSON form is stable enough to store next to
results.

This constrains fields backed by large datasets — `AtmosphericProfile` wraps an xarray
`Dataset`, `MolecularAtmosphere` holds an `AbsorptionDatabase`. These serialise as
**references** (identifier, path, or dataset keyword), never as embedded data. The
loader stays on the class; the serialised form stays small.

Corollary: the identifier space for datasets has to be stable, which is part of why the
data formats below need settling.

## Data formats

**Open.** Three format changes are wanted, none specified yet:

- **Aerosol / particle single-scattering properties** — new format derived from
  libRadtran's. Consumer: `ParticleLayer.particle_properties`.
- **Absorption database** — new format. Consumer: `MolecularAtmosphere.absorption_database`
  (currently `axsdb.AbsorptionDatabase`).
- **Atmospheric profile** — new format. Consumer: `AtmosphericProfile`, today a thin
  wrapper over a Joseki dataset.

Each needs its own specification before the corresponding configuration classes can be
finished. `ParticleLayer` currently references `ParticleProperties` and
`ParticleDistribution`, neither of which exists.

## Open questions

- **Measurement configuration** is an empty stub (`BaseMeasurement`), and its design is
  tied to spectral loop ownership — see [`architecture.md`](architecture.md).
- **Coordinate transformations** are listed as a v2 feature with no home in the current
  layer structure. Configuration-level (a scene-graph transform on geometry) or
  kernel-level?
- **Material library** — v2 wants named, reusable material definitions. Is that a
  registry of configuration objects, a data format, or both?
