# Double Oak – Fencing Estimator (Refactored to st.data_editor)
# --------------------------------------------------------------
import math, uuid, copy, html
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import streamlit as st

# ---- Core app modules ----
from core.theme_persist import init_theme, render_toggle, sidebar_skin
from core.theme import apply_theme, fix_select_colors
from core.ui_sidebar import apply_sidebar_shell, sidebar_card, SIDEBAR_CFG
from core import settings as cfg
from core import pricebook

pricebook.ensure_loaded()

# -------------------- Page + Global CSS --------------------
st.set_page_config(
    page_title="Double Oak Fencing Estimator",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Hide Streamlit chrome
st.markdown(
    """
    <style>
      header[data-testid="stHeader"] { display: none !important; }
      #MainMenu, footer { visibility: hidden; }
      .block-container { max-width: 100% !important; padding-top: .5rem; padding-left: 1rem; padding-right: 1rem; }
      input[type=number]::-webkit-inner-spin-button,
      input[type=number]::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
      input[type=number] { -moz-appearance: textfield; }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------- Utilities --------------------
try:
    from core.sanitize import e  # type: ignore
except Exception:  # robust escape fallback
    def e(x) -> str:
        return html.escape(str(x))


def price_text_input(label: str, key: str, default: float = 2.50, *, min_v=0.0, max_v=100.0) -> float:
    """Text field that remembers last valid numeric value; clamps to [min_v, max_v]."""
    prior = st.session_state.get(f"{key}__val", default)
    seed_text = st.session_state.get(f"{key}__text", f"{prior:.2f}")
    txt = st.text_input(label, value=seed_text, key=f"{key}__text", help="Type a price like 2.50 (no %).")
    raw = (txt or "").strip().replace("$", "").replace(",", "")
    try:
        val = float(raw)
    except Exception:
        val = prior
    val = max(min_v, min(max_v, val))
    st.session_state[f"{key}__val"] = val
    return val


# ---------- Pricing helpers ----------
class _P:
    @staticmethod
    def required_footage(total_lf: float, waste_pct: float) -> float:
        tl = max(0.0, float(total_lf or 0))
        wp = max(0.0, float(waste_pct or 0))
        return tl * (1.0 + wp / 100.0)

    @staticmethod
    def posts_needed(required_ft: float, spacing_ft: int) -> int:
        rf = max(0.0, float(required_ft or 0))
        sp = max(1, int(spacing_ft or 1))
        return int(math.ceil(rf / sp)) + 1 if rf > 0 else 0

    @staticmethod
    def rolls_needed(required_ft: float, roll_len: int = 100) -> int:
        rf = max(0.0, float(required_ft or 0))
        rl = max(1, int(roll_len or 100))
        return int(math.ceil(rf / rl)) if rf > 0 else 0

    @staticmethod
    def get_labor_per_day() -> float:
        return 554.34

    @staticmethod
    def fuel_cost(days: int, any_work: bool) -> float:
        return (65.0 * max(0, int(days or 0))) if any_work else 0.0

    @staticmethod
    def unit_cost_per_lf(required_ft: float, mat_sub: float, tax: float, labor: float, fuel: float) -> float:
        rf = max(0.0, float(required_ft or 0))
        total = float(mat_sub or 0) + float(tax or 0) + float(labor or 0) + float(fuel or 0)
        return total / rf if rf > 0 else 0.0

    @staticmethod
    def margin(sell_per_lf: float, unit_cost_per_lf_val: float) -> float:
        sp = float(sell_per_lf or 0)
        uc = float(unit_cost_per_lf_val or 0)
        return (sp - uc) / sp if sp > 0 else 0.0

    @staticmethod
    def materials_breakdown(required_ft: float, cost_per_lf: float, posts_count: int, post_unit_cost: float, tax_rate: float | None = None):
        """Returns: fabric_cost, hardware_cost, materials_subtotal, tax."""
        tr = _tax_rate_default if tax_rate is None else float(tax_rate)
        rf = max(0.0, float(required_ft or 0))
        cplf = max(0.0, float(cost_per_lf or 0))
        pc = max(0, int(posts_count or 0))
        puc = max(0.0, float(post_unit_cost or 0))
        fabric_cost = rf * cplf
        hardware_cost = pc * puc
        materials_subtotal = fabric_cost + hardware_cost
        tax = materials_subtotal * tr
        return fabric_cost, hardware_cost, materials_subtotal, tax


p = _P()

# -------------------- Theme --------------------
ui_dark = init_theme(apply_theme_fn=apply_theme, fix_select_colors_fn=fix_select_colors)
st.markdown("<style>[data-testid='stSidebarNav']{display:none}</style>", unsafe_allow_html=True)
with sidebar_card("Appearance", icon="🌓"):
    ui_dark = render_toggle()
apply_theme("dark" if ui_dark else "light")
fix_select_colors(ui_dark)
SIDEBAR_CFG.update(sidebar_skin(ui_dark))
apply_sidebar_shell()


def style_sidebar_buttons(is_dark: bool):
    if is_dark:
        bg, border, text, hoverbg, activebg, shadow = "#0f1b12", "#2e6d33", "#e8f5ea", "#17381b", "#112b15", "0 2px 8px rgba(0,0,0,.35)"
    else:
        bg, border, text, hoverbg, activebg, shadow = "#ffffff", "#2e6d33", "#0f172a", "#f5fbf6", "#eaf6ec", "0 2px 8px rgba(0,0,0,.08)"
    st.markdown(
        f"""
        <style>
          [data-testid="stSidebar"] .stButton > button {{
            width: 100% !important; background: {bg} !important; color: {text} !important;
            border: 2px solid {border} !important; border-radius: 12px !important; padding: 10px 12px !important;
            font-weight: 700 !important; box-shadow: {shadow} !important; transition: background .15s ease, transform .04s ease;
          }}
          [data-testid="stSidebar"] .stButton > button:hover {{ background: {hoverbg} !important; }}
          [data-testid="stSidebar"] .stButton > button:active {{ background: {activebg} !important; transform: translateY(1px); }}
        </style>
        """,
        unsafe_allow_html=True,
    )


style_sidebar_buttons(ui_dark)

# -------------------- Navigation --------------------
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
CURRENT_PAGE = "Fencing Estimator"
with sidebar_card("Navigate", icon="🧭"):
    st.markdown('<div id="nav-dd" style="display:none"></div>', unsafe_allow_html=True)
    choice = st.selectbox(
        "Go to page",
        ["— Select —", *PAGES.keys()],
        index=1 + list(PAGES.keys()).index(CURRENT_PAGE),
        key="nav_choice_fencing",
    )
    if choice != "— Select —" and choice in PAGES and choice != CURRENT_PAGE:
        try:
            st.query_params.update({"theme": "dark" if ui_dark else "light"})
        except AttributeError:
            st.experimental_set_query_params(theme="dark" if ui_dark else "light")
        st.switch_page(PAGES[choice])

# -------------------- Session State --------------------
st.session_state.setdefault("export_history_fencing", [])
st.session_state.setdefault("pricebook_warnings", [])
st.session_state.setdefault("export_locked_lines", [])        # list[dict]
st.session_state.setdefault("last_fence_signature", None)      # str|None
st.session_state.setdefault("preview_live_hidden_ids", [])     # list[str]
st.session_state.setdefault("remove_sales_tax", False)

# -------------------- Defaults / SKUs --------------------
FABRIC_SKU_14G = "silt-fence-14g"
FABRIC_SKU_125G = "silt-fence-12g5"
POST_SKU_T_POST_4FT = "t-post-4ft"
POST_SKU_TXDOT_T_POST_4FT = "tx-dot-t-post-4-ft"
POST_SKU_T_POST_6FT = "t-post-6ft"
FABRIC_SKU_ORANGE_LIGHT = "orange-fence-light-duty"
FABRIC_SKU_ORANGE_HEAVY = "orange-fence-heavy-duty"
CAP_SKU_OSHA = "cap-osha"
CAP_SKU_PLASTIC = "cap-plastic"

# -------------------- Project / Customer --------------------
with sidebar_card(
    "Project / Customer", icon="📋",
    bg=("#0f1b12" if ui_dark else "#ffffff"), border="2px solid #2e6d33", radius_px=20, pad_x=12, pad_y=12,
):
    st.text_input("Project Title:", key="project_name", value=st.session_state.get("project_name", ""), placeholder="e.g., Lakeside Retail – Phase 2")
    st.text_input("Customer Name:", key="company_name", value=st.session_state.get("company_name", ""), placeholder="e.g., ACME Builders")
    st.text_input("Address:", key="project_address", value=st.session_state.get("project_address", ""), placeholder="e.g., 1234 Main St, Austin, TX")

COMPANY_NAME = e(st.session_state.get("company_name", ""))
PROJECT_NAME = e(st.session_state.get("project_name", ""))
PROJECT_ADDR = e(st.session_state.get("project_address", ""))

# -------------------- Fencing Options --------------------
_tax_rate_default = getattr(cfg, "SALES_TAX_RATE", 0.0825)
with sidebar_card(
    "Fencing Options", icon="🛠️",
    bg=("#0f1b12" if ui_dark else "#ffffff"),
    border=("2px solid #8fd095" if ui_dark else "3px solid #2e6d33"),
    pad_x=12, pad_y=12, radius_px=12,
    shadow=("0 4px 14px rgba(0,0,0,.40)" if ui_dark else "0 4px 14px rgba(0,0,0,.06)"),
):
    total_job_footage = st.number_input("Total Job Footage (ft):", min_value=0, max_value=1_000_000, value=1000, step=1, key="fence_total_lf")
    waste_pct = st.number_input("Waste %:", min_value=0, max_value=10, value=2, step=1, key="fence_waste_pct")
    fencing_category = st.selectbox("Fencing Material:", ["Silt Fence", "Plastic Orange Fence"], key="fence_category")

    if fencing_category == "Silt Fence":
        gauge_option = st.selectbox("Silt Fence Gauge:", ["14 Gauge", "12.5 Gauge"], key="sf_gauge")
        post_spacing_ft = st.selectbox("T-Post Spacing (ft):", options=[3, 4, 6, 8, 10], index=3, key="sf_post_spacing")
        final_price_per_lf = price_text_input("Final Price / LF:", key="sf_final_price", default=2.50)
        include_caps = st.checkbox("Check for Caps", value=False, key="sf_caps")
        cap_type = (
            st.selectbox("Cap Type:", ["OSHA-Approved ($3.90)", "Regular Plastic Cap ($1.05)"], index=0, key="sf_cap_type")
            if include_caps else None
        )
        removal_selected = st.checkbox("Add fence removal pricing", value=False, key="sf_removal")
        remove_tax_selected = st.checkbox("Remove sales tax from customer printout", value=st.session_state.get("remove_sales_tax", False), key="sf_remove_tax")
        st.session_state["remove_sales_tax"] = bool(remove_tax_selected)
    else:
        orange_duty = st.selectbox("Orange Fence Duty:", ["Light Duty", "Heavy Duty"], key="orange_duty")
        post_spacing_ft = st.selectbox("T-Post Spacing (ft):", options=[3, 4, 6, 8, 10], index=4, key="orange_post_spacing")
        final_price_per_lf = price_text_input("Final Price / LF:", key="orange_final_price", default=2.50)
        include_caps, cap_type = False, None
        removal_selected = st.checkbox("Add fence removal pricing", value=False, key="orange_removal")
        remove_tax_selected = st.checkbox("Remove sales tax from customer printout", value=st.session_state.get("remove_sales_tax", False), key="orange_remove_tax")
        st.session_state["remove_sales_tax"] = bool(remove_tax_selected)

# -------------------- Pricebook lookups --------------------

def get_price_or_warn(sku: str, default_val: float, label: str) -> float:
    try:
        val = pricebook.get_price(sku, default_val)
        return default_val if val is None else float(val)
    except Exception:
        msg = f"Price not found for {label} (SKU: {sku}); using default ${default_val:.2f}."
        st.session_state.setdefault("pricebook_warnings", []).append(msg)
        st.warning(msg)
        return default_val

if fencing_category == "Silt Fence":
    if gauge_option.startswith("14"):
        fabric_sku, fabric_default = FABRIC_SKU_14G, 0.32
        post_sku, post_default = POST_SKU_T_POST_4FT, 1.80
    else:
        fabric_sku, fabric_default = FABRIC_SKU_125G, 0.38
        post_sku, post_default = POST_SKU_TXDOT_T_POST_4FT, 2.15
else:
    if orange_duty.startswith("Light"):
        fabric_sku, fabric_default = FABRIC_SKU_ORANGE_LIGHT, 0.30
    else:
        fabric_sku, fabric_default = FABRIC_SKU_ORANGE_HEAVY, 0.45
    post_sku, post_default = POST_SKU_T_POST_6FT, 2.25

cost_per_lf = get_price_or_warn(fabric_sku, fabric_default, f"Fabric ({'Silt' if fencing_category=='Silt Fence' else 'Orange'}) / LF")
post_unit_cost = get_price_or_warn(post_sku, post_default, f"Post ({post_sku}) / EA")

# Optional: echo prices
st.write(f"Fabric ({fabric_sku}) — ${float(cost_per_lf):,.2f} per unit")
st.write(f"Post ({post_sku}) — ${float(post_unit_cost):,.2f} each")

# Caps
caps_unit_cost = 0.0
caps_sku_used = None
if fencing_category == "Silt Fence" and include_caps and cap_type:
    if "OSHA" in cap_type:
        caps_sku_used = CAP_SKU_OSHA
        caps_unit_cost = pricebook.get_price(caps_sku_used, 3.90) or 3.90
    else:
        caps_sku_used = CAP_SKU_PLASTIC
        caps_unit_cost = pricebook.get_price(caps_sku_used, 1.05) or 1.05

# -------------------- Calculations --------------------
required_ft = p.required_footage(total_job_footage, waste_pct)
safe_spacing = max(1, int(post_spacing_ft or 0))
posts_count = p.posts_needed(required_ft, safe_spacing)
rolls = p.rolls_needed(required_ft)

caps_label = None
caps_qty = 0
if fencing_category == "Silt Fence" and include_caps and cap_type:
    caps_label = "OSHA-Approved" if "OSHA" in cap_type else "Regular Plastic Cap"
    caps_qty = posts_count
caps_cost = caps_qty * caps_unit_cost

fabric_cost, hardware_cost, materials_subtotal, tax = p.materials_breakdown(
    required_ft, cost_per_lf, posts_count, post_unit_cost
)
materials_subtotal_all = materials_subtotal + caps_cost
_tax_rate = _tax_rate_default
tax_all = tax + caps_cost * _tax_rate

CUSTOMER_QTY_LF = int(total_job_footage or 0)


def _calc_removal_pricing(required_ft: float, final_price_per_lf: float) -> tuple[float, float]:
    if required_ft <= 0:
        return 0.0, 0.0
    unit = final_price_per_lf * 0.40
    unit = max(unit, 1.15) if required_ft < 800 else max(unit, 0.90)
    total = unit * required_ft
    if total < 800:
        total = 800.0
        unit = total / required_ft
    return unit, total

removal_unit_price_lf, removal_total = (
    _calc_removal_pricing(required_ft, final_price_per_lf) if removal_selected else (0.0, 0.0)
)

# Production assumptions / costs
PROD_LF_PER_DAY = getattr(cfg, "PRODUCTION_LF_PER_DAY", 2500)
project_days = (required_ft / PROD_LF_PER_DAY) if required_ft > 0 else 0.0
labor_per_day = p.get_labor_per_day()
labor_cost = project_days * labor_per_day
billing_days = math.ceil(project_days) if required_ft > 0 else 0
fuel = p.fuel_cost(billing_days, any_work=required_ft > 0)

unit_cost_lf = p.unit_cost_per_lf(required_ft, materials_subtotal_all, tax_all, labor_cost, fuel)
profit_margin_install_only = p.margin(final_price_per_lf, unit_cost_lf) if required_ft > 0 else 0.0

# Customer-facing revenue & margin (caps IN, removal OUT of margin)
sell_total_main = (final_price_per_lf * required_ft) if required_ft > 0 else 0.0
caps_revenue = (caps_unit_cost * caps_qty) if (caps_qty and caps_unit_cost) else 0.0
removal_revenue = removal_total if (removal_selected and required_ft > 0) else 0.0

customer_subtotal_display = sell_total_main + caps_revenue + removal_revenue
remove_tax = bool(st.session_state.get("remove_sales_tax", False))
customer_sales_tax = 0.0 if remove_tax else (customer_subtotal_display * _tax_rate)
customer_total = customer_subtotal_display + customer_sales_tax

internal_total_cost = materials_subtotal_all + tax_all + labor_cost + fuel
subtotal_for_margin = sell_total_main + caps_revenue
gross_profit = subtotal_for_margin - internal_total_cost
profit_margin = (gross_profit / subtotal_for_margin) if subtotal_for_margin > 0 else 0.0

# -------------------- Live lines --------------------

def _live_id(kind: str) -> str:
    return f"live_{kind}"

live_install_line = {
    "_id": _live_id("install"),
    "qty": CUSTOMER_QTY_LF,
    "unit": "LF",
    "item": (f"{gauge_option} Silt Fence" if fencing_category == "Silt Fence" else f"Plastic Orange Fence – {orange_duty}"),
    "price_each": float(final_price_per_lf),
    "line_total": float(final_price_per_lf) * CUSTOMER_QTY_LF,
}

live_caps_line = None
if caps_qty > 0:
    live_caps_line = {
        "_id": _live_id("caps"),
        "qty": int(caps_qty),
        "unit": "EA",
        "item": ("Safety Caps (OSHA)" if caps_label == "OSHA-Approved" else "Safety Caps (Plastic)"),
        "price_each": float(caps_unit_cost),
        "line_total": float(caps_unit_cost) * int(caps_qty),
    }

live_removal_line = None
if removal_selected and required_ft > 0:
    live_removal_line = {
        "_id": _live_id("removal"),
        "qty": CUSTOMER_QTY_LF,
        "unit": "LF",
        "item": "Fence Removal",
        "price_each": float(removal_unit_price_lf),
        "line_total": float(removal_unit_price_lf) * CUSTOMER_QTY_LF,
    }


def _fence_signature() -> str:
    if fencing_category == "Silt Fence":
        return f"SF|{gauge_option}|{post_spacing_ft}"
    else:
        return f"OF|{orange_duty}|{post_spacing_ft}"

current_sig = _fence_signature()
last_sig = st.session_state.get("last_fence_signature")


def _num(x, default=0.0):
    try:
        return float(x)
    except Exception:
        try:
            return float(str(x).replace(",", "").strip())
        except Exception:
            return float(default)


def _build_live_pack():
    hidden_live = set(st.session_state.get("preview_live_hidden_ids", []))
    pack = []
    for ln in (live_install_line, live_removal_line, live_caps_line):
        if ln and ln.get("_id") not in hidden_live:
            pack.append(ln)
    return pack


def _sort_key(ln: dict):
    item = (ln.get("item") or "")
    if ln.get("unit") == "LF" and "Removal" not in item:
        return (0,)
    if "Removal" in item:
        return (1,)
    return (2,)


def _with_id(line: dict) -> dict:
    return {**line, "_id": str(uuid.uuid4())}

if last_sig is not None and last_sig != current_sig:
    for ln in _build_live_pack():
        st.session_state["export_locked_lines"].append(_with_id(ln))
    st.session_state["preview_live_hidden_ids"] = []

st.session_state["last_fence_signature"] = current_sig

# -------------------- Export Actions --------------------
with sidebar_card("Export Actions", icon="📦"):
    if st.button("➕ Add current selection to Export Preview", use_container_width=True, key="btn_seed_export_preview"):
        locked = list(st.session_state.get("export_locked_lines", []))
        for ln in _build_live_pack():
            ln_locked = copy.deepcopy(ln)
            ln_locked["_id"] = f"locked_{uuid.uuid4()}"
            locked.append(ln_locked)
        st.session_state["export_locked_lines"] = locked
        st.session_state["preview_live_hidden_ids"] = []
        st.success("Added current selection to export lines.")
        st.rerun()

# -------------------- Sidebar: Status badge --------------------
with sidebar_card("Status", icon="📊"):
    target = 0.30
    m = float(profit_margin or 0.0)
    ok = m >= target
    ratio = max(0.0, min(m / target, 1.0))
    fill_pct = int(ratio * 100)
    label = "PROFIT GOOD" if ok else "CHECK PROFIT"
    st.markdown(
        f"""
        <style>
          .status-wrap {{ display:flex; justify-content:center; margin:0 }}
          .status-badge {{ position:relative; border:2px solid {'#8fd095' if ok else '#cc3232'}; border-radius:10px;
            padding:10px 40px; background:linear-gradient(90deg, {'hsl(80,85%,18%)' if ok else 'hsl(0,100%,78%)'} 20%, {'hsl(80,85%,6%)' if ok else 'hsl(0,100%,58%)'} 100%);
            color:{'#ffffff' if ok else '#0f172a'} !important; font-weight:800; font-size: 16px; line-height:0.4; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,.08); }}
          .status-badge .fill {{ position:absolute; left:0; top:0; bottom:0; width:{fill_pct}%; background:rgba(255,255,255,.2); z-index:0; }}
          .status-badge span {{ position:relative; z-index:1; white-space:nowrap; }}
          .status-badge .pct {{ font-weight:700; font-size:16px; opacity:.95; }}
        </style>
        <div class="status-wrap"><div class="status-badge"><div class="fill"></div>
          <span>{label} &nbsp; <span class="pct">{m:.1%}</span></span>
        </div></div>
        """,
        unsafe_allow_html=True,
    )

# -------------------- Excel-style panels --------------------

def inject_excel_styles(dark: bool) -> None:
    col_bg = "#afb0ae" if dark else "#89cd8f"
    col_border = "#2e6d33" if dark else "#b2deb5"
    grid = "#020603" if dark else "#dbead9"
    header_bg = "#17381b" if dark else "#2e6d33"
    header_text = "#ffffff"
    alt_row = "#7e807d" if dark else "#f5fbf6"
    shadow = "0 2px 10px rgba(0,0,0,.28)" if dark else "0 2px 10px rgba(0,0,0,.08)"
    st.markdown(
        f"""
        <style>
          .excel-col {{ background:{col_bg}; border:2.5px solid {col_border}; border-radius:12px; padding:10px 8px 12px; box-shadow:{shadow}; }}
          .excel-title {{ margin:0 0 12px 0; font-weight:800; color:#000; border-bottom:2px dashed {col_border}; padding-bottom:6px; text-align:center; font-size:24px; }}
          .excel-table {{ width:100%; border-collapse:separate; border-spacing:0; table-layout:auto; }}
          .excel-table thead th {{ background:{header_bg}; color:{header_text}; text-align:center; padding:8px; font-weight:700; border:2px solid {grid}; white-space:nowrap; }}
          .excel-table tbody td {{ padding:8px 10px; font-size:16px; vertical-align:top; border-bottom:2px solid {grid}; border-left:2px solid {grid}; border-right:2px solid {grid}; }}
          .excel-table tbody tr:nth-child(odd) td {{ background:{alt_row}; }}
          .excel-table td:first-child {{ font-weight:600; width:50%; white-space:nowrap; }}
          .excel-table td:last-child  {{ text-align:right; white-space:nowrap; }}
          .excel-table tbody tr:last-child td {{ border-top: 2px solid #2e6d33; font-weight: 700; font-size: 18px !important; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def excel_panel(title: str, rows: list[tuple[str, str]]) -> None:
    body = "\n".join(f"<tr><td>{e(lbl)}</td><td>{val}</td></tr>" for lbl, val in rows)
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

inject_excel_styles(ui_dark)

rows_cost_summary = [
    ("Subtotal (excl. sales tax)", f"${customer_subtotal_display:,.2f}"),
    (f"Sales Tax ({(0 if remove_tax else _tax_rate*100):.2f}%)", f"${customer_sales_tax:,.2f}"),
    ("Customer Total", f"${customer_total:,.2f}"),
    ("Gross Profit", f"${gross_profit:,.2f}"),
]
rows_total_costs = [
    ("Total Material Cost", f"${materials_subtotal_all:,.2f}"),
    ("Labor Cost", f"${labor_cost:,.2f}"),
    ("Fuel", f"${fuel:,.2f}"),
]
if removal_selected and required_ft > 0:
    rows_total_costs.append(("Fence Removal", f"${removal_total:,.2f}"))
rows_total_costs.append(("Final Price / LF (sell)", f"${final_price_per_lf:,.2f}"))

rows_material_costs = [
    ("Fabric (Silt Fence)" if fencing_category == "Silt Fence" else f"Plastic Orange Fence ({orange_duty})", f"${fabric_cost:,.2f}"),
    ("T-Post Cost", f"${hardware_cost:,.2f}"),
]
if caps_qty > 0:
    rows_material_costs.append((f"Safety Caps ({e(caps_label)})", f"${caps_cost:,.2f}"))
rows_material_costs.append(("Total Material Cost", f"${materials_subtotal_all:,.2f}"))
rows_material_costs.append(("Total Material Cost / LF", f"${(materials_subtotal_all / required_ft) if required_ft > 0 else 0.0:,.2f}"))

c1, c2, c3 = st.columns([1, 1, 1], gap="large")
with c1: excel_panel("Cost Summary", rows_cost_summary)
with c2: excel_panel("Total Costs Breakdown", rows_total_costs)
with c3: excel_panel("Material Cost Breakdown", rows_material_costs)

st.markdown('<div style="height:24px"></div>', unsafe_allow_html=True)
st.markdown('<div style="height:2px;display:flex;background:#020603;margin:16px 0"></div>', unsafe_allow_html=True)

# -------------------- Profit Margin Gauge (robust, slim, no broken image) --------------------
try:
    m_val = float(profit_margin or 0.0) * 100.0
    target_pct = 30.0
    xmax = max(60.0, target_pct + 10.0, m_val + 10.0)

    # Slim but not paper-thin; higher dpi keeps it crisp
    WIDTH_IN, HEIGHT_IN, DPI = 5.0, 0.8, 50
    BAR_HALF_H, TEXT_SIZE = 0.35, 14

    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    import numpy as np

    # Colors
    if m_val < 20.0:
        grad_colors, target_col = ["#5a1717", "#cc3232"], "#ff9d9d"
    elif m_val < target_pct:
        grad_colors, target_col = ["#7a5900", "#e6a700"], "#ffd27a"
    else:
        grad_colors, target_col = ["#1f5a22", "#44a04c"], "#a6e0ab"

    cmap_val  = mcolors.LinearSegmentedColormap.from_list("val_grad", grad_colors)
    cmap_well = mcolors.LinearSegmentedColormap.from_list("well", ["#2b2b2b", "#1a1a1a"])

    fig, ax = plt.subplots(figsize=(WIDTH_IN, HEIGHT_IN), dpi=DPI)
    # Use solid background (no transparency) to avoid PNG alpha issues
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    # Frame/axes
    ax.set_xlim(0, xmax); ax.set_ylim(-0.5, 0.5)
    ax.axis("off")  # remove ticks/spines entirely for reliability

    # Well background
    xgrad = np.linspace(0, 1, 512).reshape(1, -1)
    ax.imshow(
        xgrad, extent=(0, xmax, -BAR_HALF_H - 0.06, BAR_HALF_H + 0.06),
        cmap=cmap_well, aspect="auto", origin="lower", zorder=1
    )

    # Value fill
    v = max(0.0, min(m_val, xmax))
    vgrad = np.linspace(0, 1, 512).reshape(1, -1)
    ax.imshow(
        vgrad, extent=(0, v, -BAR_HALF_H, BAR_HALF_H),
        cmap=cmap_val, aspect="auto", origin="lower", zorder=2
    )

    # Target marker
    ax.axvline(target_pct, color=target_col, linestyle="--", linewidth=1.2, alpha=0.95, zorder=3)

    # Label
    label_text = f"{m_val:.1f}%"
    xpos = v * 0.5 if m_val >= 12 else min(v + xmax * 0.01, xmax - 1)
    ha = "center" if m_val >= 12 else "left"
    ax.text(
        xpos, 0, label_text,
        ha=ha, va="center", color="#000000", fontweight="bold", fontsize=TEXT_SIZE, zorder=4
    )

    # Subtitle axis below bar (optional)
    ax2 = fig.add_axes([0.06, 0.05, 0.88, 0.001])
    ax2.axis("off")
    ax2.text(0.0, 0.0, "Profit Percentage (%)", fontsize=TEXT_SIZE-1, color="#333333", va="center")

    st.pyplot(fig, use_container_width=True)
    plt.close(fig)

except Exception as _exc:
    st.warning("Gauge render failed; showing text fallback.")
    st.write(f"Profit Margin: **{(profit_margin or 0.0):.1%}**  •  Target: **{target_pct/100:.0%}**  (error: {_exc})")

# -------------------- Export plumbing --------------------

def _write_summary_payload(preview_lines, subtotal, sales_tax, grand_total):
    st.session_state["summary_export_payload"] = {
        "lines": preview_lines,
        "subtotal": float(subtotal),
        "sales_tax": float(sales_tax),
        "grand_total": float(grand_total),
        "exported_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "project_name": st.session_state.get("project_name", ""),
        "company_name": st.session_state.get("company_name", ""),
        "project_address": st.session_state.get("project_address", ""),
        "remove_sales_tax": bool(st.session_state.get("remove_sales_tax", False)),
    }
    st.session_state["export_quote_lines"] = list(preview_lines)  # legacy mirror


def _navigate_to_summary():
    try:
        st.switch_page("pages/99_Material_Summary.py")
    except Exception:
        st.session_state["page"] = "summary"
        st.rerun()


def _export_preview_to_summary(preview_lines, subtotal, sales_tax, grand_total):
    _write_summary_payload(preview_lines, subtotal, sales_tax, grand_total)
    _navigate_to_summary()

# -------------------- Customer Export Preview (boxed panel, real row containers, one-click trash) --------------------
# Build source lines (locked + current live), then de-duplicate by _id
merged = (st.session_state.get("export_locked_lines", []) or []) + _build_live_pack()
uniq = {}
for ln in merged:
    rid = str(ln.get("_id") or f"locked_{uuid.uuid4()}")
    uniq[rid] = {**ln, "_id": rid}
preview_lines = sorted(uniq.values(), key=_sort_key)

if not preview_lines:
    st.caption("No rows to show yet — enter a positive footprint or seed a test line below.")
    if st.button("➕ Seed a test line", use_container_width=True, key="seed_test_line"):
        st.session_state["export_locked_lines"] = (st.session_state.get("export_locked_lines", []) or []) + [{
            "_id": f"locked_{uuid.uuid4()}",
            "qty": 100, "unit": "LF",
            "item": "12.5 Gauge Silt Fence",
            "price_each": 2.50,
            "line_total": 250.00,
        }]
        st.rerun()
    st.stop()

import pandas as pd
# Build rows for display/export
_rows = []
for ln in preview_lines:
    qty = int(_num(ln.get("qty", ln.get("qty_lf", 0)), 0))
    unit = ln.get("unit") or ("LF" if ("qty_lf" in ln) else "")
    item = ln.get("item", "") or ""
    price_each = _num(ln.get("price_each", ln.get("price_per_lf", 0.0)), 0.0)
    if price_each <= 0 and "Removal" in item:
        price_each = float(globals().get("removal_unit_price_lf", 0.0))
    line_total = _num(ln.get("line_total", 0.0), 0.0) or (price_each * qty)
    _rows.append({
        "_id": str(ln.get("_id")),
        "Qty": qty,
        "Item": item,
        "Unit": unit,
        "Price Each": float(price_each),
        "Line Total": float(line_total),
    })
df = pd.DataFrame(_rows)

# ---- Styles (theme-aware) ----
row_bg     = "#ffffff" if not ui_dark else "#0f172a"
row_border = "#e5e7eb" if not ui_dark else "#1f2937"
shadow     = "0 2px 10px rgba(0,0,0,.08)" if not ui_dark else "0 2px 10px rgba(0,0,0,.35)"
text_muted = "#64748b"

st.markdown(f"""
<style>
  /* style each row's REAL Streamlit container (identified by .row-sentinel inside) */
  div[data-testid="stContainer"]:has(.row-sentinel) {{
    border:10px solid {row_border};
    border-radius:12px;
    background:{row_bg};
    box-shadow:{shadow};
    padding:10px 12px;
    margin-bottom:8px;
  }}
  .hdr {{ font-size:13px; text-transform:uppercase; color:{text_muted}; letter-spacing:.04em; margin:6px 0; }}
  .row-item  {{ font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
  .row-qty   {{ text-align:center; }}
  .row-unit  {{ text-align:center; }}
  .row-price {{ text-align:right; }}
  .row-total {{ text-align:right; font-weight:700; }}
</style>
""", unsafe_allow_html=True)

# --- Expander header styling (theme-aware) ---
header_bg     = "#e0f2fe" if not ui_dark else "#0b1220"
header_border = "#60a5fa" if not ui_dark else "#2563eb"
header_text   = "#0f172a" if not ui_dark else "#e5e7eb"
header_hover  = "#d9effd" if not ui_dark else "#111827"

st.markdown(f"""
<style>
  /* Expander wrapper: round outer corners to match content panel */
  div[data-testid="stExpander"] {{
    border-radius: 12px;
    overflow: hidden; /* keeps header rounded */
    border: 2px solid {header_border};
    box-shadow: 0 4px 14px rgba(96,165,250,.18);
    margin-bottom: 10px;
  }}

  /* Header bar */
  div[data-testid="stExpander"] details > summary {{
    list-style: none;              /* remove default triangle */
    background: {header_bg};
    color: {header_text};
    font-weight: 800;
    padding: 10px 14px;
    border-bottom: 2px solid {header_border};
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    user-select: none;
  }}
  /* Remove default marker in some browsers */
  div[data-testid="stExpander"] details > summary::-webkit-details-marker {{ display: none; }}

  /* Custom chevron */
  div[data-testid="stExpander"] details > summary:before {{
    content: "▸";
    font-size: 14px;
    opacity: .8;
    transition: transform .15s ease;
  }}
  /* Rotate chevron when open */
  div[data-testid="stExpander"] details[open] > summary:before {{
    content: "▾";
    transform: rotate(0deg);
  }}

  /* Hover/active states */
  div[data-testid="stExpander"] details > summary:hover {{
    background: {header_hover};
  }}

  /* Tighten spacing between header and content (you already styled content panel) */
  div[data-testid="stExpander"] div[data-testid="stExpanderContent"] {{
    margin-top: 0 !important;
  }}
</style>
""", unsafe_allow_html=True)

with st.expander("Customer Export Preview", expanded=True):
    # Header + actions
    h1, h2 = st.columns([4, 2])
    with h1:
        c = st.columns([0.9, 5, 1, 1.2, 1.4, 0.9])
        c[0].markdown('<div class="hdr">Qty</div>', unsafe_allow_html=True)
        c[1].markdown('<div class="hdr">Item</div>', unsafe_allow_html=True)
        c[2].markdown('<div class="hdr">Unit</div>', unsafe_allow_html=True)
        c[3].markdown('<div class="hdr">Price Each</div>', unsafe_allow_html=True)
        c[4].markdown('<div class="hdr">Line Total</div>', unsafe_allow_html=True)
        c[5].markdown('&nbsp;', unsafe_allow_html=True)
    with h2:
        st.session_state.setdefault("confirm_delete_all", False)
        if not st.session_state["confirm_delete_all"]:
            if st.button("🧹 Delete all lines", use_container_width=True, key="btn_del_all_ask"):
                st.session_state["confirm_delete_all"] = True
                st.rerun()
        else:
            ca, cb = st.columns(2)
            with ca:
                if st.button("✅ Confirm delete all", use_container_width=True, key="btn_del_all_confirm"):
                    live_ids = [str(ln.get("_id")) for ln in preview_lines if str(ln.get("_id")).startswith("live_")]
                    hidden_live = set(st.session_state.get("preview_live_hidden_ids", [])) | set(live_ids)
                    st.session_state["preview_live_hidden_ids"] = list(hidden_live)
                    st.session_state["export_locked_lines"] = []
                    st.session_state["confirm_delete_all"] = False
                    st.rerun()
            with cb:
                if st.button("↩️ Cancel", use_container_width=True, key="btn_del_all_cancel"):
                    st.session_state["confirm_delete_all"] = False
                    st.rerun()

    # Rows — each in its own real container so the background wraps all columns
    delete_ids = []
    for _, r in df.iterrows():
        rid = str(r["_id"])
        qty = int(r["Qty"])
        item = e(r["Item"])
        unit = e(r["Unit"])
        price_each = float(r["Price Each"])
        line_total = float(r["Line Total"])

        with st.container():
            st.markdown('<div class="row-sentinel"></div>', unsafe_allow_html=True)  # lets CSS target this container
            c1, c2, c3, c4, c5, c6 = st.columns([0.9, 5, 1, 1.2, 1.4, 0.9], vertical_alignment="center")
            c1.markdown(f'<div class="row-qty">{qty}</div>', unsafe_allow_html=True)
            c2.markdown(f'<div class="row-item">{item}</div>', unsafe_allow_html=True)
            c3.markdown(f'<div class="row-unit">{unit}</div>', unsafe_allow_html=True)
            c4.markdown(f'<div class="row-price">${price_each:,.2f}</div>', unsafe_allow_html=True)
            c5.markdown(f'<div class="row-total">${line_total:,.2f}</div>', unsafe_allow_html=True)
            with c6:
                if st.button("🗑️", key=f"del_{rid}", help="Remove this line", use_container_width=True):
                    delete_ids.append(rid)

    # Apply deletions
    if delete_ids:
        delete_ids = set(delete_ids)
        hidden_live = set(st.session_state.get("preview_live_hidden_ids", []))
        hidden_live |= {rid for rid in delete_ids if str(rid).startswith("live_")}
        st.session_state["preview_live_hidden_ids"] = list(hidden_live)
        st.session_state["export_locked_lines"] = [
            ln for ln in (st.session_state.get("export_locked_lines", []) or [])
            if str(ln.get("_id")) not in delete_ids
        ]
        st.rerun()

    # Totals
    subtotal = float(df["Line Total"].sum()) if not df.empty else 0.0
    remove_tax_flag = bool(st.session_state.get("remove_sales_tax", False))
    tax_rate = float(_tax_rate)
    sales_tax = 0.0 if remove_tax_flag else (subtotal * tax_rate)
    grand_total = subtotal + sales_tax

    t1, t2 = st.columns([2, 1])
    with t2:
        st.markdown(
            f"""
            <table style="width:100%; border-collapse:collapse;">
              <tr><td style="padding:6px 10px;=#ffffff">Subtotal (excl. tax)</td><td style="text-align:right;padding:6px 10px;">${subtotal:,.2f}</td></tr>
              <tr><td style="padding:6px 10px;">Sales Tax ({(0 if remove_tax_flag else tax_rate*100):.2f}%){" (removed)" if remove_tax_flag else ""}</td>
                  <td style="text-align:right;padding:6px 10px;">${sales_tax:,.2f}</td></tr>
              <tr><td style="padding:6px 10px;font-weight:800;border-top:2px solid #2e6d33;">Grand Total</td>
                  <td style="text-align:right;padding:6px 10px;font-weight:800;border-top:2px solid #2e6d33;">${grand_total:,.2f}</td></tr>
            </table>
            """,
            unsafe_allow_html=True,
        )

    # Export (what you see is what you export)
    if st.button("📄 Export to Summary", type="primary", use_container_width=True, key="btn_export_to_summary_oneclick"):
        preview_map = {str(ln.get("_id")): ln for ln in preview_lines}
        lines_to_export = []
        for _, row in df.iterrows():
            rid = str(row["_id"])
            base = {
                "_id": rid,
                "qty": int(row["Qty"]),
                "unit": row["Unit"],
                "item": row["Item"],
                "price_each": float(row["Price Each"]),
                "line_total": float(row["Line Total"]),
            }
            found = preview_map.get(rid)
            if found:
                base.update({k: found[k] for k in ("sku_fabric", "sku_post", "sku_cap", "post_spacing_ft") if k in found})
            lines_to_export.append(base)

        _export_preview_to_summary(lines_to_export, subtotal, sales_tax, grand_total)
        st.stop()
