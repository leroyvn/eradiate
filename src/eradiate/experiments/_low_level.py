from __future__ import annotations

import logging
from typing import Optional

import attrs
import mitsuba as mi
import numpy as np
from hamilton.driver import Driver

from eradiate import KernelContext
from eradiate.kernel._kernel_dict_new import (
    KernelDictionary,
    KernelSceneParameterMap,
    mi_render,
    mi_traverse,
)
from eradiate.rng import SeedState
from eradiate.scenes.measure import Measure

logger = logging.getLogger(__name__)


@attrs.define
class CoreExperiment:
    # Additional kernel dictionary template
    kdict: KernelDictionary = attrs.field(
        factory=KernelDictionary, converter=KernelDictionary
    )

    # Additional scene parameter update map template
    kpmap: KernelSceneParameterMap = attrs.field(
        factory=KernelSceneParameterMap, converter=KernelSceneParameterMap
    )

    # Mitsuba scene
    _mi_scene: Optional["mitsuba.Scene"] = attrs.field(default=None, repr=False)

    # Mitsuba scene parameters
    _mi_params: Optional["mitsuba.SceneParameters"] = attrs.field(
        default=None, repr=False
    )

    def kdict_base(self) -> KernelDictionary:
        return KernelDictionary({"type": "scene"})

    def kdict_full(self) -> KernelDictionary:
        # Return the user-defined kdict template merged with additional scene
        # element contributions
        kdict = self.kdict_base()
        kdict.update(self.kdict)
        return kdict

    def kpmap_base(self) -> KernelSceneParameterMap:
        return KernelSceneParameterMap()

    def kpmap_full(self) -> KernelSceneParameterMap:
        # Return the user-defined kpmap template merged with additional scene
        # element contributions
        kpmap = KernelSceneParameterMap()
        kpmap.update(self.kpmap)
        return kpmap

    @property
    def mi_scene(self):
        # Return the initialized Mitsuba scene
        if self._mi_scene is None:
            logger.info("Initializing Mitsuba scene")
            ctx = self.context_init()
            kdict = self.kdict_full().render(ctx)
            self._mi_scene = mi.load_dict(kdict)

        return self._mi_scene

    @property
    def mi_params(self):
        # Return the Mitsuba scene parameter table
        if self._mi_params is None:
            logger.info("Retrieving Mitsuba scene parameters")
            self._mi_params = mi_traverse(self._mi_scene)

        return self._mi_params

    def contexts(self) -> list[KernelContext]:
        raise NotImplementedError

    def context_init(self) -> KernelContext:
        raise NotImplementedError

    def pipeline(self, measure: Measure | int) -> Driver:
        """
        Return the post-processing pipeline for a given measure.

        Parameters
        ----------
        measure : .Measure or int
            Measure for which the pipeline is generated.

        Returns
        -------
        hamilton.driver.Driver
        """
        raise NotImplementedError

    def process(self, spp: int = 0, seed_state: SeedState | None = None) -> None:
        """
        Run simulation and collect raw results.

        Parameters
        ----------
        spp : int, optional
            Sample count. If set to 0, the value set in the original scene
            definition takes precedence.

        seed_state : .SeedState, optional
            Seed state used to generate seeds to initialize Mitsuba's RNG at
            every iteration of the parametric loop. If unset, Eradiate's
            :attr:`root seed state <.root_seed_state>` is used.
        """
        mi_scene = self.mi_scene
        mi_params = self.mi_params
        kpmap = self.kpmap_full()
        ctxs = self.contexts()

        # Run Mitsuba for each context
        logger.info("Launching simulation")
        mi_results = mi_render(
            mi_scene, mi_params, kpmap, ctxs, spp=spp, seed_state=seed_state
        )

        # Assign collected results to the appropriate measure
        sensor_to_measure: dict[str, Measure] = {
            measure.sensor_id: measure for measure in self.measures
        }

        def convert_to_y_format(img):
            img_np = np.array(img, copy=False)[:, :, [0]]
            return mi.Bitmap(img_np, mi.Bitmap.PixelFormat.Y)

        # create a mapping from bitmap names to result names
        mapping = {}
        if self.integrator.stokes:
            stokes = ["S0", "S1", "S2", "S3"]
            iquv = ["I", "Q", "U", "V"]

            if self.integrator.moment:
                stokes = ["nested." + s for s in stokes]
                stokes += ["m2_" + s for s in stokes]
                iquv += ["m2_" + s for s in iquv]

            for s, i in zip(stokes, iquv):
                mapping[s] = i

        else:
            mapping = {"<root>": "bitmap"}
            if self.integrator.moment:
                mapping["m2_nested"] = "m2"

        # gather results and info from measures
        for ctx_index, spectral_group_dict in mi_results.items():
            for sensor_id, mi_bitmap in spectral_group_dict.items():
                measure = sensor_to_measure[sensor_id]
                result_imgs = {"spp": spp if spp > 0 else measure.spp}

                splits = mi_bitmap.split()
                for split in splits:
                    if split[0] in mapping:
                        img = split[1]
                        # convert any result that has more than one channel
                        if img.pixel_format() != mi.Bitmap.PixelFormat.Y:
                            img = convert_to_y_format(img)
                        result_imgs[mapping[split[0]]] = img

                measure.mi_results[ctx_index] = result_imgs

    def postprocess(self) -> None:
        """
        Post-process raw results and store them in :attr:`results`.
        """
        raise NotImplementedError
