from __future__ import annotations

import attrs

from ._core import Illumination
from ..spectra import Spectrum, spectrum_factory
from ...attrs import define, documented
from ...kernel._kernel_dict_new import KernelDictionary, KernelSceneParameterMap
from ...validators import has_quantity


@define(eq=False, slots=False)
class ConstantIllumination(Illumination):
    """
    Constant illumination scene element [``constant``].
    """

    radiance: Spectrum = documented(
        attrs.field(
            default=1.0,
            converter=spectrum_factory.converter("radiance"),
            validator=[
                attrs.validators.instance_of(Spectrum),
                has_quantity("radiance"),
            ],
        ),
        doc="Emitted radiance spectrum. Must be a radiance spectrum "
        "(in W/m²/sr/nm or compatible units).",
        type=":class:`~eradiate.scenes.spectra.Spectrum`",
        init_type=":class:`~eradiate.scenes.spectra.Spectrum` or dict or float",
        default="1.0 ucc[radiance]",
    )

    def kdict(self) -> KernelDictionary:
        # Inherit docstring

        result = KernelDictionary({"type": "constant"})
        if self.id is not None:
            result["id"] = self.id
        result["radiance"] = self.radiance.kdict()
        return result

    def kpmap(self) -> KernelSceneParameterMap:
        # Inherit docstring

        result = KernelSceneParameterMap()
        kpmap = self.radiance.kpmap()
        for k, v in kpmap.items():
            result[f"radiance.{k}"] = v
        return result
