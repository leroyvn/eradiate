"""
This module contains the infrastructure used to generate Mitsuba scene
dictionaries and scene parameter maps.
"""

from __future__ import annotations

import enum
import logging
from collections import UserDict
from collections.abc import Mapping
from typing import Any, Callable, ClassVar

import attrs

from ..attrs import define, documented
from ..contexts import KernelContext
from ..util.misc import flatten, nest

logger = logging.getLogger(__name__)


class KernelSceneParameterFlag(enum.Flag):
    """
    Update parameter flags.
    """

    NONE = 0
    SPECTRAL = enum.auto()  #: Varies during the spectral loop
    GEOMETRIC = enum.auto()  #: Triggers a scene rebuild
    ALL = SPECTRAL | GEOMETRIC


@define
class KernelDictionaryParameter:
    """
    This class declares an Eradiate parameter in a Mitsuba scene dictionary. It
    holds an evaluation protocol for this parameter depending on context
    information.
    """

    #: Sentinel value indicating that a parameter is not used
    UNUSED: ClassVar[object] = object()

    evaluator: Callable = documented(
        attrs.field(validator=attrs.validators.is_callable()),
        doc="A callable that returns the value of the parameter for a given "
        "context, with signature ``f(ctx: KernelContext) -> Any``.",
        type="callable",
    )

    def __call__(self, ctx: KernelContext) -> Any:
        return self.evaluator(ctx)


@attrs.define(slots=False)
class KernelDictionary(UserDict):
    """
    A dict-like structure which defines the structure of an instantiable
    Mitsuba scene dictionary.

    Entries are indexed by dot-separated paths which can then be expanded to
    a nested dictionary using the :meth:`.render` method.

    Each entry can be either a hard-coded value which can be directly
    interpreted by the :func:`mitsuba.load_dict` function, or an
    :class:`.InitParameter` object which must be rendered before the template
    can be instantiated.
    """

    data: dict[str, Any] = attrs.field(factory=dict, converter=flatten)

    def __setitem__(self, key, value):
        if isinstance(value, Mapping):
            value = flatten(value, name=key)
            self.data.update(value)
        else:
            super().__setitem__(key, value)

    def update(self, __m, **kwargs):
        if isinstance(__m, Mapping):
            return super().update(flatten(__m))
        else:
            raise ValueError("key-value assignment is not supported")

    def render(
        self, ctx: KernelContext, nested: bool = True, drop: bool = True
    ) -> dict:
        """
        Render the template as a nested dictionary using a parameter map to fill
        in empty fields.

        Parameters
        ----------
        ctx : :class:`.KernelContext`
            A kernel dictionary context.

        nested : bool, optional
            If ``True``, the returned dictionary will be nested and suitable for
            instantiation by Mitsuba; otherwise, the returned dictionary will be
            flat.

        drop : bool, optional
            If ``True``, drop unused parameters. Parameters may be unused either
            because they were filtered out by the flags or because context
            information implied it.

        Returns
        -------
        dict
        """
        result = {}

        for k, v in list(self.items()):
            value = v(ctx) if isinstance(v, KernelDictionaryParameter) else v
            if (value is KernelDictionaryParameter.UNUSED) and drop:
                continue
            else:
                result[k] = value

        return nest(result, sep=".") if nested else result


@define
class KernelSceneParameter:
    """
    This class declares an Eradiate parameter in a Mitsuba scene parameter
    update map. It holds an evaluation protocol depending on context
    information.

    See Also
    --------
    :class:`.KernelContext`
    """

    #: Sentinel value indicating that a parameter is not used
    UNUSED: ClassVar[object] = object()

    evaluator: Callable = documented(
        attrs.field(validator=attrs.validators.is_callable()),
        doc="A callable that returns the value of the parameter for a given "
        "context, with signature ``f(ctx: KernelContext) -> Any``.",
        type="callable",
    )

    flags: KernelSceneParameterFlag = documented(
        attrs.field(default=KernelSceneParameterFlag.ALL),
        doc="Flags specifying parameter attributes. By default, the declared "
        "parameter will pass all filters.",
        type=".Flags",
        default=".Flags.ALL",
    )

    def __call__(self, ctx: KernelContext) -> Any:
        return self.evaluator(ctx)


