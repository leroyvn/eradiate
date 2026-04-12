from __future__ import annotations

from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

from .core.experiment import Experiment

if TYPE_CHECKING:
    import xarray as xr


class Backend(metaclass=ABCMeta):
    """Abstract interface for all Eradiate backends."""

    _name: str
    _results: dict

    @abstractmethod
    def validate(self, exp: Experiment):
        """
        Check internal state consistency and compatibility with the passed
        Experiment configuration. The default implementation raises an exception.

        Parameters
        ----------
        exp : Experiment
            Processed experiment configuration.

        Raises
        ------
        RuntimeError
            If validation fails.
        """

    @abstractmethod
    def process(self, exp: Experiment, measurement: None | int | str = None):
        """
        Run the processing step for a given Experiment configuration.

        This method executes the processing step of the backend of a given
        Experiment configuration and measurement identifier. The processing step
        consists in successive iterations of the spectral loop, for which a
        radiative transfer simulation run is performed. Results are stored in
        the :attr:`._results` private attribute of the instance.

        Parameters
        ----------
        exp : Experiment
            Processed experiment configuration.

        measurement : int or str, optional
            Index or string ID of the processed measurement. If unset, defaults to
            the first measurement defined in the experiment configuration.
        """

    @abstractmethod
    def postprocess(
        self, exp: Experiment, measurement: None | int | str = None
    ) -> xr.DataTree:
        """
        Run the postprocessing step for a given Experiment configuration.

        This method executes the postprocessing step of the backend of a given
        Experiment configuration and measurement identifier. It assumes that the
        :meth:`.process` method was successfully called before and uses the
        stored results.

        Parameters
        ----------
        exp : Experiment
            Processed experiment configuration.

        measurement : int or str, optional
            Index or string ID of the processed measurement. If unset, defaults to
            the first measurement defined in the experiment configuration.

        Returns
        -------
        DataTree
            Post-processed results.
        """

    def run(self, exp: Experiment, measurement: None | int | str = None) -> xr.DataTree:
        self.validate(exp)
        self.process(exp, measurement=measurement)
        return self.postprocess(exp, measurement=measurement)
