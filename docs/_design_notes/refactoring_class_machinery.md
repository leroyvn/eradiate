# Update Plan — Class Machinery Refactoring

Consolidates two previously separate plans:
- stub generation infrastructure (Plan 1)
- field documentation refactor (Plan 2, depends on Plan 1)

Both target `ext/eradiate/src/eradiate/attrs.py` and share several components. The
refactor supersedes the incremental additions in Plan 1, so steps are ordered to avoid
double work.

---

## Background

### Problem 1 — Type checker rejects valid converter arguments

Eradiate's attrs classes use converters: a field annotated `PlaneParallelGeometry` may
accept `str | dict | SceneGeometry` at `__init__` time. Without `@dataclass_transform`,
the type checker is unaware that `define`/`frozen` produce dataclass-like classes, so it
raises `unknown-argument` errors. Adding `@dataclass_transform` fixes that class of error
but exposes `invalid-argument-type` errors, because `@dataclass_transform` propagates
field annotations directly to `__init__` parameters with no awareness of converters.

**Fix**: (a) add `@dataclass_transform` to `define`/`frozen`; (b) generate `.pyi` stubs
with accurate `__init__` signatures that reflect converter input types.

### Problem 2 — Runtime docstring mutation is architecturally unclean

`documented()` attaches metadata; `parse_docs()` mutates `cls.__doc__` at import time.
This is verbose, couples two separate functions implicitly, and complicates the stub
generator (which needs to import modules).

**Fix**: replace `documented()` with a new `field()` function; move docstring generation
to a Sphinx autodoc extension that runs at build time.

### Shared design decision

Both fixes need a `init_annotation` metadata key (Python type syntax, e.g.
`"str | dict | Foo"`) and a `_annotation_to_rst()` converter. These are implemented once
and shared by the Sphinx extension and the stub generator.

---

## Key Files

- `ext/eradiate/src/eradiate/attrs.py` — main changes
- `ext/eradiate/src/eradiate/experiments/_atmosphere.py` — primary motivating example
- `ext/eradiate/src/eradiate/util/numpydoc.py` — reused by Sphinx extension
- `ext/eradiate/docs/_ext/eradiate_autodoc.py` — new Sphinx extension
- `ext/eradiate/docs/conf.py` — register extension (line 44)
- `ext/eradiate/scripts/generate_stubs.py` — new stub generator
- `ext/eradiate/pyproject.toml` — taskipy tasks
- All source files using `documented()` — ~85 classes, incremental migration

---

## Implementation Steps

### Step 1 — Extend `MetadataKey` and add shared `_annotation_to_rst()`

**File**: `ext/eradiate/src/eradiate/attrs.py`

Add `INIT_ANNOTATION` to the enum:

```python
class MetadataKey(enum.Enum):
    DOC = "doc"
    TYPE = "type"
    INIT_TYPE = "init_type"              # deprecated RST string
    DEFAULT = "default"
    INIT_ANNOTATION = "init_annotation"  # NEW — Python type annotation string
```

Add `_annotation_to_rst()` in `attrs.py` (it will also be imported by the Sphinx
extension and stub generator):

```python
_BUILTIN_NAMES = frozenset({
    "str", "int", "float", "bool", "bytes", "dict", "list", "tuple", "set",
    "frozenset", "type", "object", "None", "Any", "Optional", "Union",
    "Callable", "Sequence", "Mapping", "Iterable", "Iterator", "Type",
    "ClassVar", "Final", "Literal",
})

def _split_union(annotation: str) -> list[str]:
    """Split a type annotation on top-level | characters (bracket-depth aware)."""
    parts, depth, start = [], 0, 0
    for i, ch in enumerate(annotation):
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == "|" and depth == 0:
            parts.append(annotation[start:i])
            start = i + 1
    parts.append(annotation[start:])
    return parts

def _annotation_to_rst(annotation: str) -> str:
    """Convert a Python type annotation string to numpydoc RST."""
    result = []
    for token in _split_union(annotation):
        token = token.strip()
        name = token.split("[")[0].strip()
        if name in _BUILTIN_NAMES:
            result.append(token)
        elif "." in name:
            result.append(f":class:`{token}`")   # qualified: no leading dot
        else:
            result.append(f":class:`.{token}`")  # unqualified: leading dot for relative lookup
    return " or ".join(result)
```

### Step 2 — Add the new `field()` function

**File**: `ext/eradiate/src/eradiate/attrs.py`

