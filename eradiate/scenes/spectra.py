"""Spectrum-related scene generation facilities.

.. admonition:: Registered factory members [:class:`SpectrumFactory`]
   :class: hint

   .. factorytable::
      :factory: SpectrumFactory
"""
from abc import ABC

import attr
import numpy as np
import pint
from pint import DimensionalityError

from .core import SceneElement
from .. import data
from ..util.attrs import attrib_quantity, validator_is_positive, validator_is_string
from ..util.exceptions import ModeError, UnitsError
from ..util.factory import BaseFactory
from ..util.units import PhysicalQuantity, compatible, ensure_units, ureg
from ..util.units import config_default_units as cdu
from ..util.units import kernel_default_units as kdu


@attr.s
class Spectrum(SceneElement, ABC):
    """Spectrum abstract base class.

    See :class:`SceneElement` for undocumented members.

    .. rubric:: Constructor arguments / instance attributes

    Parameter ``quantity`` (str or :class:`PhysicalQuantity` or None):
        Physical quantity which the spectrum represents. If not ``None``,
        the specified quantity must be one which varies with wavelength.
        See :meth:`PhysicalQuantity.spectrum` for allowed values.

        Child classes should implement value units validation and conversion
        based on ``quantity``. In particular, no unit validation or conversion
        should occur if ``quantity`` is ``None``.
    """
    quantity = attr.ib(
        default=None,
        converter=attr.converters.optional(PhysicalQuantity.from_any),
    )

    @quantity.validator
    def _quantity_validator(self, attribute, value):
        if value is None:
            return

        if value not in PhysicalQuantity.spectrum():
            raise ValueError(f"while validating {attribute.name}: "
                             f"got value '{value}', expected one of {str()}")

    @property
    def _values(self):
        raise NotImplementedError


class SpectrumFactory(BaseFactory):
    """This factory constructs objects whose classes are derived from
    :class:`Spectrum`.

    .. admonition:: Registered factory members
       :class: hint

       .. factorytable::
          :factory: SpectrumFactory
    """
    _constructed_type = Spectrum
    registry = {}

    @staticmethod
    def converter(quantity):
        """Generate a converter wrapping :meth:`SpectrumFactory.convert` to
        handle defaults for shortened spectrum definitions. The produced
        converter processes a parameter ``value`` as follows:

        * if ``value`` is a float or a :class:`pint.Quantity`, the converter
          calls itself using a dictionary
          ``{"type": "uniform", "quantity": quantity, "value": value}``;
        * if ``value`` is a dictionary, it adds a ``"quantity": quantity`` entry
          for the following values of the ``"type"`` entry:
          * ``"uniform"``;
        * otherwise, it forwards ``value`` to
          :meth:`.SpectrumFactory.convert`.

        Parameter ``quantity`` (str or :class:`PhysicalQuantity`):
            Quantity specifier (converted by :meth:`SpectrumQuantity.from_any`).
            See :meth:`PhysicalQuantity.spectrum` for suitable values.

        Returns → callable:
            Generated converter.
        """

        def f(value):
            if isinstance(value, (float, pint.Quantity)):
                return f({
                    "type": "uniform",
                    "quantity": quantity,
                    "value": value
                })

            if isinstance(value, dict):
                try:
                    if value["type"] == "uniform" and "quantity" not in value:
                        return SpectrumFactory.convert(
                            {**value, "quantity": quantity}
                        )
                except KeyError:
                    pass

            return SpectrumFactory.convert(value)

        return f


