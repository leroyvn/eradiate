from __future__ import annotations

import attrs

from ._core import BSDFNode
from ..spectra import Spectrum, spectrum_factory
from ... import validators
from ...attrs import define, documented
from ...kernel._kernel_dict_new import KernelDictionary, KernelSceneParameterMap


@define(eq=False, slots=False)
class RPVBSDF(BSDFNode):
    """
    RPV BSDF [``rpv``].

    This BSDF implements the Rahman-Pinty-Verstraete (RPV) reflection model
    :cite:`Rahman1993CoupledSurfaceatmosphereReflectance,Pinty2000SurfaceAlbedoRetrieval`.
    It notably features a controllable back-scattering lobe (`hot spot`)
    characteristic of many natural land surfaces and is frequently used in Earth
    observation because of its simple parametrisation.

    See Also
    --------
    :ref:`plugin-bsdf-rpv`

    Notes
    -----
    * The default configuration is typical of grassland in the visible domain
      (:cite:`Rahman1993CoupledSurfaceatmosphereReflectance`, Table 1).
    * Parameter names are defined as per the symbols used in the Eradiate
      Scientific Handbook :cite:`EradiateScientificHandbook2020`.
    """

    rho_0: Spectrum = documented(
        attrs.field(
            default=0.183,
            converter=spectrum_factory.converter("dimensionless"),
            validator=[
                attrs.validators.instance_of(Spectrum),
                validators.has_quantity("dimensionless"),
            ],
        ),
        doc="Amplitude parameter. Must be dimensionless. "
        "Should be in :math:`[0, 1]`.",
        type=".Spectrum",
        init_type=".Spectrum or dict or float, optional",
        default="0.183",
    )

    rho_c: Spectrum | None = documented(
        attrs.field(
            default=None,
            converter=attrs.converters.optional(
                spectrum_factory.converter("dimensionless")
            ),
            validator=attrs.validators.optional(
                [
                    attrs.validators.instance_of(Spectrum),
                    validators.has_quantity("dimensionless"),
                ]
            ),
        ),
        doc="Hot spot parameter. Must be dimensionless. "
        r"Should be in :math:`[0, 1]`. If unset, :math:`\rho_\mathrm{c}` "
        r"defaults to the kernel plugin default (equal to :math:`\rho_0`).",
        type=".Spectrum or None",
        init_type=".Spectrum or dict or float or None, optional",
        default="None",
    )

    k: Spectrum = documented(
        attrs.field(
            default=0.780,
            converter=spectrum_factory.converter("dimensionless"),
            validator=[
                attrs.validators.instance_of(Spectrum),
                validators.has_quantity("dimensionless"),
            ],
        ),
        doc="Bowl-shape parameter. Must be dimensionless. "
        "Should be in :math:`[0, 2]`.",
        type=".Spectrum",
        init_type=".Spectrum or dict or float, optional",
        default="0.780",
    )

    g: Spectrum = documented(
        attrs.field(
            default=-0.1,
            converter=spectrum_factory.converter("dimensionless"),
            validator=[
                attrs.validators.instance_of(Spectrum),
                validators.has_quantity("dimensionless"),
            ],
        ),
        doc="Asymmetry parameter. Must be dimensionless. "
        "Should be in :math:`[-1, 1]`.",
        type=".Spectrum",
        init_type=".Spectrum or dict or float, optional",
        default="-0.1",
    )

    def kdict(self) -> KernelDictionary:
        # Inherit docstring

        result = KernelDictionary({"type": "rpv"})

        if self.id is not None:
            result["id"] = self.id

        attrs = ["rho_0", "k", "g"]
        if self.rho_c is not None:
            attrs.append("rho_c")

        for attr in attrs:
            result[attr] = self.__getattribute__(attr).kdict()

        return result

    def kpmap(self) -> KernelSceneParameterMap:
        # Inherit docstring

        result = KernelSceneParameterMap()

        attrs = ["rho_0", "k", "g"]
        if self.rho_c is not None:
            attrs.append("rho_c")

        for attr in attrs:
            kpmap_template = self.__getattribute__(attr).kpmap()

            for k, v in kpmap_template.items():
                result[f"{attr}.{k}"] = v

        return result
