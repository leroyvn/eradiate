from __future__ import annotations

import typing as t
from abc import ABC, abstractmethod

import attrs
import drjit as dr
import mitsuba as mi


# attrs utilities
def define(maybe_cls=None, **kwargs):
    eq = kwargs.pop("eq") if "eq" in kwargs else False
    return attrs.define(maybe_cls=maybe_cls, eq=eq, **kwargs)


# Mitsuba object wrappers


@define(repr=False)
class MitsubaType:
    """
    Mitsuba object type, defined as a callable returning the type appropriate
    for the current active variant.
    """

    name: str = attrs.field(validator=attrs.validators.instance_of(str))

    def __call__(self):
        return getattr(mi, self.name)

    def __repr__(self):
        return f"MitsubaType({repr(self.name)})"


def test_mitsuba_type():
    mi.set_variant("scalar_rgb")
    assert MitsubaType("Float")() is float
    mi.set_variant("llvm_ad_rgb")
    assert MitsubaType("Float")() is dr.llvm.ad.Float


@define
class MitsubaObject:
    #: Mitsuba object ID
    id: str = attrs.field()

    #: Mitsuba object type
    type: MitsubaType = attrs.field(
        converter=lambda x: MitsubaType(x) if isinstance(x, str) else x,
        validator=attrs.validators.instance_of(MitsubaType),
    )

    #: Mitsuba scene parameters, defined as a dictionary mapping parameter names
    #: to callable updaters.
    _parameters: t.Callable = attrs.field(default=None)

    def parameters(self) -> dict:
        return self._parameters() if self._parameters is not None else None


@define
class MitsubaInstance(MitsubaObject):
    _object: t.Callable = attrs.field(kw_only=True)

    def object(self):
        return self._object()


def test_mitsuba_object():
    mi.set_variant("scalar_rgb")
    mesh = MitsubaInstance(id="mesh", type="Mesh", parameters=None, object=None)


@define
class MitsubaPlugin(MitsubaObject):
    _scene_dict: t.Callable = attrs.field(kw_only=True)

    def scene_dict(self) -> dict:
        return self._scene_dict()

    def instantiate(self) -> "mitsuba.Object":
        return mi.load_dict(self.scene_dict())


@define
class MitsubaReference:
    #: Referenced Mitsuba object ID
    id: str = attrs.field()

    def scene_dict(self) -> dict:
        return {"type": "ref", "id": self.id}


# Scene elements


@define
class SceneElement(ABC):
    id: str = attrs.field()

    @abstractmethod
    def umap_template(self) -> dict:
        pass

    @abstractmethod
    def traverse(self, callback: SceneTraversal) -> None:
        pass


@define
class MitsubaDictObject(SceneElement):
    @abstractmethod
    def kdict_template(self) -> dict:
        pass

    def traverse(self, callback: SceneTraversal) -> None:
        kdict_template = self.kdict_template()
        if self.id:
            kdict_template["id"] = self.id

        umap_template = self.umap_template()

        callback.put_kdict_template(kdict_template)
        callback.put_umap_template(umap_template, obj_id=self.id)


@define
class UniformSpectrum(MitsubaDictObject):
    value: float = attrs.field()

    def kdict_template(self) -> dict:
        return {"type": "uniform", "value": self.value}

    def umap_template(self) -> dict:
        return {"value": None}


@define
class DiffuseBSDF(MitsubaDictObject):
    reflectance: UniformSpectrum = attrs.field()

    def kdict_template(self) -> dict:
        return {"type": "diffuse"}

    def umap_template(self) -> dict:
        return {}

    def traverse(self, callback: SceneTraversal) -> None:
        super().traverse(callback)
        callback.put_object("reflectance", self.reflectance)


@attrs.define
class SceneParameters:
    kdict_template: dict = attrs.field()
    umap_template: dict = attrs.field()
    hierarchy: dict = attrs.field()


@attrs.define
class SceneTraversal:
    #: Current traversal node
    node: SceneElement

    #: Parent to current node
    parent: SceneElement | None = attrs.field(default=None)

    #: Current node's name
    name: str | None = attrs.field(default=None)

    #: Current depth
    depth: int = attrs.field(default=0)

    #: Dictionary mapping nodes to their parents
    hierarchy: dict = attrs.field(factory=dict)

    #: Mitsuba objects
    kdict_template: dict = attrs.field(factory=dict)

    #: Scene parameters associated to the Mitsuba objects created by the scene elements
    umap_template: dict = attrs.field(factory=dict)

    def __attrs_post_init__(self):
        self.hierarchy[self.node] = (self.parent, self.depth)

    def put_object(self, name: str, node: SceneElement) -> None:
        if node is None or node in self.hierarchy:
            return

        cb = SceneTraversal(
            node=node,
            parent=self.node,
            name=name if self.name is None else f"{self.name}.{name}",
            depth=self.depth + 1,
            hierarchy=self.hierarchy,
            kdict_template=self.kdict_template,
            umap_template=self.umap_template,
        )
        node.traverse(cb)

    def put_kdict_template(self, kdict_template: dict) -> None:
        if self.name is not None:
            self.kdict_template.update(
                **{f"{self.name}.{k}": v for k, v in kdict_template.items()}
            )
        else:
            self.kdict_template.update(kdict_template)

    def put_umap_template(self, umap_template: dict, obj_id: str | None = None) -> None:
        print(f"{self.name = }")
        print(f"{umap_template = }")
        if obj_id is not None:
            self.umap_template.update(
                **{f"{obj_id}.{k}": v for k, v in umap_template.items()}
            )
        elif self.name is not None:
            self.umap_template.update(
                **{f"{self.name}.{k}": v for k, v in umap_template.items()}
            )
        else:
            self.umap_template.update(umap_template)


def traverse(node: SceneElement) -> SceneParameters:
    # Traverse scene element tree
    cb = SceneTraversal(node)
    node.traverse(cb)
    return SceneParameters(
        kdict_template=cb.kdict_template,
        umap_template=cb.umap_template,
        hierarchy=cb.hierarchy,
    )


def test_traverse():
    obj = DiffuseBSDF(
        id="surface_bsdf",
        reflectance=UniformSpectrum("soil_reflectance", 1.0),
    )
    params = traverse(obj)
    print(f"{params.kdict_template = }")
    print(f"{params.umap_template = }")
