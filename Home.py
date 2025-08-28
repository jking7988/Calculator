# Home.py
import base64
import streamlit as st
from streamlit.components.v1 import html as st_html  # keep if you embed custom HTML
from core.theme_persist import init_theme, render_toggle, sidebar_skin, nav_colors
from core.theme import apply_theme, fix_select_colors
from core.ui_sidebar import apply_sidebar_shell, sidebar_card, SIDEBAR_CFG

# ===== Page config (call once, first) =======================================
st.set_page_config(
    page_title="Double Oak – Home",
    layout="centered",
    initial_sidebar_state="expanded",
)

# Hide Streamlit chrome (header/menu/footer) and pull content up a bit
st.markdown("""
<style>
header[data-testid="stHeader"] { display: none; }   /* top header bar */
#MainMenu { visibility: hidden; }                   /* hamburger menu */
footer { visibility: hidden; }                      /* "Made with Streamlit" */
div.block-container { padding-top: 1rem; }          /* reduce top gap after hiding header */
</style>
""", unsafe_allow_html=True)

# ===== THEME + SIDEBAR SKIN (shared pattern) ================================
# Initialize + apply theme (ensures st.session_state['ui_dark'] exists)
ui_dark = init_theme(apply_theme_fn=apply_theme, fix_select_colors_fn=fix_select_colors)

# Hide Streamlit's default page list in the sidebar
st.markdown("<style>[data-testid='stSidebarNav']{display:none}</style>", unsafe_allow_html=True)

# Appearance card (toggle uses distinct widget key under the hood)
with sidebar_card("Appearance", icon="🌓"):
    ui_dark = render_toggle()  # keeps st.session_state['ui_dark'] in sync

# Apply sidebar skin/shell AFTER toggle
SIDEBAR_CFG.update(sidebar_skin(ui_dark))
apply_sidebar_shell()

# ===================== Header (logo + title) ================================

def _load_logo_b64(path="assets/logo.png"):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    except Exception:
        return None

LOGO_B64 = st.session_state.get("logo_b64") or _load_logo_b64()
if LOGO_B64 and "logo_b64" not in st.session_state:
    st.session_state["logo_b64"] = LOGO_B64




# ---------- Navigation ----------
PAGES = {
    "Home": "Home.py",
    "Silt Fence": "pages/01_Silt_Fence.py",
    "Inlet Protection": "pages/02_Inlet_Protection.py",
    "Construction Entrance": "pages/03_Construction_Entrance.py",
    "Rock Filter Dams": "pages/04_Rock_Filter_Dams.py",
    "Turf Establishment": "pages/05_Turf_Establishment.py",
    "Aggregate": "pages/06_Aggregate.py",
    "Material Summary": "pages/99_Material_Summary.py",
}
CURRENT_PAGE = "Home"
choices = list(PAGES.keys())

# Dropdown color scheme (shared helper keeps it consistent with other pages)
c = nav_colors(ui_dark)
NAV_LABEL_COLOR, NAV_VALUE_COLOR = c["NAV_LABEL_COLOR"], c["NAV_VALUE_COLOR"]
NAV_MENU_BG, NAV_MENU_TEXT = c["NAV_MENU_BG"], c["NAV_MENU_TEXT"]
NAV_INPUT_BG, NAV_BORDER_COLOR = c["NAV_INPUT_BG"], c["NAV_BORDER_COLOR"]

st.markdown(f"""
<style>
/* Scope to the card that contains our marker #nav-dd */
section[data-testid="stSidebar"] div:has(> #nav-dd) label {{
  color: {NAV_LABEL_COLOR} !important;
}}
/* Closed select look (text + border + bg) */
section[data-testid="stSidebar"] div:has(> #nav-dd) [data-baseweb="select"] > div {{
  color: {NAV_VALUE_COLOR} !important;
  background: {NAV_INPUT_BG} !important;
  border: 1px solid {NAV_BORDER_COLOR} !important;
}}
/* Caret/icon */
section[data-testid="stSidebar"] div:has(> #nav-dd) [data-baseweb="select"] svg {{
  color: {NAV_VALUE_COLOR} !important;
  fill: {NAV_VALUE_COLOR} !important;
}}
/* Dropdown panel */
section[data-testid="stSidebar"] [data-baseweb="popover"] [role="listbox"] {{
  background: {NAV_MENU_BG} !important;
}}
/* Options inside the dropdown */
section[data-testid="stSidebar"] [data-baseweb="popover"] [role="option"] {{
  color: {NAV_MENU_TEXT} !important;
}}
</style>
""", unsafe_allow_html=True)

with sidebar_card("Navigate", icon="🧭", bg=("#0f1b12" if ui_dark else "#ffffff")):
    # marker so the CSS above only targets this select
    st.markdown('<div id="nav-dd" style="display:none"></div>', unsafe_allow_html=True)

    sel = st.selectbox(
        "Go to page",
        choices,
        index=choices.index(CURRENT_PAGE),
        key="nav_dd_home",
    )
    if sel != CURRENT_PAGE:
        # preserve theme across pages
        st.query_params.update({"theme": "dark" if st.session_state.get("ui_dark") else "light"})
        st.switch_page(PAGES[sel])

# ===================== Header (logo + title) ================================
def _load_logo_b64(path="assets/logo.png"):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    except Exception:
        return None

LOGO_B64 = st.session_state.get("logo_b64") or _load_logo_b64()
if LOGO_B64 and "logo_b64" not in st.session_state:
    st.session_state["logo_b64"] = LOGO_B64

TITLE_TEXT        = "Estimating Calculator"
TITLE_SIZE_PX     = 72
TITLE_WEIGHT      = 800
TITLE_COLOR       = "#ffffff" if ui_dark else "#"
TITLE_ALIGN       = "center"
TITLE_FONT_FAMILY = "Poppins, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"

SHOW_LOGO          = True
LOGO_WIDTH_PX      = 300
LOGO_MARGIN_BOTTOM = 20

HEADER_MAX_W_PX      = 900
HEADER_BG            = "#0f2210" if ui_dark else "#2c6731"
HEADER_PAD_X_PX      = 14
HEADER_PAD_Y_PX      = 14
HEADER_BORDER_ON     = True
HEADER_BORDER_COLOR  = "#020603"
HEADER_RADIUS_PX     = 50
HEADER_SHADOW_ON     = True
HEADER_MARGIN_TOP    = 8
HEADER_MARGIN_BOTTOM = 16

border_css = f"3px solid {HEADER_BORDER_COLOR}" if HEADER_BORDER_ON else "none"
shadow_css = "0 6px 16px rgba(0,0,0,0.08)" if HEADER_SHADOW_ON else "none"

# Optional: Google font
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&display=swap');
</style>
""", unsafe_allow_html=True)

# Render header
st.markdown(
    f"""
    <div style="
      max-width:{HEADER_MAX_W_PX}px;
      margin:{HEADER_MARGIN_TOP}px auto {HEADER_MARGIN_BOTTOM}px auto;
      background:{HEADER_BG};
      padding:{HEADER_PAD_Y_PX}px {HEADER_PAD_X_PX}px;
      border:{border_css};
      border-radius:{HEADER_RADIUS_PX}px;
      box-shadow:{shadow_css};
    ">
      {"".join([
        f'<div style="display:flex; justify-content:center; margin-bottom:{LOGO_MARGIN_BOTTOM}px;">'
        f'  <img src="data:image/png;base64,{LOGO_B64}" style="width:{LOGO_WIDTH_PX}px; height:auto; display:block;">'
        f'</div>' if (SHOW_LOGO and LOGO_B64) else ""
      ])}
      <div style="
        text-align:{TITLE_ALIGN};
        font-size:{TITLE_SIZE_PX}px;
        font-weight:{TITLE_WEIGHT};
        color:{TITLE_COLOR};
        line-height:1.2;
        font-family:{TITLE_FONT_FAMILY};
      ">{TITLE_TEXT}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ===================== Body ================================================
page_selection = st.selectbox(
    "Select a Page",
    PAGES.keys(),
    index = 1,
    key = "page_selection",
)





