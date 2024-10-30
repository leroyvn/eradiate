from __future__ import annotations

from abc import ABC

from ..core import CompositeSceneElement, NodeSceneElement
from ..._factory import Factory
from ...attrs import define

bsdf_factory = Factory()
bsdf_factory.register_lazy_batch(
    [
        ("_black.BlackBSDF", "black", {}),
        ("_checkerboard.CheckerboardBSDF", "checkerboard", {}),
        ("_lambertian.LambertianBSDF", "lambertian", {"aliases": ["diffuse"]}),
        ("_mqdiffuse.MQDiffuseBSDF", "mqdiffuse", {}),
        ("_ocean_legacy.OceanLegacyBSDF", "ocean_legacy", {}),
        ("_opacity_mask.OpacityMaskBSDF", "opacity_mask", {}),
        ("_rpv.RPVBSDF", "rpv", {}),
        ("_rtls.RTLSBSDF", "rtls", {}),
    ],
    cls_prefix="eradiate.scenes.bsdfs",
)


@define(eq=False, slots=False)
class BSDF:
    """
    An abstract base class defining common facilities for all BSDFs.

    Notes
    -----
    * This class is to be used as a mixin.
    """

    # TODO: Delete
    @property
    def template(self) -> dict:
        raise NotImplementedError

    # TODO: Delete
    @property
    def params(self) -> dict:
        raise NotImplementedError


@define(eq=False, slots=False)
class BSDFNode(BSDF, NodeSceneElement, ABC):
    pass


@define(eq=False, slots=False)
class BSDFComposite(BSDF, CompositeSceneElement, ABC):
    pass
