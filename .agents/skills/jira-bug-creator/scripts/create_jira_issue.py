"""
Enterprise Script to create a Jira issue, upload attachments, and sync to Google Bug Sheet.
Endpoints:
- POST https://jira.girnarsoft.com/rest/api/2/issue
- POST https://jira.girnarsoft.com/rest/api/2/issue/{key}/attachments
Google Sheet: https://docs.google.com/spreadsheets/d/1W06Q7G3ogU5ysQR8b_vhpoREHuRef9FE4ChnYSdVKsI/edit#gid=1449830126
Columns: issue id | description
"""

import argparse
import csv
import json
import os
import sys
import requests
from requests.auth import HTTPBasicAuth
import urllib3

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Disable insecure request warnings for internal certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..", ".."))
DEFAULT_BUG_EXCEL = os.path.join(PROJECT_ROOT, "output", "jira_prod_bugs.xlsx")
DEFAULT_BUG_CSV = os.path.join(PROJECT_ROOT, "output", "jira_prod_bugs.csv")
DEFAULT_BUG_SHEET_URL = "https://docs.google.com/spreadsheets/d/1W06Q7G3ogU5ysQR8b_vhpoREHuRef9FE4ChnYSdVKsI/edit?pli=1&gid=1449830126#gid=1449830126"

SEARCH_CONFIG_PATHS = [
    os.path.join(os.path.expanduser("~"), ".gemini", "antigravity", "jira_credentials.json"),
    os.path.join(os.path.expanduser("~"), ".agents", "jira_credentials.json"),
    os.path.join(os.path.dirname(SCRIPT_DIR), "config.json"),
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
    config = load_config()
    config.update(updates)
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"[WARN] Failed to save config: {e}")


