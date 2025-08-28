# core/theme.py
import streamlit as st

THEMES = {
    "light": {
        "page_bg":        "#44a04c",
        "text":           "#111111",
        "muted_text":     "#ffffff",
        "accent":         "#2e6d33",
        "sidebar_bg":     "#b2deb5",
        "sidebar_text":   "#357e3c",
        "sidebar_border": "3px solid #2e6d33",
        "card_bg":        "#ffffff",
        "card_border":    "3px solid #2e6d33",
    },
    "dark": {
        "page_bg":        "#1d4520",
        "text":           "#020603",
        "muted_text":     "#9ca3af",
        "accent":         "#5bd66f",
        "sidebar_bg":     "#102318",
        "sidebar_text":   "#acdcb0",     # you wanted this
        "sidebar_border": "3px solid #1f5c26",
        "card_bg":        "#132018",
        "card_border":    "5px solid #ffffff",
    },
}

def apply_theme(mode: str = "light") -> None:
    t = THEMES.get(mode, THEMES["light"])
    st.markdown(
        f"""
        <style>
          :root {{
            --do-page-bg: {t['page_bg']};
            --do-text: {t['text']};
            --do-muted-text: {t['muted_text']};
            --do-accent: {t['accent']};
            --do-sidebar-bg: {t['sidebar_bg']};
            --do-sidebar-text: {t['sidebar_text']};
            --do-sidebar-border: {t['sidebar_border']};
            --do-card-bg: {t['card_bg']};
            --do-card-border: {t['card_border']};
          }}

          html, body, .stApp {{
            background: var(--do-page-bg) !important;
            color: var(--do-text) !important;
          }}

          /* Make default text honor the theme */
          .stApp, .stMarkdown, p, span, label, li, small, strong,
          h1, h2, h3, h4, h5, h6 {{
            color: var(--do-text) !important;
          }}

          /* Sidebar shell picks up theme vars by default */
          section[data-testid="stSidebar"] {{
            background: var(--do-sidebar-bg) !important;
            border-right: var(--do-sidebar-border) !important;
          }}
          section[data-testid="stSidebar"] * {{
            color: var(--do-sidebar-text) !important;
          }}
        </style>
        """,
        unsafe_allow_html=True,
    )

def fix_select_colors(dark: bool) -> None:
    """Force readable colors for selects, their menus, and text/number/textarea inputs."""
    if dark:
        # dark palette (kept close to your choices)
        ctrl_bg       = "#204b23"   # input/select background
        ctrl_text     =  "#8acdcb"   # input/select text & icons
        border        = "#49ac51"
        menu_bg       = "#49ac51"   # dropdown panel background
        menu_text     = "#ffffff"   # readable on dark
        hover_bg      = "#ffffff"
        selected_bg   = "#3d8f44"
        selected_text = "#89cd8f"
        focus_ring    = "#ceead1"   # ring/glow color
        focus_border  = "#4bb254"   # border on focus
    else:
        # light palette
        ctrl_bg       = "#67bf6e"
        ctrl_text     = "#ffffff"
        border        = "#020603"
        menu_bg       = "#ffffff"
        menu_text     = "#ffffff"
        hover_bg      = "#112813"
        selected_bg   = "#112813"
        selected_text = "#ffffff"
        focus_ring    = "#2e6d33"
        focus_border  = "#2e6d33"

    st.markdown(
        f"""
        <style>
          /* ===== Select & Multiselect (closed control) ===== */
          .stSelectbox [data-baseweb="select"] > div,
          .stMultiSelect [data-baseweb="select"] > div {{
            background: {ctrl_bg} !important;
            color: {ctrl_text} !important;
            border: 2px solid {border} !important;
            position: relative;     /* enable ::after overlay */
            overflow: visible;
          }}
          .stSelectbox input, .stMultiSelect input {{
            color: {ctrl_text} !important;
          }}
          .stSelectbox svg, .stMultiSelect svg {{
            color: {ctrl_text} !important;
            fill: currentColor !important;
          }}
          .stSelectbox label, .stMultiSelect label {{
            color: {ctrl_text} !important;
          }}

          /* ===== Focus overlay ABOVE content ===== */
          .stSelectbox [data-baseweb="select"]:focus-within > div::after,
          .stMultiSelect [data-baseweb="select"]:focus-within > div::after,
          .stApp div[data-baseweb="input"]:focus-within > div::after {{
            content: "";
            position: absolute;
            inset: -2px;
            border-radius: inherit;
            z-index: 2;             /* sits above text/icons */
            pointer-events: none;
            /* veil + inner ring + soft outer glow */
            background: radial-gradient(150% 120% at 50% 0%, {focus_ring}26 0%, transparent 70%);
            box-shadow:
              0 0 0 2px {focus_ring} inset,
              0 6px 22px 0 {focus_ring}66;
          }}

          /* Keep border color change on focus */
          .stSelectbox [data-baseweb="select"]:focus-within > div,
          .stMultiSelect [data-baseweb="select"]:focus-within > div,
          .stApp div[data-baseweb="input"]:focus-within > div {{
            border-color: {focus_border} !important;
          }}

          /* ===== Dropdown menu (portal at app root) ===== */
          .stApp [data-baseweb="popover"] [role="listbox"],
          .stApp [data-baseweb="popover"] [data-baseweb="menu"] {{
            background: {menu_bg} !important;
            border: 1px solid {border} !important;
          }}
          .stApp [data-baseweb="popover"] [role="option"] {{
            color: {menu_text} !important;
          }}
          .stApp [data-baseweb="popover"] [role="option"][aria-selected="true"] {{
            background: {selected_bg} !important;
            color: {selected_text} !important;
          }}
          .stApp [data-baseweb="popover"] [role="option"]:hover {{
            background: {hover_bg} !important;
            color: {menu_text} !important;
          }}

          /* ===== Text / Number / Textarea ===== */
          .stApp div[data-baseweb="input"] > div {{
            background: {ctrl_bg} !important;
            border: 2px solid {border} !important;
            color: {ctrl_text} !important;
            position: relative;     /* enable ::after overlay */
            overflow: visible;
          }}
          .stApp div[data-baseweb="input"] input {{
            color: {ctrl_text} !important;
          }}
          .stApp div[data-baseweb="input"] input::placeholder,
          .stTextArea textarea::placeholder {{
            color: {ctrl_text}99 !important;
          }}
          .stTextArea textarea {{
            background: {ctrl_bg} !important;
            color: {ctrl_text} !important;
            border: 2px solid {border} !important;
          }}
          .stNumberInput svg {{
            color: {ctrl_text} !important;
            fill: currentColor !important;
          }}
        </style>
        """,
        unsafe_allow_html=True,
    )
