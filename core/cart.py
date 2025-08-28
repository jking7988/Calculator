import streamlit as st

CART_KEY = "material_cart"

def _ensure_cart():
    if CART_KEY not in st.session_state:
        st.session_state[CART_KEY] = []
    return st.session_state[CART_KEY]

def add_item(*, sku: str, description: str, unit: str, qty: float,
             source_page: str, notes: str = "",
             alt_qty_label: str = "", alt_qty_value: float | None = None):
    cart = _ensure_cart()
    cart.append({
        "sku": sku,
        "description": description,
        "unit": unit,
        "qty": float(qty),
        "source_page": source_page,
        "notes": notes,
        "alt_qty_label": alt_qty_label,
        "alt_qty_value": float(alt_qty_value) if alt_qty_value is not None else None,
    })

def get_items():
    return list(_ensure_cart())

def clear():
    st.session_state[CART_KEY] = []

def grouped_totals():
    groups: dict[str, dict] = {}
    for item in _ensure_cart():
        sku = item["sku"]
        if sku not in groups:
            groups[sku] = {**item}
        else:
            groups[sku]["qty"] += item.get("qty", 0) or 0
            if item.get("alt_qty_label") and groups[sku].get("alt_qty_label") == item["alt_qty_label"]:
                av = item.get("alt_qty_value")
                if av is not None:
                    groups[sku]["alt_qty_value"] = (groups[sku].get("alt_qty_value") or 0) + av
    return groups
