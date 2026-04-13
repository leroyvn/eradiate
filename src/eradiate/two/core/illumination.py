"""
Illumination configuration classes for the configuration layer.

These Pydantic-based classes represent the user-facing configuration of light
sources used in an Eradiate experiment. They are independent of the rendering
backend: no Mitsuba objects are created here.
"""

from __future__ import annotations

import warnings
from typing import Any, Literal

import numpy as np
import pint
from pinttrs.util import ensure_units
from pydantic import ConfigDict, Field, field_validator, model_validator

from . import spectrum
from ._factory import Registry
from .object import Object
from .spectrum import (
    BaseSpectrum,
    SolarIrradianceSpectrum,
    UniformSpectrum,
)
from ...config import settings
from ...frame import AzimuthConvention, angles_to_direction
from ...units import unit_context_config as ucc
from ...units import unit_registry as ureg

illumination_registry: Registry["BaseIllumination"] = Registry("illumination")


class BaseIllumination(Object):
    """
    Abstract base class for illumination configuration objects.
    """

    id: str = "illumination"
    """Scene element identifier."""

    @model_validator(mode="wrap")
    @classmethod
    def _dispatch(cls, value, handler, info):
        if cls is not BaseIllumination:
            return handler(value)
        return illumination_registry.dispatch(value, handler, BaseIllumination)


# ------------------------------------------------------------------------------
#                              Constant illumination
# ------------------------------------------------------------------------------


class ConstantIllumination(BaseIllumination):
    """
    Constant (isotropic) illumination.

    Emits uniform radiance in all directions.

    Parameters
    ----------
    radiance : Spectrum or float, optional
        Emitted radiance spectrum. A bare number is converted to a
        :class:`.UniformSpectrum` with ``quantity="radiance"``.
        Default: 1.0 in ``ucc["radiance"]`` units.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    type: Literal["constant"] = "constant"
    radiance: BaseSpectrum = Field(
        default_factory=lambda: UniformSpectrum(
            value=1.0 * ucc.get("radiance"), quantity="radiance"
        )
    )

    @field_validator("radiance", mode="before")
    @classmethod
    def _coerce_radiance(cls, v: Any) -> BaseSpectrum:
        return spectrum.convert(v, quantity="radiance")


# ---------------------------------------------------------------------------
# Directional illumination base
# ---------------------------------------------------------------------------


def _azimuth_converter(value: pint.Quantity) -> pint.Quantity:
    if not 0.0 <= value.m_as("deg") < 360.0:
        warnings.warn(
            "Illumination azimuth values should be in the [0°, 360°[ interval. "
            "Applying modulo operation.",
            stacklevel=3,
        )
        return value % (360.0 * ureg.deg)
    return value


class DirectionalIllumination(BaseIllumination):
    """
    Directional (collimated) illumination.

    The illumination direction is specified by zenith and azimuth angles
    following the Earth-observation angular convention.

    Parameters
    ----------
    zenith : quantity or float, optional
        Zenith angle of the illumination direction. Unitless values are
        interpreted as ``ucc["angle"]``. Default: 0°.
    azimuth : quantity or float, optional
        Azimuth angle of the illumination direction. Unitless values are
        interpreted as ``ucc["angle"]``. Values outside [0°, 360°) are
        wrapped via a modulo operation. Default: 0°.
    azimuth_convention : AzimuthConvention or str, optional
        Azimuth angle convention. If ``None``, the global default from
        :attr:`.settings.azimuth_convention` is used. Default: ``None``.
    irradiance : Spectrum or float, optional
        Emitted irradiance spectrum. A bare number is converted to a
        :class:`.UniformSpectrum` with ``quantity="irradiance"``.
        Default: :class:`.SolarIrradianceSpectrum`.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    type: Literal["directional"] = "directional"
    zenith: pint.Quantity = Field(default_factory=lambda: 0.0 * ureg.deg)
    azimuth: pint.Quantity = Field(default_factory=lambda: 0.0 * ureg.deg)
    azimuth_convention: AzimuthConvention = Field(default=None)
    irradiance: BaseSpectrum = Field(default_factory=SolarIrradianceSpectrum)

    @field_validator("zenith", mode="before")
    @classmethod
    def _coerce_zenith(cls, v: Any) -> pint.Quantity:
        q = ensure_units(v, default_units=ucc.get("angle"), convert=True)
        if q.m_as("deg") < 0.0:
            raise ValueError(f"'zenith' must be non-negative, got {q}")
        return q

    @field_validator("azimuth", mode="before")
    @classmethod
    def _coerce_azimuth(cls, v: Any) -> pint.Quantity:
        q = ensure_units(v, default_units=ucc.get("angle"), convert=True)
        return _azimuth_converter(q)

    @field_validator("azimuth_convention", mode="before")
    @classmethod
    def _coerce_azimuth_convention(cls, v: Any) -> AzimuthConvention:
        if v is None:
            return settings.azimuth_convention
        if isinstance(v, str):
            return AzimuthConvention[v.upper()]
        return v

    @field_validator("irradiance", mode="before")
    @classmethod
    def _coerce_irradiance(cls, v: Any) -> BaseSpectrum:
        return spectrum.convert(v, quantity="irradiance")

    @property
    def direction(self) -> np.ndarray:
        """
        Illumination direction as a unit vector of shape (3,), pointing
        inward (toward the scene).
        """
        return angles_to_direction(
            [self.zenith.m_as(ureg.rad), self.azimuth.m_as(ureg.rad)],
            azimuth_convention=self.azimuth_convention,
            flip=True,
        ).reshape((3,))


# ------------------------------------------------------------------------------
#                        Astronomical-object illumination
# ------------------------------------------------------------------------------


class AstroObjectIllumination(DirectionalIllumination):
    """
    Astronomical object (e.g. the Sun) illumination.

    Like :class:`DirectionalIllumination` but the source has a non-zero
    apparent angular diameter so it subtends a small disc in the sky.

    Parameters
    ----------
    angular_diameter : quantity or float, optional
        Apparent diameter of the celestial body as seen from the scene.
        Unitless values are interpreted as ``ucc["angle"]``.
        Default: 0.5358° (average apparent diameter of the Sun).
    """

    type: Literal["astro_object"] = "astro_object"
    angular_diameter: pint.Quantity = Field(default_factory=lambda: 0.5358 * ureg.deg)

    @field_validator("angular_diameter", mode="before")
    @classmethod
    def _coerce_angular_diameter(cls, v: Any) -> pint.Quantity:
        q = ensure_units(v, default_units=ucc.get("angle"), convert=True)
        if q.m_as("deg") <= 0.0:
            raise ValueError(f"'angular_diameter' must be positive, got {q}")
        return q

    @property
    def direction(self) -> np.ndarray:
        """
        Illumination direction as a unit vector of shape (3,), pointing
        outward (away from the scene, toward the source).
        """
        return angles_to_direction(
            [self.zenith.m_as(ureg.rad), self.azimuth.m_as(ureg.rad)],
            azimuth_convention=self.azimuth_convention,
            flip=False,
        ).reshape((3,))


# ---------------------------------------------------------------------------
# Registry population
# ---------------------------------------------------------------------------

illumination_registry.register("constant", ConstantIllumination)
illumination_registry.register("directional", DirectionalIllumination)
illumination_registry.register("astro_object", AstroObjectIllumination)
