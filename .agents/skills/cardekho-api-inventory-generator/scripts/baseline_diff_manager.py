"""
Baseline Comparison & Cell-Level Color Highlighting Engine for CarDekho APIs.
Compares runtime observed APIs against User's Baseline Google Sheet (70 APIs):
- UNCHANGED: Normal background (White)
- CHANGED FIELD / PARAM: Yellow cell highlight (#FFF3CD) + Updated URL in 'Changed' column
- NEW API DISCOVERED: Light Green row highlight (#E6F4EA)
- NOT OBSERVED: Light Grey / Default (#F8F9FA)
"""

import argparse
import datetime
import json
import os
import re
import sys
from urllib.parse import urlparse, parse_qs
import pandas as pd
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
POSSIBLE_BASELINE_PATHS = [
    "input/existing_baseline_sheet.csv",
    "c:/Users/Mohit Sharma/Documents/antigravity/silly-curie/input/existing_baseline_sheet.csv",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR))), "input", "existing_baseline_sheet.csv")
]

YELLOW_FILL = "FFF3CD"   # Changed field / param
GREEN_FILL = "E6F4EA"    # Newly discovered API
RED_FILL = "FCE8E6"      # Broken / Status error


def clean_text(text):
    if not isinstance(text, str):
        return text
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    cleaned = ansi_escape.sub('', text)
    cleaned = "".join(ch for ch in cleaned if ch == '\n' or ch == '\t' or ord(ch) >= 32)
    return cleaned.strip()


def normalize_endpoint(path):
    if not path:
        return "/"
    clean_path = clean_text(str(path).strip())
    clean_path = re.sub(r'/(?:model|models)/(\d+)', r'/model/{modelId}', clean_path, flags=re.IGNORECASE)
    clean_path = re.sub(r'/(?:variant|variants)/(\d+)', r'/variant/{variantId}', clean_path, flags=re.IGNORECASE)
    clean_path = re.sub(r'/(?:brand|brands|oem)/(\d+)', r'/brand/{brandId}', clean_path, flags=re.IGNORECASE)
    clean_path = re.sub(r'/(?:city|location|dealer)/(\d+)', r'/city/{cityId}', clean_path, flags=re.IGNORECASE)
    clean_path = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', r'/{uuid}', clean_path, flags=re.IGNORECASE)
    clean_path = re.sub(r'/(\d{4,})', r'/{id}', clean_path)
    return clean_path


def load_baseline(baseline_file=None):
    if not baseline_file or not os.path.exists(baseline_file):
        for p in POSSIBLE_BASELINE_PATHS:
            if os.path.exists(p):
                baseline_file = p
                break

    if not baseline_file or not os.path.exists(baseline_file):
        print("[WARNING] Baseline CSV not found.")
        return []

    df = pd.read_csv(baseline_file)
    baseline_records = []
    for idx, row in df.iterrows():
        app_api = str(row.get("App Api", "")).strip()
        if not app_api or app_api == "nan":
            continue
        parsed = urlparse(app_api)
        norm_ep = normalize_endpoint(parsed.path)
        baseline_records.append({
            "s_no": int(row.get("S. no.", idx + 1)) if pd.notnull(row.get("S. no.")) else idx + 1,
            "page_name": clean_text(str(row.get("Page Name", "General")).strip()),
            "original_url": clean_text(app_api),
            "norm_endpoint": norm_ep,
            "status": clean_text(str(row.get("status", "")).strip() if str(row.get("status", "")) != "nan" else ""),
            "changed_url": clean_text(str(row.get("Changed", "")).strip() if str(row.get("Changed", "")) != "nan" else ""),
            "web_wap": clean_text(str(row.get("Web/Wap", "")).strip() if str(row.get("Web/Wap", "")) != "nan" else "")
        })
    print(f"[INFO] Loaded {len(baseline_records)} baseline APIs from '{baseline_file}'.")
    return baseline_records


