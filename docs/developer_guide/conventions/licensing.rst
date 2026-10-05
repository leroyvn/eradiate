.. _sec-developer_guide-licensing:

Licensing and REUSE
===================

The project is licensed under ``LGPL-3.0-or-later`` and is
`REUSE <https://reuse.software/>`__-compliant. Files inherit copyright
(``The Eradiate Team``) and license from the ``**`` default annotation in
``REUSE.toml``, so new first-party files need no header. The license texts live
under ``LICENSES/``.

Third-party code is the exception: when adding a file copied or adapted from
another project, record the upstream copyright and license with an annotation in
``REUSE.toml`` (source files carry no SPDX headers) and drop the corresponding
license text in ``LICENSES/``:

.. code:: toml

    [[annotations]]
    # Adapted from upstream-project
    path = "src/eradiate/path/to/file.py"
    SPDX-FileCopyrightText = ["2020 The Eradiate Team", "2017 Upstream Author"]
    SPDX-License-Identifier = "LGPL-3.0-or-later AND Apache-2.0"

Verify compliance with ``pixi run lint-reuse``.
