from __future__ import annotations

import attrs
import pint

from ._core import Atmosphere
from ..core import traverse
from ..phase import PhaseFunction, RayleighPhaseFunction, phase_function_factory
from ..spectra import AirScatteringCoefficientSpectrum, Spectrum, spectrum_factory
from ...attrs import documented, parse_docs
from ...contexts import KernelContext
from ...kernel import InitParameter, UpdateParameter
from ...spectral.ckd import BinSet
from ...spectral.index import SpectralIndex
from ...spectral.mono import WavelengthSet
from ...units import unit_context_config as ucc
from ...units import unit_context_kernel as uck
from ...validators import has_quantity


@parse_docs
@attrs.define(eq=False, slots=False)
class HomogeneousAtmosphere(Atmosphere):
    """
    Homogeneous atmosphere scene element [``homogeneous``].

    This class builds an atmosphere consisting of a homogeneous medium with
    customizable collision coefficients and phase function.
    """

    sigma_s: Spectrum = documented(
        attrs.field(
            factory=AirScatteringCoefficientSpectrum,
            converter=spectrum_factory.converter("collision_coefficient"),
            validator=[
                attrs.validators.instance_of(Spectrum),
                has_quantity("collision_coefficient"),
            ],
        ),
        doc="Atmosphere scattering coefficient value.\n"
        "\n"
        "Can be initialised with a dictionary processed by "
        ":data:`~eradiate.scenes.spectra.spectrum_factory`.",
        type=":class:`~eradiate.scenes.spectra.Spectrum` or float",
        default=":class:`AirScatteringCoefficientSpectrum() "
        "<.AirScatteringCoefficientSpectrum>`",
    )

    sigma_a: Spectrum = documented(
        attrs.field(
            default=0.0,
            converter=spectrum_factory.converter("collision_coefficient"),
            validator=[
                attrs.validators.instance_of(Spectrum),
                has_quantity("collision_coefficient"),
            ],
        ),
        doc="Atmosphere absorption coefficient value. Defaults disable "
        "absorption.\n"
        "\n"
        "Can be initialised with a dictionary processed by "
        ":data:`~eradiate.scenes.spectra.spectrum_factory`.",
        type=":class:`~eradiate.scenes.spectra.Spectrum`",
        default="0.0 km**-1",
    )

    _phase: PhaseFunction = documented(
        attrs.field(
            factory=lambda: RayleighPhaseFunction(),
            converter=phase_function_factory.convert,
            validator=attrs.validators.instance_of(PhaseFunction),
        ),
        doc="Scattering phase function.\n"
        "\n"
        "Can be initialised with a dictionary processed by "
        ":data:`~eradiate.scenes.phase.phase_function_factory`.",
        type=":class:`~eradiate.scenes.phase.PhaseFunction`",
        default=":class:`RayleighPhaseFunction() <.RayleighPhaseFunction>`",
    )

    def __attrs_post_init__(self) -> None:
        self.update()

    def update(self) -> None:
        # Inherit docstring
        self.phase.id = self.phase_id

    # --------------------------------------------------------------------------
    #                               Properties
    # --------------------------------------------------------------------------

    @property
    def bottom(self) -> pint.Quantity:
        # Inherit docstring
        return self._bottom

    @property
    def top(self) -> pint.Quantity:
        # Inherit docstring
        return self._top

    @property
    def spectral_set(self) -> None | BinSet | WavelengthSet:
        return None

    @property
    def phase(self) -> PhaseFunction:
        # Inherit docstring
        return self._phase

    # --------------------------------------------------------------------------
    #                           Evaluation methods
    # --------------------------------------------------------------------------

    def eval_mfp(self, ctx: KernelContext) -> pint.Quantity:
        # Inherit docstring
        return (
            1.0 / self.eval_sigma_s(ctx.si)
            if self.eval_sigma_s(ctx.si).m != 0.0
            else 1.0 / self.eval_sigma_a(ctx.si)
        )

    def eval_albedo(self, si: SpectralIndex) -> pint.Quantity:
        """
        Return albedo at given spectral index.

        Parameters
        ----------
        si : :class:`.SpectralIndex`
            Spectral index.

        Returns
        -------
        quantity
            Albedo.
        """
        return self.eval_sigma_s(si) / (self.eval_sigma_s(si) + self.eval_sigma_a(si))

    def eval_sigma_a(self, si: SpectralIndex) -> pint.Quantity:
        """
        Return absorption coefficient at given spectral index.

        Parameters
        ----------
        si : :class:`.SpectralIndex`
            Spectral index.

        Returns
        -------
        quantity
            Absorption coefficient.
        """
        return self.sigma_a.eval(si)

    def eval_sigma_s(self, si: SpectralIndex) -> pint.Quantity:
        """
        Return scattering coefficient at given spectral index.

        Parameters
        ----------
        si : :class:`.SpectralIndex`
            Spectral index.

        Returns
        -------
        quantity
            Scattering coefficient.
        """
        return self.sigma_s.eval(si)

    def eval_sigma_t(self, si: SpectralIndex) -> pint.Quantity:
        """
        Return extinction coefficient at given spectral index.

        Parameters
        ----------
        si : :class:`.SpectralIndex`
            Spectral index.

        Returns
        -------
        quantity
            Extinction coefficient.
        """
        return self.eval_sigma_a(si) + self.eval_sigma_s(si)

    # --------------------------------------------------------------------------
    #                       Kernel dictionary generation
    # --------------------------------------------------------------------------

    @property
    def _template_phase(self) -> dict:
        # Inherit docstring
        result, _ = traverse(self.phase)
        return result.data

    @property
    def _template_medium(self) -> dict:
        # Inherit docstring
        return {
            "type": "homogeneous",
            "sigma_t": InitParameter(
                lambda ctx: self.eval_sigma_t(ctx.si).m_as(
                    uck.get("collision_coefficient")
                ),
            ),
            "albedo": InitParameter(
                lambda ctx: self.eval_albedo(ctx.si).m_as(uck.get("albedo"))
            ),
            # Note: "phase" is deliberately unset, this is left to the
            # Atmosphere.template property
        }

    @property
    def _params_medium(self) -> dict[str, UpdateParameter]:
        # Inherit docstring
        return {
            # Note: "value" appears twice because the mi.Spectrum is
            # encapsulated in a mi.ConstVolume
            "sigma_t.value.value": UpdateParameter(
                lambda ctx: self.eval_sigma_t(ctx.si).m_as(
                    uck.get("collision_coefficient")
                ),
                UpdateParameter.Flags.SPECTRAL,
            ),
            "albedo.value.value": UpdateParameter(
                lambda ctx: self.eval_albedo(ctx.si).m_as(uck.get("albedo")),
                UpdateParameter.Flags.SPECTRAL,
            ),
        }

    @property
    def _params_phase(self) -> dict[str, UpdateParameter]:
        # Inherit docstring
        _, params = traverse(self.phase)
        return params.data
