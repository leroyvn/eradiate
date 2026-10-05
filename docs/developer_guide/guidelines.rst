Coding guidelines
=================

*State: Draft.*

This document provides guidelines for coding in this project. It covers
fundamental principles, patterns and style.

Principles
----------

Keep expensive libraries at the boundary.
    This includes Pint and xarray: most of the operations these libraries
    perform add significant overhead which we'd rather do without in the hot
    parts of processing.

Cache expensive operations.
    Do not recompute something that is already computed. This is critical in the
    spectral loop, but also during scene initialization.

Patterns
--------

Pint best practices
^^^^^^^^^^^^^^^^^^^

.. seealso::

    `Pint's performance guide <https://pint.readthedocs.io/en/stable/advanced/performance.html>`__

* **Build quantities from a (magnitude, units) pair.**
  *Also recommended by the Pint performance guide.*
  String parsing is very costly: keep it at the interface and I/O boundaries::

    # Avoid
    ureg("1 m/s")

    # Prefer
    ureg.Quantity(1.0, "m/s")

* **Bind unit objects used multiple times to a variable.**
  Any form of lookup is more costly than dereferencing a variable::

    # Avoid
    for i in range(10):
        x = i * ureg.m

    # Prefer
    m = ureg.m
    for i in range(10):
        x = i * m

  This extends to callables that run in hot loops: those that run at every
  iteration can benefit from fetching them from a module-level constant instead
  of looking them up::

    # Avoid
    def as_hashable(self):
        return float(self.w.m_as(ureg.Unit("nanometer")))

    # Prefer
    _NANOMETER = ureg.Unit("nanometer")

    def as_hashable(self):
        return float(self.w.m_as(_NANOMETER))

* **Avoid intermediate Pint objects for conversions.**
  Use ``convert()`` to convert unitless values, not ``Quantity().m_as()``::

    # Avoid
    ureg.Quantity(1.0, "meter").m_as("kilometer")

    # Prefer
    ureg.convert(1.0, "meter", "kilometer")

  :func:`.magnitude_as` returns the magnitude of a value in target units and
  applies default units to unitless input without building a quantity::

    # Avoid
    ensure_units(value, default_units).m_as(units)

    # Prefer
    magnitude_as(value, units, default_units)

  For :class:`xarray.DataArray` objects with a ``units`` attribute, convert the
  underlying array directly::

    # Avoid
    to_quantity(da).m_as("kilometer")

    # Prefer
    ureg.convert(da.values, da.attrs["units"], "kilometer")

* **Do not build a quantity that the caller strips right away.**
  In evaluation code (``eval_*()`` methods, kernel parameter callables),
  compute on magnitudes and wrap the result once on return::

    # Avoid
    np.interp(w, self.wavelengths, self.values)

    # Prefer
    ureg.Quantity(
        np.interp(w.m_as(self.wavelengths.u), self.wavelengths.m, self.values.m),
        self.values.u,
    )

* **Check quantity types against** ``pint.Quantity``.
  ``ureg`` is Pint's application registry, a proxy that forwards attribute
  access to the actual registry. ``isinstance(x, ureg.Quantity)`` goes through
  this forwarding at every call and is about 7 times slower::

    # Avoid
    isinstance(value, ureg.Quantity)

    # Prefer
    isinstance(value, pint.Quantity)

* **For compound units, prefer string parsing over explicit operations.**
  Unit operations are significantly slower than internal equivalents done after
  parsing::

    # Avoid
    ureg.W/ureg.m**2/ureg.sr/ureg.nm

    # Prefer
    ureg.Unit("W/m^2/sr/nm")

