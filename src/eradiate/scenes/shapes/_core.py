from __future__ import annotations

from abc import ABC

import attrs

from ..bsdfs import BSDF, bsdf_factory
from ..core import BoundingBox, MitsubaDictObject, MitsubaInstanceObject, MitsubaRef
from ..._factory import Factory
from ...attrs import define, documented, get_doc, parse_docs

shape_factory = Factory()
shape_factory.register_lazy_batch(
    [
        ("_cuboid.CuboidShape", "cuboid", {}),
        ("_rectangle.RectangleShape", "rectangle", {}),
        ("_sphere.SphereShape", "sphere", {}),
        ("_filemesh.FileMeshShape", "file_mesh", {}),
        ("_buffermesh.BufferMeshShape", "buffer_mesh", {}),
    ],
    cls_prefix="eradiate.scenes.shapes",
)


@parse_docs
@define
class Shape:
    """
    Abstract interface for all shape scene elements.

    Notes
    -----
    * This class is to be used as a mixin.
    """

    id: str | None = documented(
        attrs.field(
            default="shape",
            validator=attrs.validators.optional(attrs.validators.instance_of(str)),
        ),
        doc=get_doc(MitsubaDictObject, "id", "doc"),
        type=get_doc(MitsubaDictObject, "id", "type"),
        init_type=get_doc(MitsubaDictObject, "id", "init_type"),
        default='"shape"',
    )

    bsdf: BSDF | MitsubaRef | None = documented(
        attrs.field(
            default=None,
            converter=attrs.converters.optional(bsdf_factory.convert),
            validator=attrs.validators.optional(
                attrs.validators.instance_of((BSDF, MitsubaRef))
            ),
        ),
        doc="BSDF attached to the shape. If a dictionary is passed, it is "
        "interpreted by :class:`bsdf_factory.convert() <.Factory>`. "
        "If unset, no BSDF will be specified during the kernel dictionary "
        "generation: the kernel's default will be used. If a :class:`.BSDF` "
        "instance (or a corresponding dictionary specification) is passed, "
        "its `id` member is automatically overridden.",
        type="BSDF or Ref or None",
        init_type="BSDF or Ref or dict, optional",
    )

    def __attrs_post_init__(self):
        self.update()

    def update(self) -> None:
        # Inherit docstring

        # Normalize child BSDF ID
        if isinstance(self.bsdf, BSDF):
            self.bsdf.id = self._bsdf_id

    @property
    def bbox(self) -> BoundingBox:
        """
        :class:`.BoundingBox` : Shape bounding box. Default implementation
            raises a :class:`NotImplementedError`.
        """
        raise NotImplementedError

    @property
    def _bsdf_id(self) -> str:
        return f"{self.id}_bsdf"

    @property
    def objects(self) -> dict[str, MitsubaDictObject] | None:
        # Inherit docstring
        if self.bsdf is None:
            return None
        else:
            return {"bsdf": self.bsdf}


@define
class ShapeNode(Shape, MitsubaDictObject, ABC):
    """
    Interface for shapes which can be represented as Mitsuba scene dictionary
    nodes.
    """

    pass


@define
class ShapeInstance(Shape, MitsubaInstanceObject, ABC):
    """
    Interface for shapes which have to be expanded as Mitsuba objects.
    """

    pass
