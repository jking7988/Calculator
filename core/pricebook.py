# core/pricebook.py
from __future__ import annotations
import io, os
import pandas as pd
import streamlit as st

# Optional bundled fallback inside your repo:
DEFAULT_BUNDLED_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "pricebook.xlsx")
DEFAULT_SHEET_NAME = None  # set to "Sheet1" if you want to force a sheet

# ---- cached readers ----
@st.cache_data(show_spinner=False)
def _read_from_bytes(b: bytes, sheet: str | None):
    return pd.read_excel(io.BytesIO(b), sheet_name=sheet, engine="openpyxl")

@st.cache_data(show_spinner=False)
def _read_from_path(path: str, sheet: str | None):
    return pd.read_excel(path, sheet_name=sheet, engine="openpyxl")

_pricebook_df: pd.DataFrame | None = None

def ensure_loaded(force: bool = False, sheet: str | None = DEFAULT_SHEET_NAME):
    """Load pricebook from (1) uploaded bytes or (2) bundled fallback."""
    global _pricebook_df
    if (not force) and (_pricebook_df is not None):
        return

    # 1) uploaded file from sidebar
    b = st.session_state.get("pricebook_bytes")
    if b:
        df = _read_from_bytes(b, sheet)
    # 2) bundled fallback
    elif os.path.isfile(DEFAULT_BUNDLED_PATH):
        df = _read_from_path(DEFAULT_BUNDLED_PATH, sheet)
    else:
        raise FileNotFoundError(
            "No pricebook found. Upload a pricing Excel in the sidebar, "
            "or add a bundled default at assets/pricebook.xlsx"
        )

    _pricebook_df = _normalize(df)

def get_table() -> pd.DataFrame:
    if _pricebook_df is None:
        ensure_loaded()
    return _pricebook_df

def get_item(code: str) -> dict | None:
    df = get_table()
    return df.loc[code].to_dict() if code in df.index else None

def get_price(code: str, default: float | None = None) -> float | None:
    item = get_item(code)
    return float(item["price"]) if item and pd.notna(item["price"]) else default

# ---- normalize helper ----
_UNIT_CANON = {
    "EA":"EA","EACH":"EA","UNIT":"EA",
    "LF":"LF","L.F.":"LF","LINEAR FT":"LF","LINEAR FEET":"LF","FT":"LF",
    "SY":"SY","SQ YD":"SY","SQUARE YARD":"SY",
    "SF":"SF","SQ FT":"SF","SQUARE FOOT":"SF",
}

def _money_to_float(x) -> float:
    import re
    if x is None or (isinstance(x, float) and pd.isna(x)): return float("nan")
    s = str(x).strip()
    if s == "": return float("nan")
    s = re.sub(r"[$,\s]", "", s)
    if re.fullmatch(r"\(\d+(\.\d+)?\)", s): s = "-" + s.strip("()")
    try: return float(s)
    except: return float("nan")

def _canon_unit(u: str) -> str:
    if u is None: return ""
    u = str(u).strip().upper()
    return _UNIT_CANON.get(u, u)

def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    cols = list(df.columns)
    if len(cols) < 4:
        raise ValueError("Pricebook must have at least four columns: code, name, unit, price.")
    df = df.rename(columns={cols[0]:"code", cols[1]:"name", cols[2]:"unit", cols[3]:"price"})
    for c in ("code","name","unit","price"):
        if c not in df.columns:
            raise ValueError(f"Missing column '{c}' in pricebook.")
    out = df[["code","name","unit","price"]].copy()
    out["code"] = out["code"].astype(str).str.strip()
    out["name"] = out["name"].astype(str).str.strip()
    out["unit"] = out["unit"].map(_canon_unit)
    out["price"] = out["price"].map(_money_to_float)
    out = out[out["code"] != ""].dropna(subset=["price"]).reset_index(drop=True)
    return out.set_index("code")
