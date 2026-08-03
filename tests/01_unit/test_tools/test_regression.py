import matplotlib.pyplot as plt
import numpy as np
import pytest
import scipy.stats as spstats
import xarray as xr

from eradiate.test_tools.regression import (
    RegressionTestFailure,
    RMSETest,
    ZTest,
)
from eradiate.test_tools.report import ReportLogger


def make_offset_datasets(offsets):
    """
    Build a (value, reference) pair over a ``vza`` dimension whose elementwise
    difference is exactly ``offsets``. Decoy data variables are added to both
    datasets to catch a test reading the wrong variable.
    """
    offsets = np.asarray(offsets, dtype=float)
    vza = np.linspace(0.0, 60.0, offsets.size)
    ref_da = xr.DataArray(np.ones(offsets.size), dims="vza", coords={"vza": vza})
    value_da = ref_da + offsets

    ref = xr.Dataset({"brf": ref_da, "stuff": ref_da * 0.2, "wrong": ref_da * 321.0})
    value = xr.Dataset(
        {"brf": value_da, "stuff": value_da * 0.1, "wrong": value_da * 123.0}
    )
    return value, ref


class TestConstruction:
    """
    These tests check constructor argument handling and reference resolution.
    """

    @pytest.mark.parametrize(
        "cls, name",
        [
            (RMSETest, "rmse"),
            (ZTest, "z-test"),
        ],
        ids=["rmse", "z-test"],
    )
    def test_instantiate(self, cls, name):
        # instantiate the test with reasonable defaults
        assert cls(
            name=name,
            archive_dir="tests/",
            value=xr.Dataset(),
            reference=xr.Dataset(),
            threshold=0.05,
            plot=False,
        )

    def test_instantiate_fail(self):
        # assert all arguments except reference are needed
        # only one subclass of RegressionTest (RMSETest) is tested
        with pytest.raises(TypeError):
            assert RMSETest(
                archive_dir="tests/",
                value=xr.Dataset(),
                reference=xr.Dataset(),
                threshold=0.05,
                plot=False,
            )

        with pytest.raises(TypeError):
            RMSETest(
                name="rmse",
                value=xr.Dataset(),
                reference=xr.Dataset(),
                threshold=0.05,
                plot=False,
            )

        with pytest.raises(TypeError):
            RMSETest(
                name="rmse",
                archive_dir="tests/",
                reference=xr.Dataset(),
                threshold=0.05,
                plot=False,
            )

        with pytest.raises(TypeError):
            RMSETest(
                name="rmse",
                archive_dir="tests/",
                value=xr.Dataset(),
                reference=xr.Dataset(),
                plot=False,
            )

        assert RMSETest(
            name="rmse",
            archive_dir="tests/",
            value=xr.Dataset(),
            threshold=0.05,
            plot=False,
        )

    def test_reference_converter(self, tmp_path):
        # test proper handling of missing and unreadable reference

        # file does not exist
        assert (
            RMSETest(
                name="rmse",
                archive_dir="tests/",
                value=xr.Dataset(),
                threshold=0.05,
                reference="./this/file/doesnot.exist",
                plot=False,
            ).reference
            is None
        )

        # wrong file type
        with pytest.raises(
            ValueError,
            match="did not find a match in any of xarray's currently installed IO backends",
        ):
            tempfile = tmp_path / "hello.txt"
            tempfile.write_text("test")

            RMSETest(
                name="rmse",
                archive_dir="tests/",
                value=xr.Dataset(),
                threshold=0.05,
                reference=tempfile,
                plot=False,
            )

        # wrong data type
        with pytest.raises(ValueError, match="Reference must be provided as a Dataset"):
            RMSETest(
                name="rmse",
                archive_dir="tests/",
                value=xr.Dataset(),
                threshold=0.05,
                reference=np.zeros(25),
                plot=False,
            )


