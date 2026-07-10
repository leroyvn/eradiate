import numpy as np
import pytest

from eradiate.spectral._spp import _allocate, srf_spp_distribution
from eradiate.spectral.ckd_quad import CKDQuadConfig
from eradiate.spectral.grid import CKDSpectralGrid, MonoSpectralGrid
from eradiate.spectral.response import BandSRF, DeltaSRF, UniformSRF
from eradiate.units import unit_registry as ureg

# ------------------------------------------------------------------------------
#                                  _allocate()
# ------------------------------------------------------------------------------


def test_allocate_equal_weights():
    result = _allocate(np.array([1.0, 1.0, 1.0]), 10)
    assert result.sum() == 10
    assert np.all(result >= 1)


def test_allocate_skewed_weights():
    # Heavier weight gets more samples, but everyone stays above the floor
    result = _allocate(np.array([1.0, 9.0]), 100)
    assert result.sum() == 100
    assert result[1] > result[0]
    assert np.all(result >= 1)


@pytest.mark.parametrize(
    "weights, total",
    [
        (np.array([1.0, 2.0, 3.0, 4.0]), 4),  # exact floor
        (np.array([1.0, 2.0, 3.0, 4.0]), 137),  # remainder distribution
        (np.array([1.0, 1.0, 1.0, 1.0, 1.0]), 5),
        (np.ones(20), 1000),
    ],
)
def test_allocate_exact_sum(weights, total):
    result = _allocate(weights, total)
    assert result.sum() == total


def test_allocate_floor_scalar():
    result = _allocate(np.array([1.0, 1.0]), 20, floor=5)
    assert result.sum() == 20
    assert np.all(result >= 5)


def test_allocate_floor_array():
    floor = np.array([2, 8])
    result = _allocate(np.array([1.0, 1.0]), 20, floor=floor)
    assert result.sum() == 20
    assert np.all(result >= floor)


def test_allocate_raises_below_floor():
    with pytest.raises(ValueError):
        _allocate(np.array([1.0, 1.0, 1.0]), 2)

    with pytest.raises(ValueError):
        _allocate(np.array([1.0, 1.0]), 9, floor=np.array([2, 8]))


# ------------------------------------------------------------------------------
#                             srf_spp_distribution() — mono
# ------------------------------------------------------------------------------


@pytest.fixture
def mono_grid():
    return MonoSpectralGrid(
        wavelengths=np.array([500.0, 510.0, 520.0, 530.0, 540.0]) * ureg.nm
    )


def test_spp_distribution_mono_delta_no_split(mode_mono, mono_grid):
    srf = DeltaSRF(wavelengths=[500.0, 520.0] * ureg.nm)
    result = srf_spp_distribution(srf, mono_grid.select(srf), 1000)
    assert result == {500.0: 1000, 520.0: 1000}


def test_spp_distribution_mono_uniform_no_split(mode_mono, mono_grid):
    srf = UniformSRF(wmin=505.0 * ureg.nm, wmax=535.0 * ureg.nm)
    result = srf_spp_distribution(srf, mono_grid.select(srf), 1000)
    assert set(result) == {510.0, 520.0, 530.0}
    assert all(v == 1000 for v in result.values())


def test_spp_distribution_mono_band_sums_to_target(mode_mono, mono_grid):
    srf = BandSRF.gaussian(wl_center=520.0 * ureg.nm, fwhm=15.0 * ureg.nm, pad=True)
    sel = mono_grid.select(srf)
    result = srf_spp_distribution(srf, sel, 1000)
    assert sum(result.values()) == 1000
    # More weight (closer to the band center) should get more samples
    assert result[520.0] > result[510.0]
    assert result[520.0] > result[530.0]


def test_spp_distribution_mono_band_below_floor_raises(mode_mono, mono_grid):
    srf = BandSRF.gaussian(wl_center=520.0 * ureg.nm, fwhm=15.0 * ureg.nm, pad=True)
    sel = mono_grid.select(srf)
    n = len(sel.wavelengths)
    with pytest.raises(ValueError):
        srf_spp_distribution(srf, sel, n - 1)


# ------------------------------------------------------------------------------
#                             srf_spp_distribution() — ckd
# ------------------------------------------------------------------------------


@pytest.fixture
def ckd_grid():
    return CKDSpectralGrid.arange(
        start=500.0 * ureg.nm, stop=545.0 * ureg.nm, step=10.0 * ureg.nm
    )


@pytest.fixture
def ckd_quad_config():
    return CKDQuadConfig(type="gauss_legendre", ng_max=4, policy="fixed")


def _quads_for(grid, quad_config):
    return [x[1] for x in grid.walk_quads(quad_config)]


@pytest.mark.parametrize("srf_type", ["delta", "uniform"])
def test_spp_distribution_ckd_no_split_across_bins(
    mode_ckd, ckd_grid, ckd_quad_config, srf_type
):
    if srf_type == "delta":
        srf = DeltaSRF(wavelengths=[505.0, 525.0] * ureg.nm)
    else:
        srf = UniformSRF(wmin=505.0 * ureg.nm, wmax=535.0 * ureg.nm)

    sel = ckd_grid.select(srf)
    quads = _quads_for(sel, ckd_quad_config)
    result = srf_spp_distribution(srf, sel, 1000, ckd_quads=quads)

    # Every selected bin gets the full (unsplit) target...
    bins = sorted({w for w, _ in result})
    for w in bins:
        bin_total = sum(v for (bw, _), v in result.items() if bw == w)
        assert bin_total == 1000

    # ...but is itself split across its g-points, weighted by quadrature
    # weight (not uniformly).
    for w in bins:
        g_values = sorted(v for (bw, _), v in result.items() if bw == w)
        assert len(g_values) == ckd_quad_config.ng_max
        assert len(set(g_values)) > 1  # Gauss-Legendre weights are not equal


def test_spp_distribution_ckd_band_sums_to_target(mode_ckd, ckd_grid, ckd_quad_config):
    srf = BandSRF.gaussian(wl_center=520.0 * ureg.nm, fwhm=15.0 * ureg.nm, pad=True)
    sel = ckd_grid.select(srf)
    quads = _quads_for(sel, ckd_quad_config)
    target = ckd_quad_config.ng_max * len(sel.wcenters) * 10
    result = srf_spp_distribution(srf, sel, target, ckd_quads=quads)

    assert sum(result.values()) == target

    per_bin = {}
    for (w, _g), v in result.items():
        per_bin.setdefault(w, 0)
        per_bin[w] += v

    # The bin closest to the band center should get the largest share
    assert per_bin[520.0] == max(per_bin.values())


def test_spp_distribution_ckd_band_below_floor_raises(
    mode_ckd, ckd_grid, ckd_quad_config
):
    srf = BandSRF.gaussian(wl_center=520.0 * ureg.nm, fwhm=15.0 * ureg.nm, pad=True)
    sel = ckd_grid.select(srf)
    quads = _quads_for(sel, ckd_quad_config)
    min_target = ckd_quad_config.ng_max * len(sel.wcenters)

    with pytest.raises(ValueError):
        srf_spp_distribution(srf, sel, min_target - 1, ckd_quads=quads)

    # But the exact minimum works
    result = srf_spp_distribution(srf, sel, min_target, ckd_quads=quads)
    assert sum(result.values()) == min_target


def test_spp_distribution_ckd_requires_quads(mode_ckd, ckd_grid):
    srf = DeltaSRF(wavelengths=[505.0] * ureg.nm)
    sel = ckd_grid.select(srf)
    with pytest.raises(ValueError):
        srf_spp_distribution(srf, sel, 1000)
