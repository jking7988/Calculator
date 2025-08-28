# pages/04_Rock_Filter_Dams.py
import base64
import datetime as dt
import math
import streamlit as st
import matplotlib.pyplot as plt
from streamlit.components.v1 import html as st_html

from core.theme_persist import init_theme, render_toggle, sidebar_skin, nav_colors
from core.theme import apply_theme, fix_select_colors
from core.ui_sidebar import apply_sidebar_shell, sidebar_card, SIDEBAR_CFG
from core import pricing as p
from core import settings as cfg
from core import cart

# --- Page config ---
st.set_page_config(
    page_title="Double Oak – Rock Filter Dams",
    layout="centered",
    initial_sidebar_state="expanded",
)

# --- Theme init & apply ---
ui_dark = init_theme(apply_theme_fn=apply_theme, fix_select_colors_fn=fix_select_colors)

# Hide Streamlit chrome
st.markdown(
    """
<style>
header[data-testid="stHeader"]{display:none}
#MainMenu{visibility:hidden}
footer{visibility:hidden}
div.block-container{padding-top:1rem}
</style>
""",
    unsafe_allow_html=True,
)

# Appearance
with sidebar_card("Appearance", icon="🌓"):
    ui_dark = render_toggle()

# Ensure theme applied after toggle
apply_theme("dark" if ui_dark else "light")
fix_select_colors(ui_dark)

# Sidebar skin + shell
SIDEBAR_CFG.update(sidebar_skin(ui_dark))
apply_sidebar_shell()

# Hide built-in page list
st.markdown("<style>[data-testid='stSidebarNav']{display:none}</style>", unsafe_allow_html=True)

# Colors (if you style selects later)
colors = nav_colors(ui_dark)

# ---------- Sidebar: Navigation (normalized) ----------
PAGES = {
    "Home": "Home.py",
    "Fencing Estimator": "pages/01_Fencing.py",
    "Inlet Protection": "pages/02_Inlet_Protection.py",
    "Construction Entrance": "pages/03_Construction_Entrance.py",
    "Rock Filter Dams": "pages/04_Rock_Filter_Dams.py",
    "Turf Establishment": "pages/05_Turf_Establishment.py",
    "Aggregate": "pages/06_Aggregate.py",
    "Material Summary": "pages/99_Material_Summary.py",
}
CURRENT_PAGE = "Rock Filter Dams"

with sidebar_card("Navigate", icon="🧭", bg="#fff", shadow="0 4px 14px rgba(0,0,0,.06)"):
    st.markdown('<div id="nav-dd" style="display:none"></div>', unsafe_allow_html=True)
    sel = st.selectbox(
        "Go to page",
        ["— Select —", *PAGES.keys()],
        index=1 + list(PAGES.keys()).index(CURRENT_PAGE),
        key="nav_choice_rfd",
    )
    if sel != "— Select —" and sel != CURRENT_PAGE:
        try:
            st.query_params.update({"theme": "dark" if st.session_state.get("ui_dark") else "light"})
        except Exception:
            pass
        st.switch_page(PAGES[sel])

# ---------- Sidebar: Project / Customer (sticky) ----------
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
    )
    st.text_input(
    "Customer Name:",
    key="company_name",
    value=st.session_state.get("company_name", ""),
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
    )

# ---------- Sidebar: Rock Filter Dams Options ----------
tax_rate = getattr(cfg, "SALES_TAX_RATE", 0.0825)

with sidebar_card("Rock Filter Dams Options", icon="🛠️", bg="#fff", shadow="0 4px 14px rgba(0,0,0,.06)"):
    rfd_type = st.selectbox(
        "Dam Type:",
        ["Type A – Low Flow", "Type B – Medium Flow", "Type C – High Flow"],
        key="rfd_type",
        help="Select dam type per plan/spec.",
    )
    qty = st.number_input(
        "Quantity (EA):",
        min_value=0, step=1, value=5,
        help="Total number of dams.",
        key="rfd_qty",
    )
    material_cost_per_unit = st.number_input(
        "Material Cost / Dam:",
        min_value=0.0, value=120.0, step=1.0,
        help="Rock + fabric + hardware per dam.",
        key="rfd_mat_cost",
    )
    labor_minutes_per_unit = st.number_input(
        "Labor Minutes / Dam:",
        min_value=0, value=60, step=5,
        help="Estimated install time per dam in minutes.",
        key="rfd_labor_min",
    )
    final_price_per_unit = st.number_input(
        "Final Price / Dam:",
        min_value=0.0, value=275.0, step=1.0,
        help="Customer price per dam.",
        key="rfd_price_unit",
    )

