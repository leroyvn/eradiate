from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import mitsuba as mi

    mi.set_variant("scalar_rgb")

from .scene import Scene
from .scene_object import SceneObject

__all__ = [
    "Scene",
    "SceneObject",
]
