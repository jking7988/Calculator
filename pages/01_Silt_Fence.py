# Double Oak – Fencing Estimator (Unified, Clean Rewrite)
# ------------------------------------------------------
import math, uuid, copy, html
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import streamlit as st
from datetime import datetime
from core.theme_persist import init_theme, render_toggle, sidebar_skin
from core.theme import apply_theme, fix_select_colors
from core.ui_sidebar import apply_sidebar_shell, sidebar_card, SIDEBAR_CFG
from core import settings as cfg
from core import pricebook

pricebook.ensure_loaded()

# --- st_aggrid compatibility shim (place once near your imports) ---
try:
    from st_aggrid import GridUpdateMode, DataReturnMode
except Exception:
    # In very old versions these may not exist; fall back to strings
    class _EnumShim:
        def __getattr__(self, name):  # DataReturnMode.AS_INPUT -> "AS_INPUT"
            return name
    GridUpdateMode = _EnumShim()
    DataReturnMode = _EnumShim()

def _enum_or_str(enum_cls, name: str):
    """Return enum member if available; otherwise the string name itself."""
    try:
        return getattr(enum_cls, name)
    except Exception:
        return name

# -------------------- Page + Global CSS --------------------
st.set_page_config(
    page_title="Double Oak Fencing Estimator",
    layout="wide",
    initial_sidebar_state="expanded",
    )

# Hide the +/- spinner buttons on ALL number inputs (keeps typing)
st.markdown("""
<style>
input[type=number]::-webkit-inner-spin-button,
input[type=number]::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
input[type=number] { -moz-appearance: textfield; }  /* Firefox */
</style>
""", unsafe_allow_html=True)

def price_text_input(label: str, key: str, default: float = 2.50, *, min_v=0.0, max_v=100.0) -> float:
    # seed prior good value
    prior = st.session_state.get(f"{key}__val", default)
    # show last text or default formatted
    seed_text = st.session_state.get(f"{key}__text", f"{prior:.2f}")
    txt = st.text_input(label, value=seed_text, key=f"{key}__text", help="Type a price like 2.50 (no %).")
    # parse
    raw = (txt or "").strip()
    raw = raw.replace("$", "").replace(",", "")
    try:
        val = float(raw)
    except Exception:
        val = prior  # keep last valid on bad input
    # clamp
    val = max(min_v, min(max_v, val))
    # persist last good
    st.session_state[f"{key}__val"] = val
    return val

# ---------- Minimal "p" helper namespace ----------
# Uses _tax_rate_default you already set from cfg.SALES_TAX_RATE
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
        # +1 to include start post
        return int(math.ceil(rf / sp)) + 1 if rf > 0 else 0

    @staticmethod
    def rolls_needed(required_ft: float, roll_len: int = 100) -> int:
        rf = max(0.0, float(required_ft or 0))
        rl = max(1, int(roll_len or 100))
        return int(math.ceil(rf / rl)) if rf > 0 else 0

    @staticmethod
    def get_labor_per_day() -> float:
        # tune to your org’s rate
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
        """
        Returns: fabric_cost, hardware_cost, materials_subtotal, tax
        - tax is applied only to fabric + posts (caps are added later in your flow)
        """
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

# expose as `p`
p = _P()
# ---------- end helpers ----------

st.markdown(
    """
    <style>
    header[data-testid="stHeader"] { display: none !important; }
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    .block-container { max-width: 100% !important; padding-top: .5rem; padding-left: 1rem; padding-right: 1rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Robust escape helper (works even if core.sanitize isn't available)
try:
    from core.sanitize import e  # type: ignore
except Exception:  # noqa: BLE001
    def e(x) -> str:
        return html.escape(str(x))

# -------------------- Session state init --------------------
st.session_state.setdefault("export_history_fencing", [])
st.session_state.setdefault("pricebook_warnings", [])
st.session_state.setdefault("export_locked_lines", [])        # list[dict] with optional "_id"
st.session_state.setdefault("last_fence_signature", None)      # str | None
st.session_state.setdefault("preview_live_hidden_ids", [])     # list[str] of live row ids to hide
st.session_state.setdefault("remove_sales_tax", False)

# Ensure pricebook is loaded before we start reading prices
pricebook.ensure_loaded()

# Example: show a couple of items using the S3/bundled/ uploaded pricebook
_item = pricebook.get_item("silt-fence-12g5")
if _item:
    st.write(f"12.5 Gauge Silt Fence ({_item['unit']}) — ${float(_item['price']):,.2f}")

# -------------------- Constants / SKUs --------------------
FABRIC_SKU_14G = "silt-fence-14g"
FABRIC_SKU_125G = "silt-fence-12g5"

POST_SKU_T_POST_4FT = "t-post-4ft"               # standard for 14g
POST_SKU_TXDOT_T_POST_4FT = "tx-dot-t-post-4-ft" # REQUIRED for 12.5g (TX-DOT)
POST_SKU_T_POST_6FT = "t-post-6ft"               # orange fence

FABRIC_SKU_ORANGE_LIGHT = "orange-fence-light-duty"
FABRIC_SKU_ORANGE_HEAVY = "orange-fence-heavy-duty"

CAP_SKU_OSHA = "cap-osha"
CAP_SKU_PLASTIC = "cap-plastic"

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
            width: 100% !important;
            background: {bg} !important;
            color: {text} !important;
            border: 2px solid {border} !important;
            border-radius: 12px !important;
            padding: 10px 12px !important;
            font-weight: 700 !important;
            box-shadow: {shadow} !important;
            transition: background .15s ease, transform .04s ease;
          }}
          [data-testid="stSidebar"] .stButton > button:hover {{ background: {hoverbg} !important; }}
          [data-testid="stSidebar"] .stButton > button:active {{ background: {activebg} !important; transform: translateY(1px); }}
          [data-testid="stSidebar"] .stButton > button[kind="primary"] {{ background: {bg} !important; color: {text} !important; }}
        </style>
        """,
        unsafe_allow_html=True,
    )