Define `field()` **before** `define`/`frozen` so it can be listed in their
`field_specifiers`. It replaces `documented()` and accepts all attrs/pinttr kwargs plus
inline doc metadata:

```python
def field(
    *,
    # attrs.field() pass-through:
    default=attrs.NOTHING,
    factory=None,
    validator=None,
    repr=attrs.HAS_DEFAULT_VALUE,
    hash=None,
    init=True,
    metadata=None,
    converter=None,
    kw_only=False,
    eq=None,
    on_setattr=attrs.HAS_DEFAULT_VALUE,
    alias=None,
    # pinttr-specific (routes to pinttr.field() when present):
    units=None,
    # Documentation:
    doc: str | None = None,
    type_doc: str | None = None,          # stored/attribute type string, shown in Attributes section
    init_annotation: str | None = None,   # Python type syntax, auto-converted to RST
    init_doc: str | None = None,          # free-form init type string, shown in Parameters section
    default_doc: str | None = None,       # override default repr in docs; omit to let Sphinx render it
) -> Any:
    """An attrs field with optional inline documentation metadata."""
    doc_metadata = {}
    if doc is not None:
        doc_metadata[MetadataKey.DOC] = doc
    if type_doc is not None:
        doc_metadata[MetadataKey.TYPE] = type_doc
    if init_annotation is not None:
        doc_metadata[MetadataKey.INIT_ANNOTATION] = init_annotation
    if init_doc is not None:
        doc_metadata[MetadataKey.INIT_TYPE] = init_doc
    if default_doc is not None:
        doc_metadata[MetadataKey.DEFAULT] = default_doc

    combined_metadata = {**(metadata or {}), **doc_metadata}

    if units is not None:
        import pinttr
        # Forward only kwargs pinttr.field() accepts — verify pinttr signature first
        return pinttr.field(units=units, ..., metadata=combined_metadata)
    else:
        return attrs.field(
            default=default, factory=factory, validator=validator,
            repr=repr, hash=hash, init=init, metadata=combined_metadata,
            converter=converter, kw_only=kw_only, eq=eq,
            on_setattr=on_setattr, alias=alias,
        )
```

Key notes:
- `type_doc` and `init_doc` mirror the `_doc` suffix of `default_doc`, making it clear
  these are documentation strings, not type annotations used by the runtime.
- `init_doc` is a free-form string (shown as-is in the Parameters section); use
  `init_annotation` when you want automatic RST rendering from Python type syntax.
- `default_doc` avoids name clash with attrs' `default` parameter. When omitted, the
  Sphinx autodoc extension renders the default from the live `__init__` signature — so
  `default_doc` is only needed when the repr is misleading or the value is a sentinel.
- Lazy `import pinttr` inside the `units is not None` branch avoids a hard import-time
  dependency.
- Verify exactly which kwargs `pinttr.field()` accepts before forwarding.

### Step 3 — Add `@dataclass_transform` to `define`/`frozen`, add `field` to specifiers, drop `parse_docs()`

**File**: `ext/eradiate/src/eradiate/attrs.py`

`@dataclass_transform` has not been applied yet. Add it here, together with `field` in
`field_specifiers` and removal of the `parse_docs()` call:

```python
from typing import dataclass_transform   # add import

@dataclass_transform(field_specifiers=(attrs.attrib, attrs.field, field))
def define(maybe_cls=None, **kwargs):
    def wrap(cls):
        return attrs.define(maybe_cls=cls, **kwargs)   # no parse_docs() call
    return wrap if maybe_cls is None else wrap(maybe_cls)

@dataclass_transform(frozen_default=True, field_specifiers=(attrs.attrib, attrs.field, field))
def frozen(maybe_cls=None, **kwargs):
    def wrap(cls):
        return attrs.frozen(maybe_cls=cls, **kwargs)   # no parse_docs() call
    return wrap if maybe_cls is None else wrap(maybe_cls)
```

After this step, run `uv run ty check` on a sample file to confirm `unknown-argument`
errors are gone. `invalid-argument-type` errors are expected to appear at this point and
will be resolved by the stubs in Step 7.

### Step 4 — Deprecate `documented()` and remove internal doc machinery

**File**: `ext/eradiate/src/eradiate/attrs.py`

Remove:
- `parse_docs()`
- `_FieldDoc`
- `_numpy_formatter()`
- `_eradiate_formatter()`
- `DocFlags`