# ---------- Calculations ----------
materials_subtotal = qty * material_cost_per_unit
tax = materials_subtotal * tax_rate

total_minutes = qty * labor_minutes_per_unit
days = p.job_days_inlet(total_minutes)  # reuse per-minute scheduling helper
labor_per_day = p.get_labor_per_day()
labor_cost = days * labor_per_day

fuel = p.fuel_cost(days, any_work=qty > 0)

unit_cost = p.unit_cost_per_unit(qty, materials_subtotal, tax, labor_cost, fuel)
sell_total = final_price_per_unit * qty if qty > 0 else 0.0
profit_margin = p.margin(final_price_per_unit, unit_cost)
gross_profit = sell_total - (materials_subtotal + tax + labor_cost + fuel)

# ---------- Sidebar: Status ----------
with sidebar_card("Status", icon="📊", bg="#fff"):
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
with sidebar_card("Export", icon="⬇️", bg="#fff"):
    disabled = qty <= 0
    if st.button("Export to Material Summary", use_container_width=True, disabled=disabled):
        cart.add_item(
            sku="Rock Filter Dam",
            description=rfd_type,
            unit="EA",
            qty=qty,
            source_page="Rock Filter Dams",
            notes=f"Labor {labor_minutes_per_unit} min/unit; Mat ${material_cost_per_unit:,.2f}/unit",
        )
        st.success("Exported to Material Summary.")
        try:
            st.switch_page("pages/99_Material_Summary.py")
        except Exception:
            pass

# ---------- Branding Header ----------
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
        f"<h1 style='margin:0'>Rock Filter Dams Estimate</h1>"
        f"<div style='color:#555'>{COMPANY_NAME}{' — ' + PROJECT_NAME if PROJECT_NAME else ''}</div>"
        f"{f'<div style=\"color:#555\">{PROJECT_ADDR}</div>' if PROJECT_ADDR else ''}"
        f"</div>",
        unsafe_allow_html=True,
    )

st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

# ================= Excel-like helpers =================
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