@SpectrumFactory.register("uniform")
@attr.s
class UniformSpectrum(Spectrum):
    """Uniform spectrum (*i.e.* constant against wavelength). Supports basic
    arithmetics.

    .. rubric:: Constructor arguments / instance attributes

    Parameter ``value`` (float or :class:`~pint.Quantity`):
        Uniform spectrum value. If a float is passed and ``quantity`` is not
        ``None``, it is automatically converted to appropriate configuration
        default units. If a :class:`~pint.Quantity` is passed and ``quantity``
        is not ``None``, units will be checked for consistency.

    See :class:`Spectrum` for undocumented members.
    """
    value = attrib_quantity(default=1.0)

    @value.validator
    def value_validator(self, attribute, value):
        if self.quantity is not None and isinstance(value, pint.Quantity):
            expected_units = cdu.get(self.quantity)

            if not compatible(expected_units, value.units):
                raise UnitsError(
                    f"while validating {attribute.name}, got units "
                    f"'{value.units}' incompatible with quantity {self.quantity} "
                    f"(expected '{expected_units}')"
                )

        validator_is_positive(self, attribute, value)

    def __attrs_post_init__(self):
        if self.quantity is not None and self.value is not None:
            self.value = ensure_units(self.value, cdu.get(self.quantity))

    @property
    def _values(self):
        return self.value

    def __add__(self, other):
        # Preserve quantity field only if it is the same for both operands
        if self.quantity is other.quantity:
            quantity = self.quantity
        else:
            quantity = None

        try:
            value = self.value + other.value
        except DimensionalityError as e:
            raise UnitsError(str(e))

        return UniformSpectrum(quantity=quantity, value=value)

    def __sub__(self, other):
        # Preserve quantity field only if it is the same for both
        # operands
        if self.quantity is other.quantity:
            quantity = self.quantity
        else:
            quantity = None

        try:
            value = self.value - other.value
        except DimensionalityError as e:
            raise UnitsError(str(e))

        return UniformSpectrum(quantity=quantity, value=value)

    def __mul__(self, other):
        # We can only preserve 'dimensionless', other quantities are much
        # more challenging to infer
        if self.quantity is PhysicalQuantity.DIMENSIONLESS \
                and other.quantity is PhysicalQuantity.DIMENSIONLESS:
            quantity = PhysicalQuantity.DIMENSIONLESS
        else:
            quantity = None

        try:
            value = self.value * other.value
        except DimensionalityError as e:
            raise UnitsError(str(e))

        return UniformSpectrum(quantity=quantity, value=value)

    def __truediv__(self, other):
        # We can only infer 'dimensionless' if both operands have the same
        # quantity field, other cases are much more challenging
        if self.quantity is other.quantity and self.quantity is not None:
            quantity = PhysicalQuantity.DIMENSIONLESS
        else:
            quantity = None

        try:
            value = self.value / other.value
        except DimensionalityError as e:
            raise UnitsError(str(e))

        return UniformSpectrum(quantity=quantity, value=value)

    def kernel_dict(self, ref=True):
        kernel_units = kdu.get(self.quantity)

        return {
            "spectrum": {
                "type": "uniform",
                "value": self.value.to(kernel_units).magnitude,
            }
        }


@SpectrumFactory.register("solar_irradiance")
@attr.s(frozen=True)
class SolarIrradianceSpectrum(Spectrum):
    """Solar irradiance spectrum scene element
    [:factorykey:`solar_irradiance`].

    This scene element produces the scene dictionary required to
    instantiate a kernel plugin using the Sun irradiance spectrum. The data set
    used by this element is controlled by the ``dataset`` attribute (see
    :mod:`eradiate.data.solar_irradiance_spectra` for available data sets).

    The spectral range of the data sets shipped can vary and an attempt for use
    outside of the supported spectral range will raise a :class:`ValueError`
    upon calling :meth:`kernel_dict`.

    The generated kernel dictionary varies based on the selected mode of
    operation. The ``scale`` parameter can be used to adjust the value based on
    unit conversion or to account for variations of the Sun-planet distance.

    The produced kernel dictionary automatically adjusts its irradiance units
    depending on the selected kernel default units.

    .. rubric:: Constructor arguments / instance attributes

    ``dataset`` (str):
        Dataset key. Allowed values: see
        :attr:`solar irradiance dataset documentation <eradiate.data.solar_irradiance_spectra>`.
        Default: ``"thuillier_2003"``.

    ``scale`` (float):
        Scaling factor. Default: 1.
    """

    #: Physical quantity
    quantity = attr.ib(
        default=PhysicalQuantity.IRRADIANCE,
        init=False,
        repr=False
    )

    #: Dataset identifier
    dataset = attr.ib(
        default="thuillier_2003",
        validator=validator_is_string,
    )

    scale = attr.ib(
        default=1.,
        converter=float,
        validator=validator_is_positive,
    )

    @dataset.validator
    def _dataset_validator(self, attribute, value):
        if value not in data.registered("solar_irradiance_spectrum"):
            raise ValueError(f"while setting {attribute.name}: '{value}' not in "
                             f"list of supported solar irradiance spectra "
                             f"{data.registered('solar_irradiance_spectrum')}")

    data = attr.ib(
        init=False,
        repr=False
    )

    @data.default
    def _data_factory(self):
        # Load dataset
        try:
            return data.open("solar_irradiance_spectrum", self.dataset)
        except KeyError:
            raise ValueError(f"unknown dataset {self.dataset}")

    def kernel_dict(self, ref=True):
        from eradiate import mode

        if mode.is_monochromatic():
            wavelength = mode.wavelength.to(ureg.nm).magnitude

            if self.dataset == "solid_2017":
                raise NotImplementedError(f"Solar irradiance spectrum datasets "
                                          f"with a non-empty time coordinate "
                                          f"are not supported yet.")
            # TODO: add support to solar irradiance spectrum datasets with a non-empty time coordinate

            irradiance_magnitude = float(
                self.data.ssi.interp(
                    w=wavelength,
                    method="linear",
                ).values
            )

            # Raise if out of bounds or ill-formed dataset
            if np.isnan(irradiance_magnitude):
                raise ValueError(f"dataset evaluation returned nan")

            # Apply units
            irradiance = ureg.Quantity(
                irradiance_magnitude,
                self.data.ssi.attrs["units"]
            )

            # Apply scaling, build kernel dict
            return {
                "spectrum": {
                    "type": "uniform",
                    "value": irradiance.to(kdu.get("irradiance")).magnitude *
                             self.scale
                }
            }

        else:
            raise ModeError(f"unsupported mode '{mode.id}'")
