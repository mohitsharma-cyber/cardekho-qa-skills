"""
Enterprise Jira Pod Comment & Task Tracker for CarDekho & BikeDekho.
Syncs with Google Sheet: https://docs.google.com/spreadsheets/d/1PuV4A8jCO5wMW7-Aih27688UA6aooP1z7v9gK7K2nvM/edit?usp=sharing

Features:
- Comments on Jira issues via Jira REST API
- Intelligent POD classification:
  - DB2C -> CarDekho
  - BDCV -> BikeDekho Web
  - MB2C (CarDekho) -> CD App  <Android & iOS>
  - MB2C (BikeDekho) -> BD App    <Android & iOS>
- Reads live Google Sheet to preserve existing entries
- Writes to local Excel (.xlsx) & CSV trackers
- Generates 1-click Google Apps Script (`output/sync_google_sheet.js`)
- Supports instant real-time sync via Apps Script Webhook URL
"""

import argparse
import csv
import io
import json
import os
import re
import sys
from datetime import datetime
import requests
from requests.auth import HTTPBasicAuth
import urllib3

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..", ".."))

DEFAULT_EXCEL_PATH = os.path.join(PROJECT_ROOT, "output", "jira_pod_tracker.xlsx")
DEFAULT_CSV_PATH = os.path.join(PROJECT_ROOT, "output", "jira_pod_tracker.csv")
DEFAULT_DETAILS_CSV_PATH = os.path.join(PROJECT_ROOT, "output", "jira_pod_tracker_details.csv")
DEFAULT_APPS_SCRIPT_PATH = os.path.join(PROJECT_ROOT, "output", "sync_google_sheet.js")

DEFAULT_GOOGLE_SHEET_ID = "1PuV4A8jCO5wMW7-Aih27688UA6aooP1z7v9gK7K2nvM"
DEFAULT_GOOGLE_SHEET_URL = f"https://docs.google.com/spreadsheets/d/{DEFAULT_GOOGLE_SHEET_ID}/edit?usp=sharing"

# Target Columns matching user's exact Google Sheet structure
SHEET_COLUMNS = [
    "CarDekho",
    "BikeDekho Web",
    "ZigWheels",
    "CD App  <Android & iOS>",
    "BD App    <Android & iOS>",
    "ZW App  <Android & iOS>"
]

SEARCH_CONFIG_PATHS = [
    os.path.join(os.path.expanduser("~"), ".gemini", "antigravity", "jira_credentials.json"),
    os.path.join(os.path.expanduser("~"), ".agents", "jira_credentials.json"),
    os.path.join(PROJECT_ROOT, ".agents", "skills", "jira-pod-comment-tracker", "config.json"),
    os.path.join(SCRIPT_DIR, "config.json"),
]


def load_config():
    for p in SEARCH_CONFIG_PATHS:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}


def save_config(updates):
    target = SEARCH_CONFIG_PATHS[0]
    data = load_config()
    data.update(updates)
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[WARN] Failed to save config: {e}")


def get_jira_client():
    config = load_config()
    jira_url = config.get("jira_url", "https://jira.girnarsoft.com").rstrip("/")
    username = config.get("username", "mohit.sharma@girnarsoft.com")
    password = config.get("password", "Mohit@2026")
    webhook_url = config.get("google_sheet_webhook_url", "")
    auth = HTTPBasicAuth(username, password) if username and password else None
    return jira_url, auth, username, webhook_url


def fetch_issue(key, jira_url, auth):
    url = f"{jira_url}/rest/api/2/issue/{key.upper()}"
    headers = {"Accept": "application/json"}
    try:
        r = requests.get(url, auth=auth, headers=headers, verify=False, timeout=15)
        if r.status_code == 200:
            return r.json()
        else:
            print(f"[WARN] Failed to fetch issue {key}: Status {r.status_code}")
            return None
    except Exception as e:
        print(f"[ERROR] Error fetching issue {key}: {e}")
        return None