style_sidebar_buttons(ui_dark)

# -------------------- Navigation --------------------
def _preserve_theme_param(is_dark: bool):
    try:
        st.query_params.update({"theme": "dark" if is_dark else "light"})
    except AttributeError:
        st.experimental_set_query_params(theme="dark" if is_dark else "light")

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
        _preserve_theme_param(st.session_state.get("ui_dark", False))
        st.switch_page(PAGES[choice])

# -------------------- Project / Customer --------------------
with sidebar_card(
    "Project / Customer",
    icon="📋",
    bg=("#0f1b12" if ui_dark else "#ffffff"),
    border="2px solid #2e6d33",
    radius_px=20,
    pad_x=12,
    pad_y=12,
):
    st.text_input(
        "Project Title:",
        key="project_name",
        value=st.session_state.get("project_name", ""),
        placeholder="e.g., Lakeside Retail – Phase 2",
    )
    st.text_input(
        "Customer Name:",
        key="company_name",
        value=st.session_state.get("company_name", ""),
        placeholder="e.g., ACME Builders",
    )
    st.text_input(
        "Address:",
        key="project_address",
        value=st.session_state.get("project_address", ""),
        placeholder="e.g., 1234 Main St, Austin, TX",
    )

COMPANY_NAME = e(st.session_state.get("company_name", ""))
PROJECT_NAME = e(st.session_state.get("project_name", ""))
PROJECT_ADDR = e(st.session_state.get("project_address", ""))

# -------------------- Safe defaults --------------------
fencing_category = "Silt Fence"   # or "Plastic Orange Fence"
gauge_option = "14 Gauge"
orange_duty = "Light Duty"

total_job_footage = 1000
waste_pct = 2
cost_per_lf = 0.0
post_type = ""
post_unit_cost = 0.0
post_spacing_ft = 0
include_caps = False
cap_type = None
final_price_per_lf = 2.50
_tax_rate_default = getattr(cfg, "SALES_TAX_RATE", 0.0825)

# -------------------- Fencing Options --------------------
with sidebar_card(
    "Fencing Options",
    icon="🛠️",
    bg=("#0f1b12" if ui_dark else "#ffffff"),
    border=("2px solid #8fd095" if ui_dark else "3px solid #2e6d33"),
    pad_x=12,
    pad_y=12,
    radius_px=12,
    shadow=("0 4px 14px rgba(0,0,0,.40)" if ui_dark else "0 4px 14px rgba(0,0,0,.06)"),
):
    # Shared inputs
    total_job_footage = st.number_input(
        "Total Job Footage (ft):",
        min_value=0, max_value=1_000_000, value=1000, step=1,
        key="fence_total_lf",
        help="Enter total linear feet from plans (before waste)."
    )
    waste_pct = st.number_input(
        "Waste %:",
        min_value=0, max_value=10, value=2, step=1,
        key="fence_waste_pct",
        help="Waste/overlap allowance."
    )
    fencing_category = st.selectbox(
        "Fencing Material:",
        ["Silt Fence", "Plastic Orange Fence"],
        key="fence_category",
        help="Choose between silt fence and plastic orange (tree) fencing."
    )

    if fencing_category == "Silt Fence":
        # ---- Silt Fence branch
        post_type = "T-Post"
        gauge_option = st.selectbox(
            "Silt Fence Gauge:",
            ["14 Gauge", "12.5 Gauge"],
            key="sf_gauge"
        )
        post_spacing_ft = st.selectbox(
            "T-Post Spacing (ft):",
            options=[3, 4, 6, 8, 10],
            index=3,
            key="sf_post_spacing",
            help="Select T-post spacing per plan."
        )
        final_price_per_lf = price_text_input(
    "Final Price / LF:", key="sf_final_price", default=2.50, min_v=0.0, max_v=100.0
)

        include_caps = st.checkbox(
            "Check for Caps",
            value=False,
            key="sf_caps",
            help="Add one safety cap per T-post."
        )
        cap_type = (
            st.selectbox(
                "Cap Type:",
                ["OSHA-Approved ($3.90)", "Regular Plastic Cap ($1.05)"],
                index=0,
                key="sf_cap_type"
            ) if include_caps else None
        )

        removal_selected = st.checkbox(
            "Add fence removal pricing",
            value=False,
            key="sf_removal",
            help="Show removal price per LF (labor + fuel; no materials)."
        )
        remove_tax_selected = st.checkbox(
            "Remove sales tax from customer printout",
            value=st.session_state.get("remove_sales_tax", False),
            key="sf_remove_tax",
            help="If checked, customer printout will show $0.00 sales tax."
        )
        st.session_state["remove_sales_tax"] = bool(remove_tax_selected)

    else:
        # ---- Plastic Orange Fence branch
        post_type = "T-Post"
        orange_duty = st.selectbox(
            "Orange Fence Duty:",
            ["Light Duty", "Heavy Duty"],
            key="orange_duty",
            help="Select fence strength."
        )
        post_spacing_ft = st.selectbox(
            "T-Post Spacing (ft):",
            options=[3, 4, 6, 8, 10],
            index=4,
            key="orange_post_spacing",
            help="Typical spacing is 10 ft."
        )

        # No caps for orange fence
        include_caps = False
        cap_type = None

        final_price_per_lf = price_text_input(
    "Final Price / LF:", key="orange_final_price", default=2.50, min_v=0.0, max_v=100.0
)

        removal_selected = st.checkbox(
            "Add fence removal pricing",
            value=False,
            key="orange_removal",
            help="Show removal price per LF (labor + fuel; no materials)."
        )
        remove_tax_selected = st.checkbox(
            "Remove sales tax from customer printout",
            value=st.session_state.get("remove_sales_tax", False),
            key="orange_remove_tax",
            help="If checked, customer printout will show $0.00 sales tax."
        )
        st.session_state["remove_sales_tax"] = bool(remove_tax_selected)

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
        fabric_sku, fabric_default = "silt-fence-14g", 0.32
        post_sku, post_default     = "t-post-4ft", 1.80
    else:
        fabric_sku, fabric_default = "silt-fence-12g5", 0.38
        post_sku, post_default     = "tx-dot-t-post-4-ft", 2.15
