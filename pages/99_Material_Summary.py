# --- Material Summary: stable header & nav ---
import base64
import datetime as dt
import pandas as pd
from core import cart
import streamlit as st
from streamlit.components.v1 import html as st_html  # keep if you use it
from core.sanitize import e, srcdoc_escape
from core.theme_persist import init_theme, render_toggle, sidebar_skin, nav_colors
from core.theme import apply_theme, fix_select_colors
from core.ui_sidebar import apply_sidebar_shell, sidebar_card, SIDEBAR_CFG

# Page config FIRST
st.set_page_config(
    page_title="Double Oak – Material Summary",
    layout="wide",
    initial_sidebar_state="expanded",
)

# initialize & apply (persists via session + ?theme=dark|light)
ui_dark = init_theme(apply_theme_fn=apply_theme, fix_select_colors_fn=fix_select_colors)

# Hide Streamlit chrome
st.markdown("""
<style>
header[data-testid="stHeader"] { display:none; }
#MainMenu { visibility:hidden; }
footer { visibility:hidden; }
div.block-container { padding-top: 1rem; }
</style>
""", unsafe_allow_html=True)

# Appearance toggle (render ONCE)
with sidebar_card("Appearance", icon="🌓"):
    ui_dark = render_toggle()  # distinct widget key under the hood

# Sidebar skin + shell (call ONCE)
SIDEBAR_CFG.update(sidebar_skin(ui_dark))
apply_sidebar_shell()

# Hide Streamlit's default page list (the built-in multipage links)
st.markdown("<style>[data-testid='stSidebarNav']{display:none}</style>", unsafe_allow_html=True)

# ---------------- Nav dropdown colors (AFTER we know ui_dark) ---------------
colors = nav_colors(ui_dark)
NAV_LABEL_COLOR  = colors["NAV_LABEL_COLOR"]
NAV_VALUE_COLOR  = colors["NAV_VALUE_COLOR"]
NAV_MENU_BG      = colors["NAV_MENU_BG"]
NAV_MENU_TEXT    = colors["NAV_MENU_TEXT"]
NAV_INPUT_BG     = colors["NAV_INPUT_BG"]
NAV_BORDER_COLOR = colors["NAV_BORDER_COLOR"]


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

CURRENT_PAGE = "Material Summary"

with sidebar_card("Navigate", icon="🧭", bg=("#0f1b12" if ui_dark else "#ffffff"), shadow="0 4px 14px rgba(0,0,0,.06)"):
    choices = list(PAGES.keys())
    sel = st.selectbox(
        "Go to page",
        choices,
        index=choices.index(CURRENT_PAGE),   # preselect this page
        key="nav_choice_rfd",               # unique key for this page
    )
    if sel != CURRENT_PAGE:
        st.query_params.update({"theme": "dark" if st.session_state.get("ui_dark") else "light"})
        st.switch_page(PAGES[sel])


# ── Fetch items early so buttons can disable correctly ──────────────────────
try:
    items = cart.get_items() or []
except Exception:
    items = []

# ── Sidebar: Actions ────────────────────────────────────────────────────────
with sidebar_card("Actions", icon="⚙️"):
    if st.button("Clear Material List", use_container_width=True, disabled=not items, key="ms_clear"):
        cart.clear()
        st.session_state["_cleared_cart"] = True
        st.rerun()

# one-time toast after rerun
if st.session_state.pop("_cleared_cart", False):
    st.success("Cleared material list.")

# ── Branding header (logo + title) ──────────────────────────────────────────
def _load_logo_b64(path="assets/logo.png"):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    except Exception:
        return None

LOGO_B64 = st.session_state.get("logo_b64") or _load_logo_b64()
if LOGO_B64 and "logo_b64" not in st.session_state:
    st.session_state["logo_b64"] = LOGO_B64

COMPANY_NAME = st.session_state.get("company_name", "Double Oak")
PROJECT_NAME = st.session_state.get("project_name", "")
PROJECT_ADDR = st.session_state.get("project_address", "")

col_logo, col_title = st.columns([1, 5], vertical_alignment="center")
with col_logo:
    if LOGO_B64:
        st.markdown(
            f'<img src="data:image/png;base64,{LOGO_B64}" style="max-height:64px;">',
            unsafe_allow_html=True,
        )
with col_title:
    st.markdown(
        f"<div style='line-height:1.2'>"
        f"<h1 style='margin:0'>Material Summary</h1>"
        f"<div style='color:#555'>{COMPANY_NAME}{' — ' + PROJECT_NAME if PROJECT_NAME else ''}</div>"
        f"{f'<div style=\"color:#555\">{PROJECT_ADDR}</div>' if PROJECT_ADDR else ''}"
        f"</div>",
        unsafe_allow_html=True,
    )

st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

# ── Build “Material Breakdown” table ────────────────────────────────────────
HIDE_COLS = ["source_page", "alt_qty_label", "alt_qty_value", "notes","sku"]
RAW_RENAME = {
    "sku": "Item Code",
    "description": "Description",
    "unit": "Unit",
    "qty": "Quantity",
}