class TestMissingReference:
    """
    These tests check the behaviour of a test whose reference cannot be
    resolved, with and without the reference update flag.
    """

    @staticmethod
    def make_test(tmp_path, **kwargs):
        return RMSETest(
            name="rmse",
            archive_dir=tmp_path,
            value=xr.Dataset({"brf": xr.DataArray(np.zeros(3), dims="vza")}),
            variable="brf",
            threshold=0.05,
            reference="./this/file/doesnot.exist",
            **kwargs,
        )

    def test_with_plot(self, tmp_path):
        # a missing reference must not crash the constructor when plotting is
        # on, and run() must take the "store new reference" branch when
        # reference creation is explicitly requested
        test = self.make_test(tmp_path, plot=True, update_references=True)

        # the bootstrap must be reported as a failure, but not before the
        # candidate reference has been written
        with pytest.raises(RegressionTestFailure, match="no reference data"):
            test.run()
        assert (tmp_path / "rmse-ref.nc").is_file()

        assert test.run(raise_on_failure=False) is False

    def test_without_flag(self, tmp_path):
        # without update_references, an unresolved reference is a setup error:
        # it must raise whatever raise_on_failure says, and archive nothing — a
        # typo'd path must not leave a candidate reference behind
        test = self.make_test(tmp_path, plot=True)

        with pytest.raises(ValueError, match="--update-references"):
            test.run(raise_on_failure=False)
        assert not (tmp_path / "rmse-ref.nc").exists()


class TestPlot:
    """
    These tests check chart generation for data layouts with extra dimensions.
    """

    @staticmethod
    def make_spectral_datasets(n_w=3, n_x=8, offset=0.1):
        """
        Build a (value, reference) pair with the layout a measure actually
        produces: dimensions ``(w, y_index, x_index)`` with ``vza`` a
        *non-dimension* coordinate over ``(x_index, y_index)``. The elementwise
        difference is ``offset``.
        """
        ref_da = xr.DataArray(
            np.ones((n_w, 1, n_x)),
            dims=("w", "y_index", "x_index"),
            coords={
                "w": np.linspace(440.0, 660.0, n_w),
                "vza": (
                    ("x_index", "y_index"),
                    np.linspace(0.0, 60.0, n_x)[:, np.newaxis],
                ),
            },
        )

        ref = xr.Dataset({"brf": ref_da, "brf_var": ref_da * 0.01})
        value = xr.Dataset({"brf": ref_da + offset, "brf_var": ref_da * 0.01})
        return value, ref

    @pytest.mark.parametrize("cls", [RMSETest, ZTest], ids=["rmse", "z-test"])
    def test_spectral(self, tmp_path, cls):
        # a dataset with a dimension other than the angular one must be
        # charted, with that dimension mapped to colour, rather than rejected
        # by the constructor. The datasets use the production layout, where vza
        # is a coordinate over x_index rather than a dimension of its own.
        n_w = 3
        value, ref = self.make_spectral_datasets(n_w=n_w)

        test = cls(
            name="spectral",
            value=value,
            reference=ref,
            variable="brf",
            archive_dir=tmp_path,
            threshold=0.05,
            plot=True,
        )

        figure, axes = test._plot_ref(metric_value=0.5)
        try:
            # one reference line and one result line per wavelength on the
            # comparison panel, one line per wavelength on each difference panel
            assert len(axes[0][0].lines) == 2 * n_w
            assert len(axes[1][0].lines) == n_w
            assert len(axes[1][1].lines) == n_w
        finally:
            plt.close(figure)

        # the whole run() path must go through, PNG included (the verdict
        # differs between the two classes and is not what this test is about)
        test.run(raise_on_failure=False)
        assert (tmp_path / "spectral.png").is_file()


