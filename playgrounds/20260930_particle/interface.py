"""
Dict interface examples for the proposed atmosphere component system.

See proposal.md §5. The dicts target the *proposed* API: they build without
error but are not accepted by the current code.
"""

import numpy as np
import xarray as xr

from eradiate.units import unit_registry as ureg

# ------------------------------------------------------------------------------
#                        One example per component type
# ------------------------------------------------------------------------------

molecular = {
    "type": "molecular",
    "profile": {"identifier": "afgl_1986-us_standard"},  # joseki.make() kwargs
    "properties": "monotropa",  # absorption database
    "rayleigh_depolarization": "bates",
}

# AOT-driven: all inputs scalar, vertical shape 1D
aerosols = {
    "type": "particle_aot",
    "bottom": 0.0 * ureg.km,
    "top": 2.0 * ureg.km,
    "density": {"type": "exponential", "rate": 5.0},
    "aot_ref": 0.2,
    "w_ref": 550.0 * ureg.nm,
    "properties": "govaerts_2021-continental",  # aer_core_v2 (state-free)
}

# Extinction-driven: sigma_t and albedo fully user-supplied.
# Dims ⊆ (w, x, y, z), missing dims are broadcast; coords are cell centres.
x = np.linspace(-4.5, 4.5, 10)
y = np.linspace(-4.5, 4.5, 10)
z = np.linspace(0.25, 2.75, 6)
w = np.array([400.0, 550.0, 700.0])
sigma_t = xr.DataArray(
    np.full((len(w), len(x), len(y), len(z)), 0.1),
    dims=("w", "x", "y", "z"),
    coords={
        "w": ("w", w, {"units": "nm"}),
        "x": ("x", x, {"units": "km"}),
        "y": ("y", y, {"units": "km"}),
        "z": ("z", z, {"units": "km"}),
    },
    attrs={"units": "km^-1"},
)
albedo = xr.DataArray(  # spectrally and horizontally constant: z only
    np.full(len(z), 0.9),
    dims=("z",),
    coords={"z": ("z", z, {"units": "km"})},
    attrs={"units": "dimensionless"},
)
smoke = {
    "type": "particle_extinction",
    "sigma_t": sigma_t,
    "albedo": albedo,
    "phase": {"type": "hg", "g": 0.7},  # or a dataset / keyword: phase only
}

# State-driven, generic core: state dims read from `properties`,
# bound to profile variables by name (remapped here), amount picked by units
aerosols_wet = {
    "type": "particle_state",
    "profile": "aerosol_rh-ppr_v1.nc",  # has variables: number_density, relhum
    "properties": "sulfate_rh-prt_v1.nc",  # dims: (w, rh, ...)
    "state_variables": {"rh": "relhum"},  # table dim -> profile variable
    # "amount": "number_density",  # optional: unique unit match by default
}

# State-driven, preset: binding and required variables fixed
cloud = {
    "type": "particle_psd",  # state (reff, veff), mass concentration
    "profile": "tutorials/particle_field/shallow_convection-ppr_v1.nc",
    "properties": "tutorials/particle_field/watercloud_670-prt_v1.nc",
}

# ------------------------------------------------------------------------------
#                              Container
# ------------------------------------------------------------------------------

atmosphere = {
    "type": "heterogeneous",
    # Atmosphere-wide settings live here only; components have none of them
    "extremum_resolution": (32, 32, 32),
    "use_mis": True,
    "components": {  # names become kernel ids: f"{atmosphere_id}_{name}"
        "molecular": molecular,
        "aerosols": aerosols,
        "smoke": smoke,
        "cloud": cloud,
    },
}

# Shorthand: a bare component is wrapped in a single-component container,
# equivalent to {"type": "heterogeneous", "components": {"molecular": {...}}}
atmosphere_short = {"type": "molecular"}

# ------------------------------------------------------------------------------
#                  Legacy forms (main) and their translation
# ------------------------------------------------------------------------------

legacy = {
    "type": "heterogeneous",
    "molecular_atmosphere": {"thermoprops": ..., "absorption_data": "monotropa"},
    "particle_layers": [
        {
            "type": "particle_layer",
            "tau_ref": 0.2,
            "distribution": "exponential",
            "particle_properties": "govaerts_2021-continental",
        }
    ],
}
translated = {
    "type": "heterogeneous",
    "components": {
        "molecular": {
            "type": "molecular",
            "profile": ...,
            "properties": "monotropa",
        },
        "particle_layer": {
            "type": "particle_aot",
            "aot_ref": 0.2,
            "density": "exponential",
            "properties": "govaerts_2021-continental",
        },
    },
}