def post_comment(key, comment_body, jira_url, auth):
    url = f"{jira_url}/rest/api/2/issue/{key.upper()}/comment"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {"body": comment_body}
    try:
        r = requests.post(url, auth=auth, headers=headers, json=payload, verify=False, timeout=15)
        if r.status_code in (200, 201):
            return True, r.json().get("id")
        else:
            print(f"[ERROR] Failed to post comment on {key}: Status {r.status_code} - {r.text[:200]}")
            return False, None
    except Exception as e:
        print(f"[ERROR] Exception posting comment to {key}: {e}")
        return False, None


def classify_pod(project_key, summary="", description="", labels=None, components=None, explicit_pod=None):
    if explicit_pod:
        # Flexible match explicit pod
        for col in SHEET_COLUMNS:
            if explicit_pod.lower() in col.lower():
                return col

    project_key = (project_key or "").upper()
    summary_lower = (summary or "").lower()
    description_lower = (description or "").lower()
    labels = [str(l).lower() for l in (labels or [])]
    components = [str(c).lower() for c in (components or [])]
    combined_text = f"{summary_lower} {' '.join(labels)} {' '.join(components)} {description_lower}"

    if project_key == "DB2C":
        return "CarDekho"
    elif project_key == "BDCV":
        return "BikeDekho Web"
    elif project_key == "MB2C":
        bd_patterns = [
            r"\bbd\s+app\b", r"\bbd-app\b", r"\bbd\s*-\s*", r"\bbd\b",
            r"\bbikedekho\b", r"\bbike\b", r"\bbikes\b", r"\bscooter\b",
            r"\btwo\s*wheeler\b", r"\bbd\s+android\b", r"\bbd\s+ios\b",
            r"\bbd\s*release\b"
        ]
        cd_patterns = [
            r"\bcd\s+app\b", r"\bcd-app\b", r"\bcd\s*-\s*", r"\bcd\b",
            r"\bcardekho\b", r"\bcar\b", r"\bcars\b", r"\bsuv\b",
            r"\bsedan\b", r"\bcd\s+android\b", r"\bcd\s+ios\b",
            r"\bcd\s*release\b"
        ]

        bd_score = sum(len(re.findall(p, combined_text)) for p in bd_patterns)
        cd_score = sum(len(re.findall(p, combined_text)) for p in cd_patterns)

        if re.search(r"^(bd|bikedekho)\b", summary_lower) or "bikedekho app" in summary_lower or "bd app" in summary_lower:
            return "BD App    <Android & iOS>"
        if re.search(r"^(cd|cardekho)\b", summary_lower) or "cardekho app" in summary_lower or "cd app" in summary_lower:
            return "CD App  <Android & iOS>"

        if bd_score > cd_score:
            return "BD App    <Android & iOS>"
        elif cd_score > bd_score:
            return "CD App  <Android & iOS>"
        else:
            return "CD App  <Android & iOS>"

    # Check Zigwheels
    if "zigwheels" in combined_text or "zw" in combined_text:
        return "ZigWheels"

    if "bikedekho" in combined_text or "bdcv" in combined_text:
        return "BikeDekho Web"
    if "cardekho" in combined_text or "db2c" in combined_text:
        return "CarDekho"

    return "CarDekho"


def fetch_live_google_sheet(sheet_id=DEFAULT_GOOGLE_SHEET_ID):
    """Fetches the latest live data from Google Sheet export URL."""
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    board_data = {col: [] for col in SHEET_COLUMNS}
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            reader = csv.reader(io.StringIO(r.text))
            rows = list(reader)
            if rows:
                header_row = rows[0]
                col_mapping = {}
                for idx, h in enumerate(header_row):
                    h_clean = h.strip()
                    # Match with our standard SHEET_COLUMNS
                    for target_col in SHEET_COLUMNS:
                        if target_col.lower() == h_clean.lower() or target_col.split()[0].lower() == h_clean.split()[0].lower():
                            col_mapping[idx] = target_col
                            break
                for row in rows[1:]:
                    for idx, target_col in col_mapping.items():
                        if idx < len(row):
                            val = row[idx].strip()
                            if val and val not in board_data[target_col]:
                                board_data[target_col].append(val)
                print(f"[INFO] Synced {sum(len(v) for v in board_data.values())} existing entries from live Google Sheet.")
        else:
            print(f"[WARN] Could not fetch live Google Sheet (Status: {r.status_code})")
    except Exception as e:
        print(f"[WARN] Exception fetching live Google Sheet: {e}")

    return board_data


