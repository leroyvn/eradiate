from __future__ import annotations

from typing import Any, Callable, Generic, TypeVar

import attrs
import mitsuba as mi
from typing_extensions import TypeAlias

from ..repr_html import to_html_with_styles
from ...contexts import KernelContext

T = TypeVar("T")
Updater: TypeAlias = Callable[[KernelContext], Any]


@attrs.define(eq=False, init=False)
class SceneObject(Generic[T]):
    """
    This class encapsulates a kernel object, colocated it with its scene
    parameters and a set of callables that can be used to update them based on
    a context object. This class provides a higher level of automation
    compared to using Mitsuba's scene update system by coordinating scene
    parameter updates through a common :class:`.KernelContext`.

    Parameters
    ----------
    object : mitsuba.Object
        The encapsulated kernel object.

    updaters : dict, optional
        Mapping of kernel scene parameter paths to update functions with
        signature ``f(ctx: KernelContext) -> Any``.
    """

    # Encapsulated kernel object
    _mi_object: T = attrs.field(
        repr=lambda x: f"<mi.{type(x).__name__} object [{x.class_name()}]>"
    )

    # Mapping of scene parameter paths to update functions
    _updaters: dict[str, Updater] = attrs.field(factory=dict, repr=False)

    # Associated kernel scene parameters (not exposed to constructor)
    _scene_parameters: mi.SceneParameters | None = attrs.field(
        init=False, default=None, repr=False
    )

    def __init__(
        self, object: mi.Object | dict, updaters: dict[str, Updater] | None = None
    ):
        if isinstance(object, dict):
            object = mi.load_dict(object)

        if updaters is None:
            updaters = {}

        self.__attrs_init__(object, updaters)

    def _repr_html_(self):
        return to_html_with_styles(self)

    @property
    def _exposed_scene_parameters(self) -> list[str] | None:
        """
        Return the list of exposed scene parameters.
        """
        return None

    def scene_parameters(
        self, use_cache: bool = True, keep_only_exposed: bool = True
    ) -> mi.SceneParameters:
        """
        Kernel scene parameters (initialized upon first access).
        """
        if not use_cache:
            self._scene_parameters = None

        if self._scene_parameters is None:
            self._scene_parameters = mi.traverse(self())

            if keep_only_exposed and self._exposed_scene_parameters is not None:
                self._scene_parameters.keep(self._exposed_scene_parameters)

        return self._scene_parameters

    @property
    def updaters(self) -> dict[str, Updater]:
        """
        Mapping of scene parameter paths to update functions.
        """
        return self._updaters

    def __call__(self) -> T:
        """Return the encapsulated kernel object."""
        return self._mi_object

    def id(self) -> str:
        """Return the ID of the encapsulated kernel object."""
        return self().id()

    def set_id(self, value: str) -> None:
        """Set the ID of the encapsulated kernel object."""
        self().set_id(value)

    def update(self, ctx: KernelContext, return_dict: bool = False) -> dict | None:
        """
        Update kernel scene parameters based on the passed context.

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
            self.scene_parameters().update(updated)

        return None

    def register_updater(self, maybe_func: Updater | None = None, *, param: str = ""):
        """
        Register a new updater.

        Parameters
        ----------
        maybe_func : callable
            The updater function to register. Must be omitted if used as a
            decorator.

        param : str
            Path to the parameter this function will update.
        """
        if param not in self.scene_parameters():
            raise ValueError(f"Parameter '{param}' not found")

        def wrap(f):
            self.updaters[param] = f

        return wrap if maybe_func is None else wrap(maybe_func)

    def check_parameters(self, drop: bool = False):
        """
        Check if all registered updaters are mapped to a parameter that exists.
        """
        scene_parameters = set(self.scene_parameters().keys())
        updater_keys = set(self.updaters.keys())
        missing = updater_keys - scene_parameters

        if missing:
            raise RuntimeError(
                f"Some updaters are associated with parameters that do not exist: {missing}"
            )

        if drop:
            scene_parameters.keep(updater_keys)