class TestZTest:
    """
    These tests check the Z-test statistic and its Šidák family-wise
    aggregation.
    """

    @staticmethod
    def make_datasets(
        n=100, bias_in_sigma=0.0, var_res=0.5, var_ref=0.5, outlier_in_sigma=None
    ):
        """
        Build a (value, reference) pair whose elementwise difference is
        ``bias_in_sigma`` times the standard error of the difference, i.e.
        sqrt(var_res + var_ref). If ``outlier_in_sigma`` is set, the last
        element is shifted by that many standard errors instead.
        """
        sigma = np.sqrt(var_res + var_ref)
        bias = np.full(n, bias_in_sigma * sigma)
        if outlier_in_sigma is not None:
            bias[-1] = outlier_in_sigma * sigma

        ref = xr.Dataset(
            {
                "brf": xr.DataArray(np.zeros(n), dims="vza"),
                "brf_var": xr.DataArray(np.full(n, var_ref), dims="vza"),
            }
        )
        value = xr.Dataset(
            {
                "brf": xr.DataArray(bias, dims="vza"),
                "brf_var": xr.DataArray(np.full(n, var_res), dims="vza"),
            }
        )
        return value, ref

    @staticmethod
    def family_p_value(p_min, n):
        """Expected reported metric: the Šidák-corrected family-wise p-value."""
        return 1.0 - (1.0 - p_min) ** n

    @pytest.mark.parametrize(
        "bias_in_sigma, expected_passed",
        [(0.0, True), (1.0, True), (5.0, False)],
        ids=["identical", "1-sigma", "5-sigma"],
    )
    def test_sidak_evaluate(self, bias_in_sigma, expected_passed):
        # known-answer check: a uniform k-sigma shift must yield the two-tailed
        # normal p-value 2 * sf(k) for every pair. The standard error uses both
        # variances, so an implementation ignoring the reference variance would
        # report a p-value for k * sqrt(2) instead. The reported metric
        # aggregates the paired p-values with the Šidák correction.
        #
        n = 100
        value, ref = self.make_datasets(n=n, bias_in_sigma=bias_in_sigma)

        test = ZTest(
            name="sidak",
            value=value,
            reference=ref,
            variable="brf",
            archive_dir="tests/",
            threshold=0.05,
            plot=False,
        )

        passed, p_value = test._evaluate()

        assert p_value == pytest.approx(
            self.family_p_value(2.0 * spstats.norm.sf(bias_in_sigma), n)
        )
        assert passed is expected_passed

    def test_sidak_no_outlier_quota(self):
        # a single 5-sigma outlier among n = 100 pairs must fail the test: the
        # old 99.75% quota tolerated int(0.9975 * 100) = 99 accepted pairs out
        # of 100, plain Šidák tolerates none
        n = 100
        value, ref = self.make_datasets(n=n, outlier_in_sigma=5.0)

        test = ZTest(
            name="outlier",
            value=value,
            reference=ref,
            variable="brf",
            archive_dir="tests/",
            threshold=0.05,
            plot=False,
        )

        passed, p_value = test._evaluate()

        assert passed is False
        # the reported metric is comparable with the threshold:
        # passed <=> p > alpha
        assert p_value == pytest.approx(
            self.family_p_value(2.0 * spstats.norm.sf(5.0), n)
        )
        assert p_value < test.threshold

    def test_missing_reference_variance(self):
        # legacy references carry no variance: fall back to the result variance
        # alone, i.e. the difference is scaled by sqrt(var_res) instead of
        # sqrt(var_res + var_ref)
        var_res = var_ref = 0.5
        value, ref = self.make_datasets(
            bias_in_sigma=1.0, var_res=var_res, var_ref=var_ref
        )
        ref = ref.drop_vars("brf_var")

        test = ZTest(
            name="z-test",
            value=value,
            reference=ref,
            variable="brf",
            archive_dir="tests/",
            threshold=0.05,
            plot=False,
        )

        _, p_value = test._evaluate()

        inflated = np.sqrt((var_res + var_ref) / var_res)
        assert p_value == pytest.approx(
            self.family_p_value(2.0 * spstats.norm.sf(inflated), value.sizes["vza"])
        )

    def test_requires_result_variance(self):
        # the result variance is mandatory
        value, ref = self.make_datasets()
        value = value.drop_vars("brf_var")

        test = ZTest(
            name="z-test",
            value=value,
            reference=ref,
            variable="brf",
            archive_dir="tests/",
            threshold=0.05,
            plot=False,
        )

        with pytest.raises(ValueError, match="The result data for this Z-test"):
            test._evaluate()


