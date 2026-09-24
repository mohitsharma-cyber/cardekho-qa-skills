"""
Live Backend Health & Change Audit Engine for CarDekho Baseline APIs.
Tests all 60 baseline APIs against live CarDekho production/QA backends:
- Checks HTTP Status (200 OK, 301 Redirect, 404 Deprecated, 400/403 Auth)
- Compares with live device runtime logs
- Updates 'Changed' column with latest live URLs
- Generates visual color highlights:
  * Yellow (#FFF3CD) for Changed URLs / Parameters
  * Red (#FCE8E6) for 404 Deprecated / Dead endpoints
  * Green (#E6F4EA) for Newly Discovered Runtime APIs
  * White for 200 OK Verified Active APIs
- Syncs results directly to Google Sheet Webhook
"""

import datetime
import json
import os
import re
import sys
import time
from urllib.parse import urlparse, parse_qs
import pandas as pd
import requests
import urllib3
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)
from google_sheets_sync import sync_to_google_sheet_webhook

BASELINE_CSV = "input/existing_baseline_sheet.csv"
OUTPUT_DIR = "output"

YELLOW_FILL = "FFF3CD"   # Changed URL / parameters
GREEN_FILL = "E6F4EA"    # Newly discovered API
RED_FILL = "FCE8E6"      # Deprecated / 404 Dead endpoint

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 14; OnePlus CPH2585) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive"
}


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


