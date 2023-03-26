import pint

from .units import unit_registry as ureg

#: Earth radius
EARTH_RADIUS: pint.Quantity = 6378.1 * ureg.km
