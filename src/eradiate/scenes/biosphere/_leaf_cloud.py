from __future__ import annotations
from ast import Import

import os
import typing as t

import attr
import mitsuba as mi
import numpy as np
import pint
import pinttr
import scipy as sp

from ._core import CanopyElement, biosphere_factory
from ..core import SceneElement
from ..spectra import Spectrum, spectrum_factory
from ... import validators
from ...attrs import documented, get_doc, parse_docs
from ...contexts import KernelDictContext
from ...units import unit_context_config as ucc
from ...units import unit_context_kernel as uck
from ...units import unit_registry as ureg


def _solve(eqs, symbols, vars, **values):
    import sympy as sm

    unknowns = [symbols[x] for x in symbols.keys() if x not in values.keys()]
    solutions = list(
        sm.solve(
            eqs,
            unknowns,
            domain=sm.Interval(0, sm.oo, left_open=True),
            dict=True,
        )
    )

    if len(solutions) > 1:
        raise RuntimeError("more than 1 solution")

    solution = solutions[0]
    result = {}
    subs = {symbols[var]: values[var] for var in values}

    for var in vars:
        if var in values:
            result[var] = values[var]
        else:
            try:
                result[var] = solution[symbols[var]].evalf(subs=subs)
            except KeyError:
                raise ValueError(f"cannot compute variable '{var}', too many unknowns")

    return result


def _sample_lad(mu, nu, rng):
    """
    Generate an angle sample from the leaf angle distribution (LAD) function
    according to :cite:`GoelStrebel1984` using a rejection method.
    """

    while True:
        rands = rng.random(2)
        theta_candidate = rands[0] * np.pi / 2.0
        gs_lad = (
            2.0
            / np.pi
            * sp.special.gamma(mu + nu)
            / (sp.special.gamma(mu) * sp.special.gamma(mu))
            * pow((1 - (2 * theta_candidate) / np.pi), mu - 1)
            * pow((2 * theta_candidate) / np.pi, nu - 1)
        )

        # scaling factor for the rejection method set to 2.0 to encompass the
        # entire distribution
        if rands[1] * 2.0 <= gs_lad:
            return theta_candidate


@ureg.wraps(ureg.m, (None, ureg.m, ureg.m, None))
def _leaf_cloud_positions_cuboid(n_leaves, l_horizontal, l_vertical, rng):
    """
    Compute leaf positions for a cuboid-shaped leaf cloud (square footprint).
    """
    positions = np.empty((n_leaves, 3))

    for i in range(n_leaves):
        rand = rng.random(3)
        positions[i, :] = [
            rand[0] * l_horizontal - 0.5 * l_horizontal,
            rand[1] * l_horizontal - 0.5 * l_horizontal,
            rand[2] * l_vertical,
        ]

    return positions


@ureg.wraps(ureg.m, (None, ureg.m, ureg.m, ureg.m, None, None))
def _leaf_cloud_positions_cuboid_avoid_overlap(
    n_leaves, l_horizontal, l_vertical, leaf_radius, n_attempts, rng
):
    """
    Compute leaf positions for a cuboid-shaped leaf cloud (square footprint).
    This function also performs conservative collision checks to avoid leaf
    overlapping. This process might take a very long time, if the parameters
    specify a very dense leaf cloud. Consider using
    :func:`_leaf_cloud_positions_cuboid`.
    """
    try:
        import aabbtree
    except ImportError as e:
        raise ImportError(
            "Generating a leaf cloud with collision detection requires the "
            "aabbtree library. To proceed, please install aabbtree."
        ) from e

    n_attempts = int(n_attempts)  # For safety, ensure conversion to int

    # try placing the leaves such that they do not overlap by creating
    # axis-aligned bounding boxes and checking them for intersection
    positions = np.empty((n_leaves, 3))
    tree = aabbtree.AABBTree()

    for i in range(n_leaves):
        for j in range(n_attempts):
            rand = rng.random(3)
            pos_candidate = [
                rand[0] * l_horizontal - 0.5 * l_horizontal,
                rand[1] * l_horizontal - 0.5 * l_horizontal,
                rand[2] * l_vertical,
            ]
            aabb = aabbtree.AABB(
                [
                    (pos_candidate[0] - leaf_radius, pos_candidate[0] + leaf_radius),
                    (pos_candidate[1] - leaf_radius, pos_candidate[1] + leaf_radius),
                    (pos_candidate[2] - leaf_radius, pos_candidate[2] + leaf_radius),
                ]
            )
            if i == 0:
                positions[i, :] = pos_candidate
                tree.add(aabb)
                break
            else:
                if not tree.does_overlap(aabb):
                    positions[i, :] = pos_candidate
                    tree.add(aabb)
                    break
        else:
            raise RuntimeError(
                "unable to place all leaves: the specified canopy might be too dense"
            )

    return positions


