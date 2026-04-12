import pint

from .bsdf import BaseBSDF
from .object import Object


class BaseSurface(Object):
    """
    Abstract base class for a uniform flat surface.
    """

    bsdf: BaseBSDF
    elevation: pint.Quantity