else:
    if orange_duty.startswith("Light"):
        fabric_sku, fabric_default = "orange-fence-light-duty", 0.30
    else:
        fabric_sku, fabric_default = "orange-fence-heavy-duty", 0.45
    post_sku, post_default = "t-post-6ft", 2.25

cost_per_lf   = get_price_or_warn(fabric_sku, fabric_default, f"Fabric ({gauge_option}) / LF")
post_unit_cost = get_price_or_warn(post_sku,   post_default,   f"Post ({post_sku}) / EA")

def get_unit_for(code: str, fallback: str = "") -> str:
    item = pricebook.get_item(code)
    return item["unit"] if item and "unit" in item else fallback

st.write(f"Fabric {gauge_option} ({get_unit_for(fabric_sku,'LF')}) — ${cost_per_lf:,.2f}")
st.write(f"Post {post_sku} ({get_unit_for(post_sku,'EA')}) — ${post_unit_cost:,.2f}")

caps_unit_cost = 0.0
caps_sku_used  = None
if fencing_category == "Silt Fence" and post_type == "T-Post" and include_caps and cap_type:
    if "OSHA" in cap_type:
        caps_sku_used  = "cap-osha"
        caps_unit_cost = pricebook.get_price(caps_sku_used, 3.90) or 3.90
    else:
        caps_sku_used  = "cap-plastic"
        caps_unit_cost = pricebook.get_price(caps_sku_used, 1.05) or 1.05

# -------------------- Calculations --------------------
required_ft = p.required_footage(total_job_footage, waste_pct)
safe_spacing = max(1, int(post_spacing_ft or 0))
posts_count = p.posts_needed(required_ft, safe_spacing)
rolls = p.rolls_needed(required_ft)

caps_label = None
caps_qty = 0
if fencing_category == "Silt Fence" and post_type == "T-Post" and include_caps and cap_type:
    caps_label = "OSHA-Approved" if "OSHA" in cap_type else "Regular Plastic Cap"
    caps_qty = posts_count

caps_cost = caps_qty * caps_unit_cost

fabric_cost, hardware_cost, materials_subtotal, tax = p.materials_breakdown(
    required_ft, cost_per_lf, posts_count, post_unit_cost
)

materials_subtotal_all = materials_subtotal + caps_cost
_tax_rate = _tax_rate_default
tax_all = tax + caps_cost * _tax_rate

# Customer-visible quantity (no waste)
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
    _calc_removal_pricing(required_ft, final_price_per_lf) if 'removal_selected' in locals() and removal_selected else (0.0, 0.0)
)

# Production assumptions / costs
PROD_LF_PER_DAY = getattr(cfg, "PRODUCTION_LF_PER_DAY", 2500)
project_days = (required_ft / PROD_LF_PER_DAY) if required_ft > 0 else 0.0
labor_per_day = p.get_labor_per_day()
labor_cost = project_days * labor_per_day
billing_days = math.ceil(project_days) if required_ft > 0 else 0
fuel = p.fuel_cost(billing_days, any_work=required_ft > 0)
days = billing_days

unit_cost_lf = p.unit_cost_per_lf(required_ft, materials_subtotal_all, tax_all, labor_cost, fuel)
profit_margin_install_only = p.margin(final_price_per_lf, unit_cost_lf) if required_ft > 0 else 0.0

# Customer-facing revenue & margin (caps IN, removal OUT of margin)
removal_total = removal_total if "removal_total" in locals() else 0.0
sell_total_main = (final_price_per_lf * required_ft) if required_ft > 0 else 0.0
caps_revenue = (caps_unit_cost * caps_qty) if (caps_qty and caps_unit_cost) else 0.0
removal_revenue = removal_total if ('removal_selected' in locals() and removal_selected and required_ft > 0) else 0.0

customer_subtotal_display = sell_total_main + caps_revenue + removal_revenue
remove_tax = bool(st.session_state.get("remove_sales_tax", False))
customer_sales_tax = 0.0 if remove_tax else (customer_subtotal_display * _tax_rate)
customer_total = customer_subtotal_display + customer_sales_tax

internal_total_cost = materials_subtotal_all + tax_all + labor_cost + fuel
subtotal_for_margin = sell_total_main + caps_revenue
gross_profit = subtotal_for_margin - internal_total_cost
profit_margin = (gross_profit / subtotal_for_margin) if subtotal_for_margin > 0 else 0.0
profit_margin_install_only = p.margin(final_price_per_lf, unit_cost_lf) if required_ft > 0 else 0.0

# -------------------- Live lines --------------------

def _live_id(kind: str) -> str:
    return f"live_{kind}"

live_install_line = {
    "_id": _live_id("install"),
    "qty": CUSTOMER_QTY_LF,                 # 👈 no waste in preview
    "unit": "LF",
    "item": (f"{gauge_option} Silt Fence" if fencing_category == "Silt Fence" else f"Plastic Orange Fence – {orange_duty}"),
    "price_each": float(final_price_per_lf),
    "line_total": float(final_price_per_lf) * CUSTOMER_QTY_LF,  # 👈 preview total on unwasted LF
}

live_caps_line = None
if caps_qty > 0:
    live_caps_line = {
        "_id": _live_id("caps"),
        "qty": int(caps_qty),                # caps still based on posts (backend w/ waste OK)
        "unit": "EA",
        "item": ("Safety Caps (OSHA)" if caps_label == "OSHA-Approved" else "Safety Caps (Plastic)"),
        "price_each": float(caps_unit_cost),
        "line_total": float(caps_unit_cost) * int(caps_qty),
    }

