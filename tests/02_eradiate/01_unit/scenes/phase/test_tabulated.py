import mitsuba as mi
import numpy as np
import pytest
import xarray as xr

import eradiate
from eradiate.contexts import KernelDictContext, SpectralContext
from eradiate.scenes.core import NodeSceneElement, traverse
from eradiate.scenes.phase import PhaseFunction, TabulatedPhaseFunction
from eradiate.test_tools.types import check_type


def test_tabulated_phase_type():
    check_type(
        TabulatedPhaseFunction,
        expected_mro=[PhaseFunction, NodeSceneElement],
        expected_slots=[],
    )


@pytest.fixture
def regular() -> xr.DataArray:
    """Phase function data with a regular mu grid."""
    result = eradiate.data.load_dataset("tests/spectra/particles/random-regular_mu.nc")
    return result.phase


@pytest.fixture
def irregular() -> xr.DataArray:
    """Phase function data with an irregular mu grid."""
    result = eradiate.data.load_dataset(
        "tests/spectra/particles/random-irregular_mu.nc"
    )
    return result.phase


@pytest.mark.parametrize("grid", ["regular", "irregular"])
def test_tabulated_construct(modes_all_double, grid, request):
    phase = TabulatedPhaseFunction(data=request.getfixturevalue(grid))

    # Irregular grid layout is detected
    assert phase._is_irregular == (grid == "irregular")
    assert (
        phase.kernel_type == "tabphase" if "grid" == "regular" else "tabphase_irregular"
    )

    # Kernel dict can be generated and instantiated
    template, params = traverse(phase)
    kernel_phase = mi.load_dict(template.render(KernelDictContext()))
    assert isinstance(kernel_phase, mi.PhaseFunction)

    # Phase function can be updated
    kernel_params = mi.traverse(kernel_phase)
    kernel_params.update(params.render(KernelDictContext()))


def test_tabulated_order(mode_mono, tmpdir):
    """
    TabulatedPhaseFunction returns phase function values by increasing order of
    scattering angle cosine values, regardless how its input is ordered.
    """

    def make_da(mu, phase):
        return xr.DataArray(
            phase[:, :, np.newaxis, np.newaxis],
            coords={
                "w": ("w", [240.0, 2800.0], dict(units="nm")),
                "mu": ("mu", mu),
                "i": ("i", [0]),
                "j": ("j", [0]),
            },
        )

    da_mu_increasing = make_da(
        mu=np.linspace(-1, 1, 3), phase=np.array([np.arange(1, 4), np.arange(1, 4)])
    )

    da_mu_decreasing = make_da(
        mu=np.linspace(1, -1, 3),
        phase=np.array([np.arange(3, 0, -1), np.arange(3, 0, -1)]),
    )

    spectral_ctx = SpectralContext.new()

    layer_mu_increasing = TabulatedPhaseFunction(data=da_mu_increasing)
    phase_mu_increasing = layer_mu_increasing.eval(spectral_ctx)

    layer_mu_decreasing = TabulatedPhaseFunction(data=da_mu_decreasing)
    phase_mu_decreasing = layer_mu_decreasing.eval(spectral_ctx)

    assert np.all(phase_mu_increasing == phase_mu_decreasing)
