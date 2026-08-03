import pytest

import eradiate
from eradiate import fresolver
from eradiate.test_tools.regression import RMSETest, ZTest
from eradiate.test_tools.test_cases.ocean import (
    create_ocean_grasp_coastal_no_atm,
    create_ocean_grasp_open_atm,
    create_ocean_grasp_open_no_atm,
    ocean_grasp_wavelength,
)


@pytest.mark.regression
def test_ocean_grasp_coastal_no_atm(
    mode_mono_double, artefact_dir, session_timestamp, plot_figures, update_references
):
    """
    *Ocean GRASP Coastal no atm regression test*

    Compare the simulation results of the current branch to results directly
    validated against the GRASP model. This test targets a coastal ocean
    scenario and does not include an atmosphere.

    *Expected behaviour*

    This test uses the RMSE criterion with a threshold of 10⁻⁶.
    """
    ref = fresolver.load_dataset(
        "tests/regression_test_references/ocean_grasp_REF_OC_NN00_I_S20_PPL.nc"
    )
    exp = create_ocean_grasp_coastal_no_atm()
    result = eradiate.run(exp)

    wavelength = ocean_grasp_wavelength()
    for w in wavelength:
        test = RMSETest(
            # The wavelength is part of the name so that each iteration gets
            # its own artefacts and identifies itself upon failure
            name=(
                f"{session_timestamp:%Y%m%d-%H%M%S}"
                f"-ocean_grasp_REF_OC_NN00_I_S20_PPL-{w}"
            ),
            value=result.sel(w=w),
            reference=ref.sel(w=w),
            threshold=1e-6,
            archive_dir=artefact_dir,
            variable="brf",
            plot=plot_figures,
            update_references=update_references,
        )

        test.run()


@pytest.mark.regression
def test_ocean_grasp_open_no_atm(
    mode_mono_double, artefact_dir, session_timestamp, plot_figures, update_references
):
    """
    *Ocean GRASP Open no atm regression test*

    Compare the simulation results of the current branch to results directly
    validated against the GRASP model. This test targets an open ocean scenario
    and does not include an atmosphere.

    *Expected behaviour*

    This test uses the RMSE criterion with a threshold of 10⁻⁶.
    """
    ref = fresolver.load_dataset(
        "tests/regression_test_references/ocean_grasp_REF_OO_NN00_I_S20_PPL.nc"
    )
    exp = create_ocean_grasp_open_no_atm()
    result = eradiate.run(exp)

    wavelength = ocean_grasp_wavelength()
    for w in wavelength:
        test = RMSETest(
            # The wavelength is part of the name so that each iteration gets
            # its own artefacts and identifies itself upon failure
            name=f"{session_timestamp:%Y%m%d-%H%M%S}-ocean_grasp_REF_OO_NN00_I_S20_PPL-{w}",
            value=result.sel(w=w),
            reference=ref.sel(w=w),
            threshold=1e-6,
            archive_dir=artefact_dir,
            variable="brf",
            plot=plot_figures,
            update_references=update_references,
        )

        test.run()


@pytest.mark.regression
def test_ocean_grasp_open_atm(
    mode_mono_double, artefact_dir, session_timestamp, plot_figures, update_references
):
    """
    *Ocean GRASP Open atm regression test*

    Compares the simulation results of the current branch to results directly
    validated against the GRASP model. This test targets a coastal ocean
    scenario and includes an atmosphere.

    *Expected behaviour*

    This test uses the z-test criterion with a threshold of 0.01.
    """
    ref = fresolver.load_dataset(
        "tests/regression_test_references/ocean_grasp_REF_OO_UB01_I_S20_PPL.nc"
    )
    exp = create_ocean_grasp_open_atm()
    result = eradiate.run(exp, spp=int(1e5))

    test = ZTest(
        name=f"{session_timestamp:%Y%m%d-%H%M%S}-ocean_grasp_REF_OO_UB01_I_S20_PPL",
        value=result,
        reference=ref,
        threshold=0.01,
        archive_dir=artefact_dir,
        variable="radiance",
        plot=False,
        update_references=update_references,
    )

    test.run()
