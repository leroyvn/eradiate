"""
Plugin-style registry/factory for Pydantic-based configuration types.

Each type family (Spectrum, Material, etc.) has a module-level :class:`.Registry`
instance. Base classes install a ``model_validator(mode="wrap")`` that
delegates to :meth:`.Registry.dispatch`, which resolves the ``"type"`` key in
incoming dicts and calls ``model_validate`` on the correct registered class.

Backends register their own concrete types at import time::

    from eradiate.two.core import measurement_registry

    @measurement_registry.register("my_sensor")
    class MySensor(BaseMeasurement):
        type: Literal["my_sensor"] = "my_sensor"
        ...
"""

from __future__ import annotations

from typing import Callable, Generic, TypeVar, overload

T = TypeVar("T")


class Registry(Generic[T]):
    """
    Runtime registry mapping string type IDs to Pydantic model classes.

    Parameters
    ----------
    name : str
        Human-readable name of the type family (used in error messages).
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._registry: dict[str, type] = {}

    def __repr__(self) -> str:
        return f"Registry({self.name!r}, types={sorted(self._registry)})"

    @overload
    def register(self, type_id: str, maybe_cls: type[T]) -> type[T]: ...

    @overload
    def register(
        self, type_id: str, maybe_cls: None = None
    ) -> Callable[[type[T]], type[T]]: ...

    def register(self, type_id: str, maybe_cls: type[T] | None = None):
        """
        Register a class under a type ID.

        Can be used as a plain call or as a class decorator::

            # Plain call
            registry.register("foo", FooClass)

            # Decorator
            @registry.register("foo")
            class FooClass(BaseClass):
                type: Literal["foo"] = "foo"

        Parameters
        ----------
        type_id : str
            String identifier for the type (matches the ``"type"`` key in
            configuration dicts).

        maybe_cls : type, optional
            The class to register. If omitted, returns a decorator.

        Returns
        -------
        type or callable
            The class itself (plain call) or a decorator (no ``maybe_cls``).
        """
        if maybe_cls is None:

            def decorator(c: type[T]) -> type[T]:
                self._registry[type_id] = c
                return c

            return decorator
        self._registry[type_id] = maybe_cls
        return maybe_cls

    def dispatch(self, value, handler, base_cls: type[T]) -> T:
        """
        Dispatch logic for use inside a ``model_validator(mode="wrap")``.

        Call this from the base class validator (where ``cls is base_cls``).
        Handles three cases:

        * ``value`` is already an instance of ``base_cls``: returned as-is.
        * ``value`` is a dict: looks up ``value["type"]`` in the registry,
          then calls ``model_validate`` on the resolved class.
        * anything else: delegates to ``handler(value)`` (normal Pydantic
          validation path).

        Parameters
        ----------
        value :
            Raw input to validate.

        handler :
            The Pydantic wrap-validator handler (normal validation path).

        base_cls : type
            The base class on which the validator is defined.

        Returns
        -------
        instance of base_cls

        Raises
        ------
        ValueError
            If ``value`` is a dict but ``value["type"]`` is not registered.
        """
        if isinstance(value, base_cls):
            return value

        if isinstance(value, dict):
            type_id = value.get("type")
            resolved = self._registry.get(type_id)
            if resolved is None:
                available = sorted(self._registry)
                raise ValueError(
                    f"Unknown {self.name} type '{type_id}'. "
                    f"Available types: {available}"
                )
            return resolved.model_validate(value)

        return handler(value)
