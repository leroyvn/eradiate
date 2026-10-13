.. _sec-design_notes-factories:

Factories
=========

:Status: Implemented
:Last updated: 2025-09
:Code: ``src/eradiate/_factory.py``

Eradiate's object creation process is heavily supported by a set of instances of
the :class:`.Factory` class. They serve two purposes:

* provide a safe and flexible converter system to support Eradiate's
  ``attrs``-based features;
* based on the previous mechanism, create objects from a uniform specification
  method based on (possibly nested) dictionaries.

.. warning:: It is strongly advised to read the documentation of the
   `Dessine-moi library <https://dessinemoi.readthedocs.io/>`__ for an overview
   of Eradiate's factories.

Overview and usage
------------------

Eradiate's factories are instances of the :class:`.Factory` class, itself
derived from the :class:`dessinemoi.Factory` class.

Internally, a :class:`.Factory` instance maintains a *registry* which maps
string-typed identifiers to information required to create instances of
registered types. Each registry entry consists of the type registered under the
associated identifier, as well as an optional field specifying which class
method constructor should be used when converting dictionaries.

The :meth:`Factory.convert() <dessinemoi.Factory.convert>` method is the main
entry point to factories in Eradiate. If this method is passed a dictionary, it
pre-processes it, then tries to instantiate one of the registered types based on
the information contained in the dictionary; otherwise, it does nothing and just
returns the object it is passed.

.. admonition:: Example
   :class: tip

   The following code snippet instantiates a
   :class:`~eradiate.scenes.illumination.DirectionalIllumination` element
   using its ``directional`` factory identifier:

   .. code:: python

      from eradiate.scenes.illumination import illumination_factory

      illumination = illumination_factory.convert({
          "type": "directional",
          "irradiance": {"type": "uniform", "value": 1.0},
          "zenith": 30.0,
          "azimuth": 180.0,
      })

   In practice, the ``type`` key is used to look up the class to instantiate,
   then popped from the configuration dictionary. Therefore, the corresponding
   object creation call is, in this particular case:

   .. code:: python

      DirectionalIllumination(
          irradiance={"type": "uniform", "value": 1.0},
          zenith=30.0,
          azimuth=180.0,
      )

.. admonition:: Notes
   :class: note

   * :meth:`Factory.convert() <dessinemoi.Factory.convert>` is powered by the
     low-level :meth:`Factory.create() <dessinemoi.Factory.create>` method.
   * :class:`.Factory` is sometimes subclassed to allow for different conversion
     protocols.
