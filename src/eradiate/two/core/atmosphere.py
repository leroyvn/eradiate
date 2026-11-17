"""
Atmosphere configuration classes for the configuration layer.

An atmosphere is either a :class:`HomogeneousAtmosphere` or a
:class:`HeterogeneousAtmosphere` holding named :class:`AtmosphereComponent`
instances. Component types are named after their input data. See
``docs/_design_notes/atmosphere.md`` for the design.

These classes describe and validate the configuration only. Radiative property
evaluation is not implemented yet.
"""

from __future__ import annotations

import os
from typing import Any, Callable, Literal

import numpy as np
import pint
import xarray as xr
from axsdb import AbsorptionDatabase, ErrorHandlingConfiguration
from pinttrs.util import ensure_units
from pydantic import ConfigDict, Field, field_validator, model_validator

from . import spectrum
from ._factory import Registry
from .object import Object
from .spectrum import BaseSpectrum, PhysicalQuantity, UniformSpectrum
from ...radprops import ParticleProperties
from ...scenes.atmosphere._particle_profile import ParticleProfile
from ...units import to_quantity, units_compatible
from ...units import unit_context_config as ucc
from ...units import unit_registry as ureg

atmosphere_registry: Registry[Atmosphere] = Registry("atmosphere")
atmosphere_component_registry: Registry[AtmosphereComponent] = Registry(
    "atmosphere_component"
)
vertical_density_registry: Registry[VerticalDensity] = Registry("vertical_density")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _coerce_quantity(
    value: Any, quantity: str, name: str, scalar: bool = False
) -> pint.Quantity:
    """
    Convert ``value`` to a quantity compatible with ``ucc[quantity]``.

    Bare numbers are interpreted in ``ucc[quantity]``; a ``{"value", "units"}``
    dict is accepted. If ``scalar`` is set, arrays are rejected.
    """
    expected = ucc.get(quantity)
    if isinstance(value, dict):
        value = ureg.Quantity(value["value"], value["units"])
    result = ensure_units(value, expected)
    if not units_compatible(result.units, expected):
        raise ValueError(
            f"'{name}' must have units compatible with '{expected}', "
            f"got '{result.units}'"
        )
    if scalar and np.ndim(result.m) != 0:
        raise ValueError(f"'{name}' must be a scalar, got shape {np.shape(result.m)}")
    return result


def _check_phase_spec(value: dict[str, Any]) -> dict[str, Any]:
    # shortcut: phase functions are raw specs until a v2 phase function family
    # exists (atmosphere.md, open questions); the backend interprets them
    if "type" not in value:
        raise ValueError("phase function specification must have a 'type' key")
    return value


# ---------------------------------------------------------------------------
# Thermophysical profile
# ---------------------------------------------------------------------------


