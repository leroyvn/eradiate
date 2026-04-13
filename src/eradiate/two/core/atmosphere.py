from __future__ import annotations

from typing import Literal

import pint
from axsdb import AbsorptionDatabase
from pydantic import ConfigDict, model_validator

from ._factory import Registry
from .object import Object

atmosphere_registry: Registry["Atmosphere"] = Registry("atmosphere")
atmosphere_component_registry: Registry["AtmosphereComponent"] = Registry(
    "atmosphere_component"
)


class Atmosphere(Object):
    """
    Atmosphere configuration object.

    An atmosphere is composed of one or more :class:`AtmosphereComponent`
    instances (e.g. molecular atmosphere, particle layers).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    components: list[AtmosphereComponent]

    @model_validator(mode="wrap")
    @classmethod
    def _dispatch(cls, value, handler, info):
        if cls is not Atmosphere:
            return handler(value)
        return atmosphere_registry.dispatch(value, handler, Atmosphere)


class AtmosphereComponent(Object):
    """
    Abstract base class for atmosphere layer components.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    top: pint.Quantity
    bottom: pint.Quantity
    has_absorption: bool
    has_scattering: bool

    @model_validator(mode="wrap")
    @classmethod
    def _dispatch(cls, value, handler, info):
        if cls is not AtmosphereComponent:
            return handler(value)
        return atmosphere_component_registry.dispatch(
            value, handler, AtmosphereComponent
        )


class MolecularAtmosphere(AtmosphereComponent):
    """
    Molecular (gas-phase) atmosphere component.

    Parameters
    ----------
    absorption_database : AbsorptionDatabase
        Absorption cross-section database.
    profile : AtmosphericProfile
        Thermodynamic profile (pressure, temperature, concentrations).
    """

    type: Literal["molecular"] = "molecular"
    absorption_database: AbsorptionDatabase
    profile: AtmosphericProfile  # Interface to the thermoprops xarray dataset


class ParticleLayer(AtmosphereComponent):
    """
    Particulate (aerosol/cloud) atmosphere layer.

    Parameters
    ----------
    particle_properties : ParticleProperties
        Single-scattering properties dataset (Aer v2 format).
    tau_ref : pint.Quantity
        Optical thickness at the reference wavelength.
    w_ref : pint.Quantity
        Reference wavelength for ``tau_ref``.
    distribution : ParticleDistribution
        Vertical distribution of particles within the layer.
    """

    type: Literal["particle_layer"] = "particle_layer"
    particle_properties: ParticleProperties  # Interface to the Aer v2 data format
    tau_ref: pint.Quantity
    w_ref: pint.Quantity
    distribution: ParticleDistribution  # Same as before


# ---------------------------------------------------------------------------
# Registry population
# ---------------------------------------------------------------------------

atmosphere_component_registry.register("molecular", MolecularAtmosphere)
atmosphere_component_registry.register("particle_layer", ParticleLayer)
