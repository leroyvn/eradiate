from __future__ import annotations

import attrs
import pint

from ._core import Spectrum
from ...attrs import define
from ...kernel._kernel_dict import (
    KernelDictionary,
    KernelSceneParameterFlag,
    KernelSceneParameterMap,
    dict_parameter,
    scene_parameter,
)
from ...radprops.rayleigh import compute_sigma_s_air
from ...units import PhysicalQuantity
from ...units import unit_context_kernel as uck


@define(eq=False, slots=False)
class AirScatteringCoefficientSpectrum(Spectrum):
    """
    Air scattering coefficient spectrum [``air_scattering_coefficient``].

    See Also
    --------
    :func:`~eradiate.radprops.rayleigh.compute_sigma_s_air`
    """

    quantity: PhysicalQuantity = attrs.field(
        default=PhysicalQuantity.COLLISION_COEFFICIENT,
        init=False,
        repr=False,
    )

    def eval_mono(self, w: pint.Quantity) -> pint.Quantity:
        # Inherit docstring
        return compute_sigma_s_air(wavelength=w)

    def eval_ckd(self, w: pint.Quantity, g: float) -> pint.Quantity:
        # Inherit docstring
        return self.eval_mono(w)

    def integral(self, wmin: pint.Quantity, wmax: pint.Quantity) -> pint.Quantity:
        raise NotImplementedError

    def kdict(self) -> KernelDictionary:
        # Inherit docstring

        return KernelDictionary(
            {
                "type": "uniform",
                "value": dict_parameter(
                    lambda ctx: float(
                        self.eval(ctx.si).m_as(uck.get("collision_coefficient"))
                    )
                ),
            }
        )

    def kpmap(self) -> KernelSceneParameterMap:
        # Inherit docstring

        return KernelSceneParameterMap(
            {
                "value": scene_parameter(
                    lambda ctx: float(
                        self.eval(ctx.si).m_as(uck.get("collision_coefficient"))
                    ),
                    flags=KernelSceneParameterFlag.SPECTRAL,
                )
            }
        )
