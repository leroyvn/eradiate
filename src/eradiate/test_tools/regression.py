from __future__ import annotations

import functools
import os
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import attrs
import colorcet as cc
import matplotlib.pyplot as plt
import numpy as np
import scipy.stats as spstats
import xarray as xr
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from matplotlib.lines import Line2D
from numpy.typing import ArrayLike

from .report import ReportLogger, figure_to_html, report_logger
from ..attrs import define, documented
from ..typing import PathLike
from ..util.misc import summary_repr

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure


class RegressionTestFailure(Exception):
    """
    Raised by :meth:`.RegressionTest.run` when a test does not pass, i.e. when
    the comparison against the reference fails or when no reference is
    available.
    
    Distinct from the :class:`ValueError`\\ s the framework raises
    for malformed data, so that a caller can tell a failed comparison from a
    broken one.
    """


def sidak_family_p_value(p_min: float, n: int) -> float:
    """
    Aggregate ``n`` paired p-values into a single family-wise p-value using the
    Šidák correction, *i.e.* the probability of observing a minimum p-value at
    least as extreme as ``p_min`` among ``n`` independent comparisons.

    Parameters
    ----------
    p_min : float
        Smallest of the paired p-values.

    n : int
        Number of paired comparisons.

    Returns
    -------
    float
        Family-wise p-value, directly comparable with the test threshold: it
        exceeds the threshold if and only if every paired p-value exceeds the
        Šidák-corrected per-comparison level
        ``1 - (1 - threshold) ** (1 / n)``.

    Notes
    -----
    Computed as ``-expm1(n * log1p(-p_min))`` rather than
    ``1 - (1 - p_min) ** n`` to remain accurate for small ``p_min``.
    """
    if p_min >= 1.0:  # log1p(-1) is -inf: the limit is 1, computed without warning
        return 1.0

    return float(-np.expm1(n * np.log1p(-p_min)))


def vza_dim(ds: xr.Dataset) -> str:
    """
    Name of the dimension the plots use as their x axis.

    ``vza`` is usually a non-dimension coordinate: a measure yields
    ``vza(x_index, y_index)`` and the angular sweep lives on ``x_index``. Only
    the datasets built by hand in the unit tests have a ``vza`` dimension.

    Parameters
    ----------
    ds : Dataset
        Dataset to inspect. Must have a ``vza`` coordinate.

    Returns
    -------
    str
        The single non-degenerate dimension of the ``vza`` coordinate, or its
        first dimension if all of them are of length 1.
    """
    vza = ds["vza"]
    sweep = [d for d in vza.dims if vza.sizes[d] > 1]
    return str(sweep[0] if sweep else vza.dims[0])


def hue_from_extra_dims(
    da: xr.DataArray, x_dim: str
) -> tuple[np.ndarray, np.ndarray | None, str | None]:
    """
    Flatten every dimension of ``da`` except `x_dim` into a single one, meant to
    be mapped to colour by :func:`regression_test_plots`.

    Parameters
    ----------
    da : DataArray
        Data to flatten.

    x_dim : str
        Dimension held out, plotted along the x axis. See :func:`vza_dim`.

    Returns
    -------
    values : ndarray
        ``(n_x,)`` if `x_dim` is the only dimension left after squeezing,
        ``(n_hue, n_x)`` otherwise.

    hue : ndarray or None
        Coordinate values of the flattened dimension, ``None`` if there is none.

    hue_label : str or None
        Name of the flattened dimension, ``None`` if there is none.
    """
    # Squeeze length-1 dimensions, except `x_dim`
    # which always has to be preserved so it can be plotted
    da = da.squeeze([d for d in da.dims if d != x_dim and da.sizes[d] == 1], drop=True)

    extra = [str(d) for d in da.dims if d != x_dim]
    if not extra:
        return da.values, None, None

    da = da.transpose(*extra, x_dim)
    values = da.values.reshape(-1, da.sizes[x_dim])

    if len(extra) == 1 and extra[0] in da.coords:
        return values, np.asarray(da[extra[0]].values, dtype=float), extra[0]

    # No coordinate, or several dimensions stacked: the hue is an ordinal index
    # (fallback) 
    return values, np.arange(values.shape[0], dtype=float), " x ".join(extra)


