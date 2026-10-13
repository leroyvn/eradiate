.. _sec-developer_guide-docstrings:

Docstrings
==========

The API reference is generated from docstrings. This page documents the
docstring format and the helpers used to document ``attrs`` fields. How to
build the documentation is covered in :ref:`sec-developer_guide-documentation`.

We follow the
`Numpy docstring style <https://numpydoc.readthedocs.io/en/latest/format.html>`__,
with a few changes and updates documented hereafter.

Conventions
-----------

Docstrings start with a newline:

.. code:: python

   def my_func():
       """
       Docstring contents.
       """
       ...

Documenting classes
-------------------

In addition to the sections defined in the Numpy style guide, we add a "Fields"
section to our class docstrings. Class docstrings therefore have the following
structure:

Short summary
    A one-line summary that does not use variable names or the function name.
    It is notably printed in summary tables.
    `See the Numpy docstring style guide for more detail <https://numpydoc.readthedocs.io/en/latest/format.html#short-summary>`__.
Deprecation warning
    `See the Numpy docstring style guide for more detail <https://numpydoc.readthedocs.io/en/latest/format.html#deprecation-warning>`__.
Extended Summary
    `See the Numpy docstring style guide for more detail <https://numpydoc.readthedocs.io/en/latest/format.html#extended-summary>`__.
Parameters
    Description of the function arguments, keywords and their respective types.
    This section documents constructor parameters. Note that argument types
    should reflect types expected by the constructor, which can be broader
    than field types thanks to the ``attrs`` initialization sequence.
    `See the Numpy docstring style guide for more detail <https://numpydoc.readthedocs.io/en/latest/format.html#parameters>`__.
Fields
    Description of class attributes. This section replaces the *Attributes*
    section defined in the Numpy style guide. Since Eradiate uses ``attrs``,
    fields are usually very similar to constructor parameters and rendered with
    the same style. Types indicated in this section should reflect the true
    field type, after applying converters. We use dedicated utility functions
    to generate the *Parameters* and *Fields* sections from in-source
    documentation (see below).

    Important *don'ts*:

    * Properties are documented automatically by the autosummary extension: do
      not document them in this section, they will be displayed in a dedicated
      *Attributes* rubric on the class documentation page.
    * Do not use *ivar* to document attributes: use this section instead.
    * Do not use the *Methods* section.

Returns
    `See the Numpy docstring style guide for more detail <https://numpydoc.readthedocs.io/en/latest/format.html#returns>`__.
Yields
    `See the Numpy docstring style guide for more detail <https://numpydoc.readthedocs.io/en/latest/format.html#yields>`__.
Receives
    `See the Numpy docstring style guide for more detail <https://numpydoc.readthedocs.io/en/latest/format.html#receives>`__.
Other Parameters
    `See the Numpy docstring style guide for more detail <https://numpydoc.readthedocs.io/en/latest/format.html#other-parameters>`__.
Raises
    `See the Numpy docstring style guide for more detail <https://numpydoc.readthedocs.io/en/latest/format.html#raises>`__.
Warns
    `See the Numpy docstring style guide for more detail <https://numpydoc.readthedocs.io/en/latest/format.html#warns>`__.
Warnings
    `See the Numpy docstring style guide for more detail <https://numpydoc.readthedocs.io/en/latest/format.html#warnings>`__.
See Also
    `See the Numpy docstring style guide for more detail <https://numpydoc.readthedocs.io/en/latest/format.html#see-also>`__.
Notes
    `See the Numpy docstring style guide for more detail <https://numpydoc.readthedocs.io/en/latest/format.html#notes>`__.
References
    `See the Numpy docstring style guide for more detail <https://numpydoc.readthedocs.io/en/latest/format.html#references>`__.
Examples
    `See the Numpy docstring style guide for more detail <https://numpydoc.readthedocs.io/en/latest/format.html#examples>`__.

Field documentation helpers
---------------------------

Fields are documented using specific helper functions provided as part of
Eradiate' documentation framework. They notably allow to automatically create
class docstrings for classes with inherited fields.

The :func:`.parse_docs` decorator must be applied to the documented class  prior
to any other action. Then, each declared attribute can be documented using the
:func:`.documented` function:

.. code:: python

   import attrs
   from eradiate.attrs import documented, parse_docs

   @parse_docs  # Must be applied **after** attrs.define
   @attrs.define
   class MyClass:
       field: float | None = documented(
           attrs.field(default=None),
           doc="A documented attribute",
           type="float, optional",
           default="None",
       )

In addition, a ``init_type`` argument lets the user specify if constructor
argument types are different from the field type. This is particularly useful
when a converter is systematically applied to field values upon initialization:

.. code:: python

   import attrs
   import numpy as np
   from eradiate.attrs import documented, parse_docs

   @parse_docs  # Must be applied **after** attrs.define
   @attrs.define
   class MyClass:
       field: np.ndarray = documented(
           attrs.field(converter=np.array),
           doc="A documented attribute",
           type="ndarray",
           init_type="array-like",
       )

The ``doc``, ``type``, ``init_type`` and ``default`` parameters currently only
support string values.

Fields are sometimes partially redefined, but parts of their documentation can
be reused. For such cases, we provide the :func:`.get_doc` function:

.. code:: python

   import attrs
   from eradiate.attrs import documented, get_doc, parse_docs

   @parse_docs
   @attrs.define
   class MyChildClass(MyClass):
       field = documented(
           attrs.field(default=1.0),
           doc=get_doc(MyClass, "field", "doc"),
           type=get_doc(MyClass, "field", "type"),
           default="1.0",
       )
