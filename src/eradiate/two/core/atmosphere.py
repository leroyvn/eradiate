from __future__ import annotations

import os
from typing import Any, Literal

import pint
import xarray as xr
from axsdb import AbsorptionDatabase
from pydantic import ConfigDict, field_validator, model_validator

from ._factory import Registry
from .object import Object
from ...units import to_quantity

atmosphere_registry: Registry["Atmosphere"] = Registry("atmosphere")
atmosphere_component_registry: Registry["AtmosphereComponent"] = Registry(
    "atmosphere_component"
)


class AtmosphericProfile(Object):
    """
    Thin wrapper around a `Joseki <https://joseki.readthedocs.io>`_
    thermophysical profile dataset.

    The wrapped dataset holds altitude ``z`` (levels) as its single dimension
    and, at minimum, pressure ``p``, temperature ``t``, number density ``n`` and
    per-molecule mole fractions ``x_M``. Query methods return :class:`pint.Quantity`
    values so callers do not have to reach into the xarray layer.

    Parameters
    ----------
    data : Dataset or path-like or dict
        * :class:`xarray.Dataset` — used as-is.
        * path-like — loaded from a NetCDF file via :func:`joseki.load_dataset`.
        * dict — forwarded to :func:`joseki.make` as keyword arguments.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    data: xr.Dataset

    @field_validator("data", mode="before")
    @classmethod
    def _coerce_data(cls, value: Any) -> xr.Dataset:
        import joseki  # noqa: PLC0415

        if isinstance(value, xr.Dataset):
            ds = value
        elif isinstance(value, (os.PathLike, str)):
            ds = joseki.load_dataset(value)
        elif isinstance(value, dict):
            ds = joseki.make(**value)
        else:
            raise TypeError(
                f"invalid type for 'data': {type(value)} "
                "(expected Dataset, path-like or dict)"
            )

        if not ds.joseki.is_valid:
            raise ValueError("'data' is not a valid Joseki thermophysical profile")
        return ds

    # -- Serialization ------------------------------------------------------

    @classmethod
    def from_netcdf(cls, path: str | os.PathLike) -> AtmosphericProfile:
        """Load a profile from a NetCDF file."""
        return cls(data=path)

    def to_netcdf(self, path: str | os.PathLike) -> None:
        """Write the wrapped profile to a NetCDF file."""
        self.data.to_netcdf(path)

    # -- Thermophysical queries ---------------------------------------------

    @property
    def z(self) -> pint.Quantity:
        """Altitude levels."""
        return to_quantity(self.data.z)

    @property
    def pressure(self) -> pint.Quantity:
        """Pressure at each level."""
        return to_quantity(self.data.p)

    @property
    def temperature(self) -> pint.Quantity:
        """Temperature at each level."""
        return to_quantity(self.data.t)

    @property
    def number_density(self) -> pint.Quantity:
        """Air number density at each level."""
        return to_quantity(self.data.n)

    @property
    def molecules(self) -> list[str]:
        """Molecules described by the profile."""
        return list(self.data.joseki.molecules)

    def mole_fraction(self, molecule: str) -> pint.Quantity:
        """Mole fraction of ``molecule`` at each level."""
        return to_quantity(self.data[f"x_{molecule}"])

    def column_number_density(self, molecule: str) -> pint.Quantity:
        """Column number density (integrated over altitude) of ``molecule``."""
        return self.data.joseki.column_number_density[molecule]

    def column_mass_density(self, molecule: str) -> pint.Quantity:
        """Column mass density (integrated over altitude) of ``molecule``."""
        return self.data.joseki.column_mass_density[molecule]

    def interp(
        self, z_new: pint.Quantity, method: str = "linear"
    ) -> AtmosphericProfile:
        """Interpolate the profile onto a new altitude grid ``z_new``."""
        from joseki.profiles.core import interp  # noqa: PLC0415

        return AtmosphericProfile(
            data=interp(self.data, z_new=z_new, method={"default": method})
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
    Abstract base class for atmosphere components.
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
        Thermophysical profile (pressure, temperature, concentrations).
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