@define(slots=False)
class KernelSceneParameterMap(UserDict):
    """
    A dict-like structure which contains the structure of a Mitsuba scene
    parameter update map.

    Entries are indexed by dot-separated paths which can then be expanded to
    a nested dictionary using the :meth:`.render` method.
    """

    data: dict = attrs.field(factory=dict)

    def remove(self, keys: str | list[str]) -> None:
        """
        Remove all parameters matching the given regular expression.

        Parameters
        ----------
        keys : str or list of str
            Regular expressions matching the parameters to remove.

        Notes
        -----
        This method mutates the parameter map.
        """
        if not isinstance(keys, list):
            keys = [keys]

        import re

        regexps = [re.compile(k).match for k in keys]
        keys = [k for k in self.keys() if any(r(k) for r in regexps)]

        for key in keys:
            del self.data[key]

    def keep(self, keys: str | list[str]) -> None:
        """
        Keep only parameters matching the given regular expression.

        Parameters
        ----------
        keys : str or list of str
            Regular expressions matching the parameters to keep.

        Notes
        -----
        This method mutates the parameter map.
        """
        if not isinstance(keys, list):
            keys = [keys]

        import re

        regexps = [re.compile(k).match for k in keys]
        keys = [k for k in self.keys() if any(r(k) for r in regexps)]
        result = {k: self.data[k] for k in keys}
        self.data = result

    def render(
        self,
        ctx: KernelContext,
        flags: KernelSceneParameterFlag = KernelSceneParameterFlag.ALL,
        strict: bool = False,
    ) -> dict:
        """
        Evaluate the parameter map for a set of arguments.

        Parameters
        ----------
        ctx : .KernelContext
            A kernel dictionary context.

        flags : .KernelSceneParameterFlag
            Parameter flags. Only parameters with at least one of the specified
            will pass the filter.

        strict : bool, optional
            If ``True``, raise if parameters remain unused. Parameters end up
            unused when filtered out by flags. This parameter exists for
            debugging purposes.

        Returns
        -------
        dict

        Raises
        ------
        ValueError
            If a value is not a :class:`.KernelSceneParameter`.

        ValueError
            If ``strict`` is ``True`` and the rendered parameter map contains an
            unused parameter.
        """
        unused = []
        result = {}

        for key in list(
            self.keys()
        ):  # Ensures correct iteration even if the loop mutates the mapping
            v = self[key]

            if isinstance(v, KernelSceneParameter):
                if v.flags & flags:
                    result[key] = v(ctx)
                else:
                    unused.append(key)
                    if strict:
                        result[key] = KernelSceneParameter.UNUSED

        # Check for leftover empty values
        if strict and unused:
            raise ValueError(f"Unevaluated parameters: {unused}")

        return result


def dict_parameter(maybe_fn=None):
    """
    This function wraps another one into a :class:`.KernelDictionaryParameter`
    instance. It is primarily meant to be used as a decorator.

    Parameters
    ----------
    maybe_fn : callable, optional
    """
    return (
        KernelDictionaryParameter
        if maybe_fn is None
        else KernelDictionaryParameter(maybe_fn)
    )


def scene_parameter(
    maybe_fn=None, flags: KernelSceneParameterFlag | str = KernelSceneParameterFlag.ALL
):
    """
    This function wraps another one into a :class:`.KernelSceneParameter`
    instance. It is primarily meant to be used as a decorator.

    Parameters
    ----------
    maybe_fn : callable, optional

    flags : .KernelSceneParameterFlag, optional
        Scene parameter flags used for filtering during a scene parameter loop.
    """
    if isinstance(flags, str):
        flags = KernelSceneParameterFlag[flags.upper()]

    def wrap(f):
        return KernelSceneParameter(f, flags=flags)

    return wrap if maybe_fn is None else wrap(maybe_fn)
