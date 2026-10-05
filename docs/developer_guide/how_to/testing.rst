.. _sec-developer_guide-testing:

Testing
=======

How to run the test suite, the pytest options and fixtures specific to
Eradiate, and how to document tests. Regression tests have their own page:
:ref:`sec-developer_guide-regression_tests`.

Eradiate's tests are written with `pytest <https://docs.pytest.org/en/latest/>`__.
They live in the ``tests/`` directory, grouped by complexity: unit tests, then
system tests, then regression tests.

Running the test suite
----------------------

.. code:: shell

   pixi run test          # Full test suite
   pixi run test-quick    # Skip tests marked 'slow' and 'regression'
   pixi run test-cov      # Full test suite with coverage report

Any pytest argument can be passed through ``pixi run pytest``. Tests can be
selected with the ``unit``, ``system``, ``regression`` and ``slow`` markers,
*e.g.* ``pixi run pytest -m "not slow"``.

pytest is configured in ``pytest.toml`` (not ``pyproject.toml``). This
configuration requires pytest 9 or later and turns warnings into errors.

Command-line options
--------------------

The following options are declared in ``tests/conftest.py``:

``--plot``
    Produce and save diagnostic plots.
``--artefact-dir``
    Directory where test artefacts are written. Defaults to
    ``$ERADIATE_SOURCE_DIR/test_artefacts/``.
``--reference-dir``
    Directory regression test references are read from and written to (see
    :ref:`sec-developer_guide-regression_tests`).

Mode fixtures
-------------

``tests/conftest.py`` generates fixtures that activate an operational mode from
the list returned by :func:`eradiate.modes`. They are not defined literally
anywhere, so searching for their name will not find their definition:

* ``mode_<name>`` activates a single mode, *e.g.* ``mode_mono``,
  ``mode_ckd_double``;
* ``modes_<group>`` is parametrized over a group of modes, *e.g.*
  ``modes_all_mono``, ``modes_all_ckd``, ``modes_all_polarized``. The full
  list of groups is defined by the ``variant_groups`` dictionary.

Writing test specifications
---------------------------

Eradiate's tests can be roughly categorised as follows:

* unit tests focus on the smallest testable units of code;
* system tests check the behaviour of entire applications;
* regression tests which compare simulation results with previous versions.

While categorising each individual test is not always an easy task, this
nomenclature highlights the fact that tests have varied degrees of complexity.
When the rationale, setup and course of action of a test is not obvious by
reading the corresponding source code, properly documenting it in a structured
way is crucial. For this reason, Eradiate defines a test description template to
be used for system and regression tests.

The test specification consists of three main parts:

1. the **description of the test rationale**;
2. the **details of the setup**, explaining, in prose, how a test is designed;
3. the **expected outcome** of the test, which describes based on what the test
   should pass or fail.

The following template can be copied to new test cases and the information
filled in as needed. Note that we strongly suggest using string literals
(prefixed with a ``r``) in order to avoid issues with escape sequences.

.. code:: python

    r"""
    Test title
    ==========

    :Description: This is the short description of the test case

    Rationale
    ---------

    This is some explanatory text

    * This section explains the details
    * Of how the test is implemented
    * It can contain math! :math:`e^{i\pi}=-1`

    Expected behaviour
    ------------------

    This section explains the expected result of the test and how it is asserted.

    * We assert that something was calculated
    * Additionally the result must be correct
    """

The test specification can hold any valid restructured text. A quick rundown on that can be found
`here <https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html>`__.

Test reports
------------

Test results can be compiled into an HTML report using
`Robot Framework <https://robotframework.org/>`__. The robotframework pytest
plugin is disabled by default; the following tasks enable it:

.. code:: shell

   pixi run test-report             # All tests
   pixi run test-unit-report        # Tests marked 'unit'
   pixi run test-system-report      # Tests marked 'system'
   pixi run test-regression-report  # Tests marked 'regression'
   pixi run test-slow-report        # Tests marked 'slow'

Reports are written to ``reports/``. This default is set by the
``pytest_robot_modify_options()`` hook in ``tests/conftest.py``; explicit
``--robot-*`` options take precedence.

Tests send messages and plots to the report through
:class:`eradiate.testing.report.ReportLogger`, which falls back to standard
:mod:`logging` when no Robot Framework run is active. Do not import
``robot.api`` directly in tests.

The test specification of unit tests does not have to comply with the
template above. For those, a short explanation is sufficient, but the three
parts of the template should still serve as a guideline.

.. admonition:: To be written
   :class: warning

   State whether the Robot Framework report renders the test specification
   docstrings, and what the report contains. The previous version of this
   page referred to a separate
   `report tool <https://github.com/eradiate/eradiate-test-report>`__; check
   whether it is still in use.
