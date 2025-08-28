# pages/06_Aggregate.py
import base64
import datetime as dt
import streamlit as st
from streamlit.components.v1 import html as st_html
from core.sanitize import e, srcdoc_escape
from core.theme_persist import init_theme, render_toggle, sidebar_skin, nav_colors
from core.theme import apply_theme, fix_select_colors
from core.ui_sidebar import apply_sidebar_shell, sidebar_card, SIDEBAR_CFG
from core import pricing as p
from core import settings as cfg
from core import cart
# Inject styles once
inject_excel_styles(ui_dark)



def inject_excel_styles(dark: bool) -> None:
    col_bg      = "#0f2210" if dark else "#e7f4ea"
    col_border  = "#020603" if dark else "#b2deb5"
    grid        = "#ffffff" if dark else "#dbead9"
    header_bg   = "#17381b" if dark else "#2e6d33"
    header_text = "#bfe6c4" if dark else "#ffffff"
    label_col   = "#ceead1" if dark else "#0f1b12"
    value_col   = "#ceead1" if dark else "#0f1b12"
    alt_row     = "#1f2b20" if dark else "#f2f7f2"
    shadow      = "0 2px 10px rgba(0,0,0,.28)" if dark else "0 2px 10px rgba(0,0,0,.08)"

    st.markdown(f"""
    <style>
      .excel-col {{ background:{col_bg}; border:2.5px solid {col_border}; border-radius:12px; padding:12px 12px 18px; box-shadow:{shadow}; }}
      .excel-title {{ margin:0 0 20px 0; font-weight:800; color:{label_col}; border-bottom:2px dashed {col_border}; padding-bottom:4px; text-align:center; font-size:32px; }}
      .excel-table {{ width:100%; border-collapse:separate; border-spacing:0; table-layout:fixed; }}
      .excel-table thead th {{ background:{header_bg}; color:{header_text}; text-align:center; padding:0 10px; font-weight:700; border:2px solid {grid}; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
      .excel-table tbody td {{ padding:8px 10px; vertical-align:top; border-bottom:2px solid {grid}; border-left:2px solid {grid}; border-right:5px solid {grid}; background:transparent; }}
      .excel-table tbody tr:nth-child(odd) td {{ background:{alt_row}; }}
      .excel-table td:first-child {{ color:{label_col}; font-weight:600; width:55%; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
      .excel-table td:last-child {{ color:{value_col}; text-align:right; white-space:nowrap; }}
    </style>
    """, unsafe_allow_html=True)


st.set_page_config(
    page_title="Double Oak – Aggregate",
    layout="centered",
    initial_sidebar_state="expanded",
)

ui_dark = init_theme(apply_theme_fn=apply_theme, fix_select_colors_fn=fix_select_colors)

st.markdown("""
<style>
header[data-testid="stHeader"]{display:none}
#MainMenu{visibility:hidden}
footer{visibility:hidden}
div.block-container{padding-top:1rem}
</style>
""", unsafe_allow_html=True)

with sidebar_card("Appearance", icon="🌓"):
    ui_dark = render_toggle()

# Sidebar skin + shell (once)
SIDEBAR_CFG.update(sidebar_skin(ui_dark))
apply_sidebar_shell()



with sidebar_card(
    "Project / Customer",
    icon="📋",
    bg=("#0f1b12" if ui_dark else "#ffffff"),
    border="2px solid #2e6d33",
    radius_px=20,
    pad_x=12, pad_y=12,
):
    st.text_input(
    "Project Title:",
    key="project_name",
    value=st.session_state.get("project_name", ""),
    placeholder="e.g., Lakeside Retail – Phase 2",
),
    placeholder="e.g., Lakeside Retail – Phase 2",
),
    placeholder="e.g., Lakeside Retail – Phase 2",
),
    placeholder="e.g., Lakeside Retail – Phase 2",
),
        placeholder="e.g., Lakeside Retail – Phase 2",
    )
    st.text_input(
    "Customer Name:",
    key="company_name",
    value=st.session_state.get("company_name", ""),
    placeholder="e.g., ACME Builders",
),
    placeholder="e.g., ACME Builders",
),
    placeholder="e.g., ACME Builders",
),
    placeholder="e.g., ACME Builders",
),
        placeholder="e.g., ACME Builders",
    )
    st.text_input(
    "Address:",
    key="project_address",
    value=st.session_state.get("project_address", ""),
    placeholder="e.g., 1234 Main St, Austin, TX",
),
    placeholder="e.g., 1234 Main St, Austin, TX",
),
    placeholder="e.g., 1234 Main St, Austin, TX",
),
    placeholder="e.g., 1234 Main St, Austin, TX",
),
        placeholder="e.g., 1234 Main St, Austin, TX",
    )
st.markdown("<style>[data-testid='stSidebarNav']{display:none}</style>", unsafe_allow_html=True)

colors = nav_colors(ui_dark)

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
CURRENT_PAGE = "Aggregate"

with sidebar_card("Navigate", icon="🧭", bg=("#0f1b12" if ui_dark else "#ffffff"), shadow="0 4px 14px rgba(0,0,0,.06)"):
    st.markdown('<div id="nav-dd" style="display:none"></div>', unsafe_allow_html=True)
    sel = st.selectbox(
        "Go to page",
        ["— Select —", *PAGES.keys()],
        index=1 + list(PAGES.keys()).index(CURRENT_PAGE),
        key="nav_choice_agg",
    )
    if sel != "— Select —" and sel != CURRENT_PAGE:
        st.query_params.update({"theme": "dark" if st.session_state.get("ui_dark") else "light"})
        st.switch_page(PAGES[sel])

COMPANY_NAME = e(st.session_state.get("company_name", "Double Oak"))
PROJECT_NAME = e(st.session_state.get("project_name", ""))
PROJECT_ADDR = e(st.session_state.get("project_address", ""))

# ---------- Sidebar: Aggregate Options ----------
tax_rate = getattr(cfg, "SALES_TAX_RATE", 0.0825)

with sidebar_card("Aggregate Options", icon="🛠️", bg=("#0f1b12" if ui_dark else "#ffffff"), shadow="0 4px 14px rgba(0,0,0,.06)"):
    agg_type = st.selectbox(
        "Aggregate Type:",
        ["#57 Stone", "Flex Base", "Pea Gravel", "Riprap"],
        key="agg_type",
        help="Select aggregate material.",
    )
    qty = st.number_input(
        "Quantity (tons):",
        min_value=0.0, step=1.0, value=50.0,
        help="Total tonnage.",
        key="agg_qty_tons",
    )
    material_cost_per_unit = st.number_input(
        "Material Cost / Ton:",
        min_value=0.0, value=18.0, step=0.5,
        help="Delivered material cost per ton (exclude trucking overhead if separate).",
        key="agg_mat_cost",
    )
    labor_minutes_per_unit = st.number_input(
        "Labor Minutes / Ton:",
        min_value=0, value=6, step=1,
        help="Placing/distribution minutes per ton.",
        key="agg_labor_min_per_ton",
    )
    final_price_per_unit = st.number_input(
        "Final Price / Ton:",
        min_value=0.0, value=35.0, step=0.5,
        help="Customer price per ton placed.",
        key="agg_price_per_ton",
    )

# ---------- Calculations ----------
materials_subtotal = qty * material_cost_per_unit
tax = materials_subtotal * tax_rate

total_minutes = qty * labor_minutes_per_unit
days = p.job_days_inlet(total_minutes)  # reuse minute-based calc
labor_per_day = p.get_labor_per_day()
labor_cost = days * labor_per_day

fuel = p.fuel_cost(days, any_work=qty > 0)