def read_existing_tracker_data(excel_path, sheet_id=DEFAULT_GOOGLE_SHEET_ID):
    jira_url, _, _, _ = get_jira_client()
    # First get live Google Sheet data
    board_data = fetch_live_google_sheet(sheet_id)
    details_data = []

    # Then merge any local Excel entries
    if os.path.exists(excel_path):
        try:
            from openpyxl import load_workbook
            wb = load_workbook(excel_path, data_only=True)
            if "POD Board" in wb.sheetnames:
                ws = wb["POD Board"]
                header_map = {}
                for col_idx in range(1, ws.max_column + 1):
                    val = ws.cell(row=1, column=col_idx).value
                    for target_col in SHEET_COLUMNS:
                        if val and target_col.lower() in str(val).lower():
                            header_map[col_idx] = target_col
                            break

                for row_idx in range(2, ws.max_row + 1):
                    for col_idx, col_name in header_map.items():
                        val = ws.cell(row=row_idx, column=col_idx).value
                        if val and str(val).strip():
                            val_str = str(val).strip()
                            if not val_str.startswith("http") and re.match(r"^[A-Z0-9]+-\d+$", val_str):
                                val_str = f"{jira_url}/browse/{val_str}"
                            # Check if key already in column
                            key_match = re.search(r"([A-Z0-9]+-\d+)", val_str)
                            k = key_match.group(1) if key_match else val_str
                            if not any(k in v for v in board_data[col_name]):
                                board_data[col_name].append(val_str)

            if "Task Details & Comments" in wb.sheetnames:
                ws_details = wb["Task Details & Comments"]
                for r in range(2, ws_details.max_row + 1):
                    row_vals = [ws_details.cell(row=r, column=c).value for c in range(1, ws_details.max_column + 1)]
                    if any(row_vals):
                        details_data.append(row_vals)

            wb.close()
        except Exception as e:
            print(f"[WARN] Error reading local tracker: {e}")

    return board_data, details_data


