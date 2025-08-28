"""Theme persistence helpers for Streamlit apps.

Keeps a dark/light toggle consistent across pages and refreshes by using
st.session_state *and* the URL query string (?theme=dark|light).

Usage (on every page):

    from core.theme_persist import init_theme, render_toggle, sidebar_skin, nav_colors
    from core.theme import apply_theme, fix_select_colors
    from core.ui_sidebar import apply_sidebar_shell, SIDEBAR_CFG

    # 1) Initialize before reading ui_dark
    ui_dark = init_theme(default=False,
                         apply_theme_fn=apply_theme,
                         fix_select_colors_fn=fix_select_colors)

    # 2) (Optional) Render the toggle inside a sidebar card
    with sidebar_card("Appearance", icon="🌓"):
        ui_dark = render_toggle()

    # 3) Build/attach sidebar skin
    SIDEBAR_CFG.update(sidebar_skin(ui_dark))
    apply_sidebar_shell()

    # 4) Use nav_colors(ui_dark) for your select/menu CSS

"""
from __future__ import annotations

from typing import Callable, Dict
import streamlit as st

# ------------------------------- Internals ---------------------------------

def _get_qs_theme() -> str | None:
    """Return 'dark'/'light'/None from the URL query string.

    Supports Streamlit new and legacy query param APIs.
    """
    try:
        # Streamlit >= 1.30
        qs = st.query_params  # type: ignore[attr-defined]
        theme = qs.get("theme") if qs else None
        if isinstance(theme, list):
            theme = theme[0] if theme else None
        return theme
    except Exception:
        pass

    try:
        # Legacy
        qs = st.experimental_get_query_params()
        theme_list = qs.get("theme", [])
        return theme_list[0] if theme_list else None
    except Exception:
        return None


def _set_qs_theme(theme: str) -> None:
    """Write theme to the URL query string (keeps other params intact)."""
    try:
        # Streamlit >= 1.30
        current = dict(st.query_params)  # type: ignore[attr-defined]
        current["theme"] = theme
        st.query_params.update(current)  # type: ignore[attr-defined]
        return
    except Exception:
        pass

    try:
        # Legacy
        current = st.experimental_get_query_params()
        current["theme"] = theme
        st.experimental_set_query_params(**current)
    except Exception:
        # Non-fatal if this fails
        return


# ------------------------------ Public API ---------------------------------

def init_theme(
    default: bool = False,
    apply_theme_fn: Callable[[str], None] | None = None,
    fix_select_colors_fn: Callable[[bool], None] | None = None,
) -> bool:
    """Initialize `ui_dark` in session_state and apply the theme.

    Args:
        default: fallback if neither session nor URL has a value.
        apply_theme_fn: function like core.theme.apply_theme(mode: str).
        fix_select_colors_fn: function like core.theme.fix_select_colors(is_dark: bool).

    Returns:
        bool: the resolved `ui_dark` value.
    """
    # Resolve from URL on first load; otherwise keep existing session choice
    if "ui_dark" not in st.session_state:
        qs_theme = _get_qs_theme()
        if qs_theme in {"dark", "light"}:
            st.session_state["ui_dark"] = (qs_theme == "dark")
        else:
            st.session_state["ui_dark"] = bool(default)

    ui_dark: bool = bool(st.session_state["ui_dark"])  # type: ignore[assignment]

    # Apply if hooks provided
    if apply_theme_fn:
        apply_theme_fn("dark" if ui_dark else "light")
    if fix_select_colors_fn:
        fix_select_colors_fn(ui_dark)

    return ui_dark


def render_toggle(
    label: str = "Dark mode",
    state_key: str = "ui_dark",
    widget_key: str = "ui_dark_toggle",
) -> bool:
    """Render a dark-mode toggle and sync to URL without colliding widget keys.

    Args:
        label: UI label for the toggle.
        state_key: session_state key that stores the actual dark/light boolean.
        widget_key: unique widget key for the toggle component itself
                    (kept distinct to avoid DuplicateWidgetID if something
                    else also uses `state_key`).

    Returns:
        bool: updated dark-mode state from session_state[state_key].
    """
    # Read current state
    current = bool(st.session_state.get(state_key, False))

    # Callback to mirror widget value -> state key and update URL
    def _sync():
        val = bool(st.session_state.get(widget_key, current))
        st.session_state[state_key] = val
        _set_qs_theme("dark" if val else "light")

    # Create the widget using a *different* key from the state key
    st.toggle(label, value=current, key=widget_key, on_change=_sync)

    # Ensure state is in sync even on first render (when on_change hasn't fired yet)
    _sync()

    return bool(st.session_state[state_key])


def sidebar_skin(ui_dark: bool) -> Dict[str, str]:
    """Return a dictionary of sidebar skin variables to merge into SIDEBAR_CFG."""
    if ui_dark:
        return {
            "bg": "#111827",
            "text_color": "#e5e7eb",
            "border_right": "1px solid #374151",
        }
    else:
        return {
            "bg": "#b2deb5",
            "text_color": "#357e3c",
            "border_right": "3px solid #2e6d33",
        }


def nav_colors(ui_dark: bool) -> Dict[str, str]:
    """Provide consistent nav/select colors based on the theme."""
    return {
        "NAV_LABEL_COLOR":  "#000000" if ui_dark else "#2e6d33",
        "NAV_VALUE_COLOR":  "#e5e7eb" if ui_dark else "#2e6d33",
        "NAV_MENU_BG":      "#204b23" if ui_dark else "#ffffff",
        "NAV_MENU_TEXT":    "#000000" if ui_dark else "#111111",
        "NAV_INPUT_BG":     "#111827" if ui_dark else "#ffffff",
        "NAV_BORDER_COLOR": "#374151" if ui_dark else "#2e6d33",
    }


def is_dark() -> bool:
    """Helper to read the current `ui_dark` flag safely."""
    return bool(st.session_state.get("ui_dark", False))
