from __future__ import annotations

from typing import Any, Callable, Generic, TypeVar

import attrs
import mitsuba as mi
from typing_extensions import TypeAlias

from .attrs import attrs_to_html_with_styles
from ..contexts import KernelContext

T = TypeVar("T")
Updater: TypeAlias = Callable[[KernelContext], Any]


@attrs.define(eq=False, init=False)
class SceneObject(Generic[T]):
    """
    This class encapsulates a Mitsuba object, colocating it with its scene
    parameters and a set of callables that can be used to update them.

    Parameters
    ----------
    object : mi.Object
        The encapsulated Mitsuba object.
    """

    _object: T = attrs.field(
        repr=lambda x: f"<mi.{type(x).__name__} object [{x.class_().name()}]>"
    )

    _scene_parameters: mi.SceneParameters = attrs.field(
        init=False, default=None, repr=False
    )

    _updaters: dict[str, Updater] = attrs.field(factory=dict, repr=False)

    def __init__(
        self, object: mi.Object | dict, updaters: dict[str, Updater] | None = None
    ):
        if isinstance(object, dict):
            object = mi.load_dict(object)

        self.__attrs_init__(object, updaters)

    def _repr_html_(self):
        return attrs_to_html_with_styles(self)

    @property
    def scene_parameters(self) -> mi.SceneParameters:
        if self._scene_parameters is None:
            self._scene_parameters = mi.traverse(self())
        return self._scene_parameters

    @property
    def updaters(self) -> dict[str, Updater]:
        return self._updaters

    def __call__(self) -> T:
        """Return the encapsulated Mitsuba object."""
        return self._object

    def id(self) -> str:
        """Return the ID of the encapsulated Mitsuba object."""
        return self().id()

    def set_id(self, value: str) -> None:
        """Set the ID of the encapsulated Mitsuba object."""
        self().set_id(value)

    def update(self, ctx: KernelContext, return_dict: bool = False) -> dict | None:
        """
        Update Mitsuba scene parameters based on the passed context.

        Parameters
        ----------
        ctx : KernelContext
            Context data used to evaluate the update protocols.

        return_dict : bool, default: False
            Debugging tool: If ``True``, do not perform the update, but instead
            return the dictionary containing the updated scene parameters.

        Returns
        -------
        dict or None
        """
        updated = {}

        for key, updater in self.updaters.items():
            updated[key] = updater(ctx)

        if return_dict:
            return updated
        else:
            self.scene_parameters.update(updated)

        return None

    def register_updater(self, maybe_func: Updater | None = None, param: str = ""):
        if param not in self.scene_parameters:
            raise ValueError(f"Parameter '{param}' not found")

        def wrap(f):
            self.updaters[param] = f

        return wrap if maybe_func is None else wrap(maybe_func)

    def check_parameters(self, drop: bool = False):
        """
        Check if all registered updaters are mapped to a parameter that exists.
        """
        scene_parameters = set(self.scene_parameters.keys())
        updater_keys = set(self.updaters.keys())
        missing = updater_keys - scene_parameters

        if missing:
            raise RuntimeError(
                f"Some updaters are associated with parameters that do not exist: {missing}"
            )

        if drop:
            scene_parameters.keep(updater_keys)