def generate_google_apps_script(board_data, output_path=DEFAULT_APPS_SCRIPT_PATH):
    """Generates an Apps Script runner file to update Google Sheet directly or via Webhook."""
    jira_url, _, _, _ = get_jira_client()
    max_rows = max([len(board_data[c]) for c in SHEET_COLUMNS] or [0])
    rows = []
    for r in range(max_rows):
        row = []
        for c in SHEET_COLUMNS:
            val = board_data[c][r] if r < len(board_data[c]) else ""
            if val and not val.startswith("http") and re.match(r"^[A-Z0-9]+-\d+$", val):
                val = f"{jira_url}/browse/{val}"
            row.append(val)
        rows.append(row)

    js_rows = json.dumps(rows, ensure_ascii=False)
    js_headers = json.dumps(SHEET_COLUMNS, ensure_ascii=False)

    script_content = f"""/**
 * Google Apps Script for Jira POD Column Tracker
 * Sheet URL: {DEFAULT_GOOGLE_SHEET_URL}
 * 
 * Instructions:
 * 1. Open Google Sheet: Extensions > Apps Script
 * 2. Paste this entire code and click 'Save'.
 * 3. Run 'updateJiraPodBoard()' to update the sheet directly with 1-click!
 * 4. (Optional) For 100% Real-Time Automated Sync from Terminal:
 *    - Click 'Deploy' > 'New deployment'
 *    - Select type: 'Web app'
 *    - Execute as: 'Me'
 *    - Who has access: 'Anyone'
 *    - Click 'Deploy' and copy the Web App URL.
 *    - Run in terminal: python .agents/skills/jira-pod-comment-tracker/scripts/comment_and_track.py --set-webhook "<WEB_APP_URL>"
 */

function updateJiraPodBoard() {{
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getActiveSheet();
  
  var headers = {js_headers};
  var rows = {js_rows};
  
  // Set headers on row 1 if empty
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  
  // Header Styling
  sheet.getRange(1, 1, 1, headers.length)
       .setBackground('#1A365D')
       .setFontColor('#FFFFFF')
       .setFontWeight('bold')
       .setHorizontalAlignment('center');
  
  // Clear previous data rows
  if (sheet.getLastRow() > 1) {{
    sheet.getRange(2, 1, Math.max(sheet.getLastRow() - 1, 1), headers.length).clearContent();
  }}
  
  // Write updated rows
  if (rows.length > 0) {{
    sheet.getRange(2, 1, rows.length, headers.length).setValues(rows);
    sheet.getRange(2, 1, rows.length, headers.length)
         .setHorizontalAlignment('left')
         .setFontColor('#004B87');
  }}
  
  SpreadsheetApp.flush();
  Logger.log("Successfully updated Jira POD Board! Total rows: " + rows.length);
}}

function doGet(e) {{
  return ContentService.createTextOutput(JSON.stringify({{
    status: "active",
    message: "Jira POD Webhook is running and ready to receive POST updates!",
    sheet_url: "https://docs.google.com/spreadsheets/d/1PuV4A8jCO5wMW7-Aih27688UA6aooP1z7v9gK7K2nvM/edit?usp=sharing"
  }})).setMimeType(ContentService.MimeType.JSON);
}}

function doPost(e) {{
  try {{
    var contents = JSON.parse(e.postData.contents);
    var headers = contents.headers || {js_headers};
    var rows = contents.rows || [];
    
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getActiveSheet();
    
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    
    if (sheet.getLastRow() > 1) {{
      sheet.getRange(2, 1, sheet.getLastRow() - 1, headers.length).clearContent();
    }}
    
    if (rows.length > 0) {{
      sheet.getRange(2, 1, rows.length, headers.length).setValues(rows);
    }}
    
    return ContentService.createTextOutput(JSON.stringify({{
      status: "success",
      rows_updated: rows.length
    }})).setMimeType(ContentService.MimeType.JSON);
  }} catch (err) {{
    return ContentService.createTextOutput(JSON.stringify({{
      status: "error",
      message: err.toString()
    }})).setMimeType(ContentService.MimeType.JSON);
  }}
}}
"""
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(script_content)
        print(f"[INFO] Generated Google Apps Script sync file: {output_path}")
    except Exception as e:
        print(f"[WARN] Failed to write Google Apps Script: {e}")


def push_to_google_sheet_webhook(webhook_url, board_data):
    """Pushes data directly to Google Sheet via deployed Apps Script Webhook."""
    if not webhook_url:
        return False
    max_rows = max([len(board_data[c]) for c in SHEET_COLUMNS] or [0])
    rows = []
    for r in range(max_rows):
        row = [board_data[c][r] if r < len(board_data[c]) else "" for c in SHEET_COLUMNS]
        rows.append(row)

    payload = {
        "headers": SHEET_COLUMNS,
        "rows": rows
    }
    try:
        print(f"[*] Pushing updates to Google Sheet Webhook...")
        r = requests.post(webhook_url, json=payload, timeout=15)
        if r.status_code == 200:
            print("[SUCCESS] Real-time Google Sheet updated successfully via Webhook!")
            return True
        else:
            print(f"[WARN] Webhook update returned status {r.status_code}: {r.text[:200]}")
            return False
    except Exception as e:
        print(f"[WARN] Error calling Webhook: {e}")
        return False


