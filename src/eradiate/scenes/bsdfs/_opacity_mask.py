from __future__ import annotations

import attrs
import mitsuba as mi
import numpy as np

from ._core import BSDF, BSDFComposite, BSDFNode, bsdf_factory
from ._lambertian import LambertianBSDF
from ... import converters
from ...attrs import define, documented
from ...kernel._kernel_dict import KernelDictionary, KernelSceneParameterMap


def _to_bitmap(value):
    if isinstance(value, mi.Bitmap):
        return value

    elif isinstance(value, np.ndarray):
        return mi.Bitmap(value)

    elif isinstance(value, list):
        return mi.Bitmap(np.array(value))

    else:
        return value


@define(eq=False, slots=False)
class OpacityMaskBSDF(BSDFComposite):
    """
    Opacity Mask BSDF [``opacity_mask``]
    """

    opacity_bitmap: np.typing.ArrayLike | "mi.Bitmap" = documented(
        attrs.field(converter=_to_bitmap, kw_only=True),
        doc="Mitsuba bitmap that specifies the opacity of the nested BSDF "
        "plugin. This parameter has no default and is required.",
        init_type="array-like or mitsuba.Bitmap",
        type="mitsuba.Bitmap",
    )

    @opacity_bitmap.validator
    def _opacity_bitmap_validator(self, attribute, value):
        if value is not None:
            if not isinstance(value, mi.Bitmap):
                raise TypeError(
                    f"while validating '{attribute.name}': "
                    f"'{attribute.name}' must be a mitsuba Bitmap instance; "
                    f"found: {type(value)}",
                )

    uv_trafo: "mi.ScalarTransform4f" = documented(
        attrs.field(converter=converters.to_mi_scalar_transform, kw_only=True),
        doc="Transform to scale the opacity mask. This parameter has no "
        "default and is required.",
        init_type="array-like or mitsuba.ScalarTransform4f",
        type="mitsuba.ScalarTransform4f",
    )

    @uv_trafo.validator
    def _uv_trafo_validator(self, attribute, value):
        if value is not None:
            if not isinstance(value, mi.ScalarTransform4f):
                raise TypeError(
                    f"while validating '{attribute.name}': "
                    f"'{attribute.name}' must be a mitsuba ScalarTransform4f instance; "
                    f"found: {type(value)}"
                )

    # TODO: Check if nested BSDF has an ID

    nested_bsdf: BSDF = documented(
        attrs.field(
            factory=LambertianBSDF,
            converter=bsdf_factory.convert,
            validator=attrs.validators.instance_of(BSDFNode),
        ),
        doc="The reflection model attached to the surface.",
        type=".BSDF",
        init_type=".BSDF or dict, optional",
        default=":class:`LambertianBSDF() <.LambertianBSDF>`",
    )

    def kdict(self) -> KernelDictionary:
        # Inherit docstring

        result = KernelDictionary()

        kdict_nested_bsdf = self.nested_bsdf.kdict()
        for k, v in kdict_nested_bsdf:
            result[f"{self.nested_bsdf.id}.{k}"] = v

        kdict_mask = {
            "type": "mask",
            "id": self.id,
            "nested_bsdf": {"type": "ref", "id": self.nested_bsdf.id},
            "opacity.type": "bitmap",
            "opacity.bitmap": self.opacity_bitmap,
            "opacity.filter_type": "nearest",
            "opacity.wrap_mode": "clamp",
        }

        if self.uv_trafo is not None:
            kdict_mask["opacity.to_uv"] = self.uv_trafo

        for k, v in kdict_mask:
            result[f"{self.id}.{k}"] = v

        return result

    def kpmap(self) -> KernelSceneParameterMap:
        # Inherit Docstring

        result = KernelSceneParameterMap()
        kpmap_nested_bsdf = self.nested_bsdf.kpmap()

        for k, v in kpmap_nested_bsdf.items():
            result[f"{self.nested_bsdf.id}.{k}"] = v

        return result
