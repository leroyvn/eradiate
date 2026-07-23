from __future__ import annotations

import logging
from typing import ClassVar

import attrs
import mitsuba as mi

from eradiate.contexts import KernelContext

from .materials import Material
from .scene_object import SceneObject
from ..repr_html import to_html_with_styles

logger = logging.getLogger(__name__)


@attrs.define(eq=False)
class Scene:
    """
    Kernel scene data structure that encapsulates multiple :class:`.SceneObject`
    instances, grouped into sections, and a kernel scene object that aggregates
    them.

    Parameters
    ----------
    phase_functions : dict, optional
        Mapping of phase function IDs to scene objects encapsulating a
        :class:`~mitsuba.PhaseFunction` instance.

    media : dict, optional
        Mapping of medium IDs to scene objects encapsulating a
        :class:`~mitsuba.Medium` instance.

    materials : dict, optional
        Mapping of BSDF IDs to scene objects encapsulating a
        :class:`~mitsuba.BSDF` instance.

    shapes : dict, optional
        Mapping of shape IDs to scene objects encapsulating a
        :class:`~mitsuba.Shape` instance.

    emitters : dict, optional
        Mapping of emitter IDs to scene objects encapsulating an
        :class:`~mitsuba.Emitter` instance.
    """

    #: Mapping of phase function IDs to scene objects encapsulating a
    #: :class:`~mitsuba.PhaseFunction` instance.
    phase_functions: dict[str, SceneObject[mi.PhaseFunction]] = attrs.field(
        factory=dict
    )

    #: Mapping of medium IDs to scene objects encapsulating a
    #: :class:`~mitsuba.Medium` instance.
    media: dict[str, SceneObject[mi.Medium]] = attrs.field(factory=dict)

    #: Mapping of BSDF IDs to scene objects encapsulating a
    #: :class:`~mitsuba.BSDF` instance.
    materials: dict[str, Material] = attrs.field(factory=dict)

    #: Mapping of shape IDs to scene objects encapsulating a
    #: :class:`~mitsuba.Shape` instance.
    shapes: dict[str, SceneObject[mi.Shape]] = attrs.field(factory=dict)

    #: Mapping of emitter IDs to scene objects encapsulating an
    #: :class:`~mitsuba.Emitter` instance.
    emitters: dict[str, SceneObject[mi.Emitter]] = attrs.field(factory=dict)

    #: Internal :class:`mitsuba.Scene` instance once initialized (otherwise ``None``).
    mi_scene: mi.Scene | None = attrs.field(default=None, init=False, repr=False)

    # Defines kernel scene sections and their order
    _SECTIONS: ClassVar[list[str]] = [
        "phase_functions",
        "media",
        "materials",
        "shapes",
        "emitters",
    ]

    # Maps kernel object type to section name
    _OBJECT_TYPES_TO_SECTIONS: ClassVar[dict[str, str]] = {
        "phase_function": "phase_functions",
        "medium": "media",
        "material": "materials",
        "shape": "shapes",
        "emitter": "emitters",
    }

    # Maps section content to Mitsuba ID prefix
    _SECTIONS_TO_OBJECT_TYPES: ClassVar[dict[str, str]] = {
        "phase_functions": "phase_function",
        "media": "medium",
        "materials": "bsdf",
        "shapes": "shape",
        "emitters": "emitter",
    }

    @classmethod
    def _get_section_index(cls, section_name: str) -> int:
        return cls._SECTIONS.index(section_name)

    @classmethod
    def _get_object_type_name(cls, section_name: str) -> str:
        return cls._SECTIONS_TO_OBJECT_TYPES[section_name]

    @classmethod
    def _get_section_name(cls, obj_type_name: str) -> str:
        return cls._OBJECT_TYPES_TO_SECTIONS[obj_type_name]

    def _get_object_dict(self, section_name: str) -> dict[str, SceneObject]:
        return getattr(self, section_name)

    def _get_object_id_prefix(self, section_name: str) -> str:
        i = self._get_section_index(section_name)
        object_type_name = self._get_object_type_name(section_name)
        id_prefix = f"{i:02d}_{object_type_name}"
        return id_prefix

    def init(self, return_dict: bool = False) -> dict | None:
        """
        Initialize kernel scene.

        Parameters
        ----------
        return_dict : bool, default: False
            (Debugging option) If ``True``, return the Python dictionary used to
            initialize the scene instead of initializing it. Otherwise, this
            method returns ``None``.
        """
        scene_dict = {"type": "scene"}
        for section_name in ["materials", "shapes", "emitters"]:
            obj_id_prefix = self._get_object_id_prefix(section_name)

            for _i_obj, (obj_id, obj) in enumerate(
                self._get_object_dict(section_name).items()
            ):
                obj_id = f"{obj_id_prefix}_{obj_id}"
                scene_dict.update({obj_id: obj()})

        if return_dict:
            return scene_dict
        else:
            self.mi_scene = mi.load_dict(scene_dict)
            return None

    def parameters_changed(self, keys: list[str] = None) -> None:
        """
        Force a kernel scene object update. This is, in particular, needed
        after a geometry update.
        """
        if self.mi_scene is None:
            return None

        keys = keys or []

        return self.mi_scene.parameters_changed(keys)

    def _repr_html_(self):
        return to_html_with_styles(self)

    def update(self, ctx: KernelContext):
        for section_id in self._SECTIONS:
            logger.debug(f"Updating scene section '{section_id}'")
            section = getattr(self, section_id)
            for obj in section.values():
                # TODO: avoid double updates of shared objects
                # TODO: update children (e.g. spectra)
                obj.update(ctx)
