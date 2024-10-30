from __future__ import annotations

import attrs

from ._core import BSDFNode
from ...kernel._kernel_dict_new import KernelDictionary, KernelSceneParameterMap


@attrs.define(eq=False, slots=False)
class BlackBSDF(BSDFNode):
    """
    Black BSDF [``black``].

    This BSDF models a perfectly absorbing surface. It is equivalent to a
    :class:`.LambertianBSDF` with zero reflectance.
    """

    def kdict(self) -> KernelDictionary:
        # Inherit docstring

        result = KernelDictionary(
            {
                "type": "diffuse",
                "reflectance": {"type": "uniform", "value": 0.0},
            }
        )

        if self.id is not None:
            result["id"] = self.id

        return result

    def kpmap(self) -> KernelSceneParameterMap:
        # Inherit docstring
        return KernelSceneParameterMap()
