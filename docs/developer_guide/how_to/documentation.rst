.. _sec-developer_guide-documentation:

Documentation
=============

How to build the documentation and edit its generated parts and tutorials.
Docstring conventions for the API reference are documented in
:ref:`sec-developer_guide-docstrings`.

Building the documentation
--------------------------

Once Eradiate is installed, the documentation can be built using the following
command:

.. code:: shell

    pixi run docs-build

After the build is completed, the html document is located in
:code:`$ERADIATE_SOURCE_DIR/docs/_build/html`.

Alternatively, an automatically refreshed server can be started:

.. code:: shell

    pixi run docs-serve

Editing the data documentation
------------------------------

Data documentation is, for a large part, automatically generated using a
`Jinja <https://jinja.palletsprojects.com>`__ template-based system. The code to
generate the data docs pages is located in the
:code:`$ERADIATE_SOURCE_DIR/docs/_generate` directory, and called upon
``sphinx-build`` invocation as defined in ``conf.py`` (see the :code:`custom_step()`
function in that file).

Each custom build step may generate plots (see conditions below) and renders one
of the Jinja templates located in the :code:`$ERADIATE_SOURCE_DIR/docs/_generate/templates`
directory. The static part of the documentation, as well as how dynamic content
is generated, are defined there.

Images are generated only if no image exists so that, usually, no data is
required to generate the documentation, in particular when building the
documentation as part of CI. Consequently, to re-render the plots, the existing
ones must first be deleted. The plots are generated again upon the next call
to ``sphinx-build``.


Editing tutorials
-----------------

Eradiate comes with tutorials shipped as Jupyter notebooks, saved to the
"`tutorials <https://github.com/eradiate/eradiate-tutorials>`_\ " submodule.
They are integrated in this documentation using the
`nbsphinx <https://nbsphinx.readthedocs.io/>`__ extension.

The recommended way to edit tutorials is as follows:

1. Open a terminal and start a Jupyter session.
2. In another terminal, open a Sphinx server using the following command at the
   root of your local copy of Eradiate:

   .. code:: shell

      pixi run docs-serve

3. Browse to the tutorial you want to edit or create a new one using the
   tutorial template. You can now edit the content and see how it renders
   dynamically.

   .. important::

      Make sure that the first cell is as follows:

      .. code:: shell

         %reload_ext eradiate.notebook.tutorials

Nbsphinx renders markdown cells, but also allows to define raw reST cells, which
then support all usual Sphinx features (references, admonitions, etc.). See
`the documentation <https://nbsphinx.readthedocs.io/en/latest/raw-cells.html>`_
for more detail.

Tutorials are currently not run as part of the documentation build process;
instead, the output of the rendered notebook is checked in to the Git
repository. The reason for this is that rendering tutorials when building the
documentation would require a fully functional copy of Eradiate, including its
radiometric kernel Mitsuba. This is currently unachievable on the Read the Docs
service we use to deploy automatically the documentation upon committing to
GitHub: Mitsuba must be compiled and Read the Docs does not support its build
process.

.. important::

   Once you're done editing a tutorial, do not forget to rerun it entirely in a
   clean Jupyter session to render it as if you were a user.

Thumbnail galleries are not trivial difficult to fine-tune. The following pages
are useful when working on them:

* Galleries are created in Markdown/reST files following
  `these instructions <https://nbsphinx.readthedocs.io/en/latest/a-normal-rst-file.html#thumbnail-galleries>`__.
* Thumbnail selection is done following the
  recommendations of the nbsphinx documentation:
  `cell tag based <https://nbsphinx.readthedocs.io/en/latest/gallery/cell-tag.html>`__,
  `cell metadata based <https://nbsphinx.readthedocs.io/en/latest/gallery/cell-metadata.html>`__,
  `Sphinx config based <https://nbsphinx.readthedocs.io/en/latest/gallery/thumbnail-from-conf-py.html>`__.
