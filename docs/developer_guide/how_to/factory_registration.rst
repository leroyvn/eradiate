.. _sec-developer_guide-factory_registration:

Registering a class to a factory
================================

How to make a class instantiable from a dictionary through a factory, and how
to document a new factory. The factory design is explained in
:ref:`sec-design_notes-factories`.

Enabling a class for factory usage
----------------------------------

Outside of Eradiate
    Classes can be registered to a factory using the
    factory's :meth:`Factory.register <dessinemoi.Factory.register>` class
    decorator (which should be applied *after* the ``attrs.define`` decorator).
    Our convention is to use the ``type_id`` keyword argument to declare the
    factory identifier—not a ``_TYPE_ID`` class attribute.

    .. note::
       All the arguments of the
       :meth:`Factory.register <dessinemoi.Factory.register>` decorator are
       keyword-only.

Within Eradiate
    Eradiate's :ref:`lazy module import system <sec-developer_guide-lazy_imports>`
    makes it impossible to populate factories upon calling ``import eradiate``
    using the :meth:`Factory.register <dessinemoi.Factory.register>` decorator:
    even though the factory instance is created, the registered types are not
    imported and therefore do not hook into the factory if not imported
    individually, which defeats the purpose of using the
    :meth:`Factory.register <dessinemoi.Factory.register>` method.
    Therefore, factory registration must be done alongside factory creation,
    using the :meth:`.Factory.register_lazy_batch` method.

Documenting factories
---------------------

Documenting factories requires specific steps to work around Python's and
Sphinx's limitations regarding data member documentation. Upon adding a new
factory, please make sure you:

* add your new factory instance to the ``docs/_generate/factories.py`` script
  (``FACTORIES`` variables);
* add your new factory to the list of instances in the
  :mod:`eradiate._factory` documentation (``docs/reference_api/factory.rst``).