class TestRMSETest:
    """
    These tests check the RMSE metric and its comparison direction.
    """

    @pytest.mark.parametrize(
        "offsets, expected_rmse",
        [
            (np.zeros(16), 0.0),
            (np.full(16, 0.25), 0.25),
            ([3.0, 4.0], 12.5**0.5),
        ],
        ids=["identical", "constant-offset", "mixed-offsets"],
    )
    def test_evaluate(self, offsets, expected_rmse):
        # known-answer check: a constant offset d yields an RMSE of exactly
        # |d|, and [3, 4] over two points yields sqrt((9 + 16) / 2). The
        # threshold is picked so that the three cases also pin the comparison
        # direction: RMSETest passes when the metric is *below* the threshold,
        # the opposite of the p-value-based classes.
        threshold = 0.25
        value, ref = make_offset_datasets(offsets)

        test = RMSETest(
            name="rmse",
            value=value,
            reference=ref,
            variable="brf",
            archive_dir="tests/",
            threshold=threshold,
            plot=False,
        )

        passed, rmse = test._evaluate()

        assert rmse == pytest.approx(expected_rmse)
        assert passed is (expected_rmse <= threshold)


class TestRun:
    """
    These tests check the run() workflow: archival, charting and failure
    reporting.
    """

    @pytest.mark.parametrize(
        "offset, expected_passed", [(0.1, True), (3.0, False)], ids=["pass", "fail"]
    )
    def test_with_reference(self, tmp_path, offset, expected_passed):
        # the reference-present branch of run(): both datasets are archived,
        # the chart is written, and the verdict is returned — including the
        # failing verdict, which no other test exercises through run()
        value, ref = make_offset_datasets(np.full(8, offset))

        test = RMSETest(
            name="rmse",
            value=value,
            reference=ref,
            variable="brf",
            archive_dir=tmp_path,
            threshold=0.25,
            plot=True,
        )

        assert test.run(raise_on_failure=False) is expected_passed
        assert (tmp_path / "rmse-ref.nc").is_file()
        assert (tmp_path / "rmse-result.nc").is_file()
        assert (tmp_path / "rmse.png").is_file()

    def test_raises_on_failure(self, tmp_path):
        # the default: a failed comparison raises, and the numbers that decided
        # the verdict are in the message — which is the whole point, since a
        # plain pytest run does not show the Robot log
        threshold = 0.25
        value, ref = make_offset_datasets(np.full(8, 3.0))

        test = RMSETest(
            name="rmse",
            value=value,
            reference=ref,
            variable="brf",
            archive_dir=tmp_path,
            threshold=threshold,
            plot=False,
        )

        with pytest.raises(RegressionTestFailure) as exc_info:
            test.run()

        msg = str(exc_info.value)
        assert "rmse" in msg
        assert str(threshold) in msg
        assert str(test._evaluate()[1]) in msg

    def test_evaluation_error_is_not_masked(self, tmp_path):
        # a failing _evaluate() triggers a chart of the same malformed data,
        # which must not replace the diagnostic exception with a plotting one
        value, ref = make_offset_datasets(np.zeros(8))
        ref = ref.isel(vza=slice(0, 4))

        test = RMSETest(
            name="rmse",
            value=value,
            reference=ref,
            variable="brf",
            archive_dir=tmp_path,
            threshold=0.25,
            plot=True,
        )

        with pytest.raises(ValueError, match="do not have the same shape"):
            test.run()


