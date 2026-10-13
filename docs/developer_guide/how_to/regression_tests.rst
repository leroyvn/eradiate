.. _sec-developer_guide-regression_tests:

Regression tests
================

Regression tests compare the output of some component (typically, a simulation
pipeline) with a provided reference. Their purpose is to detect deviations from
prior behaviour established as correct when the reference was defined. These
tests can, on-demand, produce plots showing the test data (current and
reference) and metrics.

Responsibilities are split between:

* :mod:`eradiate.testing.regression`: provides statistical testing
  infrastructure (criteria and result plotting). These components are pure
  comparators that hold only comparison criteria, not the data they are applied
  to;
* the :func:`.dataset_regression` pytest fixture manages reference data: it
  locates references, regenerates them on demand and archives artefacts. It is
  built on `pytest-regressions <https://pytest-regressions.readthedocs.io>`__
  and leverages its ``--force-regen`` and ``--regen-all`` CLI flags.

To run only the regression tests, invoke pytest like this:

.. code:: shell

    pytest tests -m "regression" --artefact-dir <a directory of your choice>

Archived results and plots are written to the directory set by
``--artefact-dir`` (see :ref:`sec-developer_guide-testing`), which is created
if it does not exist.

Writing regression tests
------------------------

A regression test requests the :func:`.dataset_regression` fixture, runs its
simulation, then hands the result over together with the criterion it must
satisfy:

.. code:: python

    from eradiate.testing.regression import ZTest


    def test_my_case(mode_ckd_double, dataset_regression):
        result = eradiate.run(exp)

        dataset_regression.check(
            result,
            ZTest(0.05, variable="radiance"),
            basename="my_case_ref",
        )

``basename`` names the reference dataset within the reference directory, without
its ``.nc`` extension; it may contain forward slashes to address a
subdirectory. The threshold may depend on the scenario and on the chosen metric.

The :meth:`~.DatasetRegressionFixture.check` method raises a
:class:`.RegressionTestFailure` when the comparison fails, with the metric value
and the threshold in the message, so the numbers that decided the verdict appear
in the pytest failure report. In contrast, a :class:`ValueError` means that the
data is malformed, *e.g.* the result and the reference have different shapes.

Several criteria may share a single reference dataset. This is how a case
comparing more than one data variable is expressed:

.. code:: python

    dataset_regression.check(
        result,
        [RMSETest(2e-3, variable="hdrf"), RMSETest(2e-3, variable="bhr")],
        basename="my_case_ref",
    )

When a dataset groups several independent measurements, *e.g.* one per
wavelength, pass ``dim`` so that the criterion is applied to each slice
separately. The test then passes only if every slice passes, and reports the
worst one; this is stricter than comparing the flattened arrays in one go, where
good slices dilute a bad one:

.. code:: python

    dataset_regression.check(
        result,
        RMSETest(1e-6, variable="brf", dim="w"),
        basename="my_case_ref",
    )

A test that needs to know whether a reference exists before deciding what to
simulate (*e.g.* to render a high-sample-count reference with a different
integrator) can ask for it:

.. code:: python

    if dataset_regression.reference_path("my_case_ref") is None:
        ...

Creating and updating references
--------------------------------

References are read through the file resolver, which normally serves them from
the ``eradiate-data`` Git submodule under ``resources/data``. They are *not*
automatically written back to where they were read from.

Regenerating a reference is a three-step procedure:

1. Run the test with the ``--force-regen`` command-line flag:

   .. code:: shell

       pytest tests -m "regression" --force-regen --plot \
           --artefact-dir <a directory of your choice>

   A test whose reference is missing, or whose comparison fails, writes its own
   result as ``<basename>.nc`` into ``$ERADIATE_SOURCE_DIR/resources/data/tests/regression_test_references/``
   and *still fails* — the candidate has not been vetted by anyone yet. Use
   ``--reference-dir`` to write somewhere else.

   Without the ``--force-regen`` flag, a missing reference is a setup error and
   nothing is written: a typo in ``basename`` must not be mistaken for a
   deliberate reference regeneration.

2. Inspect the candidate. ``--plot`` writes a visualization to the artefact
   directory, and ``git -C resources/data diff`` shows exactly which references
   changed.

3. Promote it: commit the vetted files in the ``eradiate-data`` repository and
   open a pull request for the maintainers to review. Run
   ``git -C resources/data checkout .`` to discard candidates you do not want.

Use ``--regen-all`` to regenerate every reference in one run, letting the tests
pass. It is a blunt instrument: prefer ``--force-regen``, which only touches the
references that actually changed.

Analysing the results
---------------------

When a test fails due to a significant difference between the reference and the
result, the archived output helps the analysis. The result is stored as
``<basename>.obtained.nc`` in the artefact directory and can be loaded in Python
scripts for detailed analysis. With ``--plot``, the test also adds an overview
plot that shows the results, reference, the difference between the two and the
test metrics.

If the difference stems from a deliberate change to Eradiate's behaviour, the
reference needs to be updated — see `Creating and updating references`_ above.
