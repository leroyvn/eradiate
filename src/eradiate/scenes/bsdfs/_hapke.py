from __future__ import annotations

import attrs

from ._core import BSDFNode
from ..spectra import Spectrum, spectrum_factory
from ... import validators
from ...attrs import define, documented
from ...kernel._kernel_dict_new import KernelDictionary, KernelSceneParameterMap


@define(eq=False, slots=False)
class HapkeBSDF(BSDFNode):
    """
    Hapke BSDF [``hapke``].

    This BSDF implements the Hapke surface model as described in
    :cite:`Hapke1984BidirectionalReflectanceSpectroscopy`. This highly flexible
    and robust surface model allows for the characterization of a sharp
    back-scattering hot spot. The so-called Hapke model has been adapted to
    several different use cases in the literature, the version with 6
    parameters implemented here is one of the most commonly used.

    See Also
    --------
    :ref:`plugin-bsdf-hapke`
    """

    w: Spectrum = documented(
        attrs.field(
            default=None,
            converter=spectrum_factory.converter("dimensionless"),
            validator=[
                attrs.validators.instance_of(Spectrum),
                validators.has_quantity("dimensionless"),
            ],
        ),
        doc="Single scattering albedo 'w'. Must be in [0; 1]",
        type=".Spectrum",
        init_type=".Spectrum or dict or float",
    )

    b: Spectrum = documented(
        attrs.field(
            default=None,
            converter=spectrum_factory.converter("dimensionless"),
            validator=[
                attrs.validators.instance_of(Spectrum),
                validators.has_quantity("dimensionless"),
            ],
        ),
        doc="Anisotropy parameter 'b' Must be in [0; 1]",
        type=".Spectrum",
        init_type=".Spectrum or dict or float",
    )

    c: Spectrum | None = documented(
        attrs.field(
            default=None,
            converter=spectrum_factory.converter("dimensionless"),
            validator=[
                attrs.validators.instance_of(Spectrum),
                validators.has_quantity("dimensionless"),
            ],
        ),
        doc="Scattering coefficient 'c'. Must be in [0; 1]",
        type=".Spectrum",
        init_type=".Spectrum or dict or float",
    )

    theta: Spectrum = documented(
        attrs.field(
            default=0.183,
            converter=spectrum_factory.converter("angle"),
            validator=[
                attrs.validators.instance_of(Spectrum),
                validators.has_quantity("angle"),
            ],
        ),
        doc="Photometric roughness 'theta'. Angle in degree. Must be in [0; 90]°",
        type=".Spectrum",
        init_type="quantity or float",
    )

    B_0: Spectrum = documented(
        attrs.field(
            default=None,
            converter=spectrum_factory.converter("dimensionless"),
            validator=[
                attrs.validators.instance_of(Spectrum),
                validators.has_quantity("dimensionless"),
            ],
        ),
        doc="Shadow hiding opposition effect amplitude 'B_0'. Must be in [0; 1]",
        type=".Spectrum",
        init_type=".Spectrum or dict or float",
    )

    h: Spectrum = documented(
        attrs.field(
            default=None,
            converter=spectrum_factory.converter("dimensionless"),
            validator=[
                attrs.validators.instance_of(Spectrum),
                validators.has_quantity("dimensionless"),
            ],
        ),
        doc="shadow hiding opposition effect width 'h'. Must be in [0; 1]",
        type=".Spectrum",
        init_type=".Spectrum or dict or float",
    )

    def kdict(self) -> KernelDictionary:
        # Inherit docstring

        result = KernelDictionary({"type": "hapke"})

        if self.id is not None:
            result["id"] = self.id

        for attr in ["w", "b", "c", "theta", "B_0", "h"]:
            result[attr] = self.__getattribute__(attr).kdict()

        return result

    def kpmap(self) -> KernelSceneParameterMap:
        # Inherit docstring

        result = KernelSceneParameterMap()

        for attr in ["w", "b", "c", "theta", "B_0", "h"]:
            kpmap_template = self.__getattribute__(attr).kpmap()

            for k, v in kpmap_template.items():
                result[f"{attr}.{k}"] = v

        return result