def _format_descriptor(unit: str, alt_qty_value, description: str) -> str:
    u = (unit or "").strip().upper()
    if u == "LF" and alt_qty_value is not None:
        return "Rolls"      # fabric
    if u in ("EA", "EACH"):
        return "Each"       # posts/stakes/caps
    return {"LF": "Linear Feet"}.get(u, unit or "")

df_raw = pd.DataFrame(items)
df_show = df_raw.copy()

if not df_show.empty:
    df_show["Format"] = [
        _format_descriptor(u, a, d)
        for u, a, d in zip(
            df_show.get("unit", pd.Series(dtype=object)),
            df_show.get("alt_qty_value", pd.Series(dtype=object)),
            df_show.get("description", pd.Series(dtype=object)),
        )
    ]
    df_show = df_show.drop(columns=HIDE_COLS, errors="ignore").rename(columns=RAW_RENAME)
    order = ["Item Code", "Description", "Unit", "Format", "Quantity"]
    df_show = df_show[[c for c in order if c in df_show.columns]
                      + [c for c in df_show.columns if c not in order]]

# ── Printable HTML + icon actions ───────────────────────────────────────────
def _tbl_html(df: pd.DataFrame, title: str) -> str:
    if df is None or df.empty:
        return "<p>No materials have been added.</p>"
    return f"<h3 style='margin:8px 0 8px 0;'>{title}</h3>" + df.to_html(index=False, border=0)

header_html = (
    f"<div style='display:flex;align-items:center;gap:16px;margin:0 0 16px 0;'>"
    f"{f'<img src=\"data:image/png;base64,{LOGO_B64}\" style=\"height:60px;\">' if LOGO_B64 else ''}"
    f"<div>"
    f"<div style='font-size:18px;font-weight:700;'>{COMPANY_NAME}</div>"
    f"<div style='font-size:14px;color:#555;'>Material Summary"
    f"{' — ' + PROJECT_NAME if PROJECT_NAME else ''}</div>"
    f"<div style='font-size:12px;color:#777;'>{dt.datetime.now().strftime('%m/%d/%Y')}</div>"
    f"</div></div>"
)

summary_html = (
    "<!doctype html><html><head><meta charset='utf-8'>"
    "<title>Material Summary</title>"
    "<style>"
    "body{font-family:Arial, sans-serif; margin:24px; color:#111;}"
    "table{border-collapse:collapse;width:100%;font-size:14px}"
    "th,td{border:1px solid #ececec;padding:8px 10px;text-align:left}"
    "th{background:#fafafa}"
    "</style></head><body>"
    f"<div style='max-width:900px;'>{header_html}{_tbl_html(df_show, 'Material Breakdown')}</div>"
    "</body></html>"
)

_print_html   = summary_html.replace("</body>", "<script>window.print()</script></body>")
_download_b64 = base64.b64encode(summary_html.encode("utf-8")).decode("ascii")
_print_b64    = base64.b64encode(_print_html.encode("utf-8")).decode("ascii")
download_url  = f"data:text/html;base64,{_download_b64}"
print_url     = f"data:text/html;base64,{_print_b64}"

st_html(
    f"""
    <div style="display:flex; justify-content:flex-end; gap:8px; align-items:center; margin-bottom:8px;">
      <a href="{print_url}" target="_blank" title="Print"
         style="display:inline-flex; align-items:center; justify-content:center; width:38px; height:38px;
                border-radius:10px; border:1px solid #e5e7eb; text-decoration:none; background:#fff; color:#111;">
        <!-- printer icon -->
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
             fill="none" stroke="#111" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M6 9V2h12v7"></path>
          <path d="M6 18H5a3 3 0 0 1-3-3v-3a3 3 0 0 1 3-3h14a3 3 0 0 1 3 3v3a3 3 0 0 1-3 3h-1"></path>
          <path d="M16 18H8v4h8v-4z"></path>
        </svg>
      </a>
      <a href="{download_url}" download="material_summary.html" title="Download"
         style="display:inline-flex; align-items:center; justify-content:center; width:38px; height:38px;
                border-radius:10px; border:1px solid #e5e7eb; text-decoration:none; background:#fff; color:#111;">
        <!-- download icon -->
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
             fill="none" stroke="#111" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"></path>
          <path d="M7 10l5 5 5-5"></path>
          <path d="M12 15V3"></path>
        </svg>
      </a>
    </div>
    """,
    height=60,
)

# ── Table render + CSV download ─────────────────────────────────────────────
if df_show.empty:
    st.info("No materials have been added yet. Go to a scope page and click **Export to Material Summary**.")
else:
    with st.container(border=True):
        st.subheader("Material Breakdown")
        st.dataframe(df_show, use_container_width=True, hide_index=True)

    st.download_button(
        "Download Items (CSV)",
        data=df_show.to_csv(index=False).encode("utf-8"),
        file_name="material_items.csv",
        mime="text/csv",
        use_container_width=True,
        key="download_items_csv",
    )
