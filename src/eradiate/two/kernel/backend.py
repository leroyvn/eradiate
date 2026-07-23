from __future__ import annotations

import xarray as xr

from . import SceneObject
from .materials import DiffuseMaterial, Material
from .scene import Scene
from .. import core
from ..backend import Backend


def _kernel_material(material: core.BaseMaterial) -> Material:
    if isinstance(material, core.material.DiffuseMaterial):
        return DiffuseMaterial(material.reflectance)
    else:
        raise ValueError(f"unsupported material type {type(material)}")


class MitsubaBackend(Backend):
    _name: str = "mitsuba"
    _scene: Scene

    def validate(self, exp: Experiment) -> None:
        raise NotImplementedError

    def _setup_global(self, exp: Experiment) -> None:
        """Global scene setup, independent of spectral loop iterations."""
        # raise NotImplementedError

        self._scene = Scene()

        # Add objects to the scene
        # -- Add materials
        if exp.surface is not None:
            self._scene.materials["mat_surface"] = _kernel_material(exp.surface.bsdf)

        # -- Add surfaces
        if exp.surface is not None:
            self._scene.shapes["shape_surface"] = SceneObject(
                {"type": "rectangle", "bsdf": self._scene.materials["mat_surface"]()}
            )

        # -- Add media
        # TODO

        # -- Add illuminants
        # TODO

        # Initialize scene
        self._scene.init()

    def _setup_spectral(self, exp: Experiment) -> None:
        """
        Spectrally dependent scene updates, executed at each spectral loop
        iteration.
        """
        raise NotImplementedError

    def process(self, exp: Experiment, measurement: None | int | str = None) -> None:
        raise NotImplementedError

    def postprocess(
        self, exp: Experiment, measurement: None | int | str = None
    ) -> xr.DataTree:
        raise NotImplementedError