live_removal_line = None
if 'removal_selected' in locals() and removal_selected and required_ft > 0:
    live_removal_line = {
        "_id": _live_id("removal"),
        "qty": CUSTOMER_QTY_LF,              # 👈 no waste in preview
        "unit": "LF",
        "item": "Fence Removal",
        "price_each": float(removal_unit_price_lf),
        "line_total": float(removal_unit_price_lf) * CUSTOMER_QTY_LF,  # 👈 compute on unwasted LF
    }

# Signature + append-don't-overwrite: lock ALL visible live rows when selection changes

def _fence_signature() -> str:
    if fencing_category == "Silt Fence":
        return f"SF|{gauge_option}|{post_spacing_ft}"
    else:
        return f"OF|{orange_duty}|{post_spacing_ft}"

current_sig = _fence_signature()
last_sig = st.session_state.get("last_fence_signature")

# Helper builders (single authoritative copies)

def _num(x, default=0.0):
    try:
        return float(x)
    except Exception:
        try:
            return float(str(x).replace(",", "").strip())
        except Exception:
            return float(default)


def _build_live_pack():
    """Collect current visible live lines (install/removal/caps), honoring hidden IDs."""
    hidden_live = set(st.session_state.get("preview_live_hidden_ids", []))
    pack = []
    for ln in (live_install_line, live_removal_line, live_caps_line):
        if ln and ln.get("_id") not in hidden_live:
            pack.append(ln)
    return pack


def _sort_key(ln: dict):
    """Install (LF, not removal) → Removal → Others."""
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

# -------------------- Export Actions (seed the preview early) --------------------
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

    if ok:
        above_ratio = max(0.0, min((m - target) / 0.30, 1.0))
        scale = 1.00 + 0.25 * above_ratio
    else:
        scale = 0.85 + 0.05 * ratio

    fs = max(14, int(18 * scale))
    pad_y = max(0, int(6 * scale))
    pad_x = max(40, int(12 * scale * 2))
    border_w = max(0, int(2 * scale))

    if not ok:
        hue, sat = 0, 100
        light_base = 50 + (88 - 70) * ratio
        grad_start = f"hsl({hue}, {sat}%, {light_base + 4:.1f}%)"
        grad_end = f"hsl({hue}, {sat}%, {light_base - 4}%)"
        text_col = "#0f172a"; border_col = "#cc3232"; pad_y = max(20, int(10 * scale)); fs = max(24, int(18 * scale))
    else:
        hue, sat, light = 80, 85, 10
        grad_start = f"hsl({hue}, {sat}%, {light + 8}%)"
        grad_end = f"hsl({hue}, {sat}%, {light - 4}%)"
        text_col = "#ffffff"; border_col = "#8fd095"; fs = max(24, int(20 * scale)); pad_y = max(10, int(10 * scale))

    fill_pct = int(ratio * 100)
    label = "PROFIT GOOD" if ok else "CHECK PROFIT"

    st.markdown(
        f"""
         <style>
           .status-wrap {{ display:flex; justify-content:center; margin:0 }}
           .status-badge {{
             position:relative; border:{border_w}px solid {border_col}; border-radius:10px;
             padding:{pad_y}px {pad_x}px; background:linear-gradient(90deg, {grad_start} 20%, {grad_end} 100%);
             color:{text_col} !important; -webkit-text-fill-color:{text_col} !important;
             font-weight:800; font-size: 16px; line-height:0.4; overflow:hidden;
             box-shadow:0 2px 8px rgba(0,0,0,.08);
           }}
           .status-badge .fill {{ position:absolute; left:0; top:0; bottom:0; width:{fill_pct}%;
             background:linear-gradient(90deg, {grad_start} 0%, {grad_end} 100%); z-index:0; opacity:0.35; }}
           .status-badge span {{ position:relative; z-index:1; white-space:nowrap; }}
           .status-badge .pct {{ font-weight:700; font-size:{max(12, int(fs * 0.8))}px; opacity:.95; }}
         </style>
         <div class="status-wrap"><div class="status-badge"><div class="fill"></div>
           <span>{label} &nbsp; <span class="pct">{m:.1%}</span></span>
         </div></div>
         """,
        unsafe_allow_html=True,
    )

# ---------- Summary export plumbing (single source of truth) ----------

def _write_summary_payload(preview_lines, subtotal, sales_tax, grand_total):
    """Write BOTH the new and legacy keys so any summary page reads the data."""
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
    # Legacy mirror
    st.session_state["export_quote_lines"] = list(preview_lines)


def _navigate_to_summary():
    try:
        st.switch_page("pages/99_Material_Summary.py")
    except Exception:
        st.session_state["page"] = "summary"
        st.rerun()


def _export_preview_to_summary(preview_lines, subtotal, sales_tax, grand_total):
    """Single authoritative exporter used by ALL buttons."""
    _write_summary_payload(preview_lines, subtotal, sales_tax, grand_total)
    _navigate_to_summary()

# ---------- Snapshot builders (exactly mirrors the preview math) ----------
def _synthesize_live_pack_from_current_selection():
    pack = []
    CUSTOMER_QTY_LF = int(globals().get("total_job_footage", 0) or 0)

    if CUSTOMER_QTY_LF > 0:
        item_name = (f"{globals().get('gauge_option','14 Gauge')} Silt Fence"
                     if globals().get("fencing_category") == "Silt Fence"
                     else f"Plastic Orange Fence – {globals().get('orange_duty','Light Duty')}")
        price_each = float(globals().get("final_price_per_lf", 0.0) or 0.0)
        pack.append({
            "_id": "live_install_syn",
            "qty": CUSTOMER_QTY_LF,                # 👈 no waste
            "unit": "LF",
            "item": item_name,
            "price_each": price_each,
            "line_total": price_each * CUSTOMER_QTY_LF,  # 👈 no waste
        })

    if (globals().get("caps_qty", 0) or 0) > 0:
        cap_cost = float(globals().get("caps_unit_cost", 0.0) or 0.0)
        pack.append({
            "_id": "live_caps_syn",
            "qty": int(globals().get("caps_qty", 0) or 0),
            "unit": "EA",
            "item": ("Safety Caps (OSHA)" if "OSHA" in str(globals().get("caps_label","")) else "Safety Caps (Plastic)"),
            "price_each": cap_cost,
            "line_total": cap_cost * int(globals().get("caps_qty", 0) or 0),
        })

    if globals().get("removal_selected") and CUSTOMER_QTY_LF > 0:
        price_each = float(globals().get("removal_unit_price_lf", 0.0) or 0.0)
        pack.append({
            "_id": "live_removal_syn",
            "qty": CUSTOMER_QTY_LF,                # 👈 no waste
            "unit": "LF",
            "item": "Fence Removal",
            "price_each": price_each,
            "line_total": price_each * CUSTOMER_QTY_LF,  # 👈 no waste
        })
    return pack


