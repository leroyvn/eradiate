"""
Class skeletons for the proposed atmosphere component system (proposal.md §4),
followed by a runnable sketch of the name-agnostic state-driven evaluation
(proposal.md §6).

Skeletons declare fields and abstract methods only; converters, validators and
docs are omitted.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import attrs
import numpy as np
import pint
import xarray as xr

from eradiate.units import unit_registry as ureg

# ------------------------------------------------------------------------------
#                                 Skeletons
# ------------------------------------------------------------------------------


@attrs.define
class HeterogeneousAtmosphere:  # [heterogeneous], derives from Atmosphere
    """Container. Sole owner of id, geometry and medium-level settings."""

    components: dict[str, AtmosphereComponent]
    id: str = "atmosphere"
    geometry: Any = None  # SceneGeometry
    scale: float | None = None
    force_majorant: bool = False
    extremum_resolution: tuple[int, int, int] = (1, 1, 1)
    use_mis: bool = True

    # eval_sigma_t(si)  = sum(c.eval_sigma_t(si, self.geometry.grid) for c in components)
    # phase             = MultiPhaseFunction(weights=sigma_s per component)
    # validation        = component input shapes checked against self.geometry


class AtmosphereComponent(ABC):
    """No id, no geometry: evaluated on the grid the container passes."""

    @abstractmethod
    def eval_sigma_t(self, si, grid) -> pint.Quantity: ...

    @abstractmethod
    def eval_sigma_s(self, si, grid) -> pint.Quantity: ...

    @abstractmethod
    def phase(self, geometry): ...  # -> PhaseFunction

    # eval_albedo, eval_mfp, bottom, top: derived or abstract as today


@attrs.define
class MolecularComponent(AtmosphereComponent):  # [molecular]
    profile: xr.Dataset  # thermoprops, 1D or 3D
    properties: Any  # AbsorptionDatabase
    rayleigh_depolarization: Any = "bates"
    has_absorption: bool = True
    has_scattering: bool = True


@attrs.define
class ParticleComponent(AtmosphereComponent, ABC):
    has_absorption: bool = attrs.field(default=True, kw_only=True)
    has_scattering: bool = attrs.field(default=True, kw_only=True)
    force_polarized_phase: bool = attrs.field(default=False, kw_only=True)


@attrs.define
class ParticleAOTComponent(ParticleComponent):  # [particle_aot]
    properties: Any  # ParticleProperties, state_dims == ()
    bottom: pint.Quantity = 0.0 * ureg.km  # scalar
    top: pint.Quantity = 1.0 * ureg.km  # scalar
    density: Any = "uniform"  # VerticalDensity, 1D
    aot_ref: pint.Quantity = 0.2 * ureg.dimensionless  # scalar
    w_ref: pint.Quantity = 550.0 * ureg.nm  # scalar


@attrs.define
class ParticleExtinctionComponent(ParticleComponent):  # [particle_extinction]
    sigma_t: xr.DataArray  # dims: w (required) + subset of (x, y, z)
    albedo: xr.DataArray  # dims: w (required) + subset of (x, y, z)
    phase_spec: Any  # "phase" in the dict: PhaseFunction spec or state-free table


@attrs.define
class ParticleStateComponent(ParticleComponent):  # [particle_state]
    profile: Any  # ParticleProfile (ppr_v1)
    properties: Any  # ParticleProperties (prt_v1), any state_dims
    amount: str | None = None  # default: unique unit match (see select_amount)
    state_variables: dict[str, str] = attrs.field(
        factory=dict
    )  # table dim -> profile var


@attrs.define
class ParticlePSDComponent(ParticleStateComponent):  # [particle_psd]
    """Preset: state (reff, veff), amount = mass concentration."""

    REQUIRED_STATE = ("reff", "veff")


# ------------------------------------------------------------------------------
#               Name-agnostic state-driven evaluation (sketch)
# ------------------------------------------------------------------------------

NON_STATE_DIMS = {"w", "phamat", "iangle", "imom"}


def state_dims(properties: xr.Dataset) -> tuple[str, ...]:
    """State dimensions of a properties table: everything not spectral/angular."""
    return tuple(d for d in properties["ext"].dims if d not in NON_STATE_DIMS)


def select_amount(profile: xr.Dataset, ext_units: pint.Unit, exclude=()) -> str:
    """
    Pick the profile variable ``a`` such that ``a × ext`` is an inverse length.
    """
    target = ureg.Unit("1/m")
    matches = [
        name
        for name, var in profile.data_vars.items()
        if name not in exclude
        and "units" in var.attrs
        and (ureg.Unit(var.attrs["units"]) * ext_units).dimensionality
        == target.dimensionality
    ]
    if len(matches) != 1:
        raise ValueError(
            f"cannot select amount variable unambiguously: candidates {matches}"
        )
    return matches[0]


def eval_sigma_t_albedo(
    profile: xr.Dataset,
    properties: xr.Dataset,
    w: pint.Quantity,
    amount: str | None = None,
    state_variables: dict[str, str] | None = None,
) -> tuple[pint.Quantity, np.ndarray]:
    """
    Evaluate σ_t and ϖ per voxel for a profile already resampled on the render
    grid (any spatial dims; values are NaN where no particles are present).

    ponytail: linear interpolation, out-of-table state values give NaN;
    clamping policy is open question 2 in proposal.md.
    """
    dims = state_dims(properties)
    binding = {d: (state_variables or {}).get(d, d) for d in dims}
    ext_units = ureg.Unit(properties["ext"].attrs["units"])
    if amount is None:
        amount = select_amount(profile, ext_units, exclude=binding.values())

    # Vectorised lookup: one indexer per state dim, sharing the profile's dims
    indexers = {
        d: _to(profile[v], properties[d].attrs["units"]) for d, v in binding.items()
    }
    indexers["w"] = w.m_as(properties["w"].attrs["units"])

    ext = properties["ext"].interp(indexers).values * ext_units
    ssa = properties["ssa"].interp(indexers).values
    amt = profile[amount].values * ureg.Unit(profile[amount].attrs["units"])
    sigma_t = np.nan_to_num((amt * ext).to("1/km"))
    return sigma_t, np.nan_to_num(ssa)


def _to(da: xr.DataArray, units: str) -> xr.DataArray:
    return da.copy(data=ureg.Quantity(da.values, da.attrs["units"]).m_as(units))


# ------------------------------------------------------------------------------
#                                 Self-check
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    # Table: ext linear in reff, constant in veff and w -> exact interpolation
    reff = np.array([5.0, 15.0])
    veff = np.array([0.05, 0.2])
    props = xr.Dataset(
        {
            "ext": (
                ("w", "reff", "veff"),
                np.broadcast_to(reff[None, :, None] / 10.0, (2, 2, 2)).copy(),
                {"units": "km^-1 / (g/m^3)"},
            ),
            "ssa": (("w", "reff", "veff"), np.full((2, 2, 2), 0.9)),
        },
        coords={
            "w": ("w", [500.0, 700.0], {"units": "nm"}),
            "reff": ("reff", reff, {"units": "micron"}),
            "veff": ("veff", veff, {"units": ""}),
        },
    )
    assert state_dims(props) == ("reff", "veff")

    # Profile on a 2×1×1 grid; reff stored in mm under another name
    profile = xr.Dataset(
        {
            "lwc": (("x", "y", "z"), [[[2.0]], [[1.0]]], {"units": "g/m^3"}),
            "r": (("x", "y", "z"), [[[0.010]], [[np.nan]]], {"units": "mm"}),
            "veff": (("x", "y", "z"), [[[0.1]], [[0.1]]], {"units": ""}),
        }
    )
    sigma_t, ssa = eval_sigma_t_albedo(
        profile, props, 550.0 * ureg.nm, state_variables={"reff": "r"}
    )
    # Voxel 0: lwc=2 g/m³, reff=10 µm -> ext=1 km⁻¹/(g/m³) -> σ_t=2 km⁻¹
    # Voxel 1: reff=NaN (empty) -> σ_t=0
    np.testing.assert_allclose(sigma_t.m_as("1/km").ravel(), [2.0, 0.0])
    np.testing.assert_allclose(ssa.ravel(), [0.9, 0.0])
    print("ok")
