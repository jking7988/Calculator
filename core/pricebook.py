# core/pricebook.py
from __future__ import annotations
import io, os, re
import pandas as pd
import streamlit as st
from typing import Optional

# -------------------------
# Locations & defaults
# -------------------------
# Project root (parent of 'core')
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))

# Candidate filenames in the REPO ROOT (no upload required)
ROOT_CANDIDATES = (
    "pricebook.xlsx",
    "pricing.xlsx",
    "pricebook.csv",
)

# Optional bundled fallback inside your repo:
DEFAULT_BUNDLED_PATH = os.path.join(PROJECT_ROOT, "assets", "pricebook.xlsx")
DEFAULT_SHEET_NAME: Optional[str | int] = 13  # or None / "Sheet1" if you prefer

# -------------------------
# Cached readers
# -------------------------
@st.cache_data(show_spinner=False)
def _read_from_bytes(b: bytes, sheet: str | int | None):
    # Try Excel first
    try:
        return pd.read_excel(io.BytesIO(b), sheet_name=sheet, engine="openpyxl")
    except Exception:
        # Fallback to CSV if it isn't an Excel file
        return pd.read_csv(io.BytesIO(b))

@st.cache_data(show_spinner=False)
def _read_excel_path(path: str, sheet: str | int | None):
    return pd.read_excel(path, sheet_name=sheet, engine="openpyxl")

@st.cache_data(show_spinner=False)
def _read_csv_path(path: str):
    # Allow common CSV variations
    return pd.read_csv(path)

def _read_any_path(path: str, sheet: str | int | None):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm", ".xls"):
        return _read_excel_path(path, sheet)
    elif ext == ".csv":
        return _read_csv_path(path)
    else:
        # Try Excel then CSV as a last resort
        try:
            return _read_excel_path(path, sheet)
        except Exception:
            return _read_csv_path(path)

# -------------------------
# Normalization / Validation
# -------------------------
_UNIT_CANON = {
    "EA":"EA","EACH":"EA","UNIT":"EA",
    "LF":"LF","L.F.":"LF","LINEAR FT":"LF","LINEAR FEET":"LF","FT":"LF",
    "SY":"SY","SQ YD":"SY","SQUARE YARD":"SY",
    "SF":"SF","SQ FT":"SF","SQUARE FOOT":"SF",
}
_REQUIRED = ("code","name","unit","price")

def _money_to_float(x) -> float:
    if x is None or (isinstance(x, float) and pd.isna(x)): return float("nan")
    s = str(x).strip()
    if s == "": return float("nan")
    s = re.sub(r"[$,\s]", "", s)
    if re.fullmatch(r"\(\d+(\.\d+)?\)", s):  # (123.45) accounting negative
        s = "-" + s.strip("()")
    try:
        return float(s)
    except Exception:
        return float("nan")

def _canon_unit(u: str) -> str:
    if u is None: return ""
    u = str(u).strip().upper()
    return _UNIT_CANON.get(u, u)

def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    cols = list(df.columns)
    if len(cols) < 4:
        raise ValueError("Pricebook must have at least four columns: code, name, unit, price.")

    # Map first 4 columns to canonical headers (tolerant of messy headers)
    mapping = {cols[0]:"code", cols[1]:"name", cols[2]:"unit", cols[3]:"price"}
    df = df.rename(columns=mapping)

    for c in _REQUIRED:
        if c not in df.columns:
            raise ValueError(f"Missing column '{c}' in pricebook.")

    out = df[list(_REQUIRED)].copy()
    out["code"] = out["code"].astype(str).str.strip()
    out["name"] = out["name"].astype(str).str.strip()
    out["unit"] = out["unit"].map(_canon_unit)
    out["price"] = out["price"].map(_money_to_float)

    # Basic validation
    problems = []
    dups = out["code"][out["code"].duplicated()].unique().tolist()
    if dups:
        problems.append(f"Duplicate code(s): {dups}")
    bad_units = out[~out["unit"].isin(set(_UNIT_CANON.values()))]["unit"].dropna().unique().tolist()
    if bad_units:
        problems.append(f"Unrecognized unit(s): {bad_units} (accepted: {sorted(set(_UNIT_CANON.values()))})")

    out = out[out["code"] != ""].dropna(subset=["price"]).reset_index(drop=True)
    if problems:
        raise ValueError("Pricing validation failed:\n- " + "\n- ".join(problems))

    return out.set_index("code")

# -------------------------
# Public API
# -------------------------
_pricebook_df: pd.DataFrame | None = None

def _find_repo_root_file() -> Optional[str]:
    """Return the first existing candidate path in repo root (or None)."""
    for name in ROOT_CANDIDATES:
        p = os.path.join(PROJECT_ROOT, name)
        if os.path.isfile(p):
            return p
    return None

def ensure_loaded(force: bool = False, sheet: str | int | None = DEFAULT_SHEET_NAME):
    """
    Load pricebook using this precedence:
      1) PRICEBOOK_PATH (env) -> absolute/relative path
      2) repo-root candidate file (pricebook.xlsx/pricing.xlsx/pricebook.csv)
      3) uploaded bytes from session (pricebook_bytes)
      4) bundled fallback at assets/pricebook.xlsx
    """
    global _pricebook_df
    if (not force) and (_pricebook_df is not None):
        return

    # 1) Env override
    env_path = os.environ.get("PRICEBOOK_PATH")
    if env_path:
        path = env_path if os.path.isabs(env_path) else os.path.join(PROJECT_ROOT, env_path)
        if os.path.isfile(path):
            df = _read_any_path(path, sheet)
            _pricebook_df = _normalize(df)
            return
        else:
            st.warning(f"PRICEBOOK_PATH points to a missing file: {path}")

    # 2) Repo-root file
    root_path = _find_repo_root_file()
    if root_path:
        df = _read_any_path(root_path, sheet)
        _pricebook_df = _normalize(df)
        return

    # 3) Uploaded file bytes (legacy path)
    b = st.session_state.get("pricebook_bytes")
    if b:
        df = _read_from_bytes(b, sheet)
        _pricebook_df = _normalize(df)
        return

    # 4) Bundled fallback
    if os.path.isfile(DEFAULT_BUNDLED_PATH):
        df = _read_any_path(DEFAULT_BUNDLED_PATH, sheet)
        _pricebook_df = _normalize(df)
        return

    raise FileNotFoundError(
        "No pricebook found. Add a pricing file at the repo root "
        "(pricebook.xlsx / pricing.xlsx / pricebook.csv), "
        "set PRICEBOOK_PATH, upload a file, or provide assets/pricebook.xlsx."
    )

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
