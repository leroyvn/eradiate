from __future__ import annotations

import logging
import typing as t
from collections.abc import Mapping

import drjit as dr
import mitsuba as mi
from mitsuba.python.util import _jit_id_hash

logger = logging.getLogger(__name__)


class SceneParameters(Mapping):
    """
    Dictionary-like object that references various parameters used in a Mitsuba
    scene graph. Parameters can be read and written using standard syntax
    (``parameter_map[key]``).

    Notes
    -----
    This class is a reimplementation of :class:`mitsuba.SceneParameters`. It
    adds support for object ID-based aliases.
    """

    def __init__(self, properties=None, hierarchy=None, aliases=None):
        """
        Private constructor (use :func:`mi_traverse()` instead).
        """
        self.properties = properties if properties is not None else {}
        self.hierarchy = hierarchy if hierarchy is not None else {}
        self.aliases = aliases if aliases is not None else {}
        self.update_candidates = {}
        self.nodes_to_update = {}

        self.set_property = mi.set_property
        self.get_property = mi.get_property

    def copy(self):
        return SceneParameters(
            dict(self.properties), dict(self.hierarchy), dict(self.aliases)
        )

    def __contains__(self, key: str):
        return self.properties.__contains__(key)

    def __get_value(self, key: str):
        value, value_type, node, _ = self.properties[key]

        if value_type is not None:
            value = self.get_property(value, value_type, node)

        return value

    def __getitem__(self, key: str):
        if key not in self.properties and key in self.aliases:
            key = self.aliases[key]
        value = self.__get_value(key)

        if key not in self.update_candidates:
            self.update_candidates[key] = _jit_id_hash(value)

        return value

    def __setitem__(self, key: str, value):
        if key not in self.properties and key in self.aliases:
            key = self.aliases[key]
        cur, value_type, node, _ = self.properties[key]

        cur_value = cur
        if value_type is not None:
            cur_value = self.get_property(cur, value_type, node)

        if _jit_id_hash(cur_value) == _jit_id_hash(value) and cur_value == value:
            # Turn this into a no-op when the set value is identical to the new value
            return

        self.set_dirty(key)

        if value_type is None:
            try:
                cur.assign(value)
            except AttributeError as e:
                if "has no attribute 'assign'" in str(e):
                    mi.Log(
                        mi.LogLevel.Warn,
                        f"Parameter '{key}' cannot be modified! This usually "
                        "happens when the parameter is not a Mitsuba type."
                        "Please use non-scalar Mitsuba types in your custom "
                        "plugins.",
                    )
                else:
                    raise e
        else:
            self.set_property(cur, value_type, value)

    def __delitem__(self, key: str) -> None:
        del self.properties[key]

    def __len__(self) -> int:
        return len(self.properties)

    def __repr__(self) -> str:
        if len(self) == 0:
            return f"SceneParameters[]"

        name_length = int(max(len(k) for k in self.properties.keys()) + 2)
        type_length = int(
            max(
                len(type(v[0] if v[1] is None else self.get_property(*v[:3])).__name__)
                for k, v in self.properties.items()
            )
        )
        hrule = "  " + "-" * (name_length + 53)

        param_list = [
            hrule,
            f"  {'Name':{name_length}}  {'Flags':7}  {'Type':{type_length}} {'Parent'}",
            hrule,
        ]
        for k, v in self.properties.items():
            value, value_type, node, flags = v

            if value_type is not None:
                value = self.get_property(value, value_type, node)

            flags_str = ""
            if (flags & mi.ParamFlags.NonDifferentiable) == 0:
                flags_str += "∂"
            if (flags & mi.ParamFlags.Discontinuous) != 0:
                flags_str += ", D"

            param_list.append(
                f"  {k:{name_length}}  {flags_str:7}  {type(value).__name__:{type_length}} {node.class_().name()}"
            )

        alias_list = [hrule, "  Aliases", hrule]
        for k, v in self.aliases.items():
            alias_list.append(f"  {k} → {v}")
        alias_list.append(hrule)

        return (
            "SceneParameters[\n"
            + "\n".join(param_list)
            + "\n"
            + "\n".join(alias_list)
            + "\n]"
        )

    def __iter__(self):
        class SceneParametersItemIterator:
            def __init__(self, pmap):
                self.pmap = pmap
                self.it = pmap.keys().__iter__()

            def __iter__(self):
                return self

            def __next__(self):
                key = next(self.it)
                return (key, self.pmap[key])

        return SceneParametersItemIterator(self)

    def items(self):
        return self.__iter__()

    def keys(self):
        return self.properties.keys()

    def _ipython_key_completions_(self):
        return self.properties.keys()

    def flags(self, key: str):
        """Return parameter flags"""
        return self.properties[key][3]

    def set_dirty(self, key: str):
        """
        Marks a specific parameter and its parent objects as dirty. A subsequent
        call to :meth:`~.SceneParameters.update()` will refresh their internal
        state.

        This method should rarely be called explicitly. The
        :class:`.SceneParameters` will detect most operations on
        its values and automatically flag them as dirty. A common exception to
        the detection mechanism is the :meth:`~drjit.scatter` operation which
        needs an explicit call to :meth:`~.SceneParameters.set_dirty()`.
        """
        value, _, node, flags = self.properties[key]

        is_nondifferentiable = flags & mi.ParamFlags.NonDifferentiable.value
        if is_nondifferentiable and dr.grad_enabled(value):
            mi.Log(
                mi.LogLevel.Warn,
                f"Parameter '{key}' is marked as non-differentiable but has "
                "gradients enabled, unexpected results may occur!",
            )

        node_key = key
        while node is not None:
            parent, depth = self.hierarchy[node]
            name = node_key
            if parent is not None:
                node_key, name = node_key.rsplit(".", 1)

            self.nodes_to_update.setdefault((depth, node), set())
            self.nodes_to_update[(depth, node)].add(name)

            node = parent

        return self.properties[key]

    def update(self, values: dict = None) -> list[tuple[t.Any, set]]:
        """
        This function should be called at the end of a sequence of writes
        to the dictionary. It automatically notifies all modified Mitsuba
        objects and their parent objects that they should refresh their
        internal state. For instance, the scene may rebuild the kd-tree
        when a shape was modified, etc.

        Parameters
        ----------
        values : dict
            Optional dictionary-like object containing a set of keys and values
            to be used to overwrite scene parameters. This operation will happen
            before propagating the update further into the scene internal state.

        Returns
        -------
        A list of tuples where each tuple corresponds to a Mitsuba node/object
        that is updated. The tuple's first element is the node itself.
        The second element is the set of keys that the node is being updated for.
        """
        if values is not None:
            for k, v in values.items():
                if k in self or k in self.aliases:
                    self[k] = v

        update_candidate_keys = list(self.update_candidates.keys())
        for key in update_candidate_keys:
            # Candidate objects might have been modified inplace, we must check
            # the JIT identifiers to see if the object has truly changed.
            if _jit_id_hash(self.__get_value(key)) == self.update_candidates[key]:
                continue

            self.set_dirty(key)

        for key in self.keys():
            dr.schedule(self.__get_value(key))

        # Notify nodes from bottom to top
        work_list = [(d, n, k) for (d, n), k in self.nodes_to_update.items()]
        work_list = reversed(sorted(work_list, key=lambda x: x[0]))
        out = []
        for _, node, keys in work_list:
            node.parameters_changed(list(keys))
            out.append((node, keys))

        self.nodes_to_update.clear()
        self.update_candidates.clear()
        dr.eval()

        return out

    def keep(self, keys: None | str | list[str]) -> None:
        """
        Reduce the size of the dictionary by only keeping elements,
        whose keys are defined by `keys`.

        Parameters
        ----------
        keys : list of str, str or None
            Specifies which parameters should be kept. Regex are supported to
            define a subset of parameters at once. If set to ``None``, all
            differentiable scene parameters will be loaded.
        """
        if type(keys) is not list:
            keys = [keys]

        import re

        regexps = [re.compile(k).match for k in keys]

        # Collect keys associated with matching aliases and param names
        alias_matches = [k for k in self.aliases.keys() if any(r(k) for r in regexps)]
        param_matches = [k for k in self.keys() if any(r(k) for r in regexps)]

        # Extend param match list with alias matches
        keys = param_matches + [self.aliases[k] for k in alias_matches]

        # Trim param list
        self.properties = {k: v for k, v in self.properties.items() if k in keys}

        # Trim alias list
        self.aliases = {k: v for k, v in self.aliases.items() if k in alias_matches}


