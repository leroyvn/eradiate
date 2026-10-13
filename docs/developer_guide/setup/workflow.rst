.. _sec-developer_guide-workflow:

Development workflow
====================

This page covers day-to-day tooling once the
:ref:`development installation <sec-developer_guide-install>` is complete: Pixi environments and tasks,
pre-commit hooks, and Git submodule handling.

Pixi environments
-----------------

Eradiate is managed with `Pixi <https://pixi.sh/>`__. Environments are
defined in ``pyproject.toml``:

``default``
    The everyday development environment (Python 3.10, with recommended, test
    and development dependencies).
``test``
    Used by the CI.
``docs``
    Python 3.11, used to build the documentation.
``py39`` … ``py313``
    Resolution-only environments, used to check that a production environment
    can be solved on every supported Python version.
``dev``
    Deprecated alias of ``default``.

Tasks are attached to features. Tasks of the ``docs`` feature therefore require
an explicit environment, *e.g.* ``pixi run -e docs docs-build``. Run
``pixi task list`` for the complete task list. Note that tasks that are defined
only for one specific environment will automatically be run in that environment
(*e.g.* ``pixi run docs-build`` should also work).

Common tasks
------------

``pixi run kernel-build``
    Compile the radiometric kernel. Run it after updating the kernel source or
    its dependencies (see :ref:`sec-developer_guide-install-compiling`).
``pixi run test``, ``pixi run test-quick``
    Run the test suite (see :ref:`sec-developer_guide-testing`).
``pixi run docs-build``
    Build the documentation (see :ref:`sec-developer_guide-documentation`).
``pixi run lint``
    Run the Ruff linter.

Pre-commit hooks
----------------

The hooks defined in ``.pre-commit-config.yaml`` format and lint code with
Ruff, strip notebook outputs, format TOML files, and regenerate the
documentation requirement file and the PyPI README. We strongly recommend
installing them, either with `pre-commit <https://pre-commit.com/>`__ or its
faster replacement `prek <https://prek.j178.dev/>`__.

Shallow submodule caveats
-------------------------

Eradiate uses Git submodules to ship some of its data. Over time, these can grow
and become large enough to justify using a *shallow submodule*. Shallow clones
do not contain the entire history of the repository and are therefore more
lightweight, saving bandwidth upon cloning.

However, shallow clones can be difficult to work with, especially when one
starts branching. If a shallow submodule is missing a remote branch you'd expect
it to track,
`this post <https://stackoverflow.com/questions/23708231/git-shallow-clone-clone-depth-misses-remote-branches>`_
contains probably what you need to do:

.. code:: shell

   cd my-shallow-submodule
   git remote set-branches origin '*'
   git fetch -v
   git checkout the-branch-i-ve-been-looking-for