def save_tracker_data(board_data, details_data, excel_path, csv_path, details_csv_path, jira_url, webhook_url=None):
    os.makedirs(os.path.dirname(os.path.abspath(excel_path)), exist_ok=True)

    # 1. Update CSV POD Board
    try:
        max_rows = max([len(board_data[c]) for c in SHEET_COLUMNS] or [0])
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(SHEET_COLUMNS)
            for i in range(max_rows):
                row = [board_data[c][i] if i < len(board_data[c]) else "" for c in SHEET_COLUMNS]
                writer.writerow(row)
    except Exception as e:
        print(f"[WARN] Error saving CSV board: {e}")

    # 2. Update Details CSV
    try:
        detail_headers = [
            "Timestamp", "Jira ID", "POD Column", "Project",
            "Issue Type", "Status", "Summary", "Comment Posted",
            "Author", "Jira URL"
        ]
        with open(details_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(detail_headers)
            for row in details_data:
                writer.writerow(row)
    except Exception as e:
        print(f"[WARN] Error saving details CSV: {e}")

    # 3. Update Excel Workbook
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        wb = openpyxl.Workbook()
        ws_board = wb.active
        ws_board.title = "POD Board"

        font_header = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
        font_data = Font(name="Segoe UI", size=9, color="004B87", bold=False, underline="single")
        font_normal = Font(name="Segoe UI", size=9)

        pod_colors = {
            "CarDekho": "E35A27",
            "BikeDekho Web": "2B5C8F",
            "ZigWheels": "D92525",
            "CD App  <Android & iOS>": "FF7A00",
            "BD App    <Android & iOS>": "0088CC",
            "ZW App  <Android & iOS>": "C0392B"
        }

        thin_border = Border(
            left=Side(style='thin', color='D3D3D3'),
            right=Side(style='thin', color='D3D3D3'),
            top=Side(style='thin', color='D3D3D3'),
            bottom=Side(style='thin', color='D3D3D3')
        )

        for col_idx, col_name in enumerate(SHEET_COLUMNS, 1):
            cell = ws_board.cell(row=1, column=col_idx, value=col_name)
            cell.font = font_header
            cell.fill = PatternFill(start_color=pod_colors.get(col_name, "1A365D"), end_color=pod_colors.get(col_name, "1A365D"), fill_type="solid")
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = thin_border
            ws_board.row_dimensions[1].height = 28

        max_rows = max([len(board_data[c]) for c in SHEET_COLUMNS] or [0])
        for r_idx in range(max_rows):
            row_num = r_idx + 2
            ws_board.row_dimensions[row_num].height = 20
            for col_idx, col_name in enumerate(SHEET_COLUMNS, 1):
                val = board_data[col_name][r_idx] if r_idx < len(board_data[col_name]) else ""
                cell = ws_board.cell(row=row_num, column=col_idx)
                if val:
                    cell.value = val
                    if val.startswith("http"):
                        cell.hyperlink = val
                    cell.font = font_data
                else:
                    cell.value = ""
                    cell.font = font_normal
                cell.alignment = Alignment(horizontal="left", vertical="center")
                cell.border = thin_border
                if r_idx % 2 == 1:
                    cell.fill = PatternFill(start_color="F8F9FA", end_color="F8F9FA", fill_type="solid")

        for col_idx in range(1, len(SHEET_COLUMNS) + 1):
            col_letter = get_column_letter(col_idx)
            ws_board.column_dimensions[col_letter].width = 38

        # Sheet 2: Details
        ws_details = wb.create_sheet(title="Task Details & Comments")
        detail_headers = [
            "Timestamp", "Jira ID", "POD Column", "Project",
            "Issue Type", "Status", "Summary", "Comment Posted",
            "Author", "Jira URL"
        ]
        ws_details.row_dimensions[1].height = 26
        header_fill = PatternFill(start_color="1A365D", end_color="1A365D", fill_type="solid")

        for col_idx, h in enumerate(detail_headers, 1):
            cell = ws_details.cell(row=1, column=col_idx, value=h)
            cell.font = font_header
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = thin_border

        for r_idx, row in enumerate(details_data, 2):
            ws_details.row_dimensions[r_idx].height = 20
            for col_idx, val in enumerate(row, 1):
                cell = ws_details.cell(row=r_idx, column=col_idx, value=val)
                cell.font = font_normal
                cell.border = thin_border
                if col_idx in (1, 2, 3, 4, 5, 9):
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="center")
                if col_idx == 2 and val:
                    cell.hyperlink = f"{jira_url}/browse/{val}"
                    cell.font = font_data
                if (r_idx - 2) % 2 == 1:
                    cell.fill = PatternFill(start_color="F7FAFC", end_color="F7FAFC", fill_type="solid")

        for col_idx, h in enumerate(detail_headers, 1):
            col_letter = get_column_letter(col_idx)
            max_len = len(str(h))
            for row in details_data:
                if col_idx - 1 < len(row) and row[col_idx - 1]:
                    max_len = max(max_len, len(str(row[col_idx - 1])[:50]))
            ws_details.column_dimensions[col_letter].width = max(max_len + 4, 14)

        wb.save(excel_path)
        wb.close()
    except Exception as e:
        print(f"[ERROR] Error saving Excel workbook: {e}")

    # 4. Generate Google Apps Script file
    generate_google_apps_script(board_data)

    # 5. Push via Webhook if configured
    if webhook_url:
        push_to_google_sheet_webhook(webhook_url, board_data)