def annotate_panel(ax: Axes, text: str) -> None:
    """
    Label a panel with an annotation placed at the top centre of its data area
    (used to replace a title, saving vertical space).

    Parameters
    ----------
    ax : Axes
        Axes to annotate.

    text : str
        Annotation text.
    """

    ax.annotate(
        text,
        xy=(0.5, 1.0),
        xycoords="axes fraction",
        xytext=(0.0, -6.0),
        textcoords="offset points",
        horizontalalignment="center",
        verticalalignment="top",
    )


def regression_test_plots(
    ref: ArrayLike,
    result: ArrayLike,
    vza: ArrayLike,
    metric: tuple[str, float],
    ref_var: ArrayLike | None = None,
    result_var: ArrayLike | None = None,
    xlabel: str | None = None,
    ylabel: str | None = None,
    hue: ArrayLike | None = None,
    hue_label: str | None = None,
    diagnostic: Callable[[Axes], None] | None = None,
) -> tuple[Figure, list[list[Axes]]]:
    """
    Create regression test report plots. Plot errorbars if both ref_var and
    result_var are set.

    Parameters
    ----------
    ref : array-like
        Variable values for the reference data. Shape ``(n_vza,)``, or
        ``(n_hue, n_vza)`` if `hue` is set.

    result : array-like
        Variable values for the simulation result. Same shape as `ref`.

    vza : array-like
        VZA values for plotting

    metric : tuple
        A tuple of the form (metric name, value) to be added to the plots.

    ref_var : array-like, optional
        Variable variance for the reference data. Ignored if `hue` is set.

    result_var : array-like, optional
        Variable variance for the simulation result. Ignored if `hue` is set.

    xlabel, ylabel : str or None
        Labels applied to the x and y axes of the plot.

    hue : array-like, optional
        Coordinate values of an extra dimension, mapped to colour: one line per
        value on each data panel, reference dashed and result solid.

    hue_label : str or None
        Label of the `hue` colour bar.

    diagnostic : callable, optional
        Callback drawing a test-specific diagnostic chart on the fourth panel,
        called as ``diagnostic(ax)``. If unset, that panel is left blank.

    Returns
    -------
    figure: Figure
        Matplotlib Figure containing the report charts

    axes: list
        2×2 array of Axes included in the report Figure
    """
    ref = np.atleast_2d(ref)
    result = np.atleast_2d(result)

    if hue is None:
        # Single slice, default colour cycle, solid lines: reference and result
        # are told apart by colour
        styles = [{}]
        ref_style = {}
    else:
        # Extra dimension is an ordered physical coordinate, hence a
        # sequential colormap. Reference and result share a colour and are told
        # apart by linestyle, so they stay comparable slice by slice.
        hue = np.asarray(hue, dtype=float)
        norm = Normalize(vmin=hue.min(), vmax=hue.max())
        cmap = cc.cm["isoluminant_cgo_70_c39"]
        styles = [{"color": cmap(norm(value))} for value in hue]
        ref_style = {"linestyle": "--"}
        # N overlaid errorbar families are unreadable
        ref_var = result_var = None

    fig, axes = plt.subplots(2, 2, figsize=(8, 6), layout="constrained")

    ax = axes[0, 0]
    ax.set_ylabel(ylabel)
    for i, style in enumerate(styles):
        label = "reference" if i == 0 else None
        if ref_var is None:
            ax.plot(vza, ref[i], label=label, **style, **ref_style)
        else:
            ax.errorbar(vza, ref[i], yerr=np.sqrt(ref_var), label=label)

    for i, style in enumerate(styles):
        label = "result" if i == 0 else None
        if result_var is None:
            ax.plot(vza, result[i], label=label, **style)
        else:
            ax.errorbar(vza, result[i], yerr=np.sqrt(result_var), label=label)

    handles, labels = ax.get_legend_handles_labels()
    if hue is not None:
        # Rewrite legend to use black line color when hue coordinate is present
        handles = [
            Line2D([], [], color="black", linestyle=handle.get_linestyle())
            for handle in handles
        ]
    ax.legend(handles=handles, labels=labels)

    ax = axes[1, 0]
    for i, style in enumerate(styles):
        ax.plot(vza, result[i] - ref[i], **style)
    annotate_panel(ax, "absolute difference")

    ax = axes[1, 1]
    for i, style in enumerate(styles):
        ax.plot(vza, (result[i] - ref[i]) / ref[i], **style)
    annotate_panel(ax, "relative difference")

    # The fourth panel hosts the diagnostic chart, if the test provides one
    ax = axes[0, 1]
    if diagnostic is None:
        ax.set_axis_off()
    else:
        diagnostic(ax)
    ax.set_title(
        f'Metric "{metric[0]}" is not available'
        if metric[1] is None
        else f"{metric[0]}: {metric[1]:.4}",
    )

    # Colorbar on top of the data panel, in place of its title
    if hue is not None:
        cbar = fig.colorbar(
            ScalarMappable(norm=norm, cmap=cmap),
            ax=axes[0][0],
            label=hue_label,
            location="top",
            pad=-0.05,
        )
        # Colorbar is continuous, data is not: mark sampled coordinates
        cbar.ax.vlines(
            hue, *cbar.ax.get_ylim(), colors="white", linestyles="--", linewidths=0.8
        )

    for i, j, _xlabel in [(0, 0, xlabel), (1, 0, xlabel), (1, 1, xlabel)]:
        ax = axes[i][j]
        if _xlabel is not None:
            ax.set_xlabel(_xlabel)

    return fig, axes


