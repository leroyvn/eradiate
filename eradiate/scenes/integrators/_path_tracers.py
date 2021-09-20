import typing as t

import attr

from ._core import Integrator, integrator_factory
from ..core import KernelDict
from ...attrs import documented, parse_docs
from ...contexts import KernelDictContext


@parse_docs
@attr.s
class MonteCarloIntegrator(Integrator):
    """
    Base class for integrator elements wrapping kernel classes
    deriving from
    :class:`mitsuba.render.MonteCarloIntegrator`.

    .. warning:: This class should not be instantiated.
    """

    max_depth: t.Optional[int] = documented(
        attr.ib(default=None, converter=attr.converters.optional(int)),
        doc="Longest path depth in the generated measure data (where -1 corresponds "
        "to ∞). A value of 1 will display only visible emitters. 2 will lead to "
        "direct illumination (no multiple scattering), etc. If unset, "
        "the kernel default value (-1) will be used.",
        type="int, optional",
    )

    rr_depth: t.Optional[int] = documented(
        attr.ib(default=None, converter=attr.converters.optional(int)),
        doc="Minimum path depth after which the implementation will start to use the "
        "Russian roulette path termination criterion. If unset, "
        "the kernel default value (5) will be used.",
        type="int, optional",
    )

    hide_emitters: t.Optional[bool] = documented(
        attr.ib(default=None, converter=attr.converters.optional(bool)),
        doc="Hide directly visible emitters. If unset, "
        "the kernel default value (``false``) will be used.",
        type="bool, optional",
    )

    def kernel_dict(self, ctx: KernelDictContext) -> KernelDict:
        result = {self.id: {}}

        if self.max_depth is not None:
            result[self.id]["max_depth"] = self.max_depth
        if self.rr_depth is not None:
            result[self.id]["rr_depth"] = self.rr_depth
        if self.hide_emitters is not None:
            result[self.id]["hide_emitters"] = self.hide_emitters

        return KernelDict(result)


@integrator_factory.register(type_id="path")
@parse_docs
@attr.s
class PathIntegrator(MonteCarloIntegrator):
    """
    A thin interface to the `path tracer kernel plugin <https://eradiate-kernel.readthedocs.io/en/latest/generated/plugins.html#path-tracer-path>`_.

    This integrator samples paths using random walks starting from the sensor.
    It supports multiple scattering and does not account for volume
    interactions.
    """

    def kernel_dict(self, ctx: KernelDictContext) -> KernelDict:
        result = super(PathIntegrator, self).kernel_dict(ctx)
        result[self.id]["type"] = "path"
        return result


@integrator_factory.register(type_id="volpath")
@parse_docs
@attr.s
class VolPathIntegrator(MonteCarloIntegrator):
    """
    A thin interface to the volumetric path tracer kernel plugin.

    This integrator samples paths using random walks starting from the sensor.
    It supports multiple scattering and accounts for volume interactions.
    """

    def kernel_dict(self, ctx: KernelDictContext) -> KernelDict:
        result = super(VolPathIntegrator, self).kernel_dict(ctx)
        result[self.id]["type"] = "volpath"
        return result


@integrator_factory.register(type_id="volpathmis")
@parse_docs
@attr.s
class VolPathMISIntegrator(MonteCarloIntegrator):
    """
    A thin interface to the volumetric path tracer (with spectral multiple
    importance sampling) kernel plugin
    :cite:`Miller2019NullscatteringPathIntegral`.
    """

    use_spectral_mis = attr.ib(default=None, converter=attr.converters.optional(bool))

    def kernel_dict(self, ctx: KernelDictContext) -> KernelDict:
        result = super(VolPathMISIntegrator, self).kernel_dict(ctx)

        result[self.id]["type"] = "volpathmis"
        if self.use_spectral_mis is not None:
            result[self.id]["use_spectral_mis"] = self.use_spectral_mis

        return result