* **Write prefixed units with their full U.S.-spelled name.**

  .. important::

      Not applicable to Pint 0.26.0 and later
      (`this PR fixed the bug <https://github.com/hgrecco/pint/issues/2320>`__).

  Short and British forms are about 15 times slower to look up, and this
  applies to registry attribute access as well (``ureg.km`` costs about 40 µs,
  ``ureg.kilometer`` about 3 µs)::

    # Avoid
    ureg.Unit("km")
    ureg.Unit("kilometre")
    ureg.Unit("um")
    ureg.Unit("micrometre")
    ureg.km

    # Prefer
    ureg.Unit("kilometer")
    ureg.Unit("micrometer")
    ureg.kilometer

  .. note::

      A benchmark against all units used across the Eradiate codebase led to the
      following conclusions:

      * Prefixed units are only fast when written as their full U.S.-spelled
        name: symbols (``km``, ``nm``, ``cm``, ``kg``, ``um``) and British
        spellings (``kilometre``) are much slower.
      * Unprefixed units are fast under any symbol or spelling (``m``,
        ``metre``, ``deg``, ``sr``, ``W``, ``g``).
      * Plurals (``meters``, ``degrees``, ``seconds``) are slow.
      * In compound strings, each slow component adds large overhead; the rest
        adds low overhead.
      * ``micron`` is a separate unit: ``Unit("micron") != Unit("micrometer")``.

      .. dropdown:: Full benchmark results

        Time per ``ureg.Unit(s)`` call after warm-up, Pint 0.24.4 (includes
        about 0.6 µs of benchmark overhead).

        .. list-table::
          :header-rows: 1
          :widths: 20 40 40

          * - Unit
            - Slow forms (µs)
            - Optimal form (µs)
          * - meter
            - ``meters`` 18
            - ``m``, ``meter``, ``metre`` 2.6
          * - kilometer
            - ``km`` 38, ``kilometre`` 38, ``kilometers`` 40
            - ``kilometer`` 2.6
          * - nanometer
            - ``nm`` 38, ``nanometre`` 37
            - ``nanometer`` 2.6
          * - centimeter
            - ``cm`` 37, ``centimetre`` 37
            - ``centimeter`` 2.6
          * - micrometer
            - ``um`` 38, ``µm`` 38, ``micrometre`` 39
            - ``micrometer``, ``micron`` 2.6
          * - degree
            - ``degrees`` 18
            - ``deg``, ``degree`` 2.5
          * - radian
            - ``radians`` 18
            - ``rad``, ``radian`` 2.5
          * - steradian
            -
            - ``sr``, ``steradian`` 2.6
          * - second
            - ``seconds`` 17
            - ``s``, ``second``, ``sec`` 2.6
          * - kilogram
            - ``kg`` 38
            - ``kilogram`` 2.5
          * - gram
            -
            - ``g``, ``gram`` 2.5
          * - watt
            -
            - ``W``, ``watt`` 2.4
          * - byte
            -
            - ``B``, ``byte`` 2.4
          * - dimensionless
            -
            - ``dimensionless`` 4.2
          * - percent
            - ``%`` 4.9
            - ``percent`` 2.4
          * - ppm
            -
            - ``ppm`` 2.5
          * - m/s
            -
            - ``m/s`` (all forms equal) 7.0
          * - 1/km
            - ``km^-1`` 36, ``1/km`` 38
            - ``kilometer^-1``, ``1/kilometer`` 5.5
          * - 1/m
            -
            - ``1/m`` (all forms equal) 5.5
          * - 1/cm
            - ``cm^-1`` 39, ``1/cm`` 39
            - ``centimeter^-1`` 5.6
          * - 1/sr
            -
            - ``1/sr`` (all forms equal) 5.6
          * - mg/m³
            - ``mg/m^3`` 40
            - ``milligram/meter^3`` 7.1
          * - g/kg
            - ``g/kg`` 39
            - ``gram/kilogram`` 6.9
          * - W/m²
            -
            - ``W/m^2`` (all forms equal) 7.0
          * - W/m²/sr/nm
            - ``W/m^2/sr/nm`` 42
            - ``watt/meter^2/steradian/nanometer`` 9.8

* **Prefer strings over Pint registry attribute lookups.**
  A registry attribute lookup is slightly more costly than a string lookup::

    # Avoid
    ureg.m

    # Prefer
    ureg.Unit("m")

* **Create quantities with the constructor and string parsing.**
  There is no significant performance difference between the operator and
  constructor forms of quantity creation; but given what we said about string
  parsing vs attribute lookup::

    # Avoid (although very compact)
    1.0 * ureg.m

    # Prefer (still quite compact)
    ureg.Quantity(1.0, "m")

xarray usage
^^^^^^^^^^^^

*TBD*

Value caching
^^^^^^^^^^^^^

*TBD*

Style
-----

Ruff all the way.
