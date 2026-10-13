.. _sec-developer_guide-deprecations:

Deprecations and removals
=========================

Eradiate tries to remain backward-compatible when possible. Sometimes however,
compatibility must be broken. Following the recommended practice in the Python
community, removals are, whenever possible, preceded by a deprecation period
during which a deprecated component is still available, marked as such in the
documentation, and using it triggers a :class:`DeprecationWarning`.

This workflow is facilitated by components defined in the
:mod:`util.deprecation <eradiate.util.deprecation>` module, and in particular
the :func:`.deprecated` decorator. Be sure to use them when relevant.