Keep/update:
- `MetadataKey` — already updated in Step 1.
- `get_doc()` — add `"init_annotation"` as a valid `field` literal value:
  ```python
  def get_doc(
      cls: type,
      attrib: str,
      field: Literal["doc", "type", "init_type", "init_annotation", "default"],
  ) -> str: ...
  ```
  (`"type"` and `"init_type"` are the internal `MetadataKey` values; the public `field()`
  parameters `type_doc`/`init_doc` map to these keys.)
- `documented()` — keep but emit `DeprecationWarning` directing users to `field()`.
- `AUTO` / `_Auto` — unchanged.

### Step 5 — Create the Sphinx autodoc extension

**New file**: `ext/eradiate/docs/_ext/eradiate_autodoc.py`

This replaces the runtime `parse_docs()` with a build-time hook:

```python
import re
import attrs
from eradiate.attrs import MetadataKey, _annotation_to_rst
from eradiate.util import numpydoc


def _field_doc_sections(cls) -> tuple[list[str], list[str]]:
    """Return (param_lines, attr_lines) in numpydoc format for an attrs class."""
    param_lines, attr_lines = [], []

    for f in attrs.fields(cls):
        meta = f.metadata
        if MetadataKey.DOC not in meta:
            continue

        doc = meta[MetadataKey.DOC]
        type_str = meta.get(MetadataKey.TYPE, str(f.type) if f.type else "")
        default_str = meta.get(MetadataKey.DEFAULT)

        if MetadataKey.INIT_ANNOTATION in meta:
            init_type_str = _annotation_to_rst(meta[MetadataKey.INIT_ANNOTATION])
        elif MetadataKey.INIT_TYPE in meta:
            init_type_str = meta[MetadataKey.INIT_TYPE]   # legacy RST string, use as-is
        else:
            init_type_str = type_str

        name = f.name.lstrip("_")

        if f.init is not False:
            # Only append default fragment when explicitly provided; otherwise Sphinx
            # autodoc renders the default from the __init__ signature automatically.
            default_part = f", default: {default_str}" if default_str else ""
            param_lines.append(f"{name} : {init_type_str}{default_part}")
            for line in doc.splitlines():
                param_lines.append(f"    {line}")
            param_lines.append("")

        if not f.name.startswith("_"):
            brief = re.split(r"\. |\.\n", doc)[0].strip()
            if not brief.endswith("."):
                brief += "."
            attr_lines.append(f"{name} : {type_str}")
            attr_lines.append(f"    {brief}")
            attr_lines.append("")

    return param_lines, attr_lines


def _process_docstring(app, what, name, obj, options, lines):
    if what != "class":
        return
    try:
        has_attrs = attrs.has(obj)
    except Exception:
        return
    if not has_attrs:
        return

    param_lines, attr_lines = _field_doc_sections(obj)
    if not param_lines and not attr_lines:
        return

    existing = "\n".join(lines)
    sections = numpydoc.parse_doc(existing) if existing.strip() else {}

    if param_lines:
        sections["Parameters"] = "\n".join(param_lines) + sections.get("Parameters", "")
    if attr_lines:
        sections["Attributes"] = "\n".join(attr_lines) + sections.get("Attributes", "")

    lines[:] = numpydoc.format_doc(sections).splitlines()


def setup(app):
    app.connect("autodoc-process-docstring", _process_docstring)
    return {"version": "0.1", "parallel_read_safe": True}
```

Notes:
- `Attributes` is a standard numpydoc/Napoleon section — no custom `napoleon_custom_sections`
  entry needed. Remove any existing `"Fields"` entry from `conf.py` line 157.
- `attrs.fields(cls)` naturally includes inherited fields; no special handling required.

### Step 6 — Register extension in `docs/conf.py`

```python
extensions = [
    ...
    "autodocsumm",
    "eradiate_autodoc",   # NEW
]
```

### Step 7 — Write the stub generator

**New file**: `ext/eradiate/scripts/generate_stubs.py`

```text
Usage:
  python scripts/generate_stubs.py             # regenerate all
  python scripts/generate_stubs.py --check     # diff only, exit 1 if stale (CI)
  python scripts/generate_stubs.py src/eradiate/experiments/_atmosphere.py  # single file
```