class AtmosphericProfile(Object):
    """
    Thin wrapper around a `Joseki <https://joseki.readthedocs.io>`_
    thermophysical profile dataset.

    The wrapped dataset holds altitude ``z`` (levels) as its single dimension
    and, at minimum, pressure ``p``, temperature ``t``, number density ``n`` and
    per-molecule mole fractions ``x_M``. Query methods return :class:`pint.Quantity`
    values so callers do not have to reach into the xarray layer.

    Parameters
    ----------
    data : Dataset or path-like or dict
        * :class:`xarray.Dataset` — used as-is.
        * path-like — loaded from a NetCDF file via :func:`joseki.load_dataset`.
        * dict — forwarded to :func:`joseki.make` as keyword arguments.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    data: xr.Dataset

    @field_validator("data", mode="before")
    @classmethod
    def _coerce_data(cls, value: Any) -> xr.Dataset:
        import joseki

        if isinstance(value, xr.Dataset):
            ds = value
        elif isinstance(value, (os.PathLike, str)):
            ds = joseki.load_dataset(value)
        elif isinstance(value, dict):
            ds = joseki.make(**value)
        else:
            raise TypeError(
                f"invalid type for 'data': {type(value)} "
                "(expected Dataset, path-like or dict)"
            )

        if not ds.joseki.is_valid:
            raise ValueError("'data' is not a valid Joseki thermophysical profile")
        return ds

    # -- Serialization ------------------------------------------------------

    @classmethod
    def from_netcdf(cls, path: str | os.PathLike) -> AtmosphericProfile:
        """Load a profile from a NetCDF file."""
        return cls(data=path)

    def to_netcdf(self, path: str | os.PathLike) -> None:
        """Write the wrapped profile to a NetCDF file."""
        self.data.to_netcdf(path)

    # -- Thermophysical queries ---------------------------------------------

    @property
    def z(self) -> pint.Quantity:
        """Altitude levels."""
        return to_quantity(self.data.z)

    @property
    def pressure(self) -> pint.Quantity:
        """Pressure at each level."""
        return to_quantity(self.data.p)

    @property
    def temperature(self) -> pint.Quantity:
        """Temperature at each level."""
        return to_quantity(self.data.t)

    @property
    def number_density(self) -> pint.Quantity:
        """Air number density at each level."""
        return to_quantity(self.data.n)

    @property
    def molecules(self) -> list[str]:
        """Molecules described by the profile."""
        return list(self.data.joseki.molecules)

    def mole_fraction(self, molecule: str) -> pint.Quantity:
        """Mole fraction of ``molecule`` at each level."""
        return to_quantity(self.data[f"x_{molecule}"])

    def column_number_density(self, molecule: str) -> pint.Quantity:
        """Column number density (integrated over altitude) of ``molecule``."""
        return self.data.joseki.column_number_density[molecule]

    def column_mass_density(self, molecule: str) -> pint.Quantity:
        """Column mass density (integrated over altitude) of ``molecule``."""
        return self.data.joseki.column_mass_density[molecule]

    def interp(
        self, z_new: pint.Quantity, method: str = "linear"
    ) -> AtmosphericProfile:
        """Interpolate the profile onto a new altitude grid ``z_new``."""
        from joseki.profiles.core import interp

        return AtmosphericProfile(
            data=interp(self.data, z_new=z_new, method={"default": method})
        )


# ---------------------------------------------------------------------------
# Vertical densities
# ---------------------------------------------------------------------------


class VerticalDensity(Object):
    """
    Abstract base class for the normalised vertical shape of the particle
    number in a :class:`ParticleOTComponent`.

    Densities are defined on the normalised altitude :math:`x \\in [0, 1]`,
    mapped to the ``[bottom, top]`` interval of the component.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @model_validator(mode="wrap")
    @classmethod
    def _dispatch(cls, value, handler, info):
        if cls is not VerticalDensity:
            return handler(value)
        return vertical_density_registry.dispatch(value, handler, VerticalDensity)


class UniformDensity(VerticalDensity):
    """
    Uniform density on ``[bounds[0], bounds[1]]``, zero elsewhere.
    """

    type: Literal["uniform"] = "uniform"
    bounds: tuple[float, float] = (0.0, 1.0)

    @field_validator("bounds")
    @classmethod
    def _check_bounds(cls, value: tuple[float, float]) -> tuple[float, float]:
        if value[1] <= value[0]:
            raise ValueError("'bounds' must be sorted in ascending order")
        return value


class ExponentialDensity(VerticalDensity):
    """
    Exponential density :math:`x \\mapsto \\lambda e^{-\\lambda x} / (1 - e^{-\\lambda})`,
    with :math:`\\lambda` = ``rate``.
    """

    type: Literal["exponential"] = "exponential"
    rate: float = Field(default=5.0, gt=0.0)


class GaussianDensity(VerticalDensity):
    """
    Gaussian density with mean ``mean`` and standard deviation ``std``.
    """

    type: Literal["gaussian"] = "gaussian"
    mean: float = 0.5
    std: float = Field(default=0.5 / 3.0, gt=0.0)