def mi_traverse(node: "mitsuba.Object") -> SceneParameters:
    """
    Traverse a node of Mitsuba's scene graph and return a dictionary-like
    object that can be used to read and write associated scene parameters.

    See also :class:`.SceneParameters`.

    Notes
    -----
    This is a reimplementation of :func:`mitsuba.traverse`, with added support
    for parameter aliases.
    """

    class SceneTraversal(mi.TraversalCallback):
        def __init__(
            self,
            node,
            parent=None,
            properties=None,
            hierarchy=None,
            prefixes=None,
            name=None,
            depth=0,
            flags=+mi.ParamFlags.Differentiable,
            aliases=None,
        ):
            mi.TraversalCallback.__init__(self)

            self.properties = dict() if properties is None else properties
            self.hierarchy = dict() if hierarchy is None else hierarchy
            self.prefixes = set() if prefixes is None else prefixes
            self.aliases = dict() if aliases is None else aliases

            if name is not None:
                ctr, name_len = 1, len(name)
                while name in self.prefixes:
                    name = "%s_%i" % (name[:name_len], ctr)
                    ctr += 1
                self.prefixes.add(name)

            self.name = name
            self.node = node
            self.depth = depth
            self.hierarchy[node] = (parent, depth)
            self.flags = flags

        def put_parameter(self, name, ptr, flags, cpptype=None):
            alias = f"{self.node.id()}.{name}" if self.node.id() else None
            name = name if self.name is None else self.name + "." + name

            flags = self.flags | flags
            # Non differentiable parameters shouldn't be flagged as discontinuous
            if (flags & mi.ParamFlags.NonDifferentiable) != 0:
                flags = flags & ~mi.ParamFlags.Discontinuous

            self.properties[name] = (ptr, cpptype, self.node, self.flags | flags)
            if alias is not None and alias != name:
                self.aliases[alias] = name

        def put_object(self, name, node, flags):
            if node is None or node in self.hierarchy:
                return
            cb = SceneTraversal(
                node=node,
                parent=self.node,
                properties=self.properties,
                hierarchy=self.hierarchy,
                prefixes=self.prefixes,
                name=name if self.name is None else self.name + "." + name,
                depth=self.depth + 1,
                flags=self.flags | flags,
                aliases=self.aliases,
            )
            node.traverse(cb)

    cb = SceneTraversal(node)
    node.traverse(cb)

    return SceneParameters(cb.properties, cb.hierarchy, cb.aliases)
