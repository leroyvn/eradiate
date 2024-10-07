"""
This module contains the infrastructure used to generate Mitsuba scene
dictionaries and scene parameter maps.
"""

from __future__ import annotations

import enum
import logging
from collections import UserDict
from typing import Any, Callable, ClassVar, Optional

import attrs
import mitsuba as mi
from tqdm.auto import tqdm

from .. import config
from ..attrs import define, documented
from ..contexts import KernelContext
from ..rng import SeedState, root_seed_state
from ..util.misc import nest

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


@define(slots=False)
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

    data: dict[str, Any] = attrs.field(factory=dict)

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
        ctx : :class:`.KernelContext`
            A kernel dictionary context.

        flags : :class:`.ParamFlags`
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
            If a value is not a :class:`.UpdateParameter`.

        ValueError
            If ``drop`` is ``False`` and the rendered parameter map contains an
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
                    if not strict:
                        result[key] = KernelSceneParameter.UNUSED

        # Check for leftover empty values
        if not strict and unused:
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


def mi_traverse(
    obj: mi.Object, name_id_override: str | list[str] | bool | None = None
) -> mi.SceneParameters:
    """
    Traverse a node of the Mitsuba scene graph and return scene parameters as
    a mutable mapping.

    Parameters
    ----------
    obj : mitsuba.Object
        Mitsuba scene graph node to be traversed.

    name_id_override : str or list of str, optional
        If set, this argument will be used to select nodes in the scene tree
        whose names will be "pinned" to their ID. Passed values are used as
        regular expressions, with all that it implies regarding ID string
        matching. If this parameter is set to ``True``, a regex that matches
        anything is used.

    Returns
    -------
    SceneParameters

    Notes
    -----
    This is a reimplementation of the :func:`mitsuba.traverse` function.
    """

    if name_id_override is None or name_id_override is False:
        name_id_override = []

    if name_id_override is True:
        name_id_override = [r".*"]

    if type(name_id_override) is not list:
        name_id_override = [name_id_override]

    import re

    regexps = [re.compile(k).match for k in name_id_override]

    class SceneTraversal(mi.TraversalCallback):
        def __init__(
            self,
            node,
            parent=None,
            properties=None,
            hierarchy=None,
            prefixes=None,
            name=None,
            depth=0,
            flags=+mi.ParamFlags.Differentiable,
        ):
            mi.TraversalCallback.__init__(self)
            self.properties = dict() if properties is None else properties
            self.hierarchy = dict() if hierarchy is None else hierarchy
            self.prefixes = set() if prefixes is None else prefixes

            node_id = node.id()
            if name_id_override and node_id:
                for r in regexps:
                    if r(node_id):
                        name = node.id()
                        break

            if name is not None:
                ctr, name_len = 1, len(name)
                while name in self.prefixes:
                    name = f"{name[:name_len]}_{ctr}"
                    ctr += 1
                self.prefixes.add(name)

            self.name = name
            self.node = node
            self.depth = depth
            self.hierarchy[node] = (parent, depth)
            self.flags = flags

        def put_parameter(self, name, ptr, flags, cpptype=None):
            name = name if self.name is None else self.name + "." + name

            flags = self.flags | flags
            # Non-differentiable parameters shouldn't be flagged as discontinuous
            if (flags & mi.ParamFlags.NonDifferentiable) != 0:
                flags = flags & ~mi.ParamFlags.Discontinuous

            self.properties[name] = (ptr, cpptype, self.node, self.flags | flags)

        def put_object(self, name, node, flags):
            if node is None or node in self.hierarchy:
                return

            cb = SceneTraversal(
                node=node,
                parent=self.node,
                properties=self.properties,
                hierarchy=self.hierarchy,
                prefixes=self.prefixes,
                name=name if self.name is None else f"{self.name}.{name}",
                depth=self.depth + 1,
                flags=self.flags | flags,
            )
            node.traverse(cb)

    cb = SceneTraversal(obj)
    obj.traverse(cb)

    return mi.SceneParameters(cb.properties, cb.hierarchy)


def mi_render(
    mi_scene: "mitsuba.Scene",
    mi_params: Optional["mitsuba.SceneParameters"],
    kpmap: KernelSceneParameterMap,
    ctxs: list[KernelContext],
    sensors: None | int | list[int] = None,
    spp: int = 0,
    seed_state: SeedState | None = None,
) -> dict[Any, mi.Bitmap]:
    """
    Render a Mitsuba scene multiple times given specified contexts and sensor
    indices.

    Parameters
    ----------
    mi_scene : mitsuba.Scene
        Mitsuba scene to render.

    mi_params : mitsuba.SceneParameters
        Mitsuba scene parameter map associated to ``mi_scene``.

    kpmap : .KernelSceneParameterMap
        Scene parameter update map template that will generate updates to
        ``mi_params`` during a scene parameter loop.

    ctxs : list of .KernelContext
        List of contexts used to generate the parameter update table at each
        iteration.

    sensors : int or list of int, optional
        Sensor indices to render. If ``None`` (default), all sensors are
        rendered in a sequence.

    spp : int, optional, default: 0
        Number of samples per pixel. If set to 0 (default), the value set in the
        original scene definition takes precedence.

    seed_state : .SeedState, optional
        Seed state used to generate seeds to initialize Mitsuba's RNG at
        each run. If unset, Eradiate's root seed state is used.

    Returns
    -------
    dict
        A nested dictionary mapping context and sensor indices to rendered
        bitmaps.

    Notes
    -----
    This function wraps sequential calls to  :func:`mitsuba.render`.
    """

    if seed_state is None:
        logger.debug("Using default RNG seed generator")
        seed_state = root_seed_state

    results = {}

    # Loop on contexts
    with tqdm(
        initial=0,
        total=len(ctxs),
        unit_scale=1.0,
        leave=True,
        bar_format="{desc}{n:g}/{total:g}|{bar}| {elapsed}, ETA={remaining}",
        disable=(config.settings.progress < config.ProgressLevel.SPECTRAL_LOOP)
        or len(ctxs) <= 1,
    ) as pbar:
        for ctx in ctxs:
            pbar.set_description(
                f"Eradiate [{ctx.index_formatted}]",
                refresh=True,
            )

            logger.debug("Updating Mitsuba scene parameters")
            mi_params.update(kpmap.render(ctx))

            if sensors is None:
                mi_sensors = [
                    (i, sensor) for i, sensor in enumerate(mi_scene.sensors())
                ]

            else:
                if isinstance(sensors, int):
                    sensors = [sensors]
                mi_sensors = [(i, mi_scene.sensors()[i]) for i in sensors]

            # Loop on sensors
            for i_sensor, mi_sensor in mi_sensors:
                # Render sensor
                seed = int(seed_state.next().squeeze())
                logger.debug(
                    'Running Mitsuba for sensor "%s" with seed value %s',
                    mi_sensor.id(),
                    seed,
                )
                mi.render(mi_scene, sensor=i_sensor, seed=seed, spp=spp)

                # Store result in a new Bitmap object
                siah = ctx.si.as_hashable
                if siah not in results:
                    results[siah] = {}

                results[siah][mi_sensor.id()] = mi.Bitmap(mi_sensor.film().bitmap())

            pbar.update()

    return results