class ArrayDensity(VerticalDensity):
    """
    Density interpolated from a 1D array of values.

    Parameters
    ----------
    values : array-like
        Density values, at least 2.

    coords : array-like, optional
        Normalised altitudes of ``values``, same shape. Defaults to the cell
        centres of a regular grid on [0, 1].

    method : str, optional
        Interpolation method (see :class:`scipy.interpolate.interp1d`, *kind*).

    extrapolate : {"zero", "nearest", "method", "nan"}, optional
        Behaviour outside ``[coords[0], coords[-1]]``.
    """

    type: Literal["array"] = "array"
    values: np.ndarray
    coords: np.ndarray | None = None
    method: Literal[
        "linear",
        "nearest",
        "nearest-up",
        "zero",
        "slinear",
        "quadratic",
        "cubic",
        "previous",
        "next",
    ] = "linear"
    extrapolate: Literal["zero", "nearest", "method", "nan"] = "zero"

    @field_validator("values", "coords", mode="before")
    @classmethod
    def _coerce_array(cls, value: Any) -> np.ndarray | None:
        return None if value is None else np.asarray(value, dtype=float)

    @model_validator(mode="after")
    def _check_shapes(self) -> ArrayDensity:
        if self.values.ndim != 1 or self.values.size < 2:
            raise ValueError("'values' must be a 1D array with at least 2 elements")
        if self.coords is None:
            edges = np.linspace(0.0, 1.0, self.values.size + 1)
            self.coords = 0.5 * (edges[:-1] + edges[1:])
        elif self.coords.shape != self.values.shape:
            raise ValueError("'coords' and 'values' must have the same shape")
        return self


class InterpolatorDensity(VerticalDensity):
    """
    Density evaluated by a user callable ``f(x: ArrayLike) -> ndarray``,
    typically a :class:`scipy.interpolate.interp1d`. Does not serialise.
    """

    type: Literal["interpolator"] = "interpolator"
    interpolator: Callable[[np.typing.ArrayLike], np.ndarray]


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------