unit_cost = p.unit_cost_per_unit(qty, materials_subtotal, tax, labor_cost, fuel)
sell_total = final_price_per_unit * qty if qty > 0 else 0.0
price_per_unit_effective = final_price_per_unit or 0.0001
profit_margin = p.margin(price_per_unit_effective, unit_cost)
gross_profit = sell_total - (materials_subtotal + tax + labor_cost + fuel)

# ---------- Sidebar: Status ----------
with sidebar_card("Status", icon="📊", bg=("#0f1b12" if ui_dark else "#ffffff")):
    ok = profit_margin >= 0.30
    badge_bg   = "#dcfce7" if ok else "#fee2e2"
    badge_text = "#065f46" if ok else "#991b1b"
    badge_bd   = "#16a34a" if ok else "#ef4444"
    label      = "ON TARGET (≥30%)" if ok else "UNDER 30%"
    st.markdown(
        f"""
        <div style="text-align:center; margin:8px 0 12px 0;">
          <span style="
            display:inline-block;
            padding:2px 12px;
            border-radius:999px;
            background:{badge_bg};
            color:{badge_text};
            border:3px solid {badge_bd};
            font-weight:600;">
            {label} {profit_margin:.1%}
          </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---------- Sidebar: Export ----------
with sidebar_card("Export", icon="⬇️", bg=("#0f1b12" if ui_dark else "#ffffff")):
    disabled = qty <= 0
    if st.button("Export to Material Summary", use_container_width=True, disabled=disabled):
        cart.add_item(
            sku="Aggregate",
            description=agg_type,
            unit="TON",
            qty=qty,
            source_page="Aggregate",
            notes=f"Labor {labor_minutes_per_unit} min/ton; Mat ${material_cost_per_unit:,.2f}/ton",
        )
        st.success("Exported to Material Summary.")
        try:
            st.switch_page("pages/99_Material_Summary.py")
        except Exception:
            pass

# ---------- Header ----------
def _load_logo_b64(path="assets/logo.png"):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    except Exception:
        return None

LOGO_B64 = st.session_state.get("logo_b64") or _load_logo_b64()
if LOGO_B64:
    st.session_state["logo_b64"] = LOGO_B64

COMPANY_NAME = st.session_state.get("company_name", "Double Oak")
PROJECT_NAME = st.session_state.get("project_name", "")
PROJECT_ADDR = st.session_state.get("project_address", "")

left, right = st.columns([1, 5], vertical_alignment="center")
with left:
    if LOGO_B64:
        st.markdown(f'<img src="data:image/png;base64,{LOGO_B64}" style="max-height:64px;">', unsafe_allow_html=True)
with right:
    st.markdown(
        f"<div style='line-height:1.2'>"
        f"<h1 style='margin:0'>Aggregate Estimate</h1>"
        f"<div style='color:#555'>{COMPANY_NAME}{' — ' + PROJECT_NAME if PROJECT_NAME else ''}</div>"
        f"{f'<div style=\"color:#555\">{PROJECT_ADDR}</div>' if PROJECT_ADDR else ''}"
        f"</div>",
        unsafe_allow_html=True,
    )

st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

# ---------- Main estimate ----------
with st.container(border=True):
    st.markdown(
        f"""
**Aggregate Estimate**
- **Type:** {agg_type}  
- **Quantity:** {qty:,.2f} tons  
- **Materials Subtotal:** ${materials_subtotal:,.2f}  
- **Sales Tax ({tax_rate*100:.2f}%):** ${tax:,.2f}  
- **Labor (crew {cfg.LOCKED_CREW_SIZE}):** ${labor_cost:,.2f}  
- **Fuel:** ${fuel:,.2f}  
- **Unit Cost (tax + labor + fuel):** ${unit_cost:,.2f} / ton  
- **Final Price:** ${final_price_per_unit:,.2f} / ton  
- **Profit Margin:** {profit_margin:.1%}  
- **Gross Profit:** ${gross_profit:,.2f}  
- **Grand Total:** ${sell_total:,.2f}
        """
    )