class TestRegressionReport:
    """
    These tests check reporting infrastructure integration in the regression
    testing components.
    """

    class ReportLoggerSpy(ReportLogger):
        """
        Report logger that records messages and HTML fragments for assertions
        while forwarding them to the active report backend. Content sent
        through this spy therefore shows up in the generated test report and
        can be inspected visually.
        """

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.messages = []
            self.fragments = []

        def info(self, msg):
            self.messages.append(msg)
            super().info(msg)

        def html(self, fragment):
            self.fragments.append(fragment)
            super().html(fragment)

    @pytest.fixture
    def spy(self):
        return self.ReportLoggerSpy()

    @pytest.fixture
    def datasets(self):
        # A difference of 1e-3, i.e. passing for any sane threshold
        return make_offset_datasets(np.full(8, 1e-3))

    def test_messages(self, tmp_path, datasets, spy):
        """
        A regression test sends its diagnostic messages to the injected
        report logger and archives result and reference datasets.
        """
        value, ref = datasets

        test = RMSETest(
            name="rmse-pass",
            value=value,
            reference=ref,
            variable="brf",
            threshold=1.0,
            archive_dir=tmp_path,
            plot=False,
            logger=spy,
        )

        assert test.run()
        assert any("Metric value: rmse" in msg for msg in spy.messages)
        assert not spy.fragments  # No plot requested
        assert (tmp_path / "rmse-pass-result.nc").exists()
        assert (tmp_path / "rmse-pass-ref.nc").exists()

    def test_failure(self, tmp_path, datasets, spy):
        """
        A failing regression test reports through the same channel.
        """
        value, ref = datasets

        test = RMSETest(
            name="rmse-fail",
            value=value,
            reference=ref,
            variable="brf",
            threshold=0.0,
            archive_dir=tmp_path,
            plot=False,
            logger=spy,
        )

        assert not test.run(raise_on_failure=False)
        assert any("Test did not pass" in msg for msg in spy.messages)

    def test_plot(self, tmp_path, datasets, spy):
        """
        With plotting enabled, the comparison chart is embedded in the report
        as an SVG fragment and saved to the archive directory as a PNG file
        """
        value, ref = datasets

        test = RMSETest(
            name="rmse-plot",
            value=value,
            reference=ref,
            variable="brf",
            threshold=1.0,
            archive_dir=tmp_path,
            plot=True,
            logger=spy,
        )

        assert test.run()
        assert len(spy.fragments) == 1
        assert spy.fragments[0].startswith("<svg")
        assert (tmp_path / "rmse-plot.png").exists()

    @pytest.mark.parametrize("use_robot", [False, True], ids=["console", "report"])
    def test_diagnostic_plot(self, tmp_path, datasets, capsys, use_robot):
        """
        The Z-test diagnostic plot is drawn on a panel of the comparison chart,
        which is embedded in the report and archived as a single PNG. The
        console message announcing the file is emitted only when no report
        backend is active.
        """
        value, ref = datasets
        for ds in (value, ref):
            ds["brf_var"] = xr.full_like(ds["brf"], 1e-4)

        spy = self.ReportLoggerSpy(use_robot=use_robot)
        test = ZTest(
            name="z-diagnostic",
            value=value,
            reference=ref,
            variable="brf",
            threshold=0.05,
            archive_dir=tmp_path,
            plot=True,
            logger=spy,
        )

        assert test.run()
        assert (tmp_path / "z-diagnostic.png").exists()
        # The diagnostic shares the comparison chart, hence a single fragment
        assert len(spy.fragments) == 1
        # The panel is actually fed with data
        assert "z" in test.diagnostic_data

        printed = capsys.readouterr().out
        assert ("Saved plot" in printed) is not use_robot

    def test_no_plot(self, tmp_path, datasets):
        """
        The ``plot`` field gates the diagnostic chart together with the
        comparison chart: no figure is drawn or archived when it is unset.
        """
        value, ref = datasets
        for ds in (value, ref):
            ds["brf_var"] = xr.full_like(ds["brf"], 1e-4)

        spy = self.ReportLoggerSpy(use_robot=False)
        test = ZTest(
            name="z-no-plot",
            value=value,
            reference=ref,
            variable="brf",
            threshold=0.05,
            archive_dir=tmp_path,
            plot=False,
            logger=spy,
        )

        assert test.run()
        assert not spy.fragments
        assert not list(tmp_path.glob("*.png"))

    def test_noref(self, tmp_path, datasets, spy):
        """
        Without reference data, the test fails, stores the result as a new
        reference candidate, says so in the report and embeds a plot of the
        reference candidate
        """
        value, _ = datasets

        test = RMSETest(
            name="rmse-noref",
            value=value,
            reference=None,
            variable="brf",
            threshold=1.0,
            archive_dir=tmp_path,
            plot=True,
            update_references=True,
            logger=spy,
        )

        assert not test.run(raise_on_failure=False)
        assert any("No reference data found" in msg for msg in spy.messages)
        assert (tmp_path / "rmse-noref-ref.nc").exists()
        assert len(spy.fragments) == 1
        assert spy.fragments[0].startswith("<svg")
