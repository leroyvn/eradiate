from __future__ import annotations

import importlib
import typing as t
from abc import ABC, abstractmethod
from typing import Mapping, Sequence

import attrs
import mitsuba as mi
import numpy as np
import pint
import pinttr
from pinttr.util import ensure_units

from .._factory import Factory
from ..attrs import define, documented, frozen
from ..kernel import KernelDictionary, KernelSceneParameterMap
from ..units import unit_context_config as ucc
from ..units import unit_registry as ureg

# ------------------------------------------------------------------------------
#                           Scene element interface
# ------------------------------------------------------------------------------


@define(eq=False, slots=False)
class SceneElement(ABC):
    """
    Abstract base class for all scene elements.

    Warnings
    --------
    All subclasses *must* have a hash, thus ``eq`` must be ``False`` (see
    `attrs docs on hashing <https://www.attrs.org/en/stable/hashing.html>`_
    for a complete explanation). This is required in order to make it possible
    to use caching decorators on instance methods.

    Notes
    -----
    The default implementation of ``__attrs_post_init__()`` executes the
    :meth:`update` method.
    """

    id: str | None = documented(
        attrs.field(
            default=None,
            validator=attrs.validators.optional(attrs.validators.instance_of(str)),
        ),
        doc="Identifier of the current scene element.",
        type="str or None",
        init_type="str, optional",
    )

    def __attrs_post_init__(self):
        self.update()

    @abstractmethod
    def kpmap(self) -> KernelSceneParameterMap:
        """
        Returns
        -------
        .KernelSceneParameterMap
            A mapping of dot-separated strings to corresponding update protocol
            definitions.

        See Also
        --------
        :class:`.KernelSceneParameter`, :class:`.KernelSceneParameterMap`
        """
        pass

    def update(self) -> None:
        """
        Enforce internal state consistency. This method should be called when
        fields are modified. It is automatically called as a post-init step.
        """
        # The default implementation is a no-op
        pass


@define(eq=False, slots=False)
class NodeSceneElement(SceneElement, ABC):
    """
    Abstract base class for scene elements which expand as a single Mitsuba
    scene tree node which can be described as a scene dictionary.
    """

    @abstractmethod
    def kdict(self) -> KernelDictionary:
        """
        Kernel dictionary template contents associated with this scene element.

        Returns
        -------
        KernelDictionary
            A flat dictionary mapping dot-separated strings describing the path
            of an item in the nested scene dictionary to values. Values may be
            objects which can be directly used by the :func:`mitsuba.load_dict`
            function, or :class:`.KernelDictionaryParameter` instances which
            must be rendered.

        See Also
        --------
        :class:`.KernelDictionaryParameter`, :class:`.KernelDictionary`
        """
        pass


@define(eq=False, slots=False)
class InstanceSceneElement(SceneElement, ABC):
    """
    Abstract base class for scene elements which represent a node in the Mitsuba
    scene graph, but can only be expanded to a Mitsuba object.
    """

    @abstractmethod
    def instance(self) -> mi.Object:
        """
        Mitsuba object which is represented by this scene element.

        Returns
        -------
        mitsuba.Object
        """
        pass


@define(eq=False, slots=False)
class CompositeSceneElement(SceneElement, ABC):
    """
    Abstract based class for scene elements which expand to multiple Mitsuba
    scene tree nodes.
    """

    @abstractmethod
    def kdict(self) -> KernelDictionary:
        """
        Kernel dictionary template contents associated with this scene element.

        Returns
        -------
        .KernelDictionary
            A flat dictionary mapping dot-separated strings describing the path
            of an item in the nested scene dictionary to values. Values may be
            objects which can be directly used by the :func:`mitsuba.load_dict`
            function, or :class:`.KernelDictionaryParameter` instances which
            must be rendered.

        See Also
        --------
        :class:`.KernelDictionaryParameter`, :class:`.KernelDictionary`
        """
        pass


@define(eq=False, slots=False)
class Ref(NodeSceneElement):
    """
    A scene element which represents a reference to a Mitsuba scene tree node.
    """

    id: str = documented(
        attrs.field(
            kw_only=True,
            validator=attrs.validators.instance_of(str),
        ),
        doc="Identifier of the referenced kernel scene object (required).",
        type="str",
    )

    def kdict(self) -> KernelDictionary:
        # Inherit docstring
        return KernelDictionary({"type": "ref", "id": self.id})

    def kpmap(self) -> KernelSceneParameterMap:
        # Inherit docstring
        return KernelSceneParameterMap()


# -- Misc (to be moved elsewhere) ----------------------------------------------


