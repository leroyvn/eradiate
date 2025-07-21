from __future__ import annotations

from typing import ClassVar

import attrs
import mitsuba as mi

from .scene_object import SceneObject


@attrs.define(eq=False)
class Scene:
    phase_functions: dict[str, SceneObject[mi.PhaseFunction]] = attrs.field(
        factory=dict
    )
    media: dict[str, SceneObject[mi.Medium]] = attrs.field(factory=dict)
    bsdfs: dict[str, SceneObject[mi.BSDF]] = attrs.field(factory=dict)
    shapes: dict[str, SceneObject[mi.Shape]] = attrs.field(factory=dict)
    emitters: dict[str, SceneObject[mi.Emitter]] = attrs.field(factory=dict)
    sensors: dict[str, SceneObject[mi.Sensor]] = attrs.field(factory=dict)
    mi_scene: mi.Scene | None = attrs.field(default=None)

    _SECTIONS: ClassVar[list[str]] = [
        "phase_functions",
        "media",
        "bsdfs",
        "shapes",
        "emitters",
        "sensors",
    ]

    _OBJECT_TYPES_TO_SECTIONS: ClassVar[dict[str, str]] = {
        "phase_function": "phase_functions",
        "medium": "media",
        "bsdf": "bsdfs",
        "shape": "shapes",
        "emitter": "emitters",
        "sensor": "sensors",
    }

    _SECTIONS_TO_OBJECT_TYPES: ClassVar[dict[str, str]] = {
        "phase_functions": "phase_function",
        "media": "medium",
        "bsdfs": "bsdf",
        "shapes": "shape",
        "emitters": "emitter",
        "sensors": "sensor",
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

    def get_object_id_prefix(self, section_name: str) -> str:
        i = self._get_section_index(section_name)
        object_type_name = self._get_object_type_name(section_name)
        id_prefix = f"{i:02d}_{object_type_name}"
        return id_prefix

    def init(self, return_dict: bool = False) -> dict | None:
        scene_dict = {"type": "scene"}
        for section_name in ["bsdfs", "shapes", "emitters", "sensors"]:
            obj_id_prefix = self.get_object_id_prefix(section_name)

            for i_obj, (obj_id, obj) in enumerate(
                self._get_object_dict(section_name).items()
            ):
                obj_id = f"{obj_id_prefix}_{obj_id}"
                scene_dict.update({obj_id: obj()})

        if return_dict:
            return scene_dict
        else:
            self.mi_scene = mi.load_dict(scene_dict)
            return None
