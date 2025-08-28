#!/usr/bin/env python3
"""
apply_export_preview_and_inputs.py

What this codemod does (per Streamlit page under pages/):
  1) Ensures the three sidebar inputs use canonical session_state keys:
       - "Project Title:"    -> key="project_name"
       - "Customer Name:"    -> key="company_name"
       - "Address:"          -> key="project_address"
     (So values persist when switching pages.)

  2) Adds an "Export Preview" panel ABOVE the "Quantities & Specs" section
     (skips if already present).

  3) If the page is missing the entire "Project / Customer" sidebar card,
     it injects a complete card (using your styling) after apply_sidebar_shell()
     or, if not found, near the top after theme setup.

  4) Ensures the Excel-like styles function `inject_excel_styles()` exists,
     and that it is called once (before any Excel panels). If not found,
     it injects both the function and a single call.

Safety:
  - Dry-run by default (no file writes). Use --write to apply changes.
  - Backs up each modified file with .bak-YYYYMMDD-HHMMSS.

Usage:
  python apply_export_preview_and_inputs.py /path/to/project           # dry run
  python apply_export_preview_and_inputs.py /path/to/project --write   # write
"""

import argparse, re, time, shutil
from pathlib import Path

# ---------- Regex setup ----------
HAS_ST = re.compile(r'^\s*import\s+streamlit\s+as\s+st\s*$', re.MULTILINE)

TEXT_INPUT_BLOCK = re.compile(
    r'st\.text_input\(\s*("Project Title:"|\'Project Title:\')\s*,[\s\S]*?\)',
    re.MULTILINE
)
TEXT_INPUT_BLOCK_COMPANY = re.compile(
    r'st\.text_input\(\s*("Customer Name:"|\'Customer Name:\')\s*,[\s\S]*?\)',
    re.MULTILINE
)
TEXT_INPUT_BLOCK_ADDR = re.compile(
    r'st\.text_input\(\s*("Address:"|\'Address:\')\s*,[\s\S]*?\)',
    re.MULTILINE
)

EXPORT_PREVIEW_TITLE = re.compile(r'Export Preview', re.IGNORECASE)
QUANT_SPECS_HEADER = re.compile(r'^\s*#\s*---\s*Quantities\s*&\s*Specs', re.IGNORECASE | re.MULTILINE)

PROJECT_CARD_PRESENT = re.compile(r'with\s+sidebar_card\(\s*["\']Project\s*/\s*Customer["\']', re.IGNORECASE)

# Good insertion anchors for the Project/Customer card
AFTER_SIDEBAR_SHELL = re.compile(r'apply_sidebar_shell\(\)\s*', re.MULTILINE)
AFTER_THEME = re.compile(r'fix_select_colors\([\s\S]*?\)\s*', re.MULTILINE)

# Excel style detection
HAS_INJECT_STYLES_FUNC = re.compile(r'^\s*def\s+inject_excel_styles\s*\(', re.MULTILINE)
HAS_STYLES_CALL = re.compile(r'\binject_excel_styles\s*\(\s*ui_dark\s*\)', re.MULTILINE)

# Where to skip
SKIP_FILENAMES = {"99_Material_Summary.py"}

# ---------- Snippets ----------
CANON_PROJECT = '''
st.text_input(
    "Project Title:",
    key="project_name",
    value=st.session_state.get("project_name", ""),
    placeholder="e.g., Lakeside Retail – Phase 2",
)'''.strip()

CANON_COMPANY = '''
st.text_input(
    "Customer Name:",
    key="company_name",
    value=st.session_state.get("company_name", ""),
    placeholder="e.g., ACME Builders",
)'''.strip()

CANON_ADDRESS = '''
st.text_input(
    "Address:",
    key="project_address",
    value=st.session_state.get("project_address", ""),
    placeholder="e.g., 1234 Main St, Austin, TX",
)'''.strip()

EXPORT_PREVIEW_BLOCK = r'''
# spacer
st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

# --- Export Preview (ABOVE Quantities & Specs) ---------------------------
with st.container():
    if fencing_category == "Silt Fence":
        _fabric_lbl = f"Silt Fence – {gauge_option}"
        _post_lbl = "T-Posts"
    else:
        _fabric_lbl = f"Plastic Orange Fence – {orange_duty}"
        _post_lbl = "6' T-Posts"

    _items = [
        {
            "item": _fabric_lbl,
            "unit": "LF",
            "qty": f"{required_ft:,}",
            "notes": f"Spacing: {post_spacing_ft} ft; Category: {fencing_category}",
        },
        {
            "item": _post_lbl,
            "unit": "EA",
            "qty": f"{posts_count:,}",
            "notes": f"Spacing: {post_spacing_ft} ft",
        },
    ]
    if fencing_category == "Silt Fence" and (caps_qty or 0) > 0:
        _cap_lbl = "Safety Caps (OSHA)" if (caps_label or "").startswith("OSHA") else "Safety Caps (Plastic)"
        _items.append({
            "item": _cap_lbl,
            "unit": "EA",
            "qty": f"{caps_qty:,}",
            "notes": "Applied to T-Posts",
        })

    rows_html = "\n".join(
        f"<tr><td>{e(it['item'])}</td><td style='text-align:center'>{it['unit']}</td>"
        f"<td style='text-align:right'>{it['qty']}</td><td>{e(it['notes'])}</td></tr>"
        for it in _items
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
'''.lstrip('\n')

