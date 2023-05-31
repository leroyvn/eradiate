from __future__ import annotations

from abc import ABC

from ..core import MitsubaDictObject
from ..._factory import Factory
from ...attrs import define, parse_docs

bsdf_factory = Factory()
bsdf_factory.register_lazy_batch(
    [
        ("_black.BlackBSDF", "black", {}),
        ("_checkerboard.CheckerboardBSDF", "checkerboard", {}),
        ("_lambertian.LambertianBSDF", "lambertian", {}),
        ("_mqdiffuse.MQDiffuseBSDF", "mqdiffuse", {}),
        ("_opacity_mask.OpacityMaskBSDF", "opacity_mask", {}),
        ("_rpv.RPVBSDF", "rpv", {}),
    ],
    cls_prefix="eradiate.scenes.bsdfs",
)


@parse_docs
@define
class BSDF(MitsubaDictObject, ABC):
    """
    Abstract base class  for all BSDF scene elements.
    """

    pass