def reference_converter(value: PathLike | xr.Dataset | None) -> xr.Dataset | None:
    """
    A converter for handling the reference data attribute.

    Parameters
    ----------
    value : path-like or Dataset or None
    
    Returns
    -------
    xr.Dataset or None
        The reference dataset.

    Raises
    ------
    ValueError
        If the reference data is not a valid dataset.

    Notes
    -----
    The ``value`` argument is processed as follows:

    * ``None`` and datasets are passed through.
    * If ``value`` is a path, resolve it with the path resolver. If the path
      points to a non-existing location, return ``None``. Otherwise, try to load
      it as a Dataset.

    Anything else raises a :class:`ValueError`.
    """
    if value is None:
        return value

    if isinstance(value, xr.Dataset):
        return value

    if isinstance(value, (str, os.PathLike, bytes)):
        report_logger.info(f'Looking up "{str(value)}" on disk')
        from .. import fresolver

        fname = fresolver.resolve(value)
        report_logger.info(f"Resolved path: {fname}")

        if not fname.exists():
            return None

        return xr.load_dataset(fname)

    raise ValueError(
        "Reference must be provided as a Dataset, a file path or None. "
        f"Got a {type(value).__name__}"
    )


@define
class RegressionTest(ABC):
    """
    Common interface for tests based on the comparison of a result array against
    reference values.
    """

    # Name used for the reference metric. Must be set be subclasses.
    METRIC_NAME: ClassVar[str | None] = None

    name: str = documented(
        attrs.field(validator=attrs.validators.instance_of(str)),
        doc="Test case name.",
        type="str",
        init_type="str",
    )

    value: xr.Dataset = documented(
        attrs.field(
            validator=attrs.validators.instance_of(xr.Dataset),
            repr=summary_repr,
        ),
        doc="Simulation result. Must be specified as a dataset.",
        type=":class:`xarray.Dataset`",
        init_type=":class:`xarray.Dataset`",
    )

    reference: xr.Dataset | None = documented(
        attrs.field(
            default=None,
            converter=reference_converter,
            validator=attrs.validators.optional(
                attrs.validators.instance_of(xr.Dataset)
            ),
        ),
        doc="Reference data. Can be specified as an xarray dataset, a path to a "
        "NetCDF file or a path to a resource.",
        type=":class:`xarray.Dataset` or None",
        init_type=":class:`xarray.Dataset` or path-like, optional",
        default="None",
    )

    variable: str = documented(
        attrs.field(kw_only=True, default="brf_srf"),
        doc="Tested variable",
        type="str",
        init_type="str",
        default="brf_srf",
    )

    threshold: float = documented(
        attrs.field(kw_only=True),
        doc="Test metric threshold",
        type="float",
        init_type="float",
    )

    archive_dir: Path = documented(
        attrs.field(kw_only=True, converter=lambda x: Path(x).resolve()),
        doc="Path to output artefact storage directory. Relative paths are "
        "interpreted with respect to the current working directory.",
        type=":class:`pathlib.Path`",
        init_type="path-like",
    )

    plot: bool = documented(
        attrs.field(kw_only=True, converter=bool),
        doc="Activate result plotting",
        type="bool",
        init_type="bool",
    )

    update_references: bool = documented(
        attrs.field(kw_only=True, default=False, converter=bool),
        doc="If ``True``, a missing reference is bootstrapped: the current "
        "result is archived as a reference candidate and the test fails. If "
        "``False``, a missing reference is a setup error and raises a "
        ":class:`ValueError`, so that a typo in the reference path cannot be "
        "mistaken for a deliberate reference regeneration. The test suite wires "
        "this to the ``--update-references`` command-line flag.",
        type="bool",
        init_type="bool",
        default="False",
    )

    logger: ReportLogger = documented(
        attrs.field(kw_only=True, default=report_logger, repr=False, eq=False),
        doc="Logger used to send messages and HTML fragments to the test report. "
        "Note that the ``reference`` field converter always reports through "
        "the default logger, since it runs before the instance exists.",
        type=":class:`.ReportLogger`",
        init_type=":class:`.ReportLogger`, optional",
        default=":data:`.report_logger`",
    )

    #: Data produced by :meth:`_evaluate` and consumed by
    #: :meth:`_plot_diagnostic`, which draws it on the comparison chart. Empty
    #: when the test has no diagnostic, or when evaluation did not complete.
    diagnostic_data: dict = attrs.field(factory=dict, init=False, repr=False, eq=False)

    def __attrs_pre_init__(self):
        if self.METRIC_NAME is None:
            raise TypeError(f"Unsupported test type {type(self).__name__}")

    def run(self, raise_on_failure: bool = True) -> bool:
        """
        Run the test.
        
        This method controls the execution steps of the regression test:

        * handle missing reference data; 
        * catch errors during test evaluation;
        * create the appropriate plots and data archives.

        Parameters
        ----------
        raise_on_failure : bool, default: True
            If ``True``, raise a :class:`.RegressionTestFailure` carrying the
            metric value and the threshold when the test does not pass. This
            makes the numbers visible in a plain ``pytest`` failure report.
            Set to ``False`` to inspect the verdict programmatically.

        Returns
        -------
        bool
            Result of the test criterion comparison.

        Raises
        ------
        RegressionTestFailure
            If the test does not pass and ``raise_on_failure`` is ``True``.

        ValueError
            If no reference could be resolved and ``update_references`` is
            ``False``.
        """

        self.logger.info(f"Regression test {self.name} results:")

        fname = self.name
        ext = ".nc"
        archive_dir = self.archive_dir

        fname_reference = archive_dir / f"{fname}-ref{ext}"
        fname_result = archive_dir / f"{fname}-result{ext}"

        # No reference resolved. Unless reference creation was explicitly
        # requested, this is a broken setup (most likely a typo in the
        # reference path) not a test verdict.
        if self.reference is None and not self.update_references:
            raise ValueError(
                f"Regression test '{self.name}' resolved no reference data. If "
                "the reference is genuinely missing and should be created, "
                "re-run with the --update-references flag; otherwise check the "
                "reference path."
            )

        # If no valid reference is found, store the results as new ref and fail
        # the test
        if self.reference is None:
            self.logger.info(
                "No reference data found. Storing test results to "
                f"{fname_reference}. This can be the new reference.",
            )
            self._archive(self.value, fname_reference)
            self._plot(metric_value=None, noref=True)

            if raise_on_failure:
                # The candidate reference is archived above, so raising here
                # loses nothing: it only keeps a bootstrap from reading as a
                # pass now that the call sites no longer assert.
                raise RegressionTestFailure(
                    f"Regression test '{self.name}' has no reference data. "
                    f"The current result was stored to {fname_reference} and "
                    "can be promoted to the new reference."
                )

            return False

        # else (we have a reference value), evaluate the test metric
        try:
            passed, metric_value = self._evaluate()
            msg = "\n".join(
                [
                    "Test passed" if passed else "Test did not pass",
                    f"Metric value: {self.METRIC_NAME} = {metric_value}",
                    f"Metric threshold: {self.threshold}",
                    f"Variable: {self.variable}",
                ]
            )
            self.logger.info(msg)

        except Exception as e:
            self.logger.info("An exception occurred during test evaluation!")
            # Never let a plotting error replace
            # the diagnostic exception
            try:
                self._plot(noref=False, metric_value=None)
            except Exception as plot_error:
                self.logger.info(
                    f"Could not plot the failed evaluation: {plot_error}",
                )
            raise e

        # We got a metric: report the results in the archive directory
        self.logger.info(f"Saving current output dataset to {fname_result}")
        self._archive(self.value, fname_result)
        self.logger.info(f"Saving reference dataset locally to {fname_reference}")
        self._archive(self.reference, fname_reference)
        self._plot(noref=False, metric_value=metric_value)

        if raise_on_failure and not passed:
            raise RegressionTestFailure(
                f"Regression test '{self.name}' did not pass: "
                f"{self.METRIC_NAME} = {metric_value}, "
                f"threshold = {self.threshold}, variable = '{self.variable}'"
            )

        return passed

    @abstractmethod
    def _evaluate(self) -> tuple[bool, float]:
        """
        Evaluate the test results and compare them to the reference
        based on the criterion defined in the specialized class.

        Implementations that provide a diagnostic chart store the data it needs
        in the ``diagnostic_data`` field; :meth:`_plot_ref` then plots it on the
        comparison chart.

        Returns
        -------
        passed : bool
            ``True`` iff the test passed.

        metric_value : float
            The value of the test metric.
        """
        pass

    def _archive(self, dataset: xr.Dataset, fname_output: PathLike) -> None:
        """
        Create an archive file for test result and reference storage.
        """
        os.makedirs(os.path.dirname(fname_output), exist_ok=True)
        dataset.to_netcdf(fname_output)

    def _plot(self, metric_value: float | None, noref: bool) -> None:
        """
        Plot test results. If the ``reference only`` parameter is set, create
        only a simple plot visualizing the new reference data. Otherwise, create
        the more complex comparison plots for the regression test.

        Parameters
        ----------
        metric_value : float or None
            The numerical value of the test metric.

        noref : bool
            If ``True``, create only a simple visualization of the computed
            data.
        """
        # TODO: check this docstring

        if not self.plot:
            return

        if noref:
            fig, _ = self._plot_noref()
        else:
            fig, _ = self._plot_ref(metric_value)

        html_svg = figure_to_html(fig)
        self.logger.html(html_svg)
        self._save_figure(fig, f"{self.name}.png")
        plt.close(fig)

    def _save_figure(self, fig: Figure, filename: str) -> None:
        """
        Save a Matplotlib Figure to the archive directory and announce its location
        on the console.

        Parameters
        ----------
        fig : Figure
            Figure to save.

        filename : str
            Name of the PNG file, relative to the archive directory.

        Notes
        -----
        The console message is suppressed when a report backend is active: the
        plot is then embedded in the report itself, which makes the PNG copy a
        secondary artefact not worth announcing.
        """
        fname_plot = self.archive_dir / filename
        fname_plot.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(fname_plot, bbox_inches="tight")

        if not self.logger.reporting:
            print(f"Saved plot to {fname_plot}")

    def _plot_noref(self):
        """
        Plot when no reference data is available.
        """
        # TODO: Why different plotting logic compared to with ref case? In particular, why use different line colouring?

        if not self.plot:
            return

        vza = np.squeeze(self.value["vza"].values)
        val, _, _ = hue_from_extra_dims(self.value[self.variable], vza_dim(self.value))

        fig, ax = plt.subplots(1, 1, figsize=(8, 6))
        # One line per slice of the extra dimensions, if any. The colour cycle
        # is enough here: this plot has no reference to compare against.
        ax.plot(vza, np.atleast_2d(val).T)
        ax.set_xlabel("VZA [deg]")
        ax.set_ylabel(self.variable)
        ax.set_title("Simulation result, can be used as new reference")

        return fig, ax

    def _plot_ref(self, metric_value: float | None = None):
        """
        Plot with reference and test data displayed together.
        """

        if not self.plot:
            return

        vza = np.squeeze(self.value["vza"].values)
        val, hue, hue_label = hue_from_extra_dims(
            self.value[self.variable], vza_dim(self.value)
        )
        ref, _, _ = hue_from_extra_dims(
            self.reference[self.variable], vza_dim(self.reference)
        )

        return regression_test_plots(
            ref,
            val,
            vza,
            (self.METRIC_NAME, metric_value),
            xlabel="VZA [deg]",
            ylabel=self.variable,
            hue=hue,
            hue_label=hue_label,
            diagnostic=self._diagnostic_plotter(),
        )

    def _diagnostic_plotter(self) -> Callable[[Axes], None] | None:
        """
        Bind :meth:`_plot_diagnostic` to the data collected by :meth:`_evaluate`,
        ready to be drawn on a panel of the comparison chart. Returns ``None``
        when there is no diagnostic to draw.
        """
        # TODO: Move below actual plotting function
        if not self.diagnostic_data:
            return None
        return functools.partial(self._plot_diagnostic, **self.diagnostic_data)

    def _plot_diagnostic(self, ax: Axes, **diagnostic_info) -> None:
        """
        Draw more technical information about the test metrics and decision
        process on a panel of the comparison chart. The diagnostic plot can help
        the user debug a failing test, or to assess the test power and
        significance.

        Parameters:
        -----------
        ax : Axes
            Axes to draw on.

        **diagnostic_info : dict
            Variadic keyword arguments for the subclasses implementation, taken
            from the ``diagnostic_data`` field.
        """

        raise NotImplementedError(
            f"{type(self)} does not implement a diagnostic plot method"
        )


