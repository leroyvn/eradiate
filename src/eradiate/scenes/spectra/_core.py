from __future__ import annotations

import typing as t
from abc import ABC, abstractmethod
from functools import singledispatchmethod

import attrs
import pint

from ..core import NodeSceneElement
from ..._factory import Factory
from ...attrs import documented, parse_docs
from ...spectral.ckd import BinSet
from ...spectral.index import (
    CKDSpectralIndex,
    MonoSpectralIndex,
    SpectralIndex,
)
from ...spectral.mono import WavelengthSet
from ...units import PhysicalQuantity


class SpectrumFactory(Factory):
    def converter(self, quantity: str | PhysicalQuantity) -> t.Callable[[t.Any], t.Any]:
        """
        Generate a converter wrapping :meth:`SpectrumFactory.convert` to
        handle defaults for shortened spectrum definitions. The produced
        converter processes a parameter ``value`` as follows:

        * if ``value`` is an int, a float or a :class:`pint.Quantity`, the
          converter calls itself using a dictionary
          ``{"type": "uniform", "quantity": quantity, "value": value}``;
        * if ``value`` is a dictionary, it adds a ``"quantity": quantity`` entry
          for the following values of the ``"type"`` entry:

          * ``"uniform"``;
          * ``"interpolated"``;

        * otherwise, it forwards ``value`` to :meth:`.SpectrumFactory.convert`.

        Parameters
        ----------
        quantity : str or .PhysicalQuantity
            Quantity specifier (converted by :class:`.PhysicalQuantity`).
            See :meth:`.PhysicalQuantity.spectrum` for suitable values.

        Returns
        -------
        callable
            Generated converter.
        """

        def f(value):
            if isinstance(value, (int, float, pint.Quantity)):
                # Convert quantity-less values with dict wrapping and recursive call
                return f({"type": "uniform", "quantity": quantity, "value": value})

            if isinstance(value, dict):
                # If generic spectrum is requested without a specified
                # "quantity" field, add pre-configured quantity and attempt
                # conversion using regular conversion protocol
                try:
                    if (
                        value["type"] in {"uniform", "interpolated"}
                        and "quantity" not in value
                    ):
                        return self.convert({**value, "quantity": quantity})
                except KeyError:
                    # Note: A missing "type" field will also run this case, and
                    # the ill-formed dict will be correctly reported upon
                    # regular conversion
                    pass

            # Regular conversion (happens if value is neither int, float nor
            # dict without "quantity" field)
            return self.convert(value)

        return f


spectrum_factory = SpectrumFactory()
spectrum_factory.register_lazy_batch(
    [
        (
            "_air_scattering_coefficient.AirScatteringCoefficientSpectrum",
            "air_scattering_coefficient",
            {},
        ),
        (
            "_interpolated.InterpolatedSpectrum",
            "interpolated",
            {},
        ),
        (
            "_solar_irradiance.SolarIrradianceSpectrum",
            "solar_irradiance",
            {},
        ),
        (
            "_uniform.UniformSpectrum",
            "uniform",
            {},
        ),
        (
            "_multi_delta.MultiDeltaSpectrum",
            "multi_delta",
            {},
        ),
    ],
    cls_prefix="eradiate.scenes.spectra",
)


@parse_docs
@attrs.define(eq=False, slots=False)
class Spectrum(NodeSceneElement, ABC):
    """
    Spectrum interface.

    Notes
    -----
    * This class is to be used as a mixin.
    * Subclasses must implement :meth:`eval_mono`, :meth:`eval_ckd` and
      :meth:`integral`.
    """

    quantity: PhysicalQuantity = documented(
        attrs.field(
            default="dimensionless",
            converter=PhysicalQuantity,
            repr=lambda x: x.value.upper(),
        ),
        doc="Physical quantity which the spectrum represents. The specified "
        "quantity must be one which varies with wavelength. "
        "See :meth:`.PhysicalQuantity.spectrum` for allowed values.\n"
        "\n"
        "Child classes should implement value units validation and conversion "
        "based on ``quantity``.",
        type=":class:`.PhysicalQuantity`",
        init_type=":class:`.PhysicalQuantity` or str",
        default="dimensionless",
    )

    @quantity.validator
    def _quantity_validator(self, attribute, value):
        if value not in PhysicalQuantity.spectrum():
            raise ValueError(
                f"while validating {attribute.name}: "
                f"got value '{value}', expected one of {str(PhysicalQuantity.spectrum())}"
            )

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

    @abstractmethod
    def eval_mono(self, w: pint.Quantity) -> pint.Quantity:
        """
        Evaluate spectrum in monochromatic modes.

        Parameters
        ----------
        w : quantity
            Wavelength.

        Returns
        -------
        value : quantity
            Evaluated spectrum as an array with the same shape as ``w``.
        """
        raise NotImplementedError

    @abstractmethod
    def eval_ckd(self, w: pint.Quantity, g: float) -> pint.Quantity:
        """
        Evaluate spectrum in CKD modes.

        Parameters
        ----------
        w : quantity
            Spectral bin center wavelength.

        g : float
            Absorption coefficient cumulative probability.

        Returns
        -------
        value : quantity
            Evaluated spectrum as an array with shape ``w``.

        Notes
        -----
        It is assumed that ``w`` and ``g`` have the same shape.
        In CKD mode, it is assumed that all spectra—except that of the
        absorption coefficient—are uniform over the spectral bin. These
        spectra are evaluated at the spectral bin center wavelength.
        """
        pass

    def integral(self, wmin: pint.Quantity, wmax: pint.Quantity) -> pint.Quantity:
        """
        Compute the integral of the spectrum on a given interval.

        Parameters
        ----------
        wmin : quantity
            Integration interval's lower bound.

        wmax : quantity
            Integration interval's upper bound.

        Returns
        -------
        value : quantity
            Computed integral value.
        """
        raise NotImplementedError

    @singledispatchmethod
    def select_in(self, spectral_set) -> BinSet | WavelengthSet:
        """
        Select a subset of a spectral set.

        Parameters
        ----------
        spectral_set : :class:`.BinSet` or :class:`.WavelengthSet`
            Spectral set.

        Returns
        -------
        subset : :class:`.BinSet` or :class:`.WavelengthSet`
            Subset of the spectral set.

        Notes
        -----
        This method is only relevant to subclasses used to represent
        spectral response function (the default implementation raises a
        :class:`NotImplementedError`). In this context, the spectral response
        function acts as a sort of filter that *selects* a subset of a spectral
        set, e.g. where the response is non-zero.
        This method is useful for :class:`.Experiment` objects to determine
        which spectral set is relevant for a given sensor.
        """
        raise NotImplementedError

    @select_in.register(WavelengthSet)
    def _(self, spectral_set) -> WavelengthSet:
        return self.select_in_wavelength_set(spectral_set)

    @select_in.register(BinSet)
    def _(self, spectral_set) -> BinSet:
        return self.select_in_bin_set(spectral_set)

    def select_in_wavelength_set(self, wset) -> WavelengthSet:
        raise NotImplementedError

    def select_in_bin_set(self, binset) -> BinSet:
        raise NotImplementedError
