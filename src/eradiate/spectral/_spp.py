"""
Sample count (spp) distribution across spectral loop iterations.

This module sits above :mod:`.grid`, :mod:`.response` and :mod:`.quad` in the
import graph (it depends on all three), which is why it cannot live in
:mod:`.response` (that would create a cycle, since :mod:`.grid` already
imports from :mod:`.response`).
"""

from __future__ import annotations

import numpy as np

from .grid import CKDSpectralGrid, MonoSpectralGrid, SpectralGrid
from .response import BandSRF, DeltaSRF, SpectralResponseFunction, UniformSRF
from ..quad import Quad
from ..units import unit_registry as ureg

__all__ = ["srf_spp_distribution"]


def _allocate(
    weights: np.typing.ArrayLike, total: int, floor: np.typing.ArrayLike = 1
) -> np.ndarray:
    """
    Split an integer sample count across a set of iterations, proportionally
    to ``weights``.

    Every iteration is guaranteed at least ``floor`` samples and the result
    always sums exactly to ``total`` (largest-remainder rounding on top of
    the floor).

    Parameters
    ----------
    weights : array-like
        Non-negative relative weights, one per iteration.

    total : int
        Total sample count to distribute.

    floor : int or array-like, optional, default: 1
        Minimum sample count guaranteed to each iteration. Scalar (applied to
        every iteration) or one value per iteration — *e.g.* the number of
        CKD quadrature points of the corresponding bin, when the result of
        this call is itself about to be split further downstream.

    Returns
    -------
    ndarray
        Integer sample count per iteration, same length as ``weights``.

    Raises
    ------
    ValueError
        If ``total`` is lower than the sum of ``floor`` (cannot give every
        iteration its minimum guaranteed sample count).
    """
    weights = np.atleast_1d(np.asarray(weights, dtype=float))
    n = len(weights)
    floor = np.broadcast_to(np.asarray(floor, dtype=int), (n,))
    floor_total = int(floor.sum())

    if total < floor_total:
        raise ValueError(
            f"cannot distribute {total} samples across {n} spectral loop "
            f"iterations: a minimum of {list(floor)} samples per iteration "
            f"is required (total >= {floor_total})"
        )

    if weights.sum() <= 0:
        weights = np.ones(n)

    remaining = total - floor_total
    shares = remaining * weights / weights.sum()
    extra_floors = np.floor(shares).astype(int)
    remainders = shares - extra_floors

    result = floor + extra_floors
    leftover = remaining - int(extra_floors.sum())

    if leftover > 0:
        order = np.argsort(-remainders, kind="stable")
        result[order[:leftover]] += 1

    return result


def _trapezoidal_weights(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """
    Per-node trapezoidal integration weight (local support width times node
    value), used to turn point samples of a spectral response function into
    relative allocation weights.
    """
    if len(x) == 1:
        return np.array([1.0])

    dx = np.empty_like(x)
    dx[0] = x[1] - x[0]
    dx[-1] = x[-1] - x[-2]
    dx[1:-1] = x[2:] - x[:-2]
    return 0.5 * dx * y


def _mono_distribution(
    srf: SpectralResponseFunction, spectral_grid: MonoSpectralGrid, target: int
) -> dict[float, int]:
    w_nm = spectral_grid.wavelengths.m_as(ureg.nm)

    if isinstance(srf, BandSRF):
        weights = _trapezoidal_weights(w_nm, srf.eval(spectral_grid.wavelengths).m)
        spp = _allocate(weights, target)
    elif isinstance(srf, (DeltaSRF, UniformSRF)):
        spp = np.full(len(w_nm), target, dtype=int)
    else:
        raise TypeError(f"unsupported SRF type '{type(srf).__name__}'")

    return {float(w): int(s) for w, s in zip(w_nm, spp)}


def _ckd_distribution(
    srf: SpectralResponseFunction,
    spectral_grid: CKDSpectralGrid,
    target: int,
    ckd_quads: list[Quad],
) -> dict[tuple[float, float], int]:
    w_nm = spectral_grid.wcenters.m_as(ureg.nm)
    n_bins = len(w_nm)

    if isinstance(srf, BandSRF):
        bin_weights = np.array(
            [
                srf.integrate(wmin, wmax).m_as(ureg.nm)
                for wmin, wmax in zip(spectral_grid.wmins, spectral_grid.wmaxs)
            ]
        )
        # Every bin must receive at least as many samples as it has
        # quadrature points, since its allocation is split further below.
        ng_per_bin = np.array([len(quad.nodes) for quad in ckd_quads])
        bin_spp = _allocate(bin_weights, target, floor=ng_per_bin)
    elif isinstance(srf, (DeltaSRF, UniformSRF)):
        bin_spp = np.full(n_bins, target, dtype=int)
    else:
        raise TypeError(f"unsupported SRF type '{type(srf).__name__}'")

    # Within each bin, split its target across quadrature g-points,
    # weighted by quadrature weight, regardless of SRF type.
    result: dict[tuple[float, float], int] = {}
    for w, quad, bin_target in zip(w_nm, ckd_quads, bin_spp):
        g_values = quad.eval_nodes([0.0, 1.0])
        g_spp = _allocate(quad.weights, int(bin_target))
        for g, s in zip(g_values, g_spp):
            result[(float(w), float(g))] = int(s)

    return result


def srf_spp_distribution(
    srf: SpectralResponseFunction,
    spectral_grid: SpectralGrid,
    target: int,
    ckd_quads: list[Quad] | None = None,
) -> dict[float, int] | dict[tuple[float, float], int]:
    """
    Distribute a sample count budget across the spectral loop iterations
    driven by ``spectral_grid``.

    Parameters
    ----------
    srf : .SpectralResponseFunction
        Spectral response function driving the distribution policy.
        :class:`.DeltaSRF` and :class:`.UniformSRF` apply ``target`` in full
        to every iteration (mono: wavelength; ckd: bin). :class:`.BandSRF`
        distributes ``target`` across iterations, weighted by spectral
        response, so that the total sums exactly to ``target``.

    spectral_grid : .SpectralGrid
        Spectral grid driving the spectral loop (already selected against
        ``srf``, *e.g.* via :meth:`.SpectralGrid.select`).

    target : int
        Sample count budget.

    ckd_quads : list of .Quad, optional
        Quadrature rules for each bin in ``spectral_grid``, in the same
        order as ``spectral_grid.wcenters``. Required if ``spectral_grid``
        is a :class:`.CKDSpectralGrid`. In ckd mode, whatever sample count
        applies to a bin (see above) is further split across that bin's
        quadrature g-points, weighted by :attr:`.Quad.weights`, regardless
        of SRF type.

    Returns
    -------
    dict
        In mono mode, maps wavelength [nm] to sample count. In ckd mode,
        maps ``(bin center wavelength [nm], g)`` to sample count. Keys match
        :attr:`.MonoSpectralIndex.as_hashable` /
        :attr:`.CKDSpectralIndex.as_hashable`.
    """
    if isinstance(spectral_grid, MonoSpectralGrid):
        return _mono_distribution(srf, spectral_grid, target)

    elif isinstance(spectral_grid, CKDSpectralGrid):
        if ckd_quads is None:
            raise ValueError(
                "ckd_quads must be specified when spectral_grid is a CKDSpectralGrid"
            )
        return _ckd_distribution(srf, spectral_grid, target, ckd_quads)

    else:
        raise TypeError(
            f"unsupported spectral grid type '{type(spectral_grid).__name__}'"
        )
