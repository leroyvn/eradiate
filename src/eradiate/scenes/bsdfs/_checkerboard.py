from __future__ import annotations

import attrs
import mitsuba as mi

from ._core import BSDF
from ..core import traverse
from ..spectra import Spectrum, spectrum_factory
from ... import validators
from ...attrs import documented, parse_docs
from ...kernel import TypeIdLookupStrategy, UpdateParameter


@parse_docs
@attrs.define(eq=False, slots=False)
class CheckerboardBSDF(BSDF):
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
        doc="Reflectance spectrum. Can be initialised with a dictionary "
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
        doc="Reflectance spectrum. Can be initialised with a dictionary "
        "processed by :data:`.spectrum_factory`.",
        type=".Spectrum",
        init_type=":class:`.Spectrum` or dict or float",
        default="0.8",
    )

    scale_pattern: float = documented(
        attrs.field(
            default=2.0, converter=float, validator=attrs.validators.instance_of(float)
        ),
        doc="Scaling factor for the checkerboard pattern. The higher the value, "
        "the more checkerboard patterns will fit on the surface to which this "
        "reflection model is attached.",
        type="float",
        default="2.0",
    )

    @property
    def template(self) -> dict:
        # Inherit docstring

        result = {"type": "diffuse", "reflectance.type": "checkerboard"}

        if self.id is not None:
            result["id"] = self.id

        for obj_key, obj_values in {
            "color0": traverse(self.reflectance_a)[0],
            "color1": traverse(self.reflectance_b)[0],
        }.items():
            for key, value in obj_values.items():
                result[f"reflectance.{obj_key}.{key}"] = value

        return result

    @property
    def params(self) -> dict[str, UpdateParameter]:
        # Inherit docstring

        result = {}

        for obj_key, obj_params in {
            "color0": traverse(self.reflectance_a)[1].data,
            "color1": traverse(self.reflectance_b)[1].data,
        }.items():
            for key, param in obj_params.items():
                result[f"reflectance.{obj_key}.{key}"] = attrs.evolve(
                    param,
                    lookup_strategy=TypeIdLookupStrategy(
                        node_type=mi.BSDF,
                        node_id=self.id,
                        parameter_relpath=f"reflectance.{obj_key}.{key}",
                    )
                    if self.id is not None
                    else None,
                )

        return result
