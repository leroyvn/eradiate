from __future__ import annotations

import logging
import typing as t

import attrs
import mitsuba as mi
from tqdm.auto import tqdm

from ._kernel_dict import KernelDictTemplate, UpdateMapTemplate
from ._traverse import SceneParameters, mi_traverse
from .._config import ProgressLevel, config
from ..attrs import documented, parse_docs
from ..contexts import KernelContext
from ..rng import SeedState, root_seed_state

logger = logging.getLogger(__name__)


@parse_docs
@attrs.define
class MitsubaObject:
    """
    This container aggregates a Mitsuba object, its associated parameters and a
    set of updaters that can be used to modify the scene parameters.

    See Also
    --------
    :func:`mi_traverse`
    """

    obj: "mitsuba.Object" = documented(
        attrs.field(repr=lambda x: f"{x.class_().name()}[...]"),
        doc="Mitsuba object.",
        type="mitsuba.Object",
    )

    umap_template: UpdateMapTemplate | None = documented(
        attrs.field(
            default=None,
            repr=lambda x: "UpdateMapTemplate[...]"
            if isinstance(x, UpdateMapTemplate)
            else str(x),
        ),
        doc="An update map template, which can be rendered and used to update "
        "Mitsuba scene parameters depending on context information.",
        type=".UpdateMapTemplate",
        init_type=".UpdateMapTemplate, optional",
        default="None",
    )

    _parameters: SceneParameters | None = documented(
        attrs.field(default=None),
        doc="Mitsuba scene parameter map.",
        type=".SceneParameters or None",
        init_type=".SceneParameters, optional",
        default="None",
    )

    def __attrs_post_init__(self):
        self.update()

    def update(self) -> None:
        """
        Update internal state for consistency.
        """
        # Collect Mitsuba object parameters
        if self._parameters is None:
            self._parameters = mi_traverse(self.obj)

        # Reduce the size of the scene parameter table by only keeping elements
        # whose keys are listed in the parameter update map template
        if self.umap_template is not None:
            self.parameters.keep(list(self.umap_template.keys()))

        # Check if the update map template key set is a subset of the parameter
        # table key set
        diff = set(self.umap_template.keys()) - (
            set(self.parameters.keys()) | set(self.parameters.aliases.keys())
        )
        if diff:
            raise RuntimeError(
                "Update map template contains parameters which could not be found "
                f"in parameter table: {diff}"
            )

    @property
    def parameters(self) -> SceneParameters | None:
        """
        SceneParameters: Mitsuba object parameter map.
        """
        return self._parameters

    @classmethod
    def from_kdict_template(
        cls,
        kdict_template: KernelDictTemplate,
        umap_template: UpdateMapTemplate,
        ctx: KernelContext | None = None,
    ) -> MitsubaObject:
        """
        Instantiate a Mitsuba object defined as a kernel dictionary template.

        Parameters
        ----------
        kdict_template : .KernelDictTemplate
            Kernel dictionary template.

        umap_template : .UpdateMapTemplate
            Parameter update map template.

        ctx : .KernelContext, optional
            Kernel context used to initialize the created object. If unset, a
            default kernel context is used.
        """
        if not isinstance(kdict_template, KernelDictTemplate):
            kdict_template = KernelDictTemplate(kdict_template)
        kdict = kdict_template.render(ctx if ctx is not None else KernelContext())
        mi_obj = mi.load_dict(kdict)
        result = cls(mi_obj, umap_template)

        if ctx:
            result.update_parameters(ctx)

        return result

    def update_parameters(self, ctx: KernelContext) -> None:
        """
        Update object parameters using the specified kernel context.

        Parameters
        ----------
        ctx : .KernelContext
            Kernel context used to generate the applied parameter update map.
        """
        params = self.umap_template.render(ctx)
        self.parameters.update(params)
        self.parameters.update()


# ------------------------------------------------------------------------------
#                             Mitsuba scene render
# ------------------------------------------------------------------------------


def mi_render(
    mi_scene: MitsubaObject,
    ctxs: list[KernelContext],
    sensors: None | int | list[int] = None,
    spp: int = 0,
    seed_state: SeedState | None = None,
) -> dict[t.Any, "mitsuba.Bitmap"]:
    """
    Render a Mitsuba scene multiple times given specified contexts and sensor
    indices.

    Parameters
    ----------
    mi_scene : .MitsubaObject
        Mitsuba scene to render.

    ctxs : list of .KernelContext
        List of contexts used to generate the parameter update table at each
        iteration.

    sensors : int or list of int, optional
        Sensor indices to render. If ``None`` (default), all sensors are
        rendered.

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
        disable=(config.progress < ProgressLevel.SPECTRAL_LOOP) or len(ctxs) <= 1,
    ) as pbar:
        for ctx in ctxs:
            pbar.set_description(
                f"Eradiate [{ctx.index_formatted}]",
                refresh=True,
            )

            logger.debug("Updating Mitsuba scene parameters")
            mi_scene.update_parameters(ctx)

            if sensors is None:
                mi_sensors = [
                    (i, sensor) for i, sensor in enumerate(mi_scene.obj.sensors())
                ]

            else:
                if isinstance(sensors, int):
                    sensors = [sensors]
                mi_sensors = [(i, mi_scene.obj.sensors()[i]) for i in sensors]

            # Loop on sensors
            for i_sensor, mi_sensor in mi_sensors:
                # Render sensor
                seed = int(seed_state.next())
                logger.debug(
                    'Running Mitsuba for sensor "%s" with seed value %s',
                    mi_sensor.id(),
                    seed,
                )
                mi.render(mi_scene.obj, sensor=i_sensor, seed=seed, spp=spp)

                # Store result in a new Bitmap object
                siah = ctx.si.as_hashable
                if siah not in results:
                    results[siah] = {}

                results[siah][mi_sensor.id()] = mi.Bitmap(mi_sensor.film().bitmap())

            pbar.update()

    return results
