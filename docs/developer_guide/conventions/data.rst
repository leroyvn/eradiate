.. _sec-developer_guide-data:

Data structures and caching
===========================

Rules for using xarray in library code and for caching expensive values.

xarray usage
------------

.. admonition:: To be written
   :class: warning

   Where xarray objects are allowed (I/O, results, user-facing interfaces) and
   where plain arrays are expected instead (hot paths); conventions for
   dimension names, coordinates and the ``units`` attribute.

Value caching
-------------

.. admonition:: To be written
   :class: warning

   Which caching tools to use (``functools``, ``cachetools``), what to cache
   (spectral loop, scene initialization), and how to invalidate caches.
