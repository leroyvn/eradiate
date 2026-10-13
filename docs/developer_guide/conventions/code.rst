.. _sec-developer_guide-code:

Coding conventions
==================

*State: Draft.*

This page covers the general principles and style rules for library code in
``src/eradiate``. Rules specific to unit handling, data structures, docstrings,
deprecations and licensing have their own pages in this section.

Required reading
----------------

Eradiate's class engine is built on a few libraries whose documentation is
worth reading before writing new classes:

* `attrs <https://www.attrs.org>`__: Eradiate's classes are ``attrs`` classes.
  Understand the ``attrs`` initialization sequence, and how callables are used
  to set defaults and to create converters and validators.
* `Pint <https://pint.readthedocs.io>`__: unit handling (see also
  :ref:`sec-developer_guide-units`).
* `Pinttrs <https://pinttrs.readthedocs.io>`__: Pint-based extensions to
  ``attrs``.
* `Dessine-moi <https://dessinemoi.readthedocs.io>`__: the library Eradiate's
  factories are built on (see :ref:`sec-design_notes-factories`).

Principles
----------

Prefer relative imports in library code
    We use relative imports in library code, and absolute imports in tests and
    application code.

Minimize class initialization code
    Using ``attrs`` encourages minimizing the amount of complex logic
    implemented by constructors. Although ``attrs`` provides the
    ``__attrs_post_init__()`` method to do so, we avoid it as much as possible.
    If a constructor must perform special tasks, this logic is usually better
    implemented as a *class method constructor* (*e.g.* ``from_something()``).

Make sure that experiment configuration objects can be reached with the dict configuration interface
    A lot of Eradiate's classes can be instantiated using dictionaries. Most of
    them use factories for that purpose (see
    :ref:`sec-design_notes-factories`). In practice, this reserves the
    ``"type"`` and ``"construct"`` parameters, meaning that factory-registered
    classes cannot have ``type`` or ``construct`` fields.

    For classes unregistered to any factory, our convention is to implement
    dictionary-based initialization as a ``from_dict()`` class method
    constructor. It should behave like :meth:`dessinemoi.Factory.convert`,
    *i.e.*:

    * interpret units using :func:`pinttrs.interpret_units`;
    * [optional] if relevant, allow for class method constructor selection using
      the ``"construct"`` parameter.

Keep expensive libraries at the boundary
    This includes Pint and xarray: most of the operations these libraries
    perform add significant overhead which we would rather do without in the hot
    parts of processing. See :ref:`sec-developer_guide-units` and
    :ref:`sec-developer_guide-data`.

Cache expensive operations
    Do not recompute something that is already computed. This is critical in the
    spectral loop, but also during scene initialization.

Style
-----

* The codebase follows `PEP8 <https://www.python.org/dev/peps/pep-0008/>`__.
  The formatter and linter is `Ruff <https://github.com/astral-sh/ruff>`__,
  configured in ``ruff.toml`` and run by the pre-commit hooks (see
  :ref:`sec-developer_guide-workflow`).
  `Editor integration instructions <https://docs.astral.sh/ruff/editors/>`__
  are available.
* Docstrings follow the Numpydoc format, with the additions documented in
  :ref:`sec-developer_guide-docstrings`.
* Library code has type hints. Test code generally does not.