def sync_bug_to_sheets(issue_link, summary, issue_key=None, webhook_url=None):
    import re
    config = load_config()
    webhook_url = webhook_url or config.get("bug_sheet_webhook_url")

    # 1. Determine App: CD, BD, or ZW
    summary_lower = (summary or "").lower()
    if re.search(r'^(bikedekho|bd)\b', summary_lower) or "bike" in summary_lower:
        app_code = "BD"
    elif re.search(r'^(zigwheels|zw)\b', summary_lower) or "zigwheel" in summary_lower:
        app_code = "ZW"
    else:
        app_code = "CD"

    # 2. Server: always Production
    server = "Production"

    # 3. Issue ID: Full Jira URL format (e.g. https://jira.girnarsoft.com/browse/MB2C-1983)
    if not issue_link:
        if issue_key:
            issue_link = f"https://jira.girnarsoft.com/browse/{issue_key}"
        else:
            issue_link = ""
    issue_display = issue_link

    # 4. Description: Short bug description (strip brand prefix)
    short_description = re.sub(r'^(CarDekho|BikeDekho|ZigWheels|CD|BD|ZW)\s*(App)?\s*[-:]+\s*', '', summary or '', flags=re.IGNORECASE).strip()
    if not short_description:
        short_description = summary or ''

    # 1. Update local CSV
    os.makedirs(os.path.dirname(DEFAULT_BUG_CSV), exist_ok=True)
    file_exists = os.path.exists(DEFAULT_BUG_CSV)
    try:
        with open(DEFAULT_BUG_CSV, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists or os.path.getsize(DEFAULT_BUG_CSV) == 0:
                writer.writerow(["App", "Server", "issue id", "Description"])
            writer.writerow([app_code, server, issue_display, short_description])
    except Exception as e:
        print(f"[WARN] Error updating local CSV: {e}")

    # 2. Update local Excel
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment

        if os.path.exists(DEFAULT_BUG_EXCEL):
            wb = openpyxl.load_workbook(DEFAULT_BUG_EXCEL)
            ws = wb.active
        else:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Prod Bugs"
            ws.append(["App", "Server", "issue id", "Description"])
            ws.row_dimensions[1].height = 26
            header_fill = PatternFill(start_color="1A365D", end_color="1A365D", fill_type="solid")
            header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
            for c in range(1, 5):
                cell = ws.cell(row=1, column=c)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center")

        ws.append([app_code, server, issue_display, short_description])
        row_idx = ws.max_row
        ws.row_dimensions[row_idx].height = 20
        ws.cell(row=row_idx, column=1).alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(row=row_idx, column=2).alignment = Alignment(horizontal="center", vertical="center")
        cell_id = ws.cell(row=row_idx, column=3)
        cell_id.font = Font(name="Segoe UI", size=9, color="004B87", underline="single")
        cell_id.hyperlink = issue_link
        cell_id.alignment = Alignment(horizontal="left", vertical="center")
        cell_desc = ws.cell(row=row_idx, column=4)
        cell_desc.font = Font(name="Segoe UI", size=9)
        cell_desc.alignment = Alignment(horizontal="left", vertical="center")

        ws.column_dimensions['A'].width = 12
        ws.column_dimensions['B'].width = 16
        ws.column_dimensions['C'].width = 45
        ws.column_dimensions['D'].width = 80

        wb.save(DEFAULT_BUG_EXCEL)
        wb.close()
        print(f"[SUCCESS] Recorded bug in local tracker (App: {app_code}, Server: {server}, Issue ID: {issue_display}):")
        print(f"  - Excel: {DEFAULT_BUG_EXCEL}")
        print(f"  - CSV:   {DEFAULT_BUG_CSV}")
    except Exception as e:
        print(f"[WARN] Error updating local Excel: {e}")

    # 3. Push to Google Sheet Webhook if configured
    if webhook_url:
        try:
            print(f"[*] Pushing bug to Google Sheet Webhook (App: {app_code}, Server: {server}, ID: {issue_display})...")
            payload = {
                "app": app_code,
                "server": server,
                "issue_id": issue_display,
                "issue_url": issue_link,
                "description": short_description
            }
            r = requests.post(webhook_url, json=payload, timeout=15)
            if r.status_code == 200:
                print(f"[SUCCESS] Real-time Bug Sheet updated via Webhook! ({app_code} | {server} | {issue_key} | {short_description})")
            else:
                print(f"[WARN] Bug Sheet Webhook returned status {r.status_code}: {r.text[:200]}")
        except Exception as e:
            print(f"[WARN] Exception sending to Bug Sheet Webhook: {e}")
    else:
        print(f"[INFO] Bug Sheet Webhook not configured yet. Run with --set-webhook '<URL>' to enable 100% real-time Google Sheet sync.")


def create_issue(jira_url=None, username=None, password=None, project_key=None, summary=None, description=None, issue_type=None, priority=None, assignee=None, labels=None, attachment_path=None):
    config = load_config()

    jira_url = jira_url or config.get("jira_url", "https://jira.girnarsoft.com")
    username = username or config.get("username", "mohit.sharma@girnarsoft.com")
    password = password or config.get("password", "Mohit@2026")
    project_key = project_key or config.get("default_project", "MB2C")
    issue_type = issue_type or config.get("default_issue_type", "Prod Bug")
    assignee = assignee or config.get("default_assignee", "vasim.akram@girnarsoft.com")

    if not username or not password:
        print("Error: Missing Jira username or password.")
        sys.exit(1)

    api_url = f"{jira_url.rstrip('/')}/rest/api/2/issue"
    auth = HTTPBasicAuth(username, password)
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    payload = {
        "fields": {
            "project": {
                "key": project_key
            },
            "summary": summary,
            "description": description,
            "issuetype": {
                "name": issue_type
            }
        }
    }

    if assignee:
        payload["fields"]["assignee"] = {"name": assignee}

    if priority:
        payload["fields"]["priority"] = {"name": priority}

    if labels:
        if isinstance(labels, str):
            label_list = [l.strip().lower() for l in labels.split(",") if l.strip()]
        else:
            label_list = [str(l).strip().lower() for l in labels if str(l).strip()]
        if label_list:
            payload["fields"]["labels"] = label_list

    response = requests.post(api_url, auth=auth, headers=headers, json=payload, verify=False)

    if response.status_code not in (200, 201):
        print(f"Failed to create issue: Status {response.status_code}")
        print(response.text)
        return None, None

    issue_data = response.json()
    issue_key = issue_data.get("key")
    issue_link = f"{jira_url.rstrip('/')}/browse/{issue_key}"
    print(f"[SUCCESS] Key: {issue_key}")
    print(f"[URL] Jira: {issue_link}")

    # Attach file if provided
    if attachment_path and os.path.exists(attachment_path):
        attach_url = f"{jira_url.rstrip('/')}/rest/api/2/issue/{issue_key}/attachments"
        attach_headers = {
            "X-Atlassian-Token": "no-check"
        }
        with open(attachment_path, "rb") as f:
            files = {"file": (os.path.basename(attachment_path), f)}
            att_resp = requests.post(attach_url, auth=auth, headers=attach_headers, files=files, verify=False)
            if att_resp.status_code in (200, 201):
                print("[SUCCESS] Screenshot attached successfully.")
            else:
                print(f"[WARNING] Screenshot upload failed: Status {att_resp.status_code}")
                print(att_resp.text)
    elif attachment_path:
        print(f"[WARNING] Attachment path not found: {attachment_path}")

    # Automatically sync bug to Google Sheet & Local Tracker
    sync_bug_to_sheets(issue_link, summary, issue_key=issue_key)

    return issue_link, issue_key


def main():
    parser = argparse.ArgumentParser(description="Create a Jira issue with optional screenshot attachment and sync to Bug Sheet")
    parser.add_argument("--jira-url", default=None, help="Jira Base URL")
    parser.add_argument("--username", default=None, help="Jira Username / Email")
    parser.add_argument("--password", default=None, help="Jira Password or PAT")
    parser.add_argument("--project", default=None, help="Jira Project Key (default: MB2C)")
    parser.add_argument("--type", default=None, help="Issue Type (default: Prod Bug)")
    parser.add_argument("--assignee", default=None, help="Assignee username / email (default: vasim.akram@girnarsoft.com)")
    parser.add_argument("--summary", default=None, help="Issue Title / Summary")
    parser.add_argument("--description", default=None, help="Issue Description")
    parser.add_argument("--priority", default=None, help="Priority (e.g. P2)")
    parser.add_argument("--labels", default=None, help="Comma-separated labels (e.g. ui-bug,visual,widget)")
    parser.add_argument("--attachment", default=None, help="Path to screenshot / attachment image")
    parser.add_argument("--set-webhook", help="Save Bug Sheet Webhook URL for 100% real-time Google Sheet sync")

    args = parser.parse_args()

    if args.set_webhook:
        save_config({"bug_sheet_webhook_url": args.set_webhook.strip()})
        print(f"[SUCCESS] Saved Bug Sheet Webhook URL: {args.set_webhook.strip()}")
        sys.exit(0)

    if not args.summary or not args.description:
        print("[ERROR] --summary and --description are required to create a bug.")
        sys.exit(1)

    create_issue(
        jira_url=args.jira_url,
        username=args.username,
        password=args.password,
        project_key=args.project,
        issue_type=args.type,
        assignee=args.assignee,
        summary=args.summary,
        description=args.description,
        priority=args.priority,
        labels=args.labels,
        attachment_path=args.attachment
    )


if __name__ == "__main__":
    main()
