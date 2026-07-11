.. _sec-config:

``eradiate.config``
===================

.. automodule:: eradiate.config

Core members
------------

.. py:currentmodule:: eradiate.config

.. data:: SOURCE_DIR
   :annotation: = pathlib.Path or None

   Path to the Eradiate source code directory, if relevant. Takes the value of
   the ``ERADIATE_SOURCE_DIR`` environment variable if it is set; otherwise
   defaults to ``None``.

.. py:currentmodule:: eradiate.config

.. data:: settings
   :annotation: = eradiate.config.EradiateSettings

   Main settings data structure (an :class:`.EradiateSettings` instance). The
   canonical access idiom is lowercase attribute access; dict-style access
   with case-insensitive dotted keys is also supported:

   .. code:: python

      settings.data_path
      settings["some.key"]
      settings.get("SOME.KEY", default)

   All settings have a default value (see the
   :ref:`example configuration file <sec-user_guide-config-default>`)
   and can be overridden by the user from an ``eradiate.toml``,
   ``eradiate.yaml`` or ``eradiate.yml`` file, placed in the current working
   directory or higher. Each setting can also be overridden using environment
   variables with the ``ERADIATE_`` prefix.

   .. admonition:: Example
      :class: tip

      The ``some.key`` setting will be accessed as ``ERADIATE_SOME__KEY`` (note
      the double underscore to figure the hierarchical separator).

.. autosummary::
   :toctree: generated/autosummary/

   _settings.EradiateSettings
   _settings.AbsorptionDatabaseSettings

Utility
-------

.. autoclass:: ProgressLevel
   :members:
