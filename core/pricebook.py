

# core/pricebook.py
from __future__ import annotations
import os
from datetime import datetime
from typing import Optional
import pandas as pd
import streamlit as st

# ---- Config ----
EXCEL_PATH  = r"Z:\Double Oak Erosion\BIDS\DOE BID Template w Calcs.xlsx"
SHEET_NAME  = "pricebook"
REQUIRED_COLS = {"sku", "price", "unit"}  # keep what you actually use

# ---- State ----
_DATA: Optional[pd.DataFrame] = None
_LAST_LOADED_AT: Optional[datetime] = None
_LAST_ERROR: Optional[str] = None

@st.cache_data(show_spinner=False)
def _read_pricebook(path: str, sheet: str) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name=sheet, engine="openpyxl")

def _load(force: bool = False) -> None:
    global _DATA, _LAST_LOADED_AT, _LAST_ERROR

    if not force and _DATA is not None:
        return

    try:
        df = _read_pricebook(EXCEL_PATH, SHEET_NAME)
        missing = REQUIRED_COLS.difference(df.columns.str.lower())
        if missing:
            raise ValueError(f"Missing columns in sheet '{SHEET_NAME}': {', '.join(sorted(missing))}")

        # normalize columns to lowercase for safety
        df.columns = [c.lower() for c in df.columns]

        _DATA = df
        _LAST_LOADED_AT = datetime.now()
        _LAST_ERROR = None
    except Exception as ex:
        _DATA = None
        _LAST_ERROR = str(ex)
        _LAST_LOADED_AT = None
        raise  # let caller show st.error

def ensure_loaded(force: bool = False) -> None:
    _load(force=force)

def reload() -> None:
    # clear cache and force re-read
    try:
        _read_pricebook.clear()  # type: ignore[attr-defined]
    except Exception:
        pass
    _load(force=True)

def get_last_loaded_at(fmt: Optional[str] = "%m/%d/%Y %I:%M %p") -> Optional[str]:
    if _LAST_LOADED_AT is None:
        return None
    return _LAST_LOADED_AT.strftime(fmt) if fmt else _LAST_LOADED_AT  # type: ignore[return-value]

def get_last_error() -> Optional[str]:
    return _LAST_ERROR

def get_price(sku: str, unit: str, default: float | None = None) -> float:
    ensure_loaded()
    if _DATA is None:
        if default is None:
            raise RuntimeError("Pricebook not loaded.")
        return float(default)

    rows = _DATA[_DATA["sku"].str.strip().str.casefold() == sku.strip().casefold()]
    if "unit" in _DATA.columns:
        rows = rows[rows["unit"].str.strip().str.casefold() == unit.strip().casefold()]
    if rows.empty:
        if default is None:
            raise KeyError(f"SKU '{sku}' with unit '{unit}' not found.")
        return float(default)
    return float(rows.iloc[0]["price"])
