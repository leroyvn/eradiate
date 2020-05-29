import numpy as np

from eradiate.util.units import ureg
from eradiate.util.frame import angles_to_direction


@ureg.wraps(None, (ureg.deg, ureg.deg, None), strict=False)
def directional(zenith=0., azimuth=0., irradiance=1.):
    """Create a dictionary which will instantiate a `directional` Mitsuba plugin
    based on the provided angular geometry.

    Parameter ``zenith`` (float)
        Zenith angle [deg].

    Parameter ``azimuth`` (float)
        Azimuth angle [deg].

    Parameter ``irradiance`` (float or dict)
        Emitted irradiance in the plane orthogonal to the emitter's direction
        [W/m^2/nm].

    Returns → dict
        A dictionary which can be used to instantiate a `directional` Mitsuba
        plugin facing the direction specified by the angular configuration.
    """

    return {
        "type": "directional",
        "direction": list(-angles_to_direction(
            theta=np.deg2rad(zenith),
            phi=np.deg2rad(azimuth)
        )),
        "irradiance":
            {"type": "uniform", "value": irradiance}
            if isinstance(irradiance, float)
            else irradiance
    }


def constant(radiance=1.):
    """Create a dictionary which will instantiate a `constant` Mitsuba plugin.

    Parameter ``radiance`` (float or dict)
        Emitted radiance [W/m^2/sr/nm].

    Returns → dict
        A dictionary which can be used to instantiate a `constant` Mitsuba
        plugin facing the direction specified by the angular configuration.
    """
    return {
        "type": "constant",
        "radiance":
            {"type": "uniform", "value": radiance}
            if isinstance(radiance, float)
            else radiance
    }