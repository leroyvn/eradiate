from __future__ import annotations

from ._core import AbstractDirectionalIllumination
from ...attrs import define
from ...kernel._kernel_dict_new import KernelDictionary, KernelSceneParameterMap


@define(eq=False, slots=False)
class DirectionalIllumination(AbstractDirectionalIllumination):
    """
    Directional illumination scene element [``directional``].

    The illumination is oriented based on the classical angular convention used
    in Earth observation.
    """

    def kdict(self) -> KernelDictionary:
        # Inherit docstring

        result = KernelDictionary({"type": "directional", "to_world": self._to_world})
        if self.id is not None:
            result["id"] = self.id
        result["irradiance"] = self.irradiance.kdict()
        return result

    def kpmap(self) -> KernelSceneParameterMap:
        # Inherit docstring

        result = KernelSceneParameterMap()
        kpmap = self.irradiance.kpmap()
        for k, v in kpmap.items():
            result[f"irradiance.{k}"] = v
        return result
