import drjit as dr
import mitsuba as mi
import numpy as np
import pytest

from eradiate import KernelContext
from eradiate.two.spectra import InterpolatedSpectrum
from eradiate.units import unit_registry as ureg


@pytest.mark.parametrize(
    "wavelengths, values",
    [
        (
            np.linspace(300, 400, 11) * ureg.nm,
            np.linspace(0, 1, 11) * ureg.dimensionless,
        ),
        (
            np.linspace(0.3, 0.4, 11) * ureg.micron,
            np.linspace(0, 1, 11) * ureg.dimensionless,
        ),
        (
            np.linspace(300, 400, 11),
            np.linspace(0, 1, 11),
        ),
    ],
    ids=["nm", "micron", "nounits"],
)
def test_interpolated_spectrum_construct(mode_mono, wavelengths, values):
    s = InterpolatedSpectrum(wavelengths=wavelengths, values=values)

    # wavelengths are converted to config units
    expected = np.linspace(300, 400, 11) * ureg.nm
    np.testing.assert_allclose(s.wavelengths.m, expected.m)
    assert s.wavelengths.u == expected.u

    # values are converted to config units
    expected = np.linspace(0, 1, 11) * ureg.dimensionless
    np.testing.assert_allclose(s.values.m, expected.m)
    assert s.values.u == expected.u


@pytest.mark.parametrize(
    "wavelengths",
    [[300, 350, 400] * ureg.nm, [300, 350, 400]],
    ids=["nm", "nounits"],
)
def test_interpolated_spectrum_eval_mono(mode_mono, wavelengths):
    s = InterpolatedSpectrum(
        wavelengths=np.linspace(300, 400, 11) * ureg.nm,
        values=np.linspace(0, 1, 11) * ureg.dimensionless,
    )

    expected = [0, 0.5, 1] * ureg.dimensionless
    actual = s.eval_mono(wavelengths)
    np.testing.assert_allclose(actual.m, expected.m)


def test_interpolated_spectrum_update(mode_mono):
    s = InterpolatedSpectrum(
        wavelengths=np.linspace(300, 400, 11) * ureg.nm,
        values=np.linspace(0, 1, 11) * ureg.dimensionless,
    )

    for w in [0.3, 0.35, 0.4] * ureg.um:
        ctx = KernelContext({"w": w})
        s.update(ctx)

        si = dr.zeros(mi.SurfaceInteraction3f)
        expected = s.eval(ctx.si).m
        assert dr.allclose(s().eval(si), expected), f"failed for {w = }"
