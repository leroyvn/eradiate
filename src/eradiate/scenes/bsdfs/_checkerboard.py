from __future__ import annotations

import attrs
import mitsuba as mi

from ._core import BSDFNode
from ..spectra import Spectrum, spectrum_factory
from ... import validators
from ...attrs import define, documented
from ...kernel._kernel_dict import KernelDictionary, KernelSceneParameterMap


@define(eq=False, slots=False)
class CheckerboardBSDF(BSDFNode):
    """
    Checkerboard BSDF [``checkerboard``].

    This class defines a Lambertian BSDF textured with a checkerboard pattern.
    """

    reflectance_a: Spectrum = documented(
        attrs.field(
            default=0.2,
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
        default="0.2",
    )

    reflectance_b: Spectrum = documented(
        attrs.field(
            default=0.8,
            converter=spectrum_factory.converter("reflectance"),
            validator=[
                attrs.validators.instance_of(Spectrum),
                validators.has_quantity("reflectance"),
            ],
        ),
        doc="Reflectance spectrum. Can be initialized with a dictionary "
        "processed by :data:`.spectrum_factory`.",
        type=".Spectrum",
        init_type=":class:`.Spectrum` or dict or float",
        default="0.8",
    )

    scale_pattern: float = documented(
        attrs.field(
            default=None,
            converter=attrs.converters.optional(float),
            validator=attrs.validators.optional(attrs.validators.instance_of(float)),
        ),
        doc="Scaling factor for the checkerboard pattern. The higher the value, "
        "the more checkerboard patterns will fit on the surface to which this "
        "reflection model is attached.",
        type="float or None",
        init_type="float, optional",
    )

    def kdict(self) -> KernelDictionary:
        # Inherit docstring

        result = KernelDictionary(
            {"type": "diffuse", "reflectance.type": "checkerboard"}
        )

        if self.id is not None:
            result["id"] = self.id

        if self.scale_pattern is not None:
            result["reflectance.to_uv"] = mi.ScalarTransform4f.scale(self.scale_pattern)

        for mi_attr, attr in [("color0", "reflectance_a"), ("color1", "reflectance_b")]:
            result.update(
                {"reflectance": {mi_attr: self.__getattribute__(attr).kdict()}}
            )

        return result

    def kpmap(self) -> KernelSceneParameterMap:
        # Inherit docstring

        result = KernelSceneParameterMap()

        for mi_attr, attr in [("color0", "reflectance_a"), ("color1", "reflectance_b")]:
            kpmap_template = self.__getattribute__(attr).kpmap()

            for k, v in kpmap_template.items():
                result[f"reflectance.{mi_attr}.{k}"] = v

        return result
