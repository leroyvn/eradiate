import numpy as np
import pytest

import eradiate
from eradiate import fresolver
from eradiate.test_tools.regression import ZTest
from eradiate.test_tools.report import report_logger
from eradiate.test_tools.test_cases import rami4atm

cases = [c for c in rami4atm.registry if c != "hom00_bla_a00s_m04_z30a000_brfpp"]


@pytest.mark.regression
def test_rami4atm_hom00_bla_a00s_m04_z30a000_brfpp(mode_ckd_double):
    r"""
    *RAMI4ATM HOM00_BLA_S00S_M04*

    This scenario is based on the ``HOM00_BLA_S00S_M04_z30a000-brfpp`` scenario
    of the RAMI4ATM benchmark.

    *Scene setup*

    - Geometry: 1D plane-parallel
    - Atmosphere: Molecular atmosphere using the AFGL 1986 (U.S. Standard) profile, absorption only
    - Surface: Black
    - Illumination: Directional illumination with a zenith angle of 30°
    - Sensor: Multi-distant measure covering the principal plane, from -75° to 75° with 2° increments, delta SRF positioned at λ = 660 nm
    """
    # TODO: This test case definition is kept for compatibility
    _, (exp,) = rami4atm.create_rami4atm_toa("hom00_bla_a00s_m04_z30a000_brfpp", 1000)

    result = eradiate.run(exp)
    report_logger.html(result._repr_html_())
    assert np.allclose(result.brf_srf, 0.0)


@pytest.mark.regression
@pytest.mark.slow
@pytest.mark.parametrize("case", cases)
@pytest.mark.filterwarnings(
    "ignore:User-specified a background spectral grid is overridden by atmosphere spectral grid"
)
def test_rami4atm(mode_ckd_double, case, dataset_regression):
    specification = rami4atm.registry[case]
    ctor = specification.get("constructor")
    postprocess = specification.get("postprocess", lambda ls, _: ls[0])
    variables = specification.get("variables", ["radiance"])
    test_ctor = specification.get("test", ZTest)
    threshold = specification.get("threshold")

    srf_id, exps = ctor(spp=1000)
    srf = fresolver.load_dataset(f"srf/{srf_id}.nc")

    raw_results = [eradiate.run(exp) for exp in exps]

    result = postprocess(raw_results, srf)
    report_logger.html(result._repr_html_())

    # All tested variables share a single reference dataset
    dataset_regression.check(
        result,
        [test_ctor(threshold, variable=variable) for variable in variables],
        basename=f"rami4atm/{case}-ref",
    )
