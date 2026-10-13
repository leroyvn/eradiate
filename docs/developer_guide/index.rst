.. _sec-developer_guide:

Developer guide
===============

Guides for working on Eradiate's codebase. The reasons behind the design of
Eradiate's components are explained in the :ref:`design notes
<sec-design_notes>`.

.. grid:: 1 2 auto auto
    :gutter: 3

    .. grid-item-card:: :iconify:`material-symbols:build height=1.5em` Setup

        Get your development environment running.

        * :doc:`setup/install`
        * :doc:`setup/update`
        * :doc:`setup/workflow`

    .. grid-item-card:: :iconify:`material-symbols:rule height=1.5em` Conventions

        Code writing rules.

        * :doc:`conventions/code`
        * :doc:`conventions/units`
        * :doc:`conventions/data`
        * :doc:`conventions/docstrings`
        * :doc:`conventions/deprecations`
        * :doc:`conventions/licensing`

    .. grid-item-card:: :iconify:`material-symbols:checklist height=1.5em` How-to

        Procedures for specific tasks.

        * :doc:`how_to/testing`
        * :doc:`how_to/regression_tests`
        * :doc:`how_to/documentation`
        * :doc:`how_to/scene_element`
        * :doc:`how_to/factory_registration`
        * :doc:`how_to/lazy_imports`
        * :doc:`how_to/benchmark_profile`

    .. grid-item-card:: :iconify:`material-symbols:engineering height=1.5em` Maintenance

        Pages for maintainers.

        * :doc:`maintainer/dependencies`
        * :doc:`maintainer/release`

.. toctree::
    :maxdepth: 1
    :hidden:

    setup/install
    setup/update
    setup/workflow

    conventions/code
    conventions/units
    conventions/data
    conventions/docstrings
    conventions/deprecations
    conventions/licensing

    how_to/testing
    how_to/regression_tests
    how_to/documentation
    how_to/scene_element
    how_to/factory_registration
    how_to/lazy_imports
    how_to/benchmark_profile

    maintainer/dependencies
    maintainer/release