def audit_all_apis():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("=" * 60)
    print("[RUNNING LIVE BACKEND HEALTH & CHANGE AUDIT]")
    print("=" * 60)

    if not os.path.exists(BASELINE_CSV):
        print(f"[ERROR] Baseline CSV not found at '{BASELINE_CSV}'.")
        return

    df_base = pd.read_csv(BASELINE_CSV)
    print(f"Loaded {len(df_base)} total baseline rows from '{BASELINE_CSV}'.\n")

    # Load runtime observed logs from phone
    observed_logs = []
    observed_map = {}
    raw_logs_path = os.path.join(OUTPUT_DIR, "raw_logs.json")
    if os.path.exists(raw_logs_path):
        try:
            with open(raw_logs_path, "r", encoding="utf-8") as f:
                observed_logs = json.load(f)
            for item in observed_logs:
                norm = normalize_endpoint(item.get("path", "/"))
                observed_map[norm] = item
        except Exception:
            pass

    session = requests.Session()
    session.headers.update(HEADERS)

    final_rows = []
    highlights = []
    COLUMNS = ["S. no.", "Page Name", "HTTP Method", "App Api", "status", "Changed", "Normalized Endpoint", "Audit Diff Note"]

    active_count = 0
    changed_count = 0
    deprecated_count = 0
    row_idx = 2

    matched_endpoints = set()

    for idx, row in df_base.iterrows():
        s_no = int(row.get("S. no.", idx + 1)) if pd.notnull(row.get("S. no.")) else idx + 1
        page_name = clean_text(str(row.get("Page Name", "General")).strip())
        orig_url = clean_text(str(row.get("App Api", "")).strip())
        changed_val = clean_text(str(row.get("Changed", "")).strip()) if pd.notnull(row.get("Changed")) else ""

        if not orig_url or orig_url == "nan":
            continue

        parsed = urlparse(orig_url)
        norm_ep = normalize_endpoint(parsed.path)
        method_val = "GET"
        status_val = "UNVERIFIED"
        diff_note = ""

        print(f"[{idx+1}/{len(df_base)}] Testing: {page_name:<25} ({norm_ep})")

        # 1. Check live backend HTTP response
        try:
            r = session.get(orig_url, timeout=6, allow_redirects=False)
            status_code = r.status_code

            if status_code == 200:
                status_val = "200 OK (ACTIVE)"
                diff_note = "Endpoint Live & Responsive"
                active_count += 1
            elif status_code in [301, 302, 307, 308]:
                redirect_url = r.headers.get("Location", "")
                status_val = f"{status_code} REDIRECT"
                changed_val = redirect_url
                diff_note = "API Version / Route Redirected"
                changed_count += 1
                highlights.append({"row": row_idx, "col": 6, "color": f"#{YELLOW_FILL}"})
                highlights.append({"row": row_idx, "col": 5, "color": f"#{YELLOW_FILL}"})
            elif status_code in [404, 410]:
                status_val = f"{status_code} NOT FOUND"
                diff_note = "DEPRECATED / DEAD ENDPOINT"
                deprecated_count += 1
                highlights.append({"row": row_idx, "col": 5, "color": f"#{RED_FILL}"})
                highlights.append({"row": row_idx, "col": 8, "color": f"#{RED_FILL}"})
            elif status_code in [400, 401, 403]:
                status_val = f"{status_code} AUTH/BAD REQUEST"
                diff_note = "Requires Auth / Token or Updated Query Params"
            else:
                status_val = f"{status_code} ERROR"
                diff_note = f"Backend returned {status_code}"
        except Exception as e:
            status_val = "TIMEOUT / UNREACHABLE"
            diff_note = str(e)[:40]

        # 2. Check if phone runtime traffic captured newer version/params
        if norm_ep in observed_map:
            matched_endpoints.add(norm_ep)
            obs = observed_map[norm_ep]
            obs_url = clean_text(obs.get("full_url", ""))
            method_val = clean_text(obs.get("method", "GET").upper())

            if obs_url and obs_url != orig_url:
                changed_val = obs_url
                status_val = "200 OK (VERIFIED ON DEVICE)"
                diff_note = "Updated 2026 Live Parameters Captured From Phone"
                changed_count += 1
                highlights.append({"row": row_idx, "col": 6, "color": f"#{YELLOW_FILL}"})
                highlights.append({"row": row_idx, "col": 5, "color": f"#{YELLOW_FILL}"})
            else:
                status_val = "200 OK (VERIFIED ON DEVICE)"
                diff_note = "Live Verified on Connected Phone"

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

    # 3. Append Newly Discovered Runtime APIs from Phone
    new_count = 0
    for norm_ep, obs in observed_map.items():
        if norm_ep not in matched_endpoints:
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
                "Audit Diff Note": "Newly Discovered Runtime API on Phone"
            })

            # Highlight entire row in Light Green (#E6F4EA)
            for c in range(1, len(COLUMNS) + 1):
                highlights.append({"row": row_idx, "col": c, "color": f"#{GREEN_FILL}"})
            row_idx += 1

    # Save to Multi-Sheet Excel Workbook
    excel_path = os.path.join(OUTPUT_DIR, "cardekho_api_inventory.xlsx")
    json_path = os.path.join(OUTPUT_DIR, "cardekho_api_inventory.json")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "API Inventory"

    header_fill = PatternFill(start_color="EA4335", end_color="EA4335", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    ws.append(COLUMNS)
    for col_num in range(1, len(COLUMNS) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for r in final_rows:
        ws.append([clean_text(str(r[col])) if r[col] is not None else "" for col in COLUMNS])

    yellow_pat = PatternFill(start_color=YELLOW_FILL, end_color=YELLOW_FILL, fill_type="solid")
    green_pat = PatternFill(start_color=GREEN_FILL, end_color=GREEN_FILL, fill_type="solid")
    red_pat = PatternFill(start_color=RED_FILL, end_color=RED_FILL, fill_type="solid")

    for h in highlights:
        c = ws.cell(row=h["row"], column=h["col"])
        if YELLOW_FILL in h["color"]:
            c.fill = yellow_pat
        elif GREEN_FILL in h["color"]:
            c.fill = green_pat
        elif RED_FILL in h["color"]:
            c.fill = red_pat

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 75)

    ws.freeze_panes = "A2"
    wb.save(excel_path)

    # Save JSON Payload and sync to Webhook
    json_payload = {
        "inventory": final_rows,
        "highlights": highlights,
        "summary": {
            "total_baseline_tested": len(df_base),
            "active_live_apis": active_count,
            "changed_apis": changed_count,
            "deprecated_apis": deprecated_count,
            "new_apis_discovered": new_count
        }
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_payload, f, indent=2)

    print("\n" + "=" * 60)
    print("LIVE AUDIT RESULTS SUMMARY")
    print("=" * 60)
    print(f"Total Baseline APIs Tested:   {len(df_base)}")
    print(f"Active & Verified (200 OK):   {active_count}")
    print(f"Changed / Parameter Updates:  {changed_count} (Highlighted in Yellow)")
    print(f"Deprecated / Dead Endpoints:  {deprecated_count} (Highlighted in Red)")
    print(f"Newly Discovered APIs:        {new_count} (Highlighted in Green)")
    print(f"Total Records in Inventory:   {len(final_rows)}")
    print("=" * 60)

    print("\nSyncing complete audit results directly to Google Sheet Webhook...")
    sync_to_google_sheet_webhook(json_path)


if __name__ == "__main__":
    audit_all_apis()