def _get_customer_printout_snapshot(*, ignore_hidden: bool = False, allow_synthesize: bool = True):
    hidden_live = set(() if ignore_hidden else st.session_state.get("preview_live_hidden_ids", []))

    live_pack = []
    for ln in (live_install_line, live_removal_line, live_caps_line):
        if ln and ln.get("_id") not in hidden_live:
            live_pack.append(ln)

    if not live_pack and allow_synthesize:
        live_pack = _synthesize_live_pack_from_current_selection()

    locked = list(st.session_state.get("export_locked_lines", []))
    preview_lines = sorted(locked + live_pack, key=_sort_key)

    subtotal = 0.0
    for ln in preview_lines:
        qty = int(_num(ln.get("qty", ln.get("qty_lf", 0)), 0))
        price_each = _num(ln.get("price_each", ln.get("price_per_lf", 0.0)), 0.0)
        if price_each <= 0 and "Removal" in (ln.get("item") or ""):
            price_each = float(globals().get("removal_unit_price_lf", 0.0))
        lt_stored = _num(ln.get("line_total", 0.0), 0.0)
        line_total = lt_stored if lt_stored > 0 else (price_each * qty)
        subtotal += line_total

    tax_rate = float(_tax_rate)
    remove_tax_flag = bool(st.session_state.get("remove_sales_tax", False))
    sales_tax = 0.0 if remove_tax_flag else (subtotal * tax_rate)
    grand_total = subtotal + sales_tax
    return preview_lines, subtotal, sales_tax, grand_total

# -------------------- Excel styles + panel helpers --------------------

