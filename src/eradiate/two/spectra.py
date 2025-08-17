from __future__ import annotations

from functools import singledispatchmethod

import attrs
import mitsuba as mi
import numpy as np
import pint
import pinttrs
import xarray as xr
from numpy.typing import ArrayLike
from pinttrs.util import ensure_units, units_compatible

from .scene_object import SceneObject
from ..spectral import CKDSpectralIndex, MonoSpectralIndex, SpectralIndex
from ..units import PhysicalQuantity, to_quantity
from ..units import unit_context_config as ucc
from ..units import unit_context_kernel as uck


@attrs.define(init=False)
class InterpolatedSpectrum(SceneObject):
    quantity: PhysicalQuantity = attrs.field(
        kw_only=True,
        default=PhysicalQuantity.DIMENSIONLESS,
        converter=PhysicalQuantity,
        repr=lambda x: x.value.upper(),
    )

    _values: np.ndarray = attrs.field(kw_only=True)

    @_values.validator
    def _values_validator(self, attribute, value):
        if self.quantity is not None:
            if not isinstance(self._values, pint.Quantity):
                raise ValueError(
                    f"while validating '{attribute.name}': expected a Pint "
                    "quantity compatible with quantity field value "
                    f"'{self.quantity}', got a unitless value instead"
                )

            expected_units = ucc.get(self.quantity)
            if not units_compatible(expected_units, value.units):
                raise pinttrs.exceptions.UnitsError(
                    value.units,
                    expected_units,
                    extra_msg=f"while validating '{attribute.name}', got units "
                    f"'{value.units}' incompatible with quantity {self.quantity} "
                    f"(expected '{expected_units}')",
                )

    _wavelengths: np.ndarray = attrs.field(kw_only=True)

    @_wavelengths.validator
    def _wavelengths_validator(self, attribute, value):
        # Wavelengths must be monotonically increasing
        if not np.all(np.diff(value) > 0):
            raise ValueError("wavelengths must be monotonically increasing")

        # Check values
        if np.any(np.isnan(value)):
            raise ValueError("Detected NaN in 'wavelengths'")

    def __init__(
        self,
        values: ArrayLike | None = None,
        wavelengths: ArrayLike | None = None,
        dataarray: xr.DataArray | None = None,
        quantity: str | PhysicalQuantity | None = None,
    ):
        if dataarray is not None:
            values = to_quantity(dataarray)
            wavelengths = to_quantity(dataarray.w)

        # Ensure units
        if quantity is None:
            quantity = "dimensionless"
        config_units = ucc.get(quantity)
        values = ensure_units(
            np.atleast_1d(values), default_units=config_units, convert=True
        )

        config_units = ucc.get("wavelength")
        wavelengths = ensure_units(
            np.atleast_1d(wavelengths), default_units=config_units, convert=True
        )

        # Sort by ascending wavelength (required by numpy.interp in eval_mono)
        idx = np.argsort(wavelengths)
        wavelengths = wavelengths[idx]
        values = values[idx]

        object = mi.load_dict({"type": "uniform", "value": 0.5})
        updaters = {"value": lambda ctx: self.eval_kernel(ctx.si)}

        self.__attrs_init__(object, updaters, wavelengths=wavelengths, values=values)

    @property
    def wavelengths(self):
        return self._wavelengths

    @property
    def values(self):
        return self._values

    def eval_kernel(self, si: SpectralIndex) -> np.ndarray:
        kernel_units = uck.get(self.quantity)
        return self.eval(si).m_as(kernel_units)

    @singledispatchmethod
    def eval(self, si: SpectralIndex) -> pint.Quantity:
        """
        Evaluate spectrum at a given spectral index.

        Parameters
        ----------
        si : :class:`.SpectralIndex`
            Spectral index.

        Returns
        -------
        value : quantity
            Evaluated spectrum.

        Notes
        -----
        This method dispatches evaluation to specialized methods depending
        on the spectral index type.
        """
        raise NotImplementedError

    @eval.register(MonoSpectralIndex)
    def _(self, si) -> pint.Quantity:
        return self.eval_mono(w=si.w)

    @eval.register(CKDSpectralIndex)
    def _(self, si) -> pint.Quantity:
        return self.eval_ckd(w=si.w, g=si.g)

    def eval_mono(self, w: ArrayLike) -> pint.Quantity:
        w = ensure_units(w, ucc.get("wavelength"))
        return np.interp(w, self.wavelengths, self.values, left=0.0, right=0.0)

    def eval_ckd(self, w: ArrayLike, g: float) -> pint.Quantity:
        return self.eval_mono(w=w)