class AtmosphereComponent(Object):
    """
    Abstract base class for atmosphere components.

    A component is a named constituent of a :class:`HeterogeneousAtmosphere`.
    It stores no geometry.

    Parameters
    ----------
    has_absorption : bool, optional
        If ``False``, the absorption coefficient is set to 0.

    has_scattering : bool, optional
        If ``False``, the scattering coefficient is set to 0.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    has_absorption: bool = True
    has_scattering: bool = True

    @model_validator(mode="wrap")
    @classmethod
    def _dispatch(cls, value, handler, info):
        if cls is not AtmosphereComponent:
            return handler(value)
        return atmosphere_component_registry.dispatch(
            value, handler, AtmosphereComponent
        )

    @model_validator(mode="after")
    def _check_switches(self) -> AtmosphereComponent:
        if not (self.has_absorption or self.has_scattering):
            raise ValueError(
                "at least one of 'has_absorption' and 'has_scattering' must be True"
            )
        return self


def _default_profile() -> AtmosphericProfile:
    return AtmosphericProfile(
        data={
            "identifier": "afgl_1986-us_standard",
            "z": np.linspace(0.0, 120.0, 121) * ureg.km,
            "additional_molecules": False,
        }
    )


def _default_absdb() -> AbsorptionDatabase:
    from ...radprops import get_default_absdb

    return get_default_absdb()


class MolecularComponent(AtmosphereComponent):
    """
    Molecular (gas-phase) atmosphere component [``molecular``].

    Parameters
    ----------
    profile : AtmosphericProfile or Dataset or path-like or dict, optional
        Thermophysical profile. A non-:class:`AtmosphericProfile` value is
        passed as :attr:`AtmosphericProfile.data`. Default: AFGL 1986 US
        Standard, 0 to 120 km, 1 km resolution.

    properties : AbsorptionDatabase or str or path-like or dict, optional
        Absorption cross-section database. Default: the database returned by
        :func:`.get_default_absdb`.

    rayleigh_depolarization : float or array-like or {"bates", "bodhaine"}, optional
        Depolarization factor of the Rayleigh phase function: a value, one
        value per layer, or the name of the formula computing it from the
        profile.

    error_handler_config : ErrorHandlingConfiguration or dict, optional
        Absorption database error handling.
    """

    type: Literal["molecular"] = "molecular"
    profile: AtmosphericProfile = Field(default_factory=_default_profile)
    properties: AbsorptionDatabase = Field(default_factory=_default_absdb)
    rayleigh_depolarization: np.ndarray | Literal["bates", "bodhaine"] = Field(
        default_factory=lambda: np.array(0.0)
    )
    error_handler_config: ErrorHandlingConfiguration | None = None

    @field_validator("profile", mode="before")
    @classmethod
    def _coerce_profile(cls, value: Any) -> AtmosphericProfile:
        if isinstance(value, AtmosphericProfile):
            return value
        return AtmosphericProfile(data=value)

    @field_validator("properties", mode="before")
    @classmethod
    def _coerce_properties(cls, value: Any) -> AbsorptionDatabase:
        from ...converters import convert_absdb

        return convert_absdb(value)

    @field_validator("rayleigh_depolarization", mode="before")
    @classmethod
    def _coerce_depolarization(cls, value: Any) -> np.ndarray | str:
        return value if isinstance(value, str) else np.asarray(value, dtype=float)

    @field_validator("error_handler_config", mode="before")
    @classmethod
    def _coerce_error_handler_config(cls, value: Any):
        return None if value is None else ErrorHandlingConfiguration.convert(value)


class ParticleComponent(AtmosphereComponent):
    """
    Abstract base class for particle components.

    Parameters
    ----------
    force_polarized_phase : bool, optional
        If ``True``, use a polarized phase function even if the properties
        only provide its (1, 1) element.
    """

    force_polarized_phase: bool = False


def _coerce_properties(value: Any) -> ParticleProperties:
    return ParticleProperties.convert(value)


class ParticleOTComponent(ParticleComponent):
    """
    Particle component parametrized by an optical thickness [``particle_ot``].

    The optical thickness ``ot_ref`` at ``w_ref`` is distributed between
    ``bottom`` and ``top`` following ``density``. All scalar: a horizontally
    varying optical thickness is a :class:`ParticleExtinctionComponent`.

    Parameters
    ----------
    bottom, top : quantity or float, optional
        Vertical extent. Default: 0 and 1 km.

    density : VerticalDensity or dict, optional
        Normalised vertical shape. Default: uniform.

    ot_ref : quantity or float, optional
        Extinction optical thickness at ``w_ref``. Default: 0.2.

    w_ref : quantity or float, optional
        Reference wavelength. Default: 550 nm.

    properties : ParticleProperties or Dataset or path-like or str, optional
        Single-scattering table in the ``prt_core_v1`` format, without state
        dimension. Default: ``"govaerts_2021-continental"``.
    """

    type: Literal["particle_ot"] = "particle_ot"
    bottom: pint.Quantity = Field(default_factory=lambda: 0.0 * ureg.km)
    top: pint.Quantity = Field(default_factory=lambda: 1.0 * ureg.km)
    density: VerticalDensity = Field(default_factory=UniformDensity)
    ot_ref: pint.Quantity = Field(default_factory=lambda: 0.2 * ureg.dimensionless)
    w_ref: pint.Quantity = Field(default_factory=lambda: 550.0 * ureg.nm)
    properties: ParticleProperties = Field(
        default_factory=lambda: ParticleProperties.convert("govaerts_2021-continental")
    )

    @field_validator("bottom", "top", mode="before")
    @classmethod
    def _coerce_length(cls, value: Any, info) -> pint.Quantity:
        return _coerce_quantity(value, "length", info.field_name, scalar=True)

    @field_validator("ot_ref", mode="before")
    @classmethod
    def _coerce_ot_ref(cls, value: Any) -> pint.Quantity:
        result = _coerce_quantity(value, "dimensionless", "ot_ref", scalar=True)
        if result.m < 0.0:
            raise ValueError("'ot_ref' must be positive or zero")
        return result

    @field_validator("w_ref", mode="before")
    @classmethod
    def _coerce_w_ref(cls, value: Any) -> pint.Quantity:
        result = _coerce_quantity(value, "wavelength", "w_ref", scalar=True)
        if result.m <= 0.0:
            raise ValueError("'w_ref' must be strictly positive")
        return result

    @field_validator("properties", mode="before")
    @classmethod
    def _coerce_properties(cls, value: Any) -> ParticleProperties:
        return _coerce_properties(value)

    @field_validator("properties")
    @classmethod
    def _check_properties(cls, value: ParticleProperties) -> ParticleProperties:
        if value.state_dims:
            raise ValueError(
                f"'properties' must have no state dimension, got {value.state_dims!r}; "
                "use 'particle_state' for a spatially varying composition"
            )
        return value

    @model_validator(mode="after")
    def _check_extent(self) -> ParticleOTComponent:
        if self.bottom >= self.top:
            raise ValueError("'bottom' must be lower than 'top'")
        return self


_EXTINCTION_DIMS = {"w", "x", "y", "z"}


class ParticleExtinctionComponent(ParticleComponent):
    """
    Particle component parametrized by extinction coefficient and albedo
    fields [``particle_extinction``].

    Parameters
    ----------
    sigma_t, albedo : DataArray or path-like
        Extinction coefficient and single-scattering albedo, with dimensions
        exactly ``w``, ``x``, ``y``, ``z`` (any order) and a ``units``
        attribute. A path is loaded with :func:`xarray.load_dataarray`. Both
        must have the same sizes; albedo values lie in [0, 1].

    w_out_of_bounds : {"raise", "extrapolate"}, optional
        Behaviour outside the ``w`` range: raise, or hold the edge value.

    phase : dict
        Phase function specification, *e.g.* ``{"type": "hg", "g": 0.85}``.
    """

    type: Literal["particle_extinction"] = "particle_extinction"
    sigma_t: xr.DataArray
    albedo: xr.DataArray
    w_out_of_bounds: Literal["raise", "extrapolate"] = "raise"
    phase: dict[str, Any]

    @field_validator("sigma_t", "albedo", mode="before")
    @classmethod
    def _load(cls, value: Any) -> xr.DataArray:
        if isinstance(value, (str, os.PathLike)):
            return xr.load_dataarray(value)
        return value

    @field_validator("sigma_t", "albedo")
    @classmethod
    def _check_array(cls, value: xr.DataArray, info) -> xr.DataArray:
        name = info.field_name
        if set(value.dims) != _EXTINCTION_DIMS or value.ndim != 4:
            raise ValueError(
                f"'{name}' dimensions must be exactly 'w', 'x', 'y', 'z', "
                f"got {value.dims}"
            )
        if "units" not in value.attrs:
            raise ValueError(f"'{name}' has no 'units' attribute")
        expected = "collision_coefficient" if name == "sigma_t" else "dimensionless"
        _coerce_quantity(to_quantity(value), expected, name)
        return value

    @field_validator("albedo")
    @classmethod
    def _check_albedo_range(cls, value: xr.DataArray) -> xr.DataArray:
        if np.any((value.values < 0.0) | (value.values > 1.0)):
            raise ValueError("'albedo' values must lie in [0, 1]")
        return value

    @field_validator("phase")
    @classmethod
    def _check_phase(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _check_phase_spec(value)

    @model_validator(mode="after")
    def _check_sizes(self) -> ParticleExtinctionComponent:
        if dict(self.sigma_t.sizes) != dict(self.albedo.sizes):
            raise ValueError(
                "'sigma_t' and 'albedo' must have the same sizes, got "
                f"{dict(self.sigma_t.sizes)} and {dict(self.albedo.sizes)}"
            )
        return self


class ParticleStateComponent(ParticleComponent):
    """
    Particle component driven by a state profile [``particle_state``].

    ``properties`` is a single-scattering table indexed by wavelength and 0 to
    2 state dimensions. Each state dimension is bound to a ``profile`` variable;
    the ``amount`` variable scales the per-unit-amount extinction.

    Parameters
    ----------
    profile : ParticleProfile or Dataset or path-like
        State profile in the ``ppr_core_v1`` format.

    properties : ParticleProperties or Dataset or path-like or str
        Single-scattering table in the ``prt_core_v1`` format, with at most 2
        state dimensions.

    amount : str, optional
        Profile variable scaling the per-unit-amount extinction. If unset,
        selected from the units of the profile variables.

    state_variables : dict[str, str], optional
        Mapping from a ``properties`` state dimension to the profile variable
        supplying its value. Unlisted dimensions bind to the same-named
        variable.

    phase : dict, optional
        Phase function specification replacing the one built from
        ``properties``.
    """

    type: Literal["particle_state"] = "particle_state"
    profile: ParticleProfile
    properties: ParticleProperties
    amount: str | None = None
    state_variables: dict[str, str] = Field(default_factory=dict)
    phase: dict[str, Any] | None = None

    @field_validator("profile", mode="before")
    @classmethod
    def _coerce_profile(cls, value: Any) -> ParticleProfile:
        return ParticleProfile.convert(value)

    @field_validator("properties", mode="before")
    @classmethod
    def _coerce_properties(cls, value: Any) -> ParticleProperties:
        return _coerce_properties(value)

    @field_validator("properties")
    @classmethod
    def _check_state_dims(cls, value: ParticleProperties) -> ParticleProperties:
        if len(value.state_dims) > 2:
            raise ValueError(
                "'properties' must have at most 2 state dimensions, "
                f"got {value.state_dims!r}"
            )
        return value

    @field_validator("phase")
    @classmethod
    def _check_phase(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return None if value is None else _check_phase_spec(value)

    @model_validator(mode="after")
    def _check_binding(self) -> ParticleStateComponent:
        state_dims = self.properties.state_dims
        variables = self.profile.variables

        unknown = sorted(set(self.state_variables) - set(state_dims))
        if unknown:
            raise ValueError(
                f"'state_variables' keys {unknown} are not state dimensions of "
                f"'properties' {state_dims!r}"
            )

        missing = [
            self.state_variables.get(d, d)
            for d in state_dims
            if self.state_variables.get(d, d) not in variables
        ]
        if missing:
            raise ValueError(f"'profile' has no variable(s) {missing}")

        if self.amount is not None and self.amount not in variables:
            raise ValueError(
                f"'profile' has no amount variable '{self.amount}' "
                f"(available: {list(variables)})"
            )
        return self


class ParticleMSComponent(ParticleStateComponent):
    """
    Particle component driven by a mass concentration and particle size
    distribution parameters (effective radius and variance) [``particle_ms``].

    Preset of :class:`ParticleStateComponent`: ``properties`` must have the
    state dimensions ``(reff, veff)`` (``prt_ms_v1``); with default bindings,
    ``profile`` follows ``ppr_ms_v1``.
    """

    type: Literal["particle_ms"] = "particle_ms"
    amount: str | None = "mass_concentration"
    state_variables: dict[str, str] = Field(
        default_factory=lambda: {"reff": "reff", "veff": "veff"}
    )

    @field_validator("properties")
    @classmethod
    def _check_ms_dims(cls, value: ParticleProperties) -> ParticleProperties:
        if value.state_dims != ("reff", "veff"):
            raise ValueError(
                "'properties' must have state dimensions ('reff', 'veff'), "
                f"got {value.state_dims!r}"
            )
        return value


# ---------------------------------------------------------------------------
# Atmospheres
# ---------------------------------------------------------------------------


class Atmosphere(Object):
    """
    Abstract base class for atmospheres.

    A bare component (instance, or dict whose ``type`` is a component type) is
    wrapped into a single-component :class:`HeterogeneousAtmosphere`, under a
    name equal to its type.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @model_validator(mode="wrap")
    @classmethod
    def _dispatch(cls, value, handler, info):
        if cls is not Atmosphere:
            return handler(value)

        if isinstance(value, AtmosphereComponent):
            value = {"type": "heterogeneous", "components": {value.type: value}}
        elif (
            isinstance(value, dict)
            and value.get("type") in atmosphere_component_registry
        ):
            value = {"type": "heterogeneous", "components": {value["type"]: value}}

        return atmosphere_registry.dispatch(value, handler, Atmosphere)