@define
class RMSETest(RegressionTest):
    """
    Root mean square error test.

    The test passes iff the computed root mean squared error (RMSE) of the result data again the reference is lower or equal to the given threshold.
    """

    METRIC_NAME = "rmse"

    def _evaluate(self) -> tuple[bool, float]:
        value_np = self.value[self.variable].values
        ref_np = self.reference[self.variable].values
        if np.shape(value_np) != np.shape(ref_np):
            raise ValueError(
                f"Result and reference do not have the same shape! "
                f"Got: {np.shape(value_np)}, {np.shape(ref_np)}"
            )

        result_flat = np.array(value_np).flatten()
        ref_flat = np.array(ref_np).flatten()

        rmse = float(np.linalg.norm(result_flat - ref_flat) / np.sqrt(len(ref_flat)))
        return rmse <= self.threshold, rmse


@define
class ZTest(RegressionTest):
    """
    Z-Test with Šidák correction factor.

    Implement a Z-test, testing the significance of paired differences between
    a set of observations and a set of references. It considers the variance of
    both the observations and the reference, which are both Monte Carlo
    estimates: the standard error of their difference is
    :math:`\\sqrt{\\sigma^2_\\mathrm{result} + \\sigma^2_\\mathrm{reference}}`.
    The observation variance (``<variable>_var``) is mandatory; if the reference
    does not carry one, the test falls back to the observation variance alone
    and logs a warning. That fallback underestimates the standard error by up to
    a factor of :math:`\\sqrt{2}`, making the test conservative.

    Paired tests are aggregated into one p-value using a Šidák correction: the
    test passes if the null hypothesis is accepted for *every* pair at the
    corrected per-comparison level :math:`1 - (1 - \\alpha)^{1/n}`. The reported
    metric is the equivalent family-wise p-value (see
    :func:`sidak_family_p_value`), so that the test passes iff the metric
    exceeds the threshold.

    This paired Z-test requires an equal degree of freedom of the two groups.
    """
    # TODO: Review docstring

    METRIC_NAME = "Z-test family p-value"

    def _plot_diagnostic(self, ax: Axes, z=None) -> None:
        """
        Diagnostic plot for a Z-test.

        Parameters:
        -----------
        ax : Axes
            Axes to draw on.

        z : array-like
            Z-statistic for each pair of measurements
        """

        ax.grid()
        ax2 = ax.twinx()

        ax.hist(z, bins=50, label="Z values")
        ax.axvline(0.0, color="red", linestyle="--")
        ax.legend(loc="upper left", fontsize="small")

        x = np.linspace(-4.0, 4.0, 100)
        y = spstats.norm.pdf(x, 0.0, 1.0)
        ax2.plot(x, y, label="target", color="black")
        ax2.legend(loc="upper right", fontsize="small")
        ax2.set_ylim([0.0, max(y) * 1.1])

    def _evaluate(self) -> tuple[bool, float]:
        variable_var = self.variable + "_var"

        if variable_var not in self.value:
            raise ValueError(
                "The result data for this Z-test does not contain expected "
                "appropriate variance values, could not find data variable "
                f"'{variable_var}'"
            )

        ref_np = self.reference[self.variable].values.ravel()
        result_np = self.value[self.variable].values.ravel()

        var_res_np = self.value[variable_var].values.ravel()

        assert ref_np.shape == result_np.shape
        assert ref_np.shape == var_res_np.shape

        # Both datasets are Monte Carlo estimates, so the variance of their
        # difference is the sum of their variances. Some legacy references were
        # archived without their variance: fall back to the result variance
        # alone, which underestimates the standard error by up to sqrt(2) and
        # therefore makes the test conservative (more likely to fail).
        # TODO: Revisit that comment (missing ref variance might be intentional)
        if variable_var in self.reference:
            var_ref_np = self.reference[variable_var].values.ravel()
            assert ref_np.shape == var_ref_np.shape
        else:
            self.logger.warning(
                f"The reference data for this Z-test has no '{variable_var}' "
                "data variable; falling back to the result variance alone. The "
                "test is conservative in this configuration. Regenerate the "
                "reference to compare both variances."
            )
            var_ref_np = 0.0

        # Calculate Z-statistic
        z = (result_np - ref_np) / np.sqrt(var_res_np + var_ref_np)

        # Calculate p-value of the two-tailed z-test null hypothesis
        p_values = spstats.norm.sf(np.abs(z)) * 2

        alpha_0 = 1.0 - (1.0 - self.threshold) ** (1.0 / result_np.size)
        accept_null = p_values > alpha_0

        passed = bool(np.all(accept_null))
        p_family = sidak_family_p_value(min(p_values), result_np.size)

        self.diagnostic_data = {"z": z}

        self.logger.info(f"min p-value = {min(p_values)}")
        self.logger.info(f"max p-value = {max(p_values)}")
        self.logger.info(
            f"n accepted  = {np.count_nonzero(accept_null)}/{result_np.size}",
        )
        self.logger.info(f"alpha_1     = {self.threshold}")
        self.logger.info(f"alpha_0     = {alpha_0}")

        return passed, p_family

    def _plot_ref(self, metric_value: float | None = None):
        """
        Draw a comparison plot with reference and test data displayed together.
        """
        vza = np.squeeze(self.value["vza"].values)
        x_dim = vza_dim(self.value)
        result, hue, hue_label = hue_from_extra_dims(self.value[self.variable], x_dim)
        result_var, _, _ = hue_from_extra_dims(
            self.value[f"{self.variable}_var"], x_dim
        )
        ref, _, _ = hue_from_extra_dims(
            self.reference[self.variable], vza_dim(self.reference)
        )

        return regression_test_plots(
            ref,
            result,
            vza,
            (self.METRIC_NAME, metric_value),
            result_var=result_var,
            xlabel="VZA [deg]",
            ylabel=self.variable,
            hue=hue,
            hue_label=hue_label,
            diagnostic=self._diagnostic_plotter(),
        )
