import numpy as np
import pytest

import eradiate
from eradiate import fresolver
from eradiate import unit_registry as ureg
from eradiate.experiments import AtmosphereExperiment
from eradiate.test_tools.regression import SidakTTest


@pytest.mark.regression
@pytest.mark.slow
def test_spherical(mode_ckd_double, artefact_dir, plot_figures):
    spp = 100
    config = {
        "surface": {
            "rho_0": {"value": 0.017051, "type": "uniform"},
            "k": {"value": 0.95, "type": "uniform"},
            "g": {"value": -0.1, "type": "uniform"},
            "rho_c": {"value": 0.017051, "type": "uniform"},
            "type": "rpv",
        },
        "atmosphere": {
            "has_absorption": True,
            "has_scattering": True,
            "thermoprops": {
                "identifier": "afgl_1986-us_standard",
                "z": np.arange(0, 120.05, 0.05) * ureg.km,
            },
            "absorption_data": "monotropa",
            "type": "molecular",
        },
        "illumination": {
            "zenith": 30.0,
            "zenith_units": "degree",
            "azimuth": 0.0,
            "azimuth_units": "degree",
            "type": "directional",
        },
        "measures": [
            {
                "type": "mdistant",
                "construct": "hplane",
                "zeniths": np.arange(-85, 65, 1),
                "zeniths_units": "degree",
                "azimuth": 0.0,
                "azimuth_units": "degree",
                "srf": "sentinel_2a-msi-4",
                "spp": spp,
                "target": [0.0, 0.0, 6378.1] * ureg.km,
            }
        ],
        "ckd_quad_config": {
            "policy": "fixed",
            "type": "gauss_legendre",
            "ng_max": 16,
        },
        "integrator": {"type": "volpath", "moment": True},
        "geometry": "spherical_shell",
    }

    exp = AtmosphereExperiment(**config)
    result = eradiate.run(exp)
    reference = fresolver.load_dataset(
        "tests/regression_test_references/test_spherical_shell-ref.nc"
    )

    test = SidakTTest(
        name="test_spherical_shell",
        value=result,
        reference=reference,
        threshold=0.01,
        archive_dir=artefact_dir,
        variable="radiance",
        plot=False,
    )

    assert test.run(plot_figures)