Algorithm:
1. Discover all Python modules under `src/eradiate/` via `pkgutil.walk_packages`.
2. Import each module; iterate classes where `attrs.has(cls) is True`.
3. Skip classes in `__init__` modules (those have hand-written re-export stubs).
4. For each class, call `attrs.fields(cls)`; for each field:
   - **Init type**: `field.metadata.get(MetadataKey.INIT_ANNOTATION)` if present; else
     the field's own type annotation string (conservative fallback).
   - **Stored type**: field type annotation.
   - **Skip**: `field.init is False`.
5. Emit a class block:
   ```python
   class Foo(Base):
       field_a: StoredTypeA
       field_b: StoredTypeB
       def __init__(self, field_a: InitTypeA = ..., field_b: InitTypeB = ...) -> None: ...
   ```
6. Collect referenced type names and emit necessary imports under a `TYPE_CHECKING` guard.
7. Write one `.pyi` file per source module **next to the `.py` file** (inline, PEP 561).
8. Prepend a header comment marking the file as auto-generated.

Commit generated stubs so downstream type checkers work without running the generator.

### Step 8 — Wire into taskipy

**File**: `ext/eradiate/pyproject.toml`

```toml
[tool.taskipy.tasks]
stubs = "python scripts/generate_stubs.py"
stubs-check = "python scripts/generate_stubs.py --check"
```

### Step 9 — Migrate priority fields

**File**: `ext/eradiate/src/eradiate/experiments/_atmosphere.py`

Convert the five `AtmosphereExperiment` fields that caused the original `ty` errors. Use
the new `field()` form with `init_annotation`:

```python
# Before
geometry = documented(
    attrs.field(default=..., converter=..., validator=...),
    doc="...", type="...", init_type="str or dict or .SceneGeometry", default='"...'",
)

# After
geometry = field(
    default=..., converter=..., validator=...,
    type_doc="...", init_annotation="str | dict | SceneGeometry",
    doc="...", default_doc='"..."',
)
```

Fields to migrate:
- `geometry`: `"str | dict | SceneGeometry"`
- `atmosphere`: `"Atmosphere | dict | None"`
- `surface`: `"BasicSurface | BSDF | dict | None"`
- `illumination`: `"AbstractDirectionalIllumination | ConstantIllumination | dict"`
- `measures`: `"MeasureRegistry | dict"`

### Step 10 — Migrate remaining `documented()` call sites (incremental)

Convert all remaining `documented(attrs.field(...), ...)` and
`documented(pinttr.field(...), ...)` calls across the ~85 classes. Can be done with an
AST-based script or class by class. The mapping is:

```python
# Before
x = documented(
    attrs.field(default="foo", converter=Bar.convert, validator=...),
    doc="...", type="...", init_type="str or dict or .Bar", default='"foo"',
)

# After
x = field(
    default="foo", converter=Bar.convert, validator=...,
    doc="...", type_doc="...", init_annotation="str | dict | Bar", default_doc='"foo"',
)
```

Per-file import update: `from eradiate.attrs import documented` → `from eradiate.attrs
import field`.

No hard deadline — `documented()` emits `DeprecationWarning` but keeps working until
fully removed.

### Step 11 — CI (follow-up)

Add `uv run task stubs-check` to the lint/type-check GitHub Actions workflow to catch
stale stubs when field definitions change.

---

## Open Points

- **pinttr kwarg routing**: confirm which kwargs `pinttr.field()` accepts. The `field()`
  implementation must forward only compatible kwargs.
- **`_annotation_to_rst()` visibility**: currently in `attrs.py` and imported by the
  Sphinx extension. If it grows complex, factor into `eradiate/util/` instead.
- **`help()` regression**: after Step 4, `help(SomeClass)` in a Python REPL will not
  show auto-generated Parameters/Attributes sections. Accepted trade-off.

---

## Verification

```bash
# After Steps 1–6: docs build correctly
cd ext/eradiate && uv run task docs
# Spot-check AtmosphereExperiment page: Parameters and Attributes sections present

# After Step 7–8: stubs generate and pass the check
uv run task stubs
uv run task stubs-check

# After Step 9: ty is happy with the motivating case
uv run ty check playgrounds/test_03_standard.ipynb
# Target: 0 invalid-argument-type errors for the five AtmosphereExperiment fields

# Always: existing tests still pass
uv run pytest

# Regression: deprecated documented() still works without hard breakage
uv run python -c "
import warnings
from eradiate.attrs import field
import attrs

@attrs.define
class Foo:
    x = field(default=1, doc='test', type='int', default_doc='1')

print('field() works:', attrs.fields(Foo))
"
```
