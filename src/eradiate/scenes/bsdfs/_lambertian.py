from __future__ import annotations

import attrs

from ._core import BSDFNode
from ..spectra import Spectrum, spectrum_factory
from ... import validators
from ...attrs import define, documented
from ...kernel._kernel_dict_new import KernelDictionary, KernelSceneParameterMap


@define(eq=False, slots=False)
class LambertianBSDF(BSDFNode):
    """
    Lambertian BSDF [``lambertian``].

    This class implements the Lambertian (a.k.a. diffuse) reflectance model.
    A surface with this scattering model attached scatters radiation equally in
    every direction.
    """

    reflectance: Spectrum = documented(
        attrs.field(
            default=0.5,
            converter=spectrum_factory.converter("reflectance"),
            validator=[
                attrs.validators.instance_of(Spectrum),
                validators.has_quantity("reflectance"),
            ],
        ),
        doc="Reflectance spectrum. Can be initialized with a dictionary "
        "processed by :data:`.spectrum_factory`.",
        type=".Spectrum",
        init_type=".Spectrum or dict or float",
        default="0.5",
    )

    def kdict(self) -> KernelDictionary:
        # Inherit docstring

        result = KernelDictionary({"type": "diffuse"})

        if self.id is not None:
            result["id"] = self.id

        for k, v in self.reflectance.kdict().items():
            result[f"reflectance.{k}"] = v

        return result

    def kpmap(self) -> KernelSceneParameterMap:
        # Inherit docstring

        result = KernelSceneParameterMap()
        kpmap_template = self.reflectance.kpmap()

        for k, v in kpmap_template.items():
            result[f"reflectance.{k}"] = v

        return result
