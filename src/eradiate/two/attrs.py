from collections.abc import Sequence
from html import escape
from typing import Any, Mapping

import attrs
import pint

from eradiate.two import units_formatting


def get_fields(obj):
    """Get fields from attrs class."""
    if attrs.has(obj):
        return [
            (f.name, getattr(obj, f.name), False if f.repr is False else True)
            for f in attrs.fields(type(obj))
        ]
    else:
        return []


def _make_collapsible(summary: str, content: str, collapsible: bool):
    """Create collapsible HTML structure if needed."""
    if collapsible:
        return f"<details><summary>{escape(summary)}</summary>{content}</details>"
    return content


def _format_sequence(obj: Sequence, indent: int, collapsible: bool):
    """Format list or tuple objects."""
    items = "".join(
        f"<li>{attrs_to_html(item, indent + 1, collapsible)}</li>" for item in obj
    )
    content = f"<ul>{items}</ul>"

    if collapsible and len(obj) > 0:
        summary = f"{type(obj).__name__}[{len(obj)}]"
        return _make_collapsible(summary, content, True)
    return content


def _format_dict(obj: Mapping, indent, collapsible):
    """Format dictionary objects."""
    rows = "".join(
        f"<tr><td>{escape(str(k))}</td><td>{attrs_to_html(v, indent + 1, collapsible)}</td></tr>"
        for k, v in obj.items()
    )
    content = f"<table>{rows}</table>"

    if collapsible and len(obj) > 0:
        summary = f"dict[{len(obj)}]"
        return _make_collapsible(summary, content, True)
    return content


def _format_repr_object(obj: Any, collapsible: bool):
    """Format objects using their repr() representation."""
    obj_repr = repr(obj)

    if collapsible and obj_repr.count("\n") >= 3:
        first_line = obj_repr.split("\n")[0]
        if len(first_line) > 60:
            first_line = first_line[:57] + "..."
        summary = f"{type(obj).__name__}: {first_line}"
        content = f"<code>{escape(obj_repr)}</code>"
        return _make_collapsible(summary, content, True)

    return f"<code>{escape(obj_repr)}</code>"


def _format_attrs_object(obj: Any, indent: int, collapsible: bool):
    """Format attrs objects."""
    class_name = obj.__class__.__name__
    field_data = get_fields(obj)

    field_rows = [
        f"<tr><td>{escape(field_name)}</td><td>{attrs_to_html(field_value, indent + 1, collapsible)}</td></tr>"
        for field_name, field_value, has_repr in field_data
        if has_repr
    ]

    content = "".join(field_rows)
    css_class = f"{class_name} attrs"

    if collapsible and indent > 0:
        n_fields = len([x for x in field_data if x[2] is not False])
        summary = f"{class_name}({n_fields} field{'s' if n_fields > 1 else ''})"
        wrapped_content = f'<div class="{css_class}"><table>{content}</table></div>'
        return _make_collapsible(summary, wrapped_content, True)

    return (
        f'<div class="{css_class}"><h3>{class_name}</h3><table>{content}</table></div>'
    )


def _format_quantity(obj: Any):
    """Format Pint quantity."""
    obj_repr = units_formatting.inline_repr(obj, 50)
    return f"<code>{escape(obj_repr)}</code>"


def attrs_to_html(obj: Any, indent: int = 0, collapsible: bool = True):
    """Convert an attrs object to HTML representation with collapsible nested objects."""
    # Handle attrs objects first to avoid recursion with _repr_html_
    if attrs.has(obj):
        return _format_attrs_object(obj, indent, collapsible)

    # Special case for Pint units
    if isinstance(obj, pint.Quantity):
        return _format_quantity(obj)

    # Check if object has its own HTML representation
    if hasattr(obj, "_repr_html_") and callable(getattr(obj, "_repr_html_")):
        return obj._repr_html_()

    # Handle non-attrs objects with type dispatch
    type_handlers = {
        (list, tuple): lambda: _format_sequence(obj, indent, collapsible),
        dict: lambda: _format_dict(obj, indent, collapsible),
    }

    for obj_type, handler in type_handlers.items():
        if isinstance(obj, obj_type):
            return handler()

    # Handle all other objects
    return _format_repr_object(obj, collapsible)


def _minify_css(css: str) -> str:
    """Minify CSS by removing comments, whitespace, and newlines."""
    import re

    # Remove comments
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    # Remove extra whitespace and newlines
    css = re.sub(r"\s+", " ", css)
    # Remove spaces around certain characters
    css = re.sub(r"\s*([{}:;,>+~])\s*", r"\1", css)
    return css.strip()


def attrs_to_html_with_styles(obj: Any, collapsible: bool = True) -> str:
    """Generate HTML with embedded CSS styles for better presentation."""
    html_content = attrs_to_html(obj, collapsible=collapsible)

    styles = """
    <style>
    .structured-root {
        --border-color: #ddd;
        --summary-bg: #f0f0f0;
        --summary-hover: #e0e0e0;
        --summary-text: #555;

        color: var(--text-color);
    }

    /* Dark theme detection */
    html[data-theme="dark"] .structured-root,
    html[data-jp-theme-name*="dark"] .structured-root,
    body[data-theme="dark"] .structured-root,
    [data-jp-theme-light="false"] .structured-root,
    body[data-vscode-theme-kind*="dark"] .structured-root,
    body[data-vscode-theme-kind*="contrast"] .structured-root,
    .vscode-dark .structured-root,
    .vscode-high-contrast .structured-root {
        --border-color: #555;
        --bg-color: #2a2a2a;
        --summary-bg: #404040;
        --summary-hover: #505050;
        --summary-text: #e0e0e0;
    }

    .structured-root code {
        background: transparent !important;
        color: var(--code-color);
        font-family: monospace !important;
        white-space: pre !important;
    }
    .structured-root details {
        margin: 4px 0;
        padding: 4px;
        border: 1px solid var(--border-color);
        border-radius: 4px;
        max-width: 800px;
    }
    .structured-root details summary {
        cursor: pointer;
        font-weight: bold;
        padding: 2px 4px;
        background-color: var(--summary-bg);
        border-radius: 2px;
        color: var(--summary-text);
    }
    .structured-root details summary:hover {
        background-color: var(--summary-hover);
    }
    .structured-root details[open] summary {
        margin-bottom: 8px;
    }
    .structured-root table {
        border-collapse: collapse;
        margin: 8px 0;
        width: 100%;
        background: transparent;
        border: none !important;
        table-layout: auto;
    }
    .structured-root td {
        padding: 4px 8px;
        vertical-align: top;
        background: transparent !important;
        border: none !important;
        border-top: none !important;
        border-bottom: none !important;
        border-left: none !important;
        border-right: none !important;
    }
    .structured-root tr {
        background: transparent !important;
        border: none !important;
    }
    .structured-root td:first-child {
        font-weight: bold;
        text-align: right;
        width: 1%;
        white-space: nowrap;
    }
    .structured-root td:last-child {
        text-align: left;
        width: 99%;
    }
    .structured-root ul {
        margin: 4px 0;
        padding-left: 20px;
    }
    </style>
    """

    minified_styles = _minify_css(styles)
    return f"{minified_styles}<div class='structured-root'>{html_content}</div>"