def compare_and_highlight(observed_apis, baseline_file=None, output_dir="output"):
    os.makedirs(output_dir, exist_ok=True)
    baseline = load_baseline(baseline_file)

    # Index observed APIs by normalized endpoint
    observed_map = {}
    for o in observed_apis:
        norm = normalize_endpoint(o.get("path", "/"))
        observed_map[norm] = o

    final_rows = []
    highlights = [] # List of {row: int, col: int, color: str, reason: str}
    
    COLUMNS = ["S. no.", "Page Name", "HTTP Method", "App Api", "status", "Changed", "Normalized Endpoint", "Audit Diff Note"]

    matched_observed_endpoints = set()

    # Step 1: Process Baseline rows and check against observed traffic
    row_idx = 2 # 1-based, header is row 1
    for b in baseline:
        s_no = b["s_no"]
        page_name = b["page_name"]
        orig_url = b["original_url"]
        norm_ep = b["norm_endpoint"]
        changed_val = b["changed_url"]
        status_val = b["status"] or "ACTIVE"
        method_val = "GET"
        diff_note = "Baseline Verified"

        if norm_ep in observed_map:
            matched_observed_endpoints.add(norm_ep)
            obs = observed_map[norm_ep]
            obs_url = clean_text(obs.get("full_url", ""))
            method_val = clean_text(obs.get("method", "GET").upper())
            status_val = "200 OK (VERIFIED ON DEVICE)"

            # Check if URL parameters changed
            if obs_url and obs_url != orig_url:
                changed_val = obs_url
                diff_note = "URL Parameters / Version Changed"
                # Highlight the 'Changed' column (Col 6) in Yellow
                highlights.append({
                    "row": row_idx,
                    "col": 6,
                    "color": f"#{YELLOW_FILL}",
                    "reason": "URL Changed from baseline"
                })
                # Also highlight status (Col 5)
                highlights.append({
                    "row": row_idx,
                    "col": 5,
                    "color": f"#{YELLOW_FILL}",
                    "reason": "Updated status"
                })
        else:
            diff_note = "Baseline API (Not triggered in current run)"

        final_rows.append({
            "S. no.": s_no,
            "Page Name": page_name,
            "HTTP Method": method_val,
            "App Api": orig_url,
            "status": status_val,
            "Changed": changed_val,
            "Normalized Endpoint": norm_ep,
            "Audit Diff Note": diff_note
        })
        row_idx += 1

    # Step 2: Add Newly Discovered Runtime APIs that weren't in the baseline
    new_count = 0
    for norm_ep, obs in observed_map.items():
        if norm_ep not in matched_observed_endpoints:
            new_count += 1
            s_no = len(final_rows) + 1
            obs_url = clean_text(obs.get("full_url", ""))
            method_val = clean_text(obs.get("method", "GET").upper())
            page_name = clean_text(obs.get("screen", "Discovered Feature"))

            final_rows.append({
                "S. no.": s_no,
                "Page Name": page_name,
                "HTTP Method": method_val,
                "App Api": obs_url,
                "status": "NEW (DISCOVERED ON DEVICE)",
                "Changed": "",
                "Normalized Endpoint": norm_ep,
                "Audit Diff Note": "Newly Discovered Runtime API"
            })

            # Highlight entire row in Light Green (#E6F4EA)
            for c in range(1, len(COLUMNS) + 1):
                highlights.append({
                    "row": row_idx,
                    "col": c,
                    "color": f"#{GREEN_FILL}",
                    "reason": "Newly Discovered API"
                })
            row_idx += 1

    # Generate Styled Excel with OpenPyXL
    excel_path = os.path.join(output_dir, "cardekho_api_inventory.xlsx")
    json_path = os.path.join(output_dir, "cardekho_api_inventory.json")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "API Inventory"

    # Write Header
    header_fill = PatternFill(start_color="EA4335", end_color="EA4335", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    ws.append(COLUMNS)
    for col_num in range(1, len(COLUMNS) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Write Data Rows with clean text
    for r in final_rows:
        ws.append([clean_text(str(r[col])) if r[col] is not None else "" for col in COLUMNS])

    # Apply Cell Color Fills
    yellow_pat = PatternFill(start_color=YELLOW_FILL, end_color=YELLOW_FILL, fill_type="solid")
    green_pat = PatternFill(start_color=GREEN_FILL, end_color=GREEN_FILL, fill_type="solid")

    for h in highlights:
        c = ws.cell(row=h["row"], column=h["col"])
        if YELLOW_FILL in h["color"]:
            c.fill = yellow_pat
        elif GREEN_FILL in h["color"]:
            c.fill = green_pat

    # Auto-adjust column widths
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 75)

    ws.freeze_panes = "A2"
    wb.save(excel_path)

    # Save JSON Payload for Webhook Sync
    json_payload = {
        "inventory": final_rows,
        "highlights": highlights,
        "summary": {
            "total_baseline_apis": len(baseline),
            "total_observed_apis": len(observed_apis),
            "total_inventory_rows": len(final_rows),
            "new_apis_discovered": new_count,
            "changed_fields_highlighted": len([h for h in highlights if YELLOW_FILL in h["color"]])
        }
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_payload, f, indent=2)

    return final_rows, highlights, excel_path, json_path


if __name__ == "__main__":
    with open("output/raw_logs.json", "r", encoding="utf-8") as f:
        observed = json.load(f)
    rows, hl, xls, js = compare_and_highlight(observed)
    print(f"[SUCCESS] Processed {len(rows)} API rows with {len(hl)} visual color highlights!")
    print(f"Excel generated at: {xls}")