def inject_excel_styles(dark: bool) -> None:
    col_bg = "#afb0ae" if dark else "#89cd8f"
    col_border = "#2e6d33" if dark else "#b2deb5"
    grid = "#020603" if dark else "#dbead9"
    header_bg = "#17381b" if dark else "#2e6d33"
    header_text = "#ffffff"
    label_col = "#000000"
    value_col = "#000000"
    alt_row = "#7e807d" if dark else "#f5fbf6"
    shadow = "0 2px 10px rgba(0,0,0,.28)" if dark else "0 2px 10px rgba(0,0,0,.08)"

    st.markdown(
        f"""
        <style>
          .excel-col {{ background:{col_bg}; border:2.5px solid {col_border}; border-radius:12px; padding:10px 8px 12px; box-shadow:{shadow}; }}
          .excel-title {{ margin:0 0 12px 0; font-weight:800; color:#000; border-bottom:2px dashed {col_border}; padding-bottom:6px; text-align:center; font-size:24px; }}
          .excel-table {{ width:100%; border-collapse:separate; border-spacing:0; table-layout:auto; }}
          .excel-table thead th {{ background:{header_bg}; color:{header_text}; text-align:center; padding:8px; font-weight:700; border:2px solid {grid}; white-space:nowrap; overflow:visible; text-overflow:ellipsis; }}
          .excel-table tbody td {{ padding:8px 10px; font-size:16px; vertical-align:top; border-bottom:2px solid {grid}; border-left:2px solid {grid}; border-right:2px solid {grid}; background:transparent; }}
          .excel-table tbody tr:nth-child(odd) td {{ background:{alt_row}; }}
          .excel-table td:first-child {{ color:{label_col}; font-weight:600; width:50%; white-space:nowrap; overflow:visible; text-overflow:ellipsis; }}
          .excel-table td:last-child  {{ color:{value_col}; text-align:right; white-space:nowrap; }}
          .excel-table tbody tr:last-child td {{ border-top: 2px solid #2e6d33; font-weight: 700; font-size: 18px !important; }}
          .del-btn {{ border: none; background: none; cursor: pointer; font-size: 18px; color: #cc3232; margin-left: 8px; }}
          .del-btn:hover {{ color: #ff5555; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def excel_panel(title: str, rows: list[tuple[str, str]]) -> None:
    def _row_html(lbl: str, val: str) -> str:
        return f"<tr><td>{e(lbl)}</td><td>{val}</td></tr>"
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

inject_excel_styles(ui_dark)

# -------------------- Cost Panels --------------------
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
if 'removal_selected' in locals() and removal_selected and required_ft > 0:
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
# REMOVED stray extra line that printed Final Price / LF under Cost Summary
st.markdown('<div style="height:24px"></div>', unsafe_allow_html=True)
st.markdown('<div style="height:2px;display:flex;background:#020603;margin:16px 0"></div>', unsafe_allow_html=True)

# -------------------- Profit Margin Gauge --------------------
try:
    m_val = float(profit_margin or 0.0) * 100.0
    target_pct = 30.0
    xmax = max(60.0, target_pct + 10.0, m_val + 10.0)
    WIDTH_IN, HEIGHT_IN, BAR_HALF_H, TEXT_SIZE = 20.2, 0.5, 0.4, 15

    if m_val < 20.0:
        grad_colors, target_col = ["#5a1717", "#cc3232"], "#ff9d9d"
    elif m_val < target_pct:
        grad_colors, target_col = ["#7a5900", "#e6a700"], "#ffd27a"
    else:
        grad_colors, target_col = ["#1f5a22", "#44a04c"], "#a6e0ab"

    cmap_val = mcolors.LinearSegmentedColormap.from_list("val_grad", grad_colors)
    cmap_well = mcolors.LinearSegmentedColormap.from_list("well", ["#2b2b2b", "#1a1a1a"])

    fig, ax = plt.subplots(figsize=(WIDTH_IN, HEIGHT_IN))
    fig.patch.set_alpha(0); ax.set_facecolor("none")
    ax.set_xlim(0, xmax); ax.set_ylim(-0.4, 0.4)
    for s in ("left", "right", "top", "bottom"): ax.spines[s].set_visible(False)
    ax.set_yticks([]); ax.set_xlabel("Profit Percentage (%)", color="#dddddd", fontsize=TEXT_SIZE)
    ax.tick_params(axis="x", colors="#bbbbbb", labelsize=TEXT_SIZE + 1)

    xgrad = np.linspace(0, 1, 512).reshape(1, -1)
    ax.imshow(xgrad, extent=(0, xmax, -BAR_HALF_H - 0.06, BAR_HALF_H + 0.06), cmap=cmap_well, aspect="auto", zorder=1, origin="lower")
    vgrad = np.linspace(0, 1, 512).reshape(1, -1)
    ax.imshow(vgrad, extent=(0, max(0, m_val), -BAR_HALF_H, BAR_HALF_H), cmap=cmap_val, aspect="auto", zorder=2, origin="lower")

    if m_val > 8:
        gloss = np.exp(-((np.linspace(-1, 1, 64)) ** 2) / 0.4).reshape(-1, 1)
        ax.imshow(gloss, extent=(0, m_val, 0.02, BAR_HALF_H), cmap=mcolors.LinearSegmentedColormap.from_list("gloss", ["white", "white"]), alpha=0.12, aspect="auto", zorder=3, origin="lower")

    ax.axvline(target_pct, color=target_col, linestyle="--", linewidth=1.1, alpha=0.9, zorder=4)

    label_text = f"{m_val:.1f}%"
    if m_val >= 12:
        ax.text(m_val * 0.5, 0, label_text, ha="center", va="center", color="#ffffff", fontweight="bold", fontsize=TEXT_SIZE, zorder=5)
    else:
        ax.text(m_val + xmax * 0.01, 0, label_text, ha="left", va="center", color="#ffffff", fontweight="bold", fontsize=TEXT_SIZE, zorder=5)

    plt.tight_layout()
    st.columns([1, 2, 1])[1].pyplot(fig, clear_figure=True)
except Exception as _exc:  # noqa: BLE001
    st.caption(f"(Chart error: {_exc})")

# -------------------- Customer Export Preview --------------------
st.markdown(
    """
    <style>
      /* Outer container */
      .customer-preview-box {
        display: inline-block;
        border: 2.5px solid #60a5fa;
        border-radius: 12px;
        background: #f8fbff;
        padding: 12px 16px;
        box-shadow: 0 4px 14px rgba(96,165,250,.25);
      }

      /* Header */
      .customer-preview-header {
        font-weight: 700;
        font-size: 18px;
        color: #1e3a8a;
        margin-bottom: 10px;
        padding: 6px 10px;
        border-radius: 6px;
        background: #e0f2fe;
        border: 1.5px solid #60a5fa;
        display: inline-block;
      }

      /* Totals table */
      .totals-table table {
        border-collapse: collapse;
        margin-top: 14px;
        margin-left: auto;   /* push right */
        margin-right: 0;
      }
      .totals-table td {
        padding: 6px 14px;
        font-size: 16px;
      }
      .totals-table tr:last-child td {
        border-top: 2px solid #2e6d33;
        font-weight: 700;
        font-size: 18px;
      }
      .totals-table td:first-child {
        text-align: left;
        white-space: nowrap;
      }
      .totals-table td:last-child {
        text-align: right;
        min-width: 120px;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

def _inject_customer_preview_col_styles():
    # Tight, content-hugging preview table (non-AgGrid fallback)
    COL_STYLE = {
        1: {"align": "center", "pad_y": 6, "pad_x": 8,  "font_head": 16, "font_body": 16},  # Qty
        2: {"align": "left",   "pad_y": 6, "pad_x": 10, "font_head": 16, "font_body": 16},  # Item
        3: {"align": "center", "pad_y": 6, "pad_x": 8,  "font_head": 16, "font_body": 16},  # Unit
        4: {"align": "right",  "pad_y": 6, "pad_x": 10, "font_head": 16, "font_body": 16},  # Price Each
        5: {"align": "right",  "pad_y": 6, "pad_x": 10, "font_head": 16, "font_body": 16},  # Line Total
    }
    css_parts = [
        '<style id="customer-export-col-styles">',
        # make the fallback table shrink to content
        'table[aria-label="Customer Export Preview"] { table-layout: auto; width: auto; display: inline-block; }',
    ]
    for idx, s in COL_STYLE.items():
        css_parts.append(
            f'table[aria-label="Customer Export Preview"] thead th:nth-child({idx}) '
            f'{{ text-align:{s["align"]}; padding:{s["pad_y"]}px {s["pad_x"]}px; font-size:{s["font_head"]}px; white-space:nowrap; }}'
        )
        css_parts.append(
            f'table[aria-label="Customer Export Preview"] tbody td:nth-child({idx}) '
            f'{{ text-align:{s["align"]}; padding:{s["pad_y"]}px {s["pad_x"]}px; font-size:{s["font_body"]}px; white-space:nowrap; }}'
        )
    css_parts.append("</style>")
    st.markdown("".join(css_parts), unsafe_allow_html=True)

# Build the source lines
preview_lines = sorted(
    list(st.session_state.get("export_locked_lines", [])) + _build_live_pack(),
    key=_sort_key,
)

# Nothing to show? Explain and seed a test line option.
if not preview_lines:
    st.caption("No rows to show yet — enter a positive footprint or seed a test line below.")
    if st.button("➕ Seed a test line", use_container_width=True, key="seed_test_line"):
        st.session_state["export_locked_lines"] = st.session_state.get("export_locked_lines", []) + [{
            "_id": f"locked_{uuid.uuid4()}",
            "qty": 100, "unit": "LF",
            "item": "12.5 Gauge Silt Fence",
            "price_each": 2.50,
            "line_total": 250.00
        }]
        st.rerun()
    st.stop()

_import_error = None
try:
    from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode
    HAS_AGGRID = True
except Exception as _exc:
    HAS_AGGRID = False
    _import_error = _exc

# Build rows/df first (so the non-aggrid path can still render)
rows = []
for ln in preview_lines:
    rid = str(ln.get("_id") or f"anon_{uuid.uuid4()}")
    qty = int(_num(ln.get("qty", ln.get("qty_lf", 0)), 0))
    unit = ln.get("unit") or ("LF" if ("qty_lf" in ln) else "")
    item = ln.get("item", "") or ""
    price_each = _num(ln.get("price_each", ln.get("price_per_lf", 0.0)), 0.0)
    if price_each <= 0 and "Removal" in item:
        price_each = float(globals().get("removal_unit_price_lf", 0.0))
    line_total = _num(ln.get("line_total", 0.0), 0.0)
    if line_total <= 0:
        line_total = price_each * qty
    rows.append({
        "_id": rid,
        "Qty": qty,
        "Item": item,
        "Unit": unit,
        "Price Each": float(price_each),
        "Line Total": float(line_total),
        "_delete": False,
    })

import pandas as pd
df = pd.DataFrame(rows)

st.markdown("")
_inject_customer_preview_col_styles()

if not HAS_AGGRID:
    st.warning("`streamlit-aggrid` not installed. Showing a simple table instead." + (f" ({_import_error})" if _import_error else ""))
    # Simple editor without delete button; users can still edit Qty/Price
    df_display = df.drop(columns=["_id", "_delete"], errors="ignore")
    edited = st.data_editor(df_display, hide_index=True, use_container_width=True)
    edited["Line Total"] = (edited["Qty"].astype(float) * edited["Price Each"].astype(float)).round(2)

    subtotal = float(edited["Line Total"].sum())
    remove_tax_flag = bool(st.session_state.get("remove_sales_tax", False))
    tax_rate = float(_tax_rate)
    sales_tax = 0.0 if remove_tax_flag else (subtotal * tax_rate)
    grand_total = subtotal + sales_tax

    st.markdown("---")
    _, r2 = st.columns([3.7, 1.6])
    with r2:
        st.markdown(f"**Subtotal:**  ${subtotal:,.2f}")
        st.markdown(f"**Sales Tax ({(0 if remove_tax_flag else tax_rate*100):.2f}%){' (removed)' if remove_tax_flag else ''}:**  ${sales_tax:,.2f}")
        st.markdown(f"**Grand Total:**  ${grand_total:,.2f}")

    # Build export lines from edited table
    lines_to_export = []
    for _, row in edited.iterrows():
        qty = int(row["Qty"]) if pd.notna(row["Qty"]) else 0
        price_each = float(row["Price Each"]) if pd.notna(row["Price Each"]) else 0.0
        lt = float(row["Line Total"]) if pd.notna(row["Line Total"]) else price_each * qty
        found = next((ln for ln in preview_lines if (ln.get("item")==row["Item"] and ln.get("unit")==row["Unit"])) , None)
        base = {"qty": qty, "unit": row["Unit"], "item": row["Item"], "price_each": price_each, "line_total": lt}
        if found:
            base.update({k: found[k] for k in ("_id","sku_fabric","sku_post","sku_cap","post_spacing_ft") if k in found})
        lines_to_export.append(base)

    c_left, c_right = st.columns([1, 1])
    with c_right:
        if st.button("📄 Export to Summary", type="primary", use_container_width=True, key="btn_export_to_summary_simple"):
            _export_preview_to_summary(lines_to_export, subtotal, sales_tax, grand_total)
    st.stop()

# -------------------- AgGrid: render + inline edit + delete --------------------
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode

# 1) Build the options builder FIRST
gob = GridOptionsBuilder.from_dataframe(df)
gob.configure_default_column(editable=False, resizable=True)

# Hide technical id; show the rest
gob.configure_column("_id", hide=True)

# Qty + Price editable; parse to numbers; format $$$
gob.configure_column(
    "Qty", type=["numericColumn"], editable=True, width=50,
    valueParser=JsCode("function(p){return Number(p.newValue)||0;}")
)
gob.configure_column("Item", editable=False, wrapText=True, autoHeight=True, flex=2, minWidth=200)
gob.configure_column("Unit", editable=False, width=50)
gob.configure_column(
    "Price Each", type=["numericColumn"], editable=True, width=30,
    valueFormatter=JsCode("function(p){return '$'+(Number(p.value||0).toFixed(2));}"),
    valueParser=JsCode("function(p){return Number(p.newValue)||0;}")
)
gob.configure_column(
    "Line Total", type=["numericColumn"], editable=False, width=50,
    valueFormatter=JsCode("function(p){return '$'+(Number(p.value||0).toFixed(2));}")
)

# Simple trash “button”
trash_renderer = JsCode("""
function(params){ return '🗑️'; }
""")
gob.configure_column("_delete", headerName="", width=70, editable=False,
                     cellRenderer=trash_renderer)

# Grid-level options
gob.configure_grid_options(suppressClickEdit=True)

# 2) Build options and add row key + event handlers
grid_options = gob.build()

# Use our stable ids from the dataframe
grid_options["getRowId"] = JsCode("function(p){ return String(p.data._id); }")

# Click on trash toggles _delete true; we delete on server side and rerun
grid_options["onCellClicked"] = JsCode("""
function(e){
  if (e.colDef && e.colDef.field === '_delete') {
    e.node.setDataValue('_delete', true);
  }
}
""")

# Recompute Line Total when Qty/Price change
grid_options["onCellValueChanged"] = JsCode("""
function(e){
  if (e.colDef.field === 'Qty' || e.colDef.field === 'Price Each') {
    var q = Number(e.data['Qty']||0);
    var p = Number(e.data['Price Each']||0);
    e.node.setDataValue('Line Total', q * p);
  }
}
""")
st.markdown("""
<style>
.ag-theme-alpine { display: inline-block; width: auto !important; }
</style>
""", unsafe_allow_html=True)

# ------- Customer Preview Panel (Header + Grid + Totals) -------

# Tight, panel-style CSS
st.markdown("""
<style>
  /* Outer panel look; tight to content */
  .customer-preview-box {
    display: inline-block;
    border: 2.5px solid #60a5fa;
    border-radius: 12px;
    background: #f8fbff;
    padding: 12px 16px;
    box-shadow: 0 4px 14px rgba(96,165,250,.25);
  }
  .customer-preview-header {
    font-weight: 700;
    font-size: 18px;
    color: #1e3a8a;
    margin-bottom: 10px;
    padding: 6px 10px;
    border-radius: 6px;
    background: #e0f2fe;
    border: 1.5px solid #60a5fa;
    display: inline-block;
    white-space: nowrap;
  }

  /* Make AgGrid shrink to fit content */
  .ag-theme-alpine {
    display: inline-block;
    width: auto !important;
  }

  /* Totals table (2 cols x 3 rows) */
  .totals-table table {
    border-collapse: collapse;
    margin-top: 14px;
    margin-left: auto;   /* push to the right inside panel */
    margin-right: 0;
  }
  .totals-table td {
    padding: 6px 14px;
    font-size: 16px;
    white-space: nowrap;
  }
  .totals-table tr:last-child td {
    border-top: 2px solid #2e6d33;
    font-weight: 700;
    font-size: 18px;
  }
  .totals-table td:first-child { text-align: left; }
  .totals-table td:last-child  { text-align: right; min-width: 120px; }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown('<div class="customer-preview-box"><div class="customer-preview-header">📑 Customer Printout Preview</div>', unsafe_allow_html=True)

from st_aggrid import AgGrid, GridOptionsBuilder, JsCode  # + the shim above

grid = AgGrid(
    df,
    gridOptions=grid_options,
    height=370,
    data_return_mode=_enum_or_str(DataReturnMode, "AS_INPUT"),
    update_mode=_enum_or_str(GridUpdateMode, "MODEL_CHANGED"),
    fit_columns_on_grid_load=True,
    allow_unsafe_jscode=True,
    theme="alpine",
)

# Server-side postprocessing after edits
edited = grid["data"].copy()
edited["Line Total"] = (edited["Qty"].astype(float) * edited["Price Each"].astype(float)).round(2)

# Handle instant deletes
to_delete_ids = set(edited.loc[edited["_delete"] == True, "_id"].astype(str).tolist())
if to_delete_ids:
    st.session_state["preview_live_hidden_ids"] = list(
        set(st.session_state.get("preview_live_hidden_ids", [])) |
        {rid for rid in to_delete_ids if rid.startswith("live_")}
    )
    st.session_state["export_locked_lines"] = [
        ln for ln in st.session_state.get("export_locked_lines", [])
        if str(ln.get("_id")) not in to_delete_ids
    ]
    st.rerun()

# Compute totals (visible rows only)
edited_filtered = edited.loc[edited["_delete"] != True].copy()
subtotal = float(edited_filtered["Line Total"].sum())
remove_tax_flag = bool(st.session_state.get("remove_sales_tax", False))
tax_rate = float(_tax_rate)
sales_tax = 0.0 if remove_tax_flag else (subtotal * tax_rate)
grand_total = subtotal + sales_tax

# Totals table inside the same panel
st.markdown(
    f"""
    <div class="totals-table">
      <table>
        <tr><td>Subtotal (excl. tax)</td><td>${subtotal:,.2f}</td></tr>
        <tr><td>Sales Tax ({(0 if remove_tax_flag else tax_rate*100):.2f}%){" (removed)" if remove_tax_flag else ""}</td>
            <td>${sales_tax:,.2f}</td></tr>
        <tr><td><strong>Grand Total</strong></td><td><strong>${grand_total:,.2f}</strong></td></tr>
      </table>
    </div>
    </div>  <!-- close .customer-preview-box -->
    """,
    unsafe_allow_html=True,
)

# Persist inline edits back to locked rows (by id)
locked_map = {str(ln.get("_id")): ln for ln in st.session_state.get("export_locked_lines", [])}
for _, row in edited_filtered.iterrows():
    rid = str(row["_id"])
    if rid in locked_map:
        ln = locked_map[rid]
        ln["qty"] = int(row["Qty"]) if pd.notna(row["Qty"]) else 0
        ln["price_each"] = float(row["Price Each"]) if pd.notna(row["Price Each"]) else 0.0
        ln["line_total"] = float(row["Line Total"]) if pd.notna(row["Line Total"]) else ln["price_each"] * ln["qty"]
st.session_state["export_locked_lines"] = list(locked_map.values())

# Export to Summary (button lives under the panel)
c_left, c_right = st.columns([1, 1])
with c_right:
    if st.button("📄 Export to Summary", type="primary", use_container_width=True, key="btn_export_to_summary_ag"):
        lines_to_export = []
        preview_map = {str(ln.get("_id")): ln for ln in preview_lines}
        for _, row in edited_filtered.iterrows():
            rid = str(row["_id"])
            qty = int(row["Qty"]) if pd.notna(row["Qty"]) else 0
            price_each = float(row["Price Each"]) if pd.notna(row["Price Each"]) else 0.0
            lt = float(row["Line Total"]) if pd.notna(row["Line Total"]) else price_each * qty
            base = {"_id": rid, "qty": qty, "unit": row["Unit"], "item": row["Item"], "price_each": price_each, "line_total": lt}
            found = preview_map.get(rid)
            if found:
                base.update({k: found[k] for k in ("sku_fabric", "sku_post", "sku_cap", "post_spacing_ft") if k in found})
            lines_to_export.append(base)
        _export_preview_to_summary(lines_to_export, subtotal, sales_tax, grand_total)

