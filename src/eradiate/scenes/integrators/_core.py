from __future__ import annotations

from abc import ABC

import attrs

from ..core import NodeSceneElement
from ..._factory import Factory
from ...attrs import define, documented, get_doc, parse_docs

integrator_factory = Factory()
integrator_factory.register_lazy_batch(
    [
        ("_path_tracers.PathIntegrator", "path", {}),
        ("_path_tracers.VolPathIntegrator", "volpath", {}),
        ("_path_tracers.VolPathMISIntegrator", "volpathmis", {}),
    ],
    cls_prefix="eradiate.scenes.integrators",
)


@parse_docs
@define
class Integrator(NodeSceneElement, ABC):
    """
    Abstract base class for all integrator elements.

    Notes
    -----
    * This class is to be used as a mixin.
    """

    id: str | None = documented(
        attrs.field(
            default="integrator",
            validator=attrs.validators.optional(attrs.validators.instance_of(str)),
        ),
        doc=get_doc(NodeSceneElement, "id", "doc"),
        type=get_doc(NodeSceneElement, "id", "type"),
        init_type=get_doc(NodeSceneElement, "id", "init_type"),
        default='"integrator"',
    )
