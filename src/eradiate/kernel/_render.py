from __future__ import annotations

import logging
from typing import Any, Optional

import drjit as dr
import mitsuba as mi
from mitsuba.python.util import SceneParameters as _MitsubaSceneParameters
from tqdm.auto import tqdm

from . import KernelSceneParameterMap
from .. import config
from ..contexts import KernelContext
from ..rng import SeedState, root_seed_state

logger = logging.getLogger(__name__)


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
            aliases=None,
        ):
            mi.TraversalCallback.__init__(self)
            self.properties = dict() if properties is None else properties
            self.hierarchy = dict() if hierarchy is None else hierarchy
            self.prefixes = set() if prefixes is None else prefixes
            self.aliases = dict() if aliases is None else aliases

            node_id = node.id()
            if name_id_override and node_id:
                for r in regexps:
                    if r(node_id):
                        if node_id != name:
                            self.aliases[node_id] = name
                        name = node_id
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
                aliases=self.aliases,
            )
            node.traverse(cb)

    cb = SceneTraversal(obj)
    obj.traverse(cb)

    return mi.SceneParameters(cb.properties, cb.hierarchy, cb.aliases)


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
