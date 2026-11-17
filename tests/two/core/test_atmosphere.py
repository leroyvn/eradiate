import importlib

import numpy as np
import pytest
import xarray as xr
from pydantic import ValidationError

from eradiate.grid import CartesianGrid
from eradiate.two.core.atmosphere import (
    ArrayDensity,
    Atmosphere,
    HeterogeneousAtmosphere,
    ParticleExtinctionComponent,
    ParticleMSComponent,
    ParticleOTComponent,
    ParticleStateComponent,
    UniformDensity,
)
from eradiate.units import unit_registry as ureg

# Directory name starts with a digit: not importable with a plain statement
helpers = importlib.import_module(
    "tests.01_unit.scenes.atmosphere._particle_state_helpers"
)

GRID = CartesianGrid(
    x_edges=np.array([-1.0, 0.0, 1.0]) * ureg.km,
    y_edges=np.array([-1.0, 1.0]) * ureg.km,
    z_edges=np.array([0.0, 1.0, 2.0]) * ureg.km,
)
STATE_DIMS = {
    "reff": np.array([0.1, 1.0]) * ureg.micron,
    "veff": np.array([0.1, 0.2]) * ureg.dimensionless,
}
PROFILE_VARS = {
    "reff": 0.5 * ureg.micron,
    "veff": 0.15 * ureg.dimensionless,
    "mass_concentration": 2.0 * ureg("g/m^3"),
}


def state_kwargs(state_dims=STATE_DIMS, profile_vars=PROFILE_VARS):
    return {
        "profile": helpers.make_state_profile_dataset(GRID, profile_vars),
        "properties": helpers.make_state_properties_dataset(state_dims),
    }


def field(units, value=0.5):
    return xr.DataArray(
        np.full((2, 2, 1, 2), value),
        dims=("w", "x", "y", "z"),
        coords={"w": ("w", [500.0, 600.0], {"units": "nm"})},
        attrs={"units": units},
    )


# -- Container --------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [{"type": "particle_ot"}, ParticleOTComponent()],
    ids=["dict", "instance"],
)
def test_bare_component_wrapped(value):
    atmosphere = Atmosphere.model_validate(value)
    assert isinstance(atmosphere, HeterogeneousAtmosphere)
    assert isinstance(atmosphere.components["particle_ot"], ParticleOTComponent)


@pytest.mark.parametrize("components", [{}, {"not valid": {"type": "particle_ot"}}])
def test_heterogeneous_invalid_components(components):
    with pytest.raises(ValidationError):
        HeterogeneousAtmosphere(components=components)


# -- Particle OT -------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"ot_ref": [0.1, 0.2]},
        {"bottom": 2.0, "top": 1.0},
        {"w_ref": {"value": 1.0, "units": "s"}},
        {"properties": helpers.make_state_properties_dataset(STATE_DIMS)},
    ],
    ids=["per_column", "extent", "units", "state_dims"],
)
def test_particle_ot_invalid(kwargs):
    with pytest.raises(ValidationError):
        ParticleOTComponent(**kwargs)


def test_particle_ot_dict_quantity():
    component = ParticleOTComponent(top={"value": 2.0, "units": "km"})
    assert component.top == 2.0 * ureg.km


# -- Vertical densities ------------------------------------------------------


def test_density_dispatch_and_default_coords():
    density = ParticleOTComponent(
        density={"type": "array", "values": [1.0, 2.0]}
    ).density
    assert isinstance(density, ArrayDensity)
    np.testing.assert_allclose(density.coords, [0.25, 0.75])


def test_uniform_density_unsorted():
    with pytest.raises(ValidationError):
        UniformDensity(bounds=(1.0, 0.0))


# -- Particle extinction -----------------------------------------------------


def test_particle_extinction():
    ParticleExtinctionComponent(
        sigma_t=field("1/km"), albedo=field(""), phase={"type": "hg"}
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"sigma_t": field("1/km").isel(y=0)},
        {"sigma_t": field("km")},
        {"albedo": field("", value=1.5)},
        {"albedo": field("").isel(z=[0])},
        {"phase": {"g": 0.8}},
    ],
    ids=["dims", "units", "albedo_range", "sizes", "phase"],
)
def test_particle_extinction_invalid(kwargs):
    kwargs = {
        "sigma_t": field("1/km"),
        "albedo": field(""),
        "phase": {"type": "hg"},
        **kwargs,
    }
    with pytest.raises(ValidationError):
        ParticleExtinctionComponent(**kwargs)


# -- Particle state ----------------------------------------------------------


@pytest.mark.parametrize(
    "state_dims",
    [{}, {"reff": STATE_DIMS["reff"]}, STATE_DIMS],
    ids=["0", "1", "2"],
)
def test_particle_state_dims(state_dims):
    ParticleStateComponent(**state_kwargs(state_dims))


@pytest.mark.parametrize(
    "kwargs",
    [
        {**state_kwargs(), "amount": "missing"},
        {**state_kwargs(), "state_variables": {"rh": "reff"}},
        state_kwargs(profile_vars={"mass_concentration": 1.0 * ureg("g/m^3")}),
        state_kwargs(
            state_dims={**STATE_DIMS, "c": np.array([1.0, 2.0]) * ureg.s},
            profile_vars={**PROFILE_VARS, "c": 1.5 * ureg.s},
        ),
    ],
    ids=["amount", "unknown_key", "unbound", "three_dims"],
)
def test_particle_state_invalid(kwargs):
    with pytest.raises(ValidationError):
        ParticleStateComponent(**kwargs)


def test_particle_ms():
    component = ParticleMSComponent(**state_kwargs())
    assert component.amount == "mass_concentration"

    with pytest.raises(ValidationError):
        ParticleMSComponent(**state_kwargs({"reff": STATE_DIMS["reff"]}))


# -- Homogeneous ---------------------------------------------------------------


def test_homogeneous_bare_float():
    atmosphere = Atmosphere.model_validate({"type": "homogeneous", "sigma_s": 1e-2})
    assert atmosphere.sigma_s.value == 1e-2 * ureg("1/m")
    assert atmosphere.sigma_a.value == 0.0 * ureg("1/m")
