.. _sec-developer_guide-scene_element:

Writing a new scene element class
=================================

How to add a scene element class. The scene element types and the traversal
protocol are explained in :ref:`sec-design_notes-scene_generation`.

1. Decide whether the scene element is a :class:`.NodeSceneElement`,
   an :class:`.InstanceSceneElement` or a :class:`.CompositeSceneElement`.
   In most cases, the choice is constrained by the scene element subtype.
   For example, :class:`.BSDF`\ s are all :class:`.NodeSceneElement`\ s,
   :class:`.Surface`\ s are all :class:`.CompositeSceneElement`\ s, etc.
2. Derive a new class from the selected type and make sure that the properties
   mentioned in :ref:`sec-design_notes-scene_generation` are all implemented.

   .. list-table::
      :widths: 1 2
      :header-rows: 1

      * - Type
        - Properties
      * - :class:`.NodeSceneElement`
        - :attr:`~.NodeSceneElement.template`,
          :attr:`~.NodeSceneElement.params` [,
          :attr:`~.NodeSceneElement.objects`]
      * - :class:`.InstanceSceneElement`
        - :attr:`~.InstanceSceneElement.instance`,
          :attr:`~.InstanceSceneElement.params`
      * - :class:`.CompositeSceneElement`
        - :attr:`~.CompositeSceneElement.template`,
          :attr:`~.CompositeSceneElement.params` [,
          :attr:`~.CompositeSceneElement.objects`]

3. When writing unit tests, make sure to include a basic sanity check using the
   :func:`.check_scene_element` function.
