from __future__ import annotations

import pint
from axsdb import AbsorptionDatabase

from .object import Object


class Atmosphere(Object):
    components: list[AtmosphereComponent]


class AtmosphereComponent(Object):
    top: pint.Quantity
    bottom: pint.Quantity
    has_absorption: bool
    has_scattering: bool


class MolecularAtmosphere(AtmosphereComponent):
    absorption_database: AbsorptionDatabase
    profile: AtmosphericProfile  # Interface to the thermoprops xarray dataset


class ParticleLayer(AtmosphereComponent):
    particle_properties: ParticleProperties  # Interface to the Aer v2 data format
    tau_ref: pint.Quantity
    w_ref: pint.Quantity
    distribution: ParticleDistribution  # Same as before
