"""
Spectral data classes for the configuration layer.

These Pydantic-based classes define spectrum representations used in scene
element configuration. They provide an evaluation protocol for spectral
quantities at given wavelengths, independent of the rendering backend.
"""

from __future__ import annotations

from functools import singledispatchmethod
from typing import Any, Literal, Union

import numpy as np
import pint
import pinttrs
import xarray as xr
from numpy.typing import ArrayLike
from pinttrs.util import ensure_units, units_compatible
from pydantic import ConfigDict, field_validator, model_validator

from ._factory import Registry
from .object import Object
from ...spectral import CKDSpectralIndex, MonoSpectralIndex, SpectralIndex
from ...units import PhysicalQuantity
from ...units import unit_context_config as ucc
from ...units import unit_registry as ureg

spectrum_registry: Registry[BaseSpectrum] = Registry("spectrum")


class BaseSpectrum(Object):
    """
    Abstract base class for spectrum configuration objects.

    Subclasses implement the evaluation protocol defined by
    :meth:`eval_mono`, :meth:`eval_ckd`, and :meth:`integral`.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    quantity: PhysicalQuantity = PhysicalQuantity.DIMENSIONLESS

    @model_validator(mode="wrap")
    @classmethod
    def _dispatch(cls, value, handler, info):
        if cls is not BaseSpectrum:
            return handler(value)
        return spectrum_registry.dispatch(value, handler, BaseSpectrum)

    """Physical quantity represented by this spectrum."""

    @field_validator("quantity", mode="before")
    @classmethod
    def _coerce_quantity(cls, v: Any) -> PhysicalQuantity:
        if isinstance(v, str):
            return PhysicalQuantity(v.lower())
        return v

    @singledispatchmethod
    def eval(self, si: SpectralIndex) -> pint.Quantity:
        """
        Evaluate the spectrum at a given spectral index.

        Parameters
        ----------
        si : SpectralIndex
            Spectral index carrying wavelength (and g-point for CKD).

        Returns
        -------
        quantity
            Evaluated spectrum value, with units consistent with
            :attr:`quantity`.
        """
        raise NotImplementedError(f"Unsupported spectral index type {type(si)}")

    @eval.register(MonoSpectralIndex)
    def _(self, si: MonoSpectralIndex) -> pint.Quantity:
        return self.eval_mono(w=si.w)

    @eval.register(CKDSpectralIndex)
    def _(self, si: CKDSpectralIndex) -> pint.Quantity:
        return self.eval_ckd(w=si.w, g=si.g)

    def eval_mono(self, w: ArrayLike) -> pint.Quantity:
        """
        Evaluate the spectrum in monochromatic mode.

        Parameters
        ----------
        w : quantity or array-like
            Wavelength. Unitless values are interpreted as
            ``ucc["wavelength"]``.

        Returns
        -------
        quantity
            Spectrum value at ``w``.
        """
        raise NotImplementedError

    def eval_ckd(self, w: ArrayLike, g: float) -> pint.Quantity:
        """
        Evaluate the spectrum in correlated k-distribution mode.

        Parameters
        ----------
        w : quantity or array-like
            Bin centre wavelength.

        g : float
            g-point within the bin.

        Returns
        -------
        quantity
            Spectrum value. The default implementation ignores ``g`` and
            delegates to :meth:`eval_mono`.
        """
        return self.eval_mono(w=w)

    def integral(self, wmin: pint.Quantity, wmax: pint.Quantity) -> pint.Quantity:
        """
        Integrate the spectrum over a wavelength interval.

        Parameters
        ----------
        wmin, wmax : quantity
            Integration bounds. Units must be compatible with
            ``ucc["wavelength"]``.

        Returns
        -------
        quantity
            Integrated value.
        """
        raise NotImplementedError


class UniformSpectrum(BaseSpectrum):
    """
    A spectrum with a constant (wavelength-independent) value.

    Parameters
    ----------
    value : quantity or float
        Constant spectral value. A bare float is converted to the default
        units for :attr:`quantity`.

    quantity : PhysicalQuantity or str, optional
        Physical quantity represented by this spectrum.
        Default: ``"dimensionless"``.
    """

    type: Literal["uniform"] = "uniform"
    value: pint.Quantity

    @field_validator("value", mode="before")
    @classmethod
    def _coerce_value(cls, v: Any) -> pint.Quantity:
        # Accept bare numbers; units are attached in the model validator
        if isinstance(v, (int, float)):
            return float(v) * ureg.dimensionless
        return v

    @model_validator(mode="after")
    def _validate_units(self) -> UniformSpectrum:
        expected = ucc.get(self.quantity)
        if not units_compatible(expected, self.value.units):
            raise pinttrs.exceptions.UnitsError(
                self.value.units,
                expected,
                extra_msg=(
                    f"while validating 'value': units '{self.value.units}' are "
                    f"incompatible with quantity {self.quantity} "
                    f"(expected '{expected}')"
                ),
            )
        # Re-attach proper units if value arrived unit-less (dimensionless sentinel)
        if self.value.units == ureg.dimensionless and expected != ureg.dimensionless:
            self.value = self.value.magnitude * expected
        return self

    def eval_mono(self, w: ArrayLike) -> pint.Quantity:
        w = ensure_units(w, ucc.get("wavelength"))
        return np.full(np.asarray(w).shape, self.value.magnitude) * self.value.units

    def eval_ckd(self, w: ArrayLike, g: float) -> pint.Quantity:
        return self.eval_mono(w=w)

    def integral(self, wmin: pint.Quantity, wmax: pint.Quantity) -> pint.Quantity:
        wmin = ensure_units(wmin, ucc.get("wavelength"))
        wmax = ensure_units(wmax, ucc.get("wavelength"))
        return self.value * (wmax - wmin)


class InterpolatedSpectrum(BaseSpectrum):
    """
    A spectrum defined by a table of wavelength–value pairs, evaluated via
    linear interpolation.

    Values outside the covered wavelength range are extrapolated as zero.

    Parameters
    ----------
    wavelengths : quantity or array-like
        Wavelength grid. Unitless values are interpreted as
        ``ucc["wavelength"]``.  Need not be sorted on input; the class
        sorts them internally.
    values : quantity or array-like
        Spectral values at each grid point. Unitless values are
        interpreted as ``ucc[quantity]``.
    quantity : PhysicalQuantity or str, optional
        Physical quantity represented by this spectrum.
    """

    type: Literal["interpolated"] = "interpolated"
    wavelengths: pint.Quantity
    values: pint.Quantity

    @field_validator("wavelengths", mode="before")
    @classmethod
    def _coerce_wavelengths(cls, v: Any) -> pint.Quantity:
        return ensure_units(
            np.atleast_1d(v), default_units=ucc.get("wavelength"), convert=True
        )

    @field_validator("values", mode="before")
    @classmethod
    def _coerce_values(cls, v: Any) -> pint.Quantity:
        # Defer unit validation to model_validator where quantity is available
        if not isinstance(v, pint.Quantity):
            return np.atleast_1d(v) * ureg.dimensionless
        return np.atleast_1d(v.magnitude) * v.units

    @model_validator(mode="after")
    def _validate_and_sort(self) -> InterpolatedSpectrum:
        # Validate wavelengths
        wl = self.wavelengths
        if np.any(np.isnan(wl.magnitude)):
            raise ValueError("'wavelengths' must not contain NaN values")

        # Validate values units against quantity
        expected = ucc.get(self.quantity)
        vals = self.values
        if not units_compatible(expected, vals.units):
            raise pinttrs.exceptions.UnitsError(
                vals.units,
                expected,
                extra_msg=(
                    f"while validating 'values': units '{vals.units}' are "
                    f"incompatible with quantity {self.quantity} "
                    f"(expected '{expected}')"
                ),
            )
        # Attach proper units if values arrived unitless
        if vals.units == ureg.dimensionless and expected != ureg.dimensionless:
            self.values = vals.magnitude * expected

        if len(wl) != len(self.values):
            raise ValueError(
                f"'wavelengths' and 'values' must have the same length, "
                f"got {len(wl)} and {len(self.values)}"
            )

        # Sort by ascending wavelength
        idx = np.argsort(wl.magnitude)
        self.wavelengths = wl[idx]
        self.values = self.values[idx]

        if not np.all(np.diff(self.wavelengths.magnitude) > 0):
            raise ValueError("'wavelengths' must be strictly monotonically increasing")

        return self

    def eval_mono(self, w: ArrayLike) -> pint.Quantity:
        w = ensure_units(w, default_units=ucc.get("wavelength"))
        w_mag = w.m_as(self.wavelengths.units)
        result = np.interp(
            w_mag,
            self.wavelengths.magnitude,
            self.values.magnitude,
            left=0.0,
            right=0.0,
        )
        return result * self.values.units

    def eval_ckd(self, w: ArrayLike, g: float) -> pint.Quantity:
        return self.eval_mono(w=w)

    def integral(self, wmin: pint.Quantity, wmax: pint.Quantity) -> pint.Quantity:
        wmin = ensure_units(wmin, default_units=ucc.get("wavelength"))
        wmax = ensure_units(wmax, default_units=ucc.get("wavelength"))
        wl_units = self.wavelengths.units
        val_units = self.values.units

        wl = self.wavelengths.magnitude
        vals = self.values.magnitude
        lo = wmin.m_as(wl_units)
        hi = wmax.m_as(wl_units)

        # Restrict to the [wmin, wmax] interval, inserting boundary points
        mask = (wl >= lo) & (wl <= hi)
        wl_seg = np.concatenate([[lo], wl[mask], [hi]])
        vals_seg = np.interp(wl_seg, wl, vals, left=0.0, right=0.0)
        result = np.trapz(vals_seg, wl_seg)
        return result * val_units * wl_units


class SolarIrradianceSpectrum(BaseSpectrum):
    """
    A spectrum that reads solar irradiance values from a bundled dataset.

    Parameters
    ----------
    dataset : str, optional
        Identifier of the solar irradiance dataset to use.
        Default: ``"thuillier_2003"``.
    """

    type: Literal["solar_irradiance"] = "solar_irradiance"
    dataset: str = "thuillier_2003"  # TODO: Change to tsis1_v2
    quantity: PhysicalQuantity = PhysicalQuantity.IRRADIANCE

    @field_validator("quantity", mode="before")
    @classmethod
    def _lock_quantity(cls, v: Any) -> PhysicalQuantity:
        # Always irradiance regardless of user input
        return PhysicalQuantity.IRRADIANCE

    # TODO: Cache this
    def _load(self) -> InterpolatedSpectrum:
        """Load the dataset and return an :class:`InterpolatedSpectrum`."""
        from ...converters import load_dataset, resolve_keyword  # noqa: PLC0415

        path = resolve_keyword(lambda x: f"solar_irradiance/{x}.nc")(self.dataset)
        ds = load_dataset(path)
        from ...units import to_quantity  # noqa: PLC0415

        wavelengths = to_quantity(ds.w)
        values = to_quantity(ds.ssi)
        return InterpolatedSpectrum(
            wavelengths=wavelengths,
            values=values,
            quantity=PhysicalQuantity.IRRADIANCE,
        )

    def eval_mono(self, w: ArrayLike) -> pint.Quantity:
        return self._load().eval_mono(w)

    def eval_ckd(self, w: ArrayLike, g: float) -> pint.Quantity:
        return self._load().eval_ckd(w, g)

    def integral(self, wmin: pint.Quantity, wmax: pint.Quantity) -> pint.Quantity:
        return self._load().integral(wmin, wmax)


# ---------------------------------------------------------------------------
# Registry population
# ---------------------------------------------------------------------------

spectrum_registry.register("uniform", UniformSpectrum)
spectrum_registry.register("interpolated", InterpolatedSpectrum)
spectrum_registry.register("solar_irradiance", SolarIrradianceSpectrum)

# ---------------------------------------------------------------------------
# Type alias (for IDEs and static type checkers)
# ---------------------------------------------------------------------------

AnySpectrum = Union[UniformSpectrum, InterpolatedSpectrum, SolarIrradianceSpectrum]


def convert(
    value: Any, quantity: str | PhysicalQuantity = "dimensionless"
) -> BaseSpectrum:
    """
    Convert a value to a :class:`Spectrum` configuration object.

    Parameters
    ----------
    value : any
        * :class:`Spectrum` — returned unchanged.
        * :class:`xarray.DataArray` — converted to an
          :class:`InterpolatedSpectrum`.
        * ``float`` or ``int`` — converted to a
          :class:`UniformSpectrum` with the given ``quantity``.

    quantity : PhysicalQuantity or str, optional
        Physical quantity to use when creating a :class:`UniformSpectrum`
        from a bare number.

    Returns
    -------
    Spectrum
    """
    if isinstance(value, BaseSpectrum):
        return value

    if isinstance(value, xr.DataArray):
        return InterpolatedSpectrum(
            wavelengths=value.w.values * ureg(value.w.attrs.get("units", "nm")),
            values=value.values * ureg(value.attrs.get("units", "")),
            quantity=quantity,
        )

    if isinstance(value, (int, float)):
        return UniformSpectrum(value=float(value), quantity=quantity)

    raise TypeError(
        f"Cannot convert {type(value)!r} to a Spectrum; expected Spectrum, "
        "DataArray, or a numeric scalar."
    )
