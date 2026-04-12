from .object import Object
from .spectrum import BaseSpectrum


class BaseBSDF(Object):
    pass


class DiffuseBSDF(BaseBSDF):
    reflectance: BaseSpectrum
