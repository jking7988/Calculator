# core/ui_sidebar.py
from contextlib import contextmanager
import streamlit as st
import uuid
import base64

# Global defaults for the sidebar shell (can be updated at runtime)
SIDEBAR_CFG = {
    "width_px": 320,
    "bg": "#b2deb5",
    "text_color": "#000000",
    "pad_x": 12,
    "pad_y": 12,
    "border_right": "3px solid #2e6d33",
}

def apply_sidebar_shell():
    """Inject base CSS for the whole sidebar using current SIDEBAR_CFG values."""
    cfg = SIDEBAR_CFG
    st.markdown(f"""
    <style>
      section[data-testid="stSidebar"] {{
        width:{cfg["width_px"]}px !important;
        min-width:{cfg["width_px"]}px !important;
        background:{cfg["bg"]};
        border-right:{cfg["border_right"]};
      }}
      section[data-testid="stSidebar"] > div {{
        padding:{cfg["pad_y"]}px {cfg["pad_x"]}px;
      }}
      
    </style>
    """, unsafe_allow_html=True)

@contextmanager
def sidebar_card(
    title: str,
    *,
    icon: str | None = None,
    bg: str = "transparent",
    color: str = "#357e3c",
    pad_x: int = 12,
    pad_y: int = 12,
    border: str = "3px solid #2e6d33",
    radius_px: int = 12,
    shadow: str = "none",
    margin_bottom_px: int = 12,
    title_size_px: int = 16,
    title_weight: int = 700,
):
    """
    Styled replacement for st.sidebar.container that never crashes and
    doesn't create 'empty boxes'. If you put no content inside, nothing shows.
    """
    marker_id = f"card-{uuid.uuid4().hex}"
    # Inject CSS that targets only the wrapper that contains our hidden marker
    st.sidebar.markdown(f"""
    <style>
      section[data-testid="stSidebar"] div:has(> #{marker_id}) {{
        background:{bg};
        padding:{pad_y}px {pad_x}px;
        border:{border};
        border-radius:{radius_px}px;
        box-shadow:{shadow};
        margin-bottom:{margin_bottom_px}px;
      }}
      section[data-testid="stSidebar"] div:has(> #{marker_id}) :is(h1,h2,h3,h4,h5,label,p,span,small,li,strong) {{
        color:{color};
      }}
      /* Hide the wrapper entirely if it would be empty (no siblings after the marker) */
      section[data-testid="stSidebar"] div:has(> #{marker_id}:only-child) {{
        display:none;
      }}
    </style>
    """, unsafe_allow_html=True)

    c = st.sidebar.container()
    with c:
        # Hidden marker (allows us to scope styles to THIS card only)
        st.markdown(f'<div id="{marker_id}" style="display:none"></div>', unsafe_allow_html=True)
        # Title row (only if a title was passed)
        if title:
            ico = f"{icon} " if icon else ""
            st.markdown(
                f"<div style='font-size:{title_size_px}px; font-weight:{title_weight}; margin:0 0 8px 0;'>{ico}{title}</div>",
                unsafe_allow_html=True,
            )
        yield  # hand control back to caller to add widgets
