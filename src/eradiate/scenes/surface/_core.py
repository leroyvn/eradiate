from __future__ import annotations

from abc import ABC, abstractmethod

import attrs

from ..core import CompositeSceneElement, MitsubaDictObject
from ..._factory import Factory
from ...attrs import define, documented, get_doc, parse_docs

surface_factory = Factory()
surface_factory.register_lazy_batch(
    [
        ("_basic.BasicSurface", "basic", {}),
        ("_central_patch.CentralPatchSurface", "central_patch", {}),
        ("_dem.DEMSurface", "dem", {}),
    ],
    cls_prefix="eradiate.scenes.surface",
)


@parse_docs
@define
class Surface(CompositeSceneElement, ABC):
    """
    An abstract base class defining common facilities for all surfaces.

    All scene elements deriving from this interface are composite and cannot be
    turned into a kernel scene instance on their own: they must be owned by a
    container which take care of expanding them.

    Notes
    -----
    * This class is to be used as a mixin.
    """

    id: str | None = documented(
        attrs.field(
            default="surface",
            validator=attrs.validators.optional(attrs.validators.instance_of(str)),
        ),
        doc=get_doc(MitsubaDictObject, "id", "doc"),
        type=get_doc(MitsubaDictObject, "id", "type"),
        init_type=get_doc(MitsubaDictObject, "id", "init_type"),
        default='"surface"',
    )

    @property
    @abstractmethod
    def _template_bsdfs(self) -> dict:
        pass

    @property
    @abstractmethod
    def _template_shapes(self) -> dict:
        pass

    @property
    def kdict(self) -> dict:
        # Inherit docstring
        return {**self._template_bsdfs, **self._template_shapes}

    @property
    @abstractmethod
    def _params_bsdfs(self) -> dict:
        pass

    @property
    @abstractmethod
    def _params_shapes(self) -> dict:
        pass

    @property
    def umap(self) -> dict:
        # Inherit docstring
        return {**self._params_bsdfs, **self._params_shapes}
