"""Small HTML escaping helpers for safe interpolation into st.markdown/st_html.

Usage:
    from core.sanitize import e, srcdoc_escape

    COMPANY = e(st.session_state.get("company_name"))
    PROJECT = e(st.session_state.get("project_name"))
    ADDR    = e(st.session_state.get("project_address"))

    # When embedding a full HTML document into an <iframe srcdoc="...">
    srcdoc = srcdoc_escape(html_string)

- e(): escapes &, <, >, and quotes for safe attribute/text contexts
- srcdoc_escape(): additionally escapes double quotes for inclusion in srcdoc="..."
"""
from __future__ import annotations

from html import escape as _escape
from typing import Any, Dict

__all__ = ["e", "srcdoc_escape", "safe_attr", "build_attr"]


def e(value: Any) -> str:
    """HTML-escape a value for safe insertion into markup.

    Escapes &, <, >, and quotes. Converts None to "".
    """
    if value is None:
        return ""
    return _escape(str(value), quote=True)


def srcdoc_escape(html_text: Any) -> str:
    """Escape an HTML document string for use inside an iframe srcdoc attribute.

    We escape &, <, >, and then double quotes to &quot; so the attribute stays valid.
    """
    if html_text is None:
        return ""
    s = str(html_text)
    # First escape general HTML special chars
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Then escape quotes for the attribute context
    s = s.replace('"', "&quot;")
    return s


def safe_attr(value: Any) -> str:
    """Escape a value for use as an HTML attribute value."""
    return e(value)


def build_attr(**attrs: Any) -> str:
    """Build a string of HTML attributes with proper escaping.

    Example:
        build_attr(id="do-print", title="Print now")
        -> 'id="do-print" title="Print now"'
    """
    parts = []
    for k, v in attrs.items():
        if v is None:
            continue
        parts.append(f"{e(k)}=\"{e(v)}\"")
    return " ".join(parts)
