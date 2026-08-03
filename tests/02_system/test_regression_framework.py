"""
Self-check of the regression testing framework: type I and type II error rates
of :class:`.ZTest`, measured on real simulation output.

This is not a regression test — it has no stored reference. It renders the same
RAMI4ATM scene twice and compares the two results against each other, which is
the only configuration exercising the framework's real data model:
per-viewing-angle means with their Monte Carlo variance.
"""

import functools

import pytest

import eradiate
from eradiate.test_tools.regression import ZTest
from eradiate.test_tools.test_cases import rami4atm

CASE = "hom00_bla_sd2s_m03_z30a000_brfpp"

#: Sample count, matching the production regression test (test_rami4atm_benchmark)
SPP = 1000

#: Family-wise significance level. The type I error rate of the framework is
#: this value by construction, so keep it low enough for the check not to be
#: flaky.
THRESHOLD = 1e-4

#: Relative radiance bias the framework must detect. At ``SPP`` the per-pixel
#: relative standard deviation is ~2 %, and the decision keys on the most
#: extreme of n = 1216 comparisons, so the detection floor at ``THRESHOLD`` sits
#: around 6 %. Measured family p-values: 0.03 → 0.05, 0.05 → 4e-4, 0.10 → 3e-11.
BIAS = 0.1


@functools.cache
def _render_pair():
    """
    Two independent renders of the same scene. Cached: both tests below compare
    the same pair, and a render costs ~5 s.
    """
    _, (exp,) = rami4atm.registry[CASE]["constructor"](spp=SPP)
    return eradiate.run(exp), eradiate.run(exp)


def _evaluate(value, reference, tmp_path):
    test = ZTest(
        name="ztest",
        value=value,
        reference=reference,
        variable="radiance",
        threshold=THRESHOLD,
        archive_dir=tmp_path,
        plot=False,
    )
    return test._evaluate()


@pytest.mark.slow
def test_type_I_error(mode_ckd_double, tmp_path):
    """
    Type I error
    ============

    Two independent renders of the same scene differ only by Monte Carlo noise,
    so the test must accept them. A failure means the framework rejects data
    drawn from the same distribution, i.e. its false alarm rate exceeds the
    threshold it advertises.
    """
    result, reference = _render_pair()
    passed, p_value = _evaluate(result, reference, tmp_path)
    assert passed, f"family p-value {p_value} <= threshold {THRESHOLD}"


@pytest.mark.slow
def test_type_II_error(mode_ckd_double, tmp_path):
    """
    Type II error
    =============

    Scaling the reference radiance by ``1 + BIAS`` introduces a bias large
    compared with the Monte Carlo noise, so the test must reject it. A failure
    means the framework misses a regression of that size.
    """
    result, reference = _render_pair()
    biased = reference.copy()
    biased["radiance"] = reference.radiance * (1.0 + BIAS)

    passed, p_value = _evaluate(result, biased, tmp_path)
    assert not passed, f"family p-value {p_value} > threshold {THRESHOLD}"
