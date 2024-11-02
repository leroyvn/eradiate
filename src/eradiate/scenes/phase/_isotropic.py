from ._core import PhaseFunctionNode
from ...attrs import define
from ...kernel._kernel_dict import KernelDictionary, KernelSceneParameterMap


@define(eq=False, slots=False)
class IsotropicPhaseFunction(PhaseFunctionNode):
    """
    Isotropic phase function [``isotropic``].

    The isotropic phase function models scattering with equal probability in
    all directions.
    """

    def kdict(self) -> KernelDictionary:
        # Inherit docstring

        return KernelDictionary({"type": "isotropic"})

    def kpmap(self) -> KernelSceneParameterMap:
        # Inherit docstring

        return KernelSceneParameterMap()
