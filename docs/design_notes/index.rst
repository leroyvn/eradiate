.. _sec-design_notes:

Design notes
============

Design notes explain why a component of Eradiate is built the way it is: the
problem it solves, the design that was chosen, and the alternatives that were
rejected. They complement the API reference, which documents what the
components do, and the :ref:`developer guide <sec-developer_guide>`, which
documents how to work on them.

Each note starts with the following fields:

``Status``
    ``Proposed``, ``Implemented``, ``Outdated`` (the code has changed and the
    note must be updated) or ``Superseded`` (with a reference to the
    replacing note).
``Last updated``
    Month of the last update of the note's content.
``Code``
    Source files the note describes.

New notes should use the following sections, skipping those that do not
apply: *Context*, *Goals*, *Design*, *Rejected alternatives*, *Consequences*.

.. toctree::
   :maxdepth: 1

   scene_generation
   factories
   atmosphere_geometry
   pipeline_engine