def format_markdown_board(board_data):
    display_headers = ["CarDekho", "BikeDekho Web", "ZigWheels", "CD App", "BD App", "ZW App"]
    lines = []
    lines.append("| " + " | ".join(display_headers) + " |")
    lines.append("| " + " | ".join([":---"] * len(display_headers)) + " |")
    max_rows = max([len(board_data[c]) for c in SHEET_COLUMNS] or [0])
    if max_rows == 0:
        lines.append("| " + " | ".join(["*(Empty)*"] * len(display_headers)) + " |")
    else:
        for i in range(max_rows):
            row = []
            for c in SHEET_COLUMNS:
                val = board_data[c][i] if i < len(board_data[c]) else ""
                if val:
                    # Extract key for clean display
                    match = re.search(r"([A-Z0-9]+-\d+)", val)
                    key = match.group(1) if match else val
                    row.append(f"[{key}]({val})" if val.startswith("http") else key)
                else:
                    row.append("")
            lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def process_ticket(key, comment=None, explicit_pod=None, excel_path=DEFAULT_EXCEL_PATH, csv_path=DEFAULT_CSV_PATH, details_csv_path=DEFAULT_DETAILS_CSV_PATH, sheet_id=DEFAULT_GOOGLE_SHEET_ID):
    key = key.strip().upper()
    jira_url, auth, username, webhook_url = get_jira_client()
    jira_link = f"{jira_url}/browse/{key}"

    print(f"[*] Processing Jira Task: {key}")

    # 1. Post Comment if provided
    comment_status = "Skipped (No comment provided)"
    if comment and comment.strip():
        print(f"[*] Posting comment to {key}...")
        success, comment_id = post_comment(key, comment.strip(), jira_url, auth)
        if success:
            comment_status = f"Success (ID: {comment_id})"
            print(f"[SUCCESS] Comment posted to {key}!")
        else:
            comment_status = "Failed to post comment"

    # 2. Fetch ticket details
    print(f"[*] Fetching ticket details for {key}...")
    issue_data = fetch_issue(key, jira_url, auth)

    project_key = ""
    summary = ""
    description = ""
    labels = []
    components = []
    status_name = "Unknown"
    issue_type = "Task"

    if issue_data:
        fields = issue_data.get("fields", {})
        project_key = fields.get("project", {}).get("key", key.split("-")[0])
        summary = fields.get("summary", "")
        description = fields.get("description", "") or ""
        labels = fields.get("labels", [])
        components = [c.get("name", "") for c in fields.get("components", [])]
        status_name = fields.get("status", {}).get("name", "Unknown")
        issue_type = fields.get("issuetype", {}).get("name", "Task")
    else:
        project_key = key.split("-")[0]
        summary = "N/A (Ticket details fetch failed)"

    # 3. Classify POD column
    pod_column = classify_pod(project_key, summary, description, labels, components, explicit_pod)
    print(f"[+] Identified POD Column: {pod_column} (Project: {project_key})")

    # 4. Read existing tracker data (merges live Google Sheet)
    board_data, details_data = read_existing_tracker_data(excel_path, sheet_id)

    # 5. Check if entry or key already exists
    exists = False
    for existing_val in board_data[pod_column]:
        if key in existing_val:
            exists = True
            break

    if not exists:
        board_data[pod_column].append(jira_link)
        print(f"[+] Added {jira_link} to '{pod_column}' column.")
    else:
        print(f"[i] {key} already exists in '{pod_column}' column.")

    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    details_data.append([
        timestamp_str,
        key,
        pod_column,
        project_key,
        issue_type,
        status_name,
        summary,
        comment.strip() if comment else "",
        username,
        jira_link
    ])

    # 6. Save Tracker & Sync
    save_tracker_data(board_data, details_data, excel_path, csv_path, details_csv_path, jira_url, webhook_url)
    print(f"[SUCCESS] Trackers updated successfully!")
    print(f"  - Google Sheet: {DEFAULT_GOOGLE_SHEET_URL}")
    print(f"  - Local Excel:  {excel_path}")
    print(f"  - Local CSV:    {csv_path}")

    return {
        "key": key,
        "pod": pod_column,
        "project": project_key,
        "summary": summary,
        "status": status_name,
        "comment_status": comment_status,
        "comment": comment,
        "jira_url": jira_link,
        "board": board_data
    }