def excel_panel(title: str, rows: list[tuple[str, str]]) -> None:
    def _row_html(lbl: str, val: str) -> str:
        return f"<tr><td>{lbl}</td><td style='text-align:right'>{val}</td></tr>"
    body = "\n".join(_row_html(lbl, val) for lbl, val in rows)
    st.markdown(
        f"""
        <div class="excel-col">
          <h4 class="excel-title">{title}</h4>
          <table class="excel-table" role="table" aria-label="{title}">
            <thead><tr><th>Item</th><th>Value</th></tr></thead>
            <tbody>{body}</tbody>
          </table>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Inject styles once (before any excel_panel calls)
inject_excel_styles(ui_dark)

# ---------- Build Cost Breakdown rows ----------
rows_cost = [
    ("Materials Subtotal",                f"${materials_subtotal:,.2f}"),
    (f"Sales Tax ({tax_rate*100:.2f}%)", f"${tax:,.2f}"),
    (f"Labor (crew {cfg.LOCKED_CREW_SIZE})", f"${labor_cost:,.2f}"),
    ("Fuel",                              f"${fuel:,.2f}"),
    ("Unit Cost (all-in) / Dam",          f"${unit_cost:,.2f}"),
    ("Final Price / Dam",                 f"${final_price_per_unit:,.2f}"),
    ("Gross Profit",                      f"${gross_profit:,.2f}"),
    ("Grand Total",                       f"${sell_total:,.2f}"),
]

# ---------- Side-by-side: Cost Breakdown (right) & Profit gauge (left) ----------
with st.container():
    col_left, col_right = st.columns([1, 1], gap="medium")

    with col_right:
        excel_panel("Cost Breakdown", rows_cost)

    with col_left:
        st.markdown("### Profit Margin")
        try:
            m_val = float(profit_margin or 0.0) * 100.0
            target_pct = 30.0
            ymax = max(60.0, target_pct + 10.0, m_val + 10.0)

            # Auto color thresholds (and matching target line)
            if m_val < 20.0:
                bar_color, target_color = "#cc3232", "#cc3232"  # red
            elif m_val < target_pct:
                bar_color, target_color = "#e6a700", "#e6a700"  # amber
            else:
                bar_color, target_color = "#44a04c", "#44a04c"  # green

            fig, ax = plt.subplots(figsize=(2, 4))
            # Background (full scale)
            ax.bar(["Profit"], [ymax], color="#e0e0e0", width=0.5, zorder=1)
            # Actual value
            ax.bar(["Profit"], [m_val], color=bar_color, width=0.5, zorder=2)
            # Target line (color matches bar category)
            ax.axhline(target_pct, color=target_color, linestyle="--", zorder=3)

            ax.set_ylim(0, ymax)
            ax.set_ylabel("Percent (%)")

            # Label inside/above logic
            in_bar_threshold = 12.0
            top_pad = ymax * 0.04
            if m_val >= in_bar_threshold:
                txt_y = max(min(m_val * 0.5, ymax - top_pad), top_pad)
                txt_color = "#ffffff" if bar_color in ("#44a04c", "#cc3232") else "#0f1b12"
                ax.text(0, txt_y, f"{m_val:.1f}%", ha="center", va="center",
                        color=txt_color, fontweight="bold", clip_on=True)
            else:
                txt_y = min(m_val + 3.0, ymax - top_pad)
                ax.text(0, txt_y, f"{m_val:.1f}%", ha="center", va="bottom",
                        color="#0f1b12", fontweight="bold", clip_on=True)

            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            st.pyplot(fig, clear_figure=True)
        except Exception as e:
            st.caption(f"(Chart error: {e})")

# spacer
st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

# ---------- Export Preview (above Quantities & Specs) ----------
with st.container():
    preview_items = [
        {
            "item": f"Rock Filter Dam – {rfd_type}",
            "unit": "EA",
            "qty": f"{qty:,}",
            "notes": f"Labor {labor_minutes_per_unit} min/unit; Mat ${material_cost_per_unit:,.2f}/unit",
        }
    ]
    rows_html = "\n".join(
        f"<tr><td>{it['item']}</td>"
        f"<td style='text-align:center'>{it['unit']}</td>"
        f"<td style='text-align:right'>{it['qty']}</td>"
        f"<td>{it['notes']}</td></tr>"
        for it in preview_items
    )
    st.markdown(
        f"""
        <div class="excel-col">
          <h4 class="excel-title">Export Preview</h4>
          <table class="excel-table" role="table" aria-label="Export Preview" style="table-layout:auto">
            <thead>
              <tr>
                <th style="text-align:left">Item</th>
                <th style="width:70px;text-align:center">Unit</th>
                <th style="width:110px;text-align:right">Qty</th>
                <th style="text-align:left">Notes</th>
              </tr>
            </thead>
            <tbody>
              {rows_html}
            </tbody>
          </table>
        </div>
        """,
        unsafe_allow_html=True,
    )

# spacer
st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

# ---------- Quantities & Specs ----------
spec_rows = [
    ("Dam Type", rfd_type),
    ("Quantity", f"{qty:,} EA"),
    ("Labor Minutes / Dam", f"{labor_minutes_per_unit:,} min"),
    ("Total Minutes", f"{total_minutes:,} min"),
    ("Crew Days (scheduled)", f"{days:.2f} days"),
]
excel_panel("Quantities & Specs", spec_rows)

# spacer
st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

# ---------- Text Summary (kept for readability) ----------
with st.container(border=True):
    st.markdown(
        f"""
**Rock Filter Dams Estimate**
- **Type:** {rfd_type}  
- **Quantity:** {qty}  
- **Materials Subtotal:** ${materials_subtotal:,.2f}  
- **Sales Tax ({tax_rate*100:.2f}%):** ${tax:,.2f}  
- **Labor (crew {cfg.LOCKED_CREW_SIZE}):** ${labor_cost:,.2f}  
- **Fuel:** ${fuel:,.2f}  
- **Unit Cost (tax + labor + fuel):** ${unit_cost:,.2f} / dam  
- **Final Price:** ${final_price_per_unit:,.2f} / dam  
- **Profit Margin:** {profit_margin:.1%}  
- **Gross Profit:** ${gross_profit:,.2f}  
- **Grand Total:** ${sell_total:,.2f}
        """
    )