@ureg.wraps(ureg.m, (None, None, ureg.m, ureg.m, ureg.m))
def _leaf_cloud_positions_ellipsoid(n_leaves: int, rng, a: float, b: float, c: float):
    r"""
    Compute leaf positions for an ellipsoid leaf cloud.
    The ellipsoid follows the equation:
    :math:`\frac{x^2}{a^2} + \frac{y^2}{b^2} + \frac{z^2}{c^2}= 1`
    """

    positions = []

    while len(positions) < n_leaves:
        rand = rng.random(3)
        x = (rand[0] - 0.5) * 2 * a
        y = (rand[1] - 0.5) * 2 * b
        z = (rand[2] - 0.5) * 2 * c

        if (x**2 / a**2) + (y**2 / b**2) + (z**2 / c**2) <= 1.0:
            positions.append([x, y, z])

    return positions


@ureg.wraps(ureg.m, (None, ureg.m, ureg.m, None))
def _leaf_cloud_positions_cylinder(n_leaves, radius, l_vertical, rng):
    """
    Compute leaf positions for a cylinder-shaped leaf cloud (vertical
    orientation).
    """

    positions = np.empty((n_leaves, 3))

    for i in range(n_leaves):
        rand = rng.random(3)
        phi = rand[0] * 2 * np.pi
        r = rand[1] * radius
        z = rand[2] * l_vertical
        positions[i, :] = [r * np.cos(phi), r * np.sin(phi), z]

    return positions


@ureg.wraps(ureg.m, (None, ureg.m, ureg.m, None))
def _leaf_cloud_positions_cone(n_leaves, radius, l_vertical, rng):
    """
    Compute leaf positions for a cone-shaped leaf cloud (vertical
    orientation, tip pointing towards positive z).
    """

    positions = np.empty((n_leaves, 3))

    # uniform cone sampling from here:
    # https://stackoverflow.com/questions/41749411/uniform-sampling-by-volume-within-a-cone
    for i in range(n_leaves):
        rand = rng.random(3)
        h = l_vertical * (rand[0] ** (1 / 3))
        r = radius / l_vertical * h * np.sqrt(rand[1])
        phi = rand[2] * 2 * np.pi
        positions[i, :] = [r * np.cos(phi), r * np.sin(phi), l_vertical - h]

    return positions


@ureg.wraps(None, (None, None, None, None))
def _leaf_cloud_orientations(n_leaves, mu, nu, rng):
    """Compute leaf orientations."""
    orientations = np.empty((n_leaves, 3))
    for i in range(np.shape(orientations)[0]):
        theta = _sample_lad(mu, nu, rng)
        phi = rng.random() * 2.0 * np.pi

        orientations[i, :] = [
            np.sin(theta) * np.cos(phi),
            np.sin(theta) * np.sin(phi),
            np.cos(theta),
        ]

    return orientations


@ureg.wraps(ureg.m, (None, ureg.m))
def _leaf_cloud_radii(n_leaves, leaf_radius):
    """Compute leaf radii."""
    return np.full((n_leaves,), leaf_radius)