def main():
    parser = argparse.ArgumentParser(description="Comment on Jira task and save ID to relative POD column in Google Sheet & Excel")
    parser.add_argument("--key", "-k", help="Jira Issue Key")
    parser.add_argument("--comment", "-c", help="Comment text to post on Jira issue")
    parser.add_argument("--pod", "-p", help="Explicit POD column override")
    parser.add_argument("--keys", nargs="+", help="Multiple Jira keys to track at once")
    parser.add_argument("--sheet-id", default=DEFAULT_GOOGLE_SHEET_ID, help="Google Sheet ID")
    parser.add_argument("--sheet-url", help="Google Sheet URL")
    parser.add_argument("--set-webhook", help="Save Google Apps Script Webhook URL for automatic live sync")
    parser.add_argument("--excel-path", default=DEFAULT_EXCEL_PATH, help="Path to Excel tracker")
    parser.add_argument("--csv-path", default=DEFAULT_CSV_PATH, help="Path to CSV board")
    parser.add_argument("--view", action="store_true", help="Print current POD Board")

    args = parser.parse_args()

    if args.set_webhook:
        save_config({"google_sheet_webhook_url": args.set_webhook.strip()})
        print(f"[SUCCESS] Saved Google Sheet Webhook URL: {args.set_webhook.strip()}")
        return

    sheet_id = args.sheet_id
    if args.sheet_url:
        match = re.search(r"/d/([a-zA-Z0-9-_]+)", args.sheet_url)
        if match:
            sheet_id = match.group(1)

    if args.view:
        board_data, _ = read_existing_tracker_data(args.excel_path, sheet_id)
        print("\n### Current Jira POD Tracker Board:\n")
        print(format_markdown_board(board_data))
        return

    keys_to_process = []
    if args.key:
        keys_to_process.append(args.key)
    if args.keys:
        keys_to_process.extend(args.keys)

    if not keys_to_process:
        print("[ERROR] Please specify at least one Jira key using --key <KEY> or --keys <KEY1> <KEY2>")
        sys.exit(1)

    results = []
    for k in keys_to_process:
        res = process_ticket(
            key=k,
            comment=args.comment,
            explicit_pod=args.pod,
            excel_path=args.excel_path,
            csv_path=args.csv_path,
            details_csv_path=DEFAULT_DETAILS_CSV_PATH,
            sheet_id=sheet_id
        )
        results.append(res)

    print("\n" + "="*50)
    print("SUMMARY OF PROCESSED TASKS")
    print("="*50)
    for r in results:
        print(f"- Task: {r['key']} | POD: {r['pod']} | Comment: {r['comment_status']}")
        print(f"  Summary: {r['summary']}")
        print(f"  URL: {r['jira_url']}\n")

    if results:
        print("### Current POD Board:\n")
        print(format_markdown_board(results[-1]["board"]))


if __name__ == "__main__":
    main()
