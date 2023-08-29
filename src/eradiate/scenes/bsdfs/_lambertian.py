from __future__ import annotations

import attrs
import mitsuba as mi

from ._core import BSDF
from ..core import MitsubaDictObject, traverse
from ..spectra import Spectrum, spectrum_factory
from ... import validators
from ...attrs import define, documented, parse_docs
from ...kernel import UpdateParameter


@parse_docs
@define
class LambertianBSDF(BSDF):
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
        doc="Reflectance spectrum. Can be initialised with a dictionary "
        "processed by :data:`.spectrum_factory`.",
        type=".Spectrum",
        init_type=".Spectrum or dict or float",
        default="0.5",
    )

    def update(self) -> None:
        if self.reflectance.id is None:
            self.reflectance.id = f"{self.id}_reflectance"

    @property
    def kdict(self) -> dict:
        # Inherit docstring
        result = {"type": "diffuse"}

        if self.id is not None:
            result["id"] = self.id

        return result

    @property
    def umap(self) -> dict[str, UpdateParameter]:
        # Inherit docstring
        return {}

    @property
    def objects(self) -> dict[str, MitsubaDictObject] | None:
        # Inherit docstring

        return {"reflectance": self.reflectance}
