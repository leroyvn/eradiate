from __future__ import annotations

from abc import ABC

import attrs
import mitsuba as mi

from ..bsdfs import BSDF, LambertianBSDF, bsdf_factory
from ..bsdfs._core import BSDFComposite, BSDFNode
from ..core import BoundingBox, InstanceSceneElement, NodeSceneElement, Ref
from ... import converters
from ..._factory import Factory
from ...attrs import define, documented, get_doc
from ...kernel import KernelSceneParameterMap

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


@define(eq=False, slots=False)
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
        doc=get_doc(NodeSceneElement, "id", "doc"),
        type=get_doc(NodeSceneElement, "id", "type"),
        init_type=get_doc(NodeSceneElement, "id", "init_type"),
        default='"shape"',
    )

    bsdf: BSDF | Ref | None = documented(
        attrs.field(
            factory=LambertianBSDF,
            converter=bsdf_factory.convert,
            validator=attrs.validators.optional(
                attrs.validators.instance_of((BSDF, Ref))
            ),
        ),
        doc="BSDF attached to the shape. If a dictionary is passed, it is "
        "interpreted by :class:`bsdf_factory.convert() <.Factory>`. "
        "If set to ``None``, no BSDF is specified during kernel dictionary "
        "generation: the kernel's default is used.",
        type=".BSDF or .Ref or None",
        init_type=".BSDF or .Ref or dict or None, optional",
        default=":class:`LambertianBSDF() <.LambertianBSDF>`",
    )

    to_world: "mitsuba.ScalarTransform4f" = documented(
        attrs.field(
            converter=converters.to_mi_scalar_transform,
            default=None,
        ),
        doc="Transform to scale, shift and rotate the shape.",
        type="mitsuba.ScalarTransform4f or None",
        init_type="mitsuba.ScalarTransform4f or array-like, optional",
        default=None,
    )

    @to_world.validator
    def to_world_validator(self, attribute, value):
        if value is not None:
            if not isinstance(value, mi.ScalarTransform4f):
                raise TypeError(
                    f"while validating '{attribute.name}': "
                    f"'{attribute.name}' must be a mitsuba.ScalarTransform4f; "
                    f"found: {type(value)}",
                )

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


@define(eq=False, slots=False)
class ShapeNode(Shape, NodeSceneElement, ABC):
    """
    Interface for shapes which can be represented as Mitsuba scene dictionary
    nodes.
    """

    def kpmap(self) -> KernelSceneParameterMap:
        # Inherit docstring

        result = KernelSceneParameterMap()

        if isinstance(self.bsdf, BSDFNode):
            # TODO: Handle BSDF with set ID
            kpmap = self.bsdf.kpmap()
            for k, v in kpmap.items():
                result[f"bsdf.{k}"] = v

        elif isinstance(self.bsdf, BSDFComposite):
            raise NotImplementedError

        return result


@define(eq=False, slots=False)
class ShapeInstance(Shape, InstanceSceneElement, ABC):
    """
    Interface for shapes which have to be expanded as Mitsuba objects.
    """

    pass
