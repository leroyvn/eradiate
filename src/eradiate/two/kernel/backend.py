from __future__ import annotations

import xarray as xr

from ..backend import Backend
from ..core.experiment import Experiment


class MitsubaBackend(Backend):
    _name: str = "mitsuba"

    def validate(self, exp: Experiment) -> None:
        raise NotImplementedError

    def process(self, exp: Experiment, measurement: None | int | str = None) -> None:
        raise NotImplementedError

    def postprocess(
        self, exp: Experiment, measurement: None | int | str = None
    ) -> xr.DataTree:
        raise NotImplementedError