PROJECT_CARD_BLOCK = r'''
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
'''.lstrip('\n')

INJECT_EXCEL_STYLES_FUNC = r'''
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
'''.lstrip('\n')

# ---------- Helpers ----------
def ensure_streamlit_import(src: str) -> tuple[str, bool]:
    if HAS_ST.search(src):
        return src, False
    return 'import streamlit as st\n' + src, True

def normalize_inputs(src: str) -> tuple[str, bool]:
    changed = False
    def repl_project(_):
        nonlocal changed; changed = True; return CANON_PROJECT
    def repl_company(_):
        nonlocal changed; changed = True; return CANON_COMPANY
    def repl_addr(_):
        nonlocal changed; changed = True; return CANON_ADDRESS
    new = TEXT_INPUT_BLOCK.sub(repl_project, src)
    new = TEXT_INPUT_BLOCK_COMPANY.sub(repl_company, new)
    new = TEXT_INPUT_BLOCK_ADDR.sub(repl_addr, new)
    return new, changed

def insert_export_preview(src: str) -> tuple[str, bool]:
    if EXPORT_PREVIEW_TITLE.search(src):
        return src, False
    m = QUANT_SPECS_HEADER.search(src)
    if not m:
        return src, False
    insert_at = m.start()
    new = src[:insert_at] + EXPORT_PREVIEW_BLOCK + src[insert_at:]
    return new, True

def ensure_project_card(src: str) -> tuple[str, bool]:
    if PROJECT_CARD_PRESENT.search(src):
        return src, False
    # Prefer to insert right after apply_sidebar_shell()
    m = AFTER_SIDEBAR_SHELL.search(src)
    if m:
        insert_at = m.end()
        new = src[:insert_at] + "\n\n" + PROJECT_CARD_BLOCK + src[insert_at:]
        return new, True
    # Fallback: after theme fix_select_colors(...)
    m = AFTER_THEME.search(src)
    if m:
        insert_at = m.end()
        new = src[:insert_at] + "\n\n" + PROJECT_CARD_BLOCK + src[insert_at:]
        return new, True
    # As a last resort, put it near the top (after first blank line)
    first_break = src.find("\n\n")
    insert_at = first_break if first_break != -1 else 0
    new = src[:insert_at] + "\n\n" + PROJECT_CARD_BLOCK + src[insert_at:]
    return new, True

def ensure_excel_styles(src: str) -> tuple[str, bool]:
    """Ensure the inject_excel_styles function exists and is called with ui_dark."""
    changed = False
    new = src
    if not HAS_INJECT_STYLES_FUNC.search(new):
        # Inject the function near the top (after imports)
        first_break = new.find("\n\n")
        insert_at = first_break if first_break != -1 else 0
        new = new[:insert_at] + "\n\n" + INJECT_EXCEL_STYLES_FUNC + new[insert_at:]
        changed = True
    if not HAS_STYLES_CALL.search(new):
        # Add a single call before the first Quantities & Specs or near the top
        m = QUANT_SPECS_HEADER.search(new)
        insert_at = m.start() if m else (new.find("\n\n") if new.find("\n\n") != -1 else 0)
        call_snippet = '\n# Inject styles once\ninject_excel_styles(ui_dark)\n\n'
        new = new[:insert_at] + call_snippet + new[insert_at:]
        changed = True
    return new, changed

def process_file(fp: Path, write: bool) -> bool:
    try:
        src = fp.read_text(encoding='utf-8')
    except Exception:
        return False

    changed_any = False
    new, ch = ensure_streamlit_import(src); changed_any |= ch
    new, ch = normalize_inputs(new);       changed_any |= ch
    new, ch = ensure_project_card(new);    changed_any |= ch
    new, ch = ensure_excel_styles(new);    changed_any |= ch
    new, ch = insert_export_preview(new);  changed_any |= ch

    if changed_any and write:
        ts = time.strftime('%Y%m%d-%H%M%S')
        bak = fp.with_suffix(fp.suffix + f'.bak-' + ts)
        shutil.copy2(fp, bak)
        fp.write_text(new, encoding='utf-8')
    return changed_any

def main():
    import sys
    ap = argparse.ArgumentParser()
    ap.add_argument('root', type=Path, help='Project root (folder containing pages/)')
    ap.add_argument('--write', action='store_true', help='Apply changes (else dry-run)')
    args = ap.parse_args()

    root = args.root.resolve()
    pages_dir = root / 'pages'
    if not pages_dir.exists():
        print("No 'pages/' directory found under:", root)
        sys.exit(2)

    touched = 0
    for fp in sorted(pages_dir.rglob('*.py')):
        if fp.name in SKIP_FILENAMES:
            continue
        changed = process_file(fp, args.write)
        if changed:
            print("Modified:", fp)
            touched += 1

    if touched == 0:
        print("No changes needed (nothing matched).")
    else:
        print(f"Files with changes: {touched}")
        if not args.write:
            print("Dry run complete. Re-run with --write to apply.")

if __name__ == '__main__':
    main()