@biosphere_factory.register(type_id="leaf_cloud")
@parse_docs
@attr.s
class LeafCloud(CanopyElement):
    """
    A container class for leaf clouds in abstract discrete canopies.
    Holds parameters completely characterising the leaf cloud's leaves.

    In practice, this class should rarely be instantiated directly using its
    constructor. Instead, several class method constructors are available:

    * generators create leaf clouds from a set of parameters:

      * :meth:`.LeafCloud.cone`;
      * :meth:`.LeafCloud.cuboid`;
      * :meth:`.LeafCloud.cylinder`;
      * :meth:`.LeafCloud.ellipsoid`;
      * :meth:`.LeafCloud.sphere`;

    * :meth:`.LeafCloud.from_file` loads leaf positions and orientations from a
      text file.

    .. admonition:: Class method constructors

       .. autosummary::

          cuboid
          cylinder
          ellipsoid
          from_file
          sphere
    """

    # --------------------------------------------------------------------------
    #                                 Fields
    # --------------------------------------------------------------------------

    id: t.Optional[str] = documented(
        attr.ib(
            default="leaf_cloud",
            validator=attr.validators.optional(attr.validators.instance_of(str)),
        ),
        doc=get_doc(SceneElement, "id", "doc"),
        type=get_doc(SceneElement, "id", "type"),
        init_type=get_doc(SceneElement, "id", "init_type"),
        default="'leaf_cloud'",
    )

    leaf_positions: pint.Quantity = documented(
        pinttr.ib(factory=list, units=ucc.deferred("length")),
        doc="Leaf positions in cartesian coordinates as a (n, 3)-array.\n"
        "\n"
        "Unit-enabled field (default: ucc['length']).",
        type="quantity",
        init_type="array-like",
        default="[]",
    )

    leaf_orientations: np.ndarray = documented(
        attr.ib(factory=list, converter=np.array),
        doc="Leaf orientations (normal vectors) in Cartesian coordinates as a "
        "(n, 3)-array.",
        type="ndarray",
        default="[]",
    )

    leaf_radii: pint.Quantity = documented(
        pinttr.ib(
            factory=list,
            validator=[
                pinttr.validators.has_compatible_units,
                attr.validators.deep_iterable(member_validator=validators.is_positive),
            ],
            units=ucc.deferred("length"),
        ),
        doc="Leaf radii as a n-array.\n\nUnit-enabled field (default: ucc[length]).",
        init_type="array-like",
        type="quantity",
        default="[]",
    )

    @leaf_positions.validator
    @leaf_orientations.validator
    def _positions_orientations_validator(self, attribute, value):
        if not len(value):
            return

        if not value.ndim == 2 or value.shape[1] != 3:
            raise ValueError(
                f"While validating {attribute.name}: shape should be (N, 3), "
                f"got {value.shape}"
            )

    @leaf_positions.validator
    @leaf_orientations.validator
    @leaf_radii.validator
    def _positions_orientations_radii_validator(self, attribute, value):
        if not (
            len(self.leaf_positions)
            == len(self.leaf_orientations)
            == len(self.leaf_radii)
        ):
            raise ValueError(
                f"While validating {attribute.name}: "
                f"leaf_positions, leaf_orientations and leaf_radii must have the "
                f"same length. Got "
                f"len(leaf_positions) = {len(self.leaf_positions)}, "
                f"len(leaf_orientations) = {len(self.leaf_orientations)}, "
                f"len(leaf_radii) = {len(self.leaf_radii)}."
            )

    leaf_reflectance: Spectrum = documented(
        attr.ib(
            default=0.5,
            converter=spectrum_factory.converter("reflectance"),
            validator=[
                attr.validators.instance_of(Spectrum),
                validators.has_quantity("reflectance"),
            ],
        ),
        doc="Reflectance spectrum of the leaves in the cloud. "
        "Must be a reflectance spectrum (dimensionless).",
        type=":class:`.Spectrum`",
        init_type=":class:`.Spectrum` or dict",
        default="0.5",
    )

    leaf_transmittance: Spectrum = documented(
        attr.ib(
            default=0.5,
            converter=spectrum_factory.converter("transmittance"),
            validator=[
                attr.validators.instance_of(Spectrum),
                validators.has_quantity("transmittance"),
            ],
        ),
        doc="Transmittance spectrum of the leaves in the cloud. "
        "Must be a transmittance spectrum (dimensionless).",
        type=":class:`.Spectrum`",
        init_type=":class:`.Spectrum` or dict",
        default="0.5",
    )

    # --------------------------------------------------------------------------
    #                          Properties and accessors
    # --------------------------------------------------------------------------

    def n_leaves(self) -> int:
        """
        int : Number of leaves in the leaf cloud.
        """
        return len(self.leaf_positions)

    def surface_area(self) -> pint.Quantity:
        """
        quantity : Total surface area as a :class:`~pint.Quantity`.
        """
        return np.sum(np.pi * self.leaf_radii * self.leaf_radii).squeeze()

    # --------------------------------------------------------------------------
    #                              Constructors
    # --------------------------------------------------------------------------

    @classmethod
    def cuboid(
        cls,
        id: str = "leaf_cloud",
        leaf_reflectance: t.Union[Spectrum, dict] = 0.5,
        leaf_transmittance: t.Union[Spectrum, dict] = 0.5,
        n_leaves: t.Optional[int] = None,
        leaf_radius: t.Union[pint.Quantity, float, None] = None,
        l_horizontal: t.Union[pint.Quantity, float, None] = None,
        l_vertical: t.Union[pint.Quantity, float, None] = None,
        lai: t.Optional[float] = None,
        hdo: t.Union[pint.Quantity, float, None] = None,
        hvr: t.Union[float, None] = None,
        mu: t.Optional[float] = 1.066,
        nu: t.Optional[float] = 1.853,
        seed: int = 12345,
        avoid_overlap: bool = False,
        n_attempts: int = 100000,
    ) -> LeafCloud:
        """
        Generate a leaf cloud with an axis-aligned cuboid shape (and a square
        footprint on the ground).

        The produced leaf cloud uniformly covers the
        :math:`(x, y, z) \\in \\left[ -\\dfrac{l_h}{2}, + \\dfrac{l_h}{2} \\right] \\times \\left[ -\\dfrac{l_h}{2}, + \\dfrac{l_h}{2} \\right] \\times [0, l_v]`
        region. Parameters `n_leaves` to `hvr` can be specified in various
        combinations to define the number and position of leaves.

        Leaf orientation is controlled by the `mu` and `nu` parameters
        of an approximated inverse beta distribution
        :cite:`Ross1991MonteCarloMethods`.

        Finally, extra parameters control the random number generator and a
        basic and conservative leaf collision detection algorithm.

        Parameters
        ----------
        id : str, optional, default: "leaf_cloud"
            Leaf cloud identifier.

        leaf_reflectance : .Spectrum or dict, optional, default: 0.5
            Leaf reflectance.

        leaf_transmittance : .Spectrum or dict, optional, default: 0.5
            Leaf transmittance.

        n_leaves : int, optional
            Number of leaves.

        leaf_radius : quantity or float, optional
            Leaf radius.
            Unitless values are interpreted as ``ucc["length"]``.

        l_horizontal : quantity or float, optional
            Leaf cloud horizontal extent.
            *Suggested value: 30 m.*
            Unitless values are interpreted as ``ucc["length"]``.

        l_vertical : quantity or float, optional
            Leaf cloud vertical extent.
            *Suggested value: 3 m.*
            Unitless values are interpreted as ``ucc["length"]``.

        lai : float, optional
            Leaf cloud leaf area index (LAI).
            *Physical range: [0, 10]; suggested value: 3.*

        hdo : quantity or float, optional
            Mean horizontal distance between leaves.
            Unitless values are interpreted as ``ucc["length"]``.

        hvr : float, optional
            Ratio of mean horizontal leaf distance and vertical leaf cloud extent.
            *Suggested value: 0.1.*

        mu : float, optional, default: 1.066
            First parameter of the inverse beta distribution approximation used
            to generate leaf orientations.

        nu : float, optional, default: 1.853
            Second parameter of the inverse beta distribution approximation used
            to generate leaf orientations.

        seed : int, optional
            Seed for the random number generator.

        avoid_overlap : bool
            If ``True``, generate leaf positions with strict collision checks to
            avoid overlapping.

        n_attempts : int
            If ``avoid_overlap`` is ``True``, number of attempts made at placing
            a leaf without collision before giving up. Default: 1e5.

        Returns
        -------
        :class:`.LeafCloud`:
            Generated leaf cloud.

        Notes
        -----
        The following parameter combinations are valid:

        * `n_leaves`, `leaf_radius`, `l_horizontal`, `l_vertical`;
        * `lai`, `leaf_radius`, `l_horizontal`, `l_vertical`;
        * `lai`, `leaf_radius`, `l_horizontal`, `hdo`, `hvr`;
        * and more! (See figure below; the outlined parameters are used to
          generate the leaf cloud.)

        .. only:: latex

           .. figure:: ../../../../fig/cuboid_leaf_cloud_params.png

        .. only:: not latex

           .. figure:: ../../../../fig/cuboid_leaf_cloud_params.svg
        """
        try:
            import sympy as sm
        except ImportError as e:
            raise ImportError(
                "Generating a cuboid-shaped leaf cloud requires sympy. Please "
                "install sympy to proceed."
            ) from e

        # Process leaf cloud parametrisation
        # -- Define default units
        length_units = ucc.get("length")
        dimless_units = ucc.get("dimensionless")
        units = {
            "n_leaves": None,
            "lai": dimless_units,
            "leaf_radius": length_units,
            "l_horizontal": length_units,
            "l_vertical": length_units,
            "hdo": length_units,
            "hvr": dimless_units,
        }

        # --  Declare symbols
        symbols = {
            name: sm.Symbol(symbol, positive=True)
            for name, symbol in [
                ("n_leaves", "n"),
                ("lai", "LAI"),
                ("leaf_radius", "r"),
                ("l_horizontal", "l_h"),
                ("l_vertical", "l_v"),
                ("hdo", "HDO"),
                ("hvr", "HVR"),
            ]
        }

        # -- Declare constitutive relations
        eqs = [
            sm.Eq(
                symbols["n_leaves"],
                symbols["lai"]
                * (symbols["l_horizontal"] / symbols["leaf_radius"]) ** 2
                / sm.pi,
            ),
            sm.Eq(
                symbols["l_vertical"],
                symbols["lai"]
                * symbols["hdo"] ** 3
                / (sm.pi * symbols["leaf_radius"] ** 2 * symbols["hvr"]),
            ),
        ]

        # -- Collect input parameters
        names = list(symbols.keys())
        input_params = {
            name: value
            for name, value in locals().items()
            if (
                name in names  # This is an unknown of the system
                and value is not None  # This is user-specified
            )
        }  # User-specified inputs

        # -- Apply default units if relevant, extract magnitude
        for name in input_params.keys():
            u = units[name]
            if u is not None:
                input_params[name] = pinttr.util.ensure_units(
                    input_params[name], default_units=u
                ).m_as(u)

        # Compute leaf cloud parameters
        params = _solve(
            eqs,
            symbols,
            ["n_leaves", "leaf_radius", "l_horizontal", "l_vertical"],
            **input_params,
        )

        # Convert from Sympy to numeric types, apply units
        for key in params.keys():
            params[key] = (
                float(params[key]) * units[key]
                if units[key] is not None
                else float(params[key])
            )

        # Special case: number of leaves must be an integer
        params["n_leaves"] = int(params["n_leaves"])

        # Compute leaf positions
        rng = np.random.default_rng(seed=seed)

        if avoid_overlap:
            leaf_positions = _leaf_cloud_positions_cuboid_avoid_overlap(
                params["n_leaves"],
                params["l_horizontal"],
                params["l_vertical"],
                params["leaf_radius"],
                n_attempts,
                rng,
            )

        else:
            leaf_positions = _leaf_cloud_positions_cuboid(
                params["n_leaves"],
                params["l_horizontal"],
                params["l_vertical"],
                rng,
            )

        # Compute leaf radii
        leaf_radii = _leaf_cloud_radii(params["n_leaves"], params["leaf_radius"])

        # Compute leaf orientations
        leaf_orientations = _leaf_cloud_orientations(params["n_leaves"], mu, nu, rng)

        # Create leaf cloud object
        return cls(
            id=id,
            leaf_positions=leaf_positions,
            leaf_orientations=leaf_orientations,
            leaf_radii=leaf_radii,
            leaf_reflectance=leaf_reflectance,
            leaf_transmittance=leaf_transmittance,
        )

    @classmethod
    def sphere(
        cls,
        id: str = "leaf_cloud",
        leaf_reflectance: t.Union[Spectrum, dict] = 0.5,
        leaf_transmittance: t.Union[Spectrum, dict] = 0.5,
        n_leaves: int = 1000,
        leaf_radius: t.Union[pint.Quantity, float] = 0.05 * ureg.m,
        radius: t.Union[pint.Quantity, float] = 1.0 * ureg.m,
        mu: t.Optional[float] = 1.066,
        nu: t.Optional[float] = 1.853,
        seed: int = 12345,
    ) -> LeafCloud:
        """
        Generate a leaf cloud with a sphere shape.
        The produced leaf cloud covers uniformly the :math:`r < \\mathtt{radius}`
        region. Leaf orientation is controlled by the `mu` and `nu` parameters
        of an approximated inverse beta distribution
        :cite:`Ross1991MonteCarloMethods`.
        An additional parameter controls the random number generator.

        Parameters
        ----------
        id : str, optional, default: "leaf_cloud"
            Leaf cloud identifier.

        leaf_reflectance : .Spectrum or dict, optional, default: 0.5
            Leaf reflectance.

        leaf_transmittance : .Spectrum or dict, optional, default: 0.5
            Leaf transmittance.

        n_leaves : int, optional, default: 1000
            Number of leaves.

        leaf_radius : quantity or float, optional, default: 0.05 m
            Leaf radius.
            Unitless values are interpreted as ``ucc["length"]``.

        radius : quantity or float, optional, default: 1 m
            Leaf cloud radius.
            Unitless values are interpreted as ``ucc["length"]``.

        mu : float, optional, default: 1.066
            First parameter of the inverse beta distribution approximation used
            to generate leaf orientations.

        nu : float, optional, default: 1.853
            Second parameter of the inverse beta distribution approximation used
            to generate leaf orientations.

        seed : int
            Seed for the random number generator.

        Returns
        -------
        .LeafCloud
            Generated leaf cloud.
        """
        rng = np.random.default_rng(seed=seed)
        length_units = ucc.get("length")
        r = pinttr.util.ensure_units(radius, default_units=length_units)
        leaf_positions = _leaf_cloud_positions_ellipsoid(n_leaves, rng, r, r, r)
        leaf_orientations = _leaf_cloud_orientations(n_leaves, mu, nu, rng)
        leaf_radii = _leaf_cloud_radii(
            n_leaves, pinttr.util.ensure_units(leaf_radius, default_units=length_units)
        )

        # Create leaf cloud object
        return cls(
            id=id,
            leaf_positions=leaf_positions,
            leaf_orientations=leaf_orientations,
            leaf_radii=leaf_radii,
            leaf_reflectance=leaf_reflectance,
            leaf_transmittance=leaf_transmittance,
        )

    @classmethod
    def ellipsoid(
        cls,
        id: str = "leaf_cloud",
        leaf_reflectance: t.Union[Spectrum, dict] = 0.5,
        leaf_transmittance: t.Union[Spectrum, dict] = 0.5,
        n_leaves: int = 1000,
        leaf_radius: t.Union[pint.Quantity, float] = 0.05 * ureg.m,
        a: t.Union[pint.Quantity, float] = 1.0 * ureg.m,
        b: t.Union[pint.Quantity, float] = 1.0 * ureg.m,
        c: t.Union[pint.Quantity, float] = 1.0 * ureg.m,
        mu: t.Optional[float] = 1.066,
        nu: t.Optional[float] = 1.853,
        seed: int = 12345,
    ) -> LeafCloud:
        """
        Generate a leaf cloud with an ellipsoid shape.
        The produced leaf cloud covers uniformly the volume enclosed by
        :math:`\\frac{x^2}{a^2} + \\frac{y^2}{b^2} + \\frac{z^2}{c^2} = 1` .
        Leaf orientation is controlled by the `mu` and `nu` parameters
        of an approximated inverse beta distribution
        :cite:`Ross1991MonteCarloMethods`.
        An additional parameter controls the random number generator.

        Parameters
        ----------
        id : str, optional, default: "leaf_cloud"
            Leaf cloud identifier.

        leaf_reflectance : .Spectrum or dict, optional, default: 0.5
            Leaf reflectance.

        leaf_transmittance : .Spectrum or dict, optional, default: 0.5
            Leaf transmittance.

        n_leaves : int, optional, default: 1000
            Number of leaves.

        leaf_radius : quantity or float, optional, default: 0.05 m
            Leaf radius.
            Unitless values are interpreted as ``ucc["length"]``.

        a : quantity or float, optional, default: 1 m
            First leaf cloud semi axis.
            Unitless values are interpreted as ``ucc["length"]``.

        b : quantity or float, optional, default: 1 m
            Second leaf cloud semi axis.
            Unitless values are interpreted as ``ucc["length"]``.

        c : quantity or float, optional, default: 1 m
            Third leaf cloud semi axis.
            Unitless values are interpreted as ``ucc["length"]``.

        mu : float, optional, default: 1.066
            First parameter of the inverse beta distribution approximation used
            to generate leaf orientations.

        nu : float, optional, default: 1.853
            Second parameter of the inverse beta distribution approximation used
            to generate leaf orientations.

        seed : int
            Seed for the random number generator.

        Returns
        -------
        .LeafCloud
            Generated leaf cloud.
        """
        rng = np.random.default_rng(seed=seed)
        length_units = ucc.get("length")
        leaf_positions = _leaf_cloud_positions_ellipsoid(
            n_leaves,
            rng,
            pinttr.util.ensure_units(a, default_units=length_units),
            pinttr.util.ensure_units(b, default_units=length_units),
            pinttr.util.ensure_units(c, default_units=length_units),
        )
        leaf_orientations = _leaf_cloud_orientations(n_leaves, mu, nu, rng)
        leaf_radii = _leaf_cloud_radii(
            n_leaves, pinttr.util.ensure_units(leaf_radius, default_units=length_units)
        )

        # Create leaf cloud object
        return cls(
            id=id,
            leaf_positions=leaf_positions,
            leaf_orientations=leaf_orientations,
            leaf_radii=leaf_radii,
            leaf_reflectance=leaf_reflectance,
            leaf_transmittance=leaf_transmittance,
        )

    @classmethod
    def cylinder(
        cls,
        id: str = "leaf_cloud",
        leaf_reflectance: t.Union[Spectrum, dict] = 0.5,
        leaf_transmittance: t.Union[Spectrum, dict] = 0.5,
        n_leaves: int = 1000,
        leaf_radius: t.Union[pint.Quantity, float] = 0.05 * ureg.m,
        radius: t.Union[pint.Quantity, float] = 1.0 * ureg.m,
        l_vertical: t.Union[pint.Quantity, float] = 1.0 * ureg.m,
        mu: t.Optional[float] = 1.066,
        nu: t.Optional[float] = 1.853,
        seed: int = 12345,
    ) -> LeafCloud:
        """
        Generate a leaf cloud with a cylindrical shape (vertical orientation).
        The produced leaf cloud covers uniformly the
        :math:`r < \\mathtt{radius}, z \\in [0, l_v]`
        region. Leaf orientation is controlled by the `mu` and `nu` parameters
        of an approximated inverse beta distribution
        :cite:`Ross1991MonteCarloMethods`.
        An additional parameter controls the random number generator.

        Parameters
        ----------
        id : str, optional, default: "leaf_cloud"
            Leaf cloud identifier.

        leaf_reflectance : .Spectrum or dict, optional, default: 0.5
            Leaf reflectance.

        leaf_transmittance : .Spectrum or dict, optional, default: 0.5
            Leaf transmittance.

        n_leaves : int, optional, default: 1000
            Number of leaves.

        leaf_radius : quantity or float, optional, default: 0.05 m
            Leaf radius.
            Unitless values are interpreted as ``ucc["length"]``.

        radius : quantity or float, optional, default: 1 m
            Leaf cloud radius.
            Unitless values are interpreted as ``ucc["length"]``.

        l_vertical : quantity or float, optional, default: 1 m
            Leaf cloud vertical extent.
            Unitless values are interpreted as ``ucc["length"]``.

        mu : float, optional, default: 1.066
            First parameter of the inverse beta distribution approximation used
            to generate leaf orientations.

        nu : float, optional, default: 1.853
            Second parameter of the inverse beta distribution approximation used
            to generate leaf orientations.

        seed : int
            Seed for the random number generator.

        Returns
        -------
        .LeafCloud
            Generated leaf cloud.
        """
        rng = np.random.default_rng(seed=seed)
        length_units = ucc.get("length")
        leaf_positions = _leaf_cloud_positions_cylinder(
            n_leaves,
            pinttr.util.ensure_units(radius, default_units=length_units),
            pinttr.util.ensure_units(l_vertical, default_units=length_units),
            rng,
        )
        leaf_orientations = _leaf_cloud_orientations(n_leaves, mu, nu, rng)
        leaf_radii = _leaf_cloud_radii(
            n_leaves, pinttr.util.ensure_units(leaf_radius, default_units=length_units)
        )

        # Create leaf cloud object
        return cls(
            id=id,
            leaf_positions=leaf_positions,
            leaf_orientations=leaf_orientations,
            leaf_radii=leaf_radii,
            leaf_reflectance=leaf_reflectance,
            leaf_transmittance=leaf_transmittance,
        )

    @classmethod
    def cone(
        cls,
        id: str = "leaf_cloud",
        leaf_reflectance: t.Union[Spectrum, dict] = 0.5,
        leaf_transmittance: t.Union[Spectrum, dict] = 0.5,
        n_leaves: int = 1000,
        leaf_radius: t.Union[pint.Quantity, float] = 0.05 * ureg.m,
        radius: t.Union[pint.Quantity, float] = 1.0 * ureg.m,
        l_vertical: t.Union[pint.Quantity, float] = 1.0 * ureg.m,
        mu: t.Optional[float] = 1.066,
        nu: t.Optional[float] = 1.853,
        seed: int = 12345,
    ) -> LeafCloud:
        """
        Generate a leaf cloud with a cone shape (vertical orientation).
        The produced leaf cloud covers uniformly the
        :math:`r < \\mathtt{radius} \\cdot \\left( 1 - \\frac{z}{l_v} \\right), z \\in [0, l_v]`
        region. Leaf orientation is controlled by the `mu` and `nu` parameters
        of an approximated inverse beta distribution
        :cite:`Ross1991MonteCarloMethods`.
        An additional parameter controls the random number generator.

        Parameters
        ----------
        id : str, optional, default: "leaf_cloud"
            Leaf cloud identifier.

        leaf_reflectance : .Spectrum or dict, optional, default: 0.5
            Leaf reflectance.

        leaf_transmittance : .Spectrum or dict, optional, default: 0.5
            Leaf transmittance.

        n_leaves : int, optional, default: 1000
            Number of leaves.

        leaf_radius : quantity or float, optional, default: 0.05 m
            Leaf radius.
            Unitless values are interpreted as ``ucc["length"]``.

        radius : quantity or float, optional, default: 1 m
            Leaf cloud base radius.
            Unitless values are interpreted as ``ucc["length"]``.

        l_vertical : quantity or float, optional, default: 1 m
            Leaf cloud vertical extent.
            Unitless values are interpreted as ``ucc["length"]``.

        mu : float, optional, default: 1.066
            First parameter of the inverse beta distribution approximation used
            to generate leaf orientations.

        nu : float, optional, default: 1.853
            Second parameter of the inverse beta distribution approximation used
            to generate leaf orientations.

        seed : int
            Seed for the random number generator.

        Returns
        -------
        .LeafCloud
            Generated leaf cloud.
        """
        rng = np.random.default_rng(seed=seed)
        length_units = ucc.get("length")
        leaf_positions = _leaf_cloud_positions_cone(
            n_leaves,
            pinttr.util.ensure_units(radius, default_units=length_units),
            pinttr.util.ensure_units(l_vertical, default_units=length_units),
            rng,
        )
        leaf_orientations = _leaf_cloud_orientations(n_leaves, mu, nu, rng)

        leaf_radii = _leaf_cloud_radii(
            n_leaves, pinttr.util.ensure_units(leaf_radius, default_units=length_units)
        )

        # Create leaf cloud object
        return cls(
            id=id,
            leaf_positions=leaf_positions,
            leaf_orientations=leaf_orientations,
            leaf_radii=leaf_radii,
            leaf_reflectance=leaf_reflectance,
            leaf_transmittance=leaf_transmittance,
        )

    @classmethod
    def from_file(
        cls,
        filename,
        leaf_transmittance: t.Union[float, Spectrum] = 0.5,
        leaf_reflectance: t.Union[float, Spectrum] = 0.5,
        id: str = "leaf_cloud",
    ) -> LeafCloud:
        """
        Construct a :class:`.LeafCloud` from a text file specifying the leaf
        positions and orientations.

        .. admonition:: File format

           Each line defines a single leaf with the following 7 numerical
           parameters separated by one or more spaces:

           * leaf radius;
           * leaf center (x, y and z coordinates);
           * leaf orientation (x, y and z of normal vector).

        .. important::

           Location coordinates are assumed to be given in meters.

        Parameters
        ----------
        filename : path-like
            Path to the text file specifying the leaves in the leaf cloud.
            Can be absolute or relative.

        leaf_reflectance : .Spectrum or float, optional, default: 0.5
            Reflectance spectrum of the leaves in the cloud.
            Must be a reflectance spectrum (dimensionless).

        leaf_transmittance : .Spectrum of float, optional, default: 0.5
            Transmittance spectrum of the leaves in the cloud.
            Must be a transmittance spectrum (dimensionless).

        id : str, optional, default: "leaf_cloud"
            ID of the created .LeafCloud instance.

        Returns
        -------
        .LeafCloud
            Generated leaf cloud.

        Raises
        ------
        FileNotFoundError
            If `filename` does not point to an existing file.
        """
        if not os.path.isfile(filename):
            raise FileNotFoundError(f"no file at {filename} found.")

        radii_ = []
        positions_ = []
        orientations_ = []
        with open(os.path.abspath(filename), "r") as definition_file:
            for i, line in enumerate(definition_file):
                values = [float(x) for x in line.split()]
                radii_.append(values[0])
                positions_.append(values[1:4])
                orientations_.append(values[4:7])

        radii = np.array(radii_) * ureg.m
        positions = np.array(positions_) * ureg.m
        orientations = np.array(orientations_)

        return cls(
            id=id,
            leaf_positions=positions,
            leaf_orientations=orientations,
            leaf_radii=radii,
            leaf_reflectance=leaf_reflectance,
            leaf_transmittance=leaf_transmittance,
        )

    # --------------------------------------------------------------------------
    #                       Kernel dictionary generation
    # --------------------------------------------------------------------------

    def kernel_bsdfs(self, ctx: KernelDictContext) -> t.Dict:
        """
        Return BSDF plugin specifications.

        Parameters
        ----------
        ctx : .KernelDictContext
            A context data structure containing parameters relevant for kernel
            dictionary generation.

        Returns
        -------
        dict
            Return a dictionary suitable for merge with a :class:`.KernelDict`
            containing all the BSDFs attached to the shapes in the leaf cloud.
        """
        return {
            f"bsdf_{self.id}": {
                "type": "bilambertian",
                "reflectance": self.leaf_reflectance.kernel_dict(ctx=ctx)["spectrum"],
                "transmittance": self.leaf_transmittance.kernel_dict(ctx=ctx)[
                    "spectrum"
                ],
            }
        }

    def kernel_shapes(self, ctx: KernelDictContext) -> t.Dict:
        """
        Return shape plugin specifications.

        Parameters
        ----------
        ctx : .KernelDictContext
            A context data structure containing parameters relevant for kernel
            dictionary generation.

        Returns
        -------
        dict
            A dictionary suitable for merge with a :class:`.KernelDict`
            containing all the shapes in the leaf cloud.
        """
        kernel_length = uck.get("length")
        shapes_dict = {}

        if ctx.ref:
            bsdf = {"type": "ref", "id": f"bsdf_{self.id}"}
        else:
            bsdf = self.kernel_bsdfs(ctx=ctx)[f"bsdf_{self.id}"]

        for i_leaf, (position, normal, radius) in enumerate(
            zip(
                self.leaf_positions.m_as(kernel_length),
                self.leaf_orientations,
                self.leaf_radii.m_as(kernel_length),
            )
        ):
            _, up = mi.coordinate_system(normal)
            to_world = mi.ScalarTransform4f.look_at(
                origin=position, target=position + normal, up=up
            ) * mi.ScalarTransform4f.scale(radius)

            shapes_dict[f"{self.id}_leaf_{i_leaf}"] = {
                "type": "disk",
                "bsdf": bsdf,
                "to_world": to_world,
            }

        return shapes_dict

    # --------------------------------------------------------------------------
    #                               Other methods
    # --------------------------------------------------------------------------

    def translated(self, xyz: pint.Quantity) -> LeafCloud:
        """
        Return a copy of self translated by the vector `xyz`.

        Parameters
        ----------
        xyz : quantity
            A 3-vector or a (N, 3)-array by which leaves will be translated. If
            (N, 3) variant is used, the array shape must match that of
            `leaf_positions`.

        Returns
        -------
        .LeafCloud
            Translated copy of self.

        Raises
        ------
        ValueError
            Sizes of `xyz` and ``self.leaf_positions`` are incompatible.
        """
        if xyz.ndim <= 1:
            xyz = xyz.reshape((1, 3))
        elif xyz.shape != self.leaf_positions.shape:
            raise ValueError(
                f"shapes of 'xyz' {xyz.shape} and 'self.leaf_positions' "
                f"{self.leaf_positions.shape} do not match"
            )

        return attr.evolve(self, leaf_positions=self.leaf_positions + xyz)