@frozen
class BoundingBox:
    """
    A basic data class representing an axis-aligned bounding box with
    unit-valued corners.

    Notes
    -----
    Instances are immutable.
    """

    min: pint.Quantity = documented(
        pinttr.field(
            units=ucc.get("length"),
            on_setattr=None,  # frozen instance: on_setattr must be disabled
        ),
        type="quantity",
        init_type="array-like or quantity",
        doc="Min corner.",
    )

    max: pint.Quantity = documented(
        pinttr.field(
            units=ucc.get("length"),
            on_setattr=None,  # frozen instance: on_setattr must be disabled
        ),
        type="quantity",
        init_type="array-like or quantity",
        doc="Max corner.",
    )

    @min.validator
    @max.validator
    def _min_max_validator(self, attribute, value):
        if not self.min.shape == self.max.shape:
            raise ValueError(
                f"while validating {attribute.name}: 'min' and 'max' must "
                f"have the same shape (got {self.min.shape} and {self.max.shape})"
            )
        if not np.all(np.less(self.min, self.max)):
            raise ValueError(
                f"while validating {attribute.name}: 'min' must be strictly "
                "less than 'max'"
            )

    @classmethod
    def convert(
        cls, value: t.Sequence | t.Mapping | np.typing.ArrayLike | pint.Quantity
    ) -> t.Any:
        """
        Attempt conversion of a value to a :class:`BoundingBox`.

        Parameters
        ----------
        value
            Value to convert.

        Returns
        -------
        any
            If `value` is an array-like, a quantity or a mapping, conversion will
            be attempted. Otherwise, `value` is returned unmodified.
        """
        if isinstance(value, (np.ndarray, pint.Quantity)):
            return cls(value[0, :], value[1, :])

        elif isinstance(value, Sequence):
            return cls(*value)

        elif isinstance(value, Mapping):
            return cls(**pinttr.interpret_units(value, ureg=ureg))

        else:
            return value

    @property
    def shape(self):
        """
        tuple: Shape of `min` and `max` arrays.
        """
        return self.min.shape

    @property
    def extents(self) -> pint.Quantity:
        """
        :class:`pint.Quantity`: Extent in all dimensions.
        """
        return self.max - self.min

    @property
    def units(self):
        """
        :class:`pint.Unit`: Units of `min` and `max` arrays.
        """
        return self.min.units

    def contains(self, p: np.typing.ArrayLike, strict: bool = False) -> bool:
        """
        Test whether a point lies within the bounding box.

        Parameters
        ----------
        p : quantity or array-like
            An array of shape (3,) (resp. (N, 3)) representing one (resp. N)
            points. If a unitless value is passed, it is interpreted as
            ``ucc['length']``.

        strict : bool
            If ``True``, comparison is done using strict inequalities (<, >).

        Returns
        -------
        result : array of bool or bool
            ``True`` iff ``p`` in within the bounding box.
        """
        p = np.atleast_2d(ensure_units(p, ucc.get("length")))

        cmp = (
            np.logical_and(p > self.min, p < self.max)
            if strict
            else np.logical_and(p >= self.min, p <= self.max)
        )

        return np.all(cmp, axis=1)


# ------------------------------------------------------------------------------
#                               Factory accessor
# ------------------------------------------------------------------------------

_FACTORIES = {
    "atmosphere": "atmosphere.atmosphere_factory",
    "biosphere": "biosphere.biosphere_factory",
    "bsdf": "bsdfs.bsdf_factory",
    "illumination": "illumination.illumination_factory",
    "integrator": "integrators.integrator_factory",
    "measure": "measure.measure_factory",
    "phase": "phase.phase_function_factory",
    "shape": "shapes.shape_factory",
    "spectrum": "spectra.spectrum_factory",
    "surface": "surface.surface_factory",
}


def get_factory(element_type: str) -> Factory:
    """
    Return the factory corresponding to a scene element type.

    Parameters
    ----------
    element_type : str
        String identity of the scene element type associated to the requested
        factory.

    Returns
    -------
    factory : Factory
        Factory corresponding to the requested scene element type.

    Raises
    ------
    ValueError
        If the requested scene element type is unknown.

    Notes
    -----
    The ``element_type`` argument value maps to factories as follows:

    .. list-table::
       :widths: 1 1
       :header-rows: 1

       * - Element type ID
         - Factory
       * ``"atmosphere"``
         - :attr:`atmosphere_factory`
       * ``"biosphere"``
         - :attr:`biosphere_factory`
       * ``"bsdf"``
         - :attr:`bsdf_factory`
       * ``"illumination"``
         - :attr:`illumination_factory`
       * ``"integrator"``
         - :attr:`integrator_factory`
       * ``"measure"``
         - :attr:`measure_factory`
       * ``"phase"``
         - :attr:`phase_function_factory`
       * ``"shape"``
         - :attr:`shape_factory`
       * ``"spectrum"``
         - :attr:`spectrum_factory`
       * ``"surface"``
         - :attr:`surface_factory`
    """
    try:
        path = f"eradiate.scenes.{_FACTORIES[element_type]}"
    except KeyError:
        raise ValueError(
            f"unknown scene element type '{element_type}' "
            f"(should be one of {set(_FACTORIES.keys())})"
        )

    mod_path, attr = path.rsplit(".", 1)
    return getattr(importlib.import_module(mod_path), attr)