class HomogeneousAtmosphere(Atmosphere):
    """
    Homogeneous atmosphere [``homogeneous``].

    Parameters
    ----------
    sigma_s : Spectrum or float
        Scattering coefficient.

    sigma_a : Spectrum or float, optional
        Absorption coefficient. Default: 0.

    phase : dict, optional
        Phase function specification. Default: ``{"type": "rayleigh"}``.
    """

    type: Literal["homogeneous"] = "homogeneous"
    sigma_s: BaseSpectrum
    sigma_a: BaseSpectrum = Field(
        default_factory=lambda: UniformSpectrum(
            value=0.0, quantity="collision_coefficient"
        )
    )
    phase: dict[str, Any] = Field(default_factory=lambda: {"type": "rayleigh"})

    @field_validator("sigma_s", "sigma_a", mode="before")
    @classmethod
    def _coerce_spectrum(cls, value: Any) -> Any:
        if isinstance(value, dict):  # Resolved by the BaseSpectrum dispatch
            return value
        return spectrum.convert(value, quantity="collision_coefficient")

    @field_validator("sigma_s", "sigma_a")
    @classmethod
    def _check_spectrum(cls, value: BaseSpectrum, info) -> BaseSpectrum:
        if value.quantity != PhysicalQuantity.COLLISION_COEFFICIENT:
            raise ValueError(
                f"'{info.field_name}' must be a collision coefficient spectrum, "
                f"got quantity '{value.quantity}'"
            )
        return value

    @field_validator("phase")
    @classmethod
    def _check_phase(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _check_phase_spec(value)


class HeterogeneousAtmosphere(Atmosphere):
    """
    Heterogeneous atmosphere [``heterogeneous``].

    Parameters
    ----------
    components : dict[str, AtmosphereComponent or dict]
        Named components. Names must be valid Python identifiers, since a
        backend derives object identifiers from them.

    scale : float, optional
        If set, the extinction coefficient of every component is multiplied
        by this value.
    """

    type: Literal["heterogeneous"] = "heterogeneous"
    components: dict[str, AtmosphereComponent]
    scale: float | None = Field(default=None, gt=0.0)

    @field_validator("components")
    @classmethod
    def _check_components(
        cls, value: dict[str, AtmosphereComponent]
    ) -> dict[str, AtmosphereComponent]:
        if not value:
            raise ValueError("'components' must not be empty")
        invalid = [name for name in value if not name.isidentifier()]
        if invalid:
            raise ValueError(
                f"component names must be valid identifiers, got {invalid}"
            )
        return value


# ---------------------------------------------------------------------------
# Registry population
# ---------------------------------------------------------------------------

atmosphere_registry.register("homogeneous", HomogeneousAtmosphere)
atmosphere_registry.register("heterogeneous", HeterogeneousAtmosphere)

atmosphere_component_registry.register("molecular", MolecularComponent)
atmosphere_component_registry.register("particle_ot", ParticleOTComponent)
atmosphere_component_registry.register(
    "particle_extinction", ParticleExtinctionComponent
)
atmosphere_component_registry.register("particle_state", ParticleStateComponent)
atmosphere_component_registry.register("particle_ms", ParticleMSComponent)

vertical_density_registry.register("uniform", UniformDensity)
vertical_density_registry.register("exponential", ExponentialDensity)
vertical_density_registry.register("gaussian", GaussianDensity)
vertical_density_registry.register("array", ArrayDensity)
vertical_density_registry.register("interpolator", InterpolatorDensity)
