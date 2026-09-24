"""
Script to fetch details for multiple Jira issues from Jira Server / Data Center.
Endpoint: https://jira.girnarsoft.com/rest/api/2/issue/{key}
"""

import argparse
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

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SEARCH_CONFIG_PATHS = [
    os.path.join(os.path.expanduser("~"), ".gemini", "antigravity", "jira_credentials.json"),
    os.path.join(os.path.expanduser("~"), ".agents", "jira_credentials.json"),
    os.path.join(os.path.dirname(SCRIPT_DIR), "config.json"),
    os.path.join(os.path.dirname(os.path.dirname(SCRIPT_DIR)), "jira-bug-creator", "config.json")
]


def load_config():
    for cfg_path in SEARCH_CONFIG_PATHS:
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}


def fetch_ticket_details(jira_keys, jira_url=None, username=None, password=None):
    config = load_config()
    jira_url = jira_url or config.get("jira_url", "https://jira.girnarsoft.com")
    username = username or config.get("username", "mohit.sharma@girnarsoft.com")
    password = password or config.get("password", "Mohit@2026")

    auth = HTTPBasicAuth(username, password) if username and password else None
    headers = {"Accept": "application/json"}

    results = []
    for key in jira_keys:
        key = key.strip().upper()
        if not key:
            continue
        api_url = f"{jira_url.rstrip('/')}/rest/api/2/issue/{key}"
        ticket_info = {
            "key": key,
            "url": f"{jira_url.rstrip('/')}/browse/{key}",
            "summary": "Summary not found",
            "status": "Unknown",
            "issue_type": "Unknown",
            "assignee": "Unassigned",
            "labels": []
        }

        if auth:
            try:
                r = requests.get(api_url, auth=auth, headers=headers, verify=False, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    fields = data.get("fields", {})
                    ticket_info["summary"] = fields.get("summary", "Summary not available")
                    status_obj = fields.get("status")
                    ticket_info["status"] = status_obj.get("name", "Unknown") if status_obj else "Unknown"
                    type_obj = fields.get("issuetype")
                    ticket_info["issue_type"] = type_obj.get("name", "Unknown") if type_obj else "Unknown"
                    assignee_obj = fields.get("assignee")
                    ticket_info["assignee"] = assignee_obj.get("displayName", "Unassigned") if assignee_obj else "Unassigned"
                    ticket_info["labels"] = fields.get("labels", [])
                    priority_obj = fields.get("priority")
                    ticket_info["priority"] = priority_obj.get("name", "Unknown") if priority_obj else "Unknown"
                else:
                    ticket_info["summary"] = f"Failed to fetch ({r.status_code})"
            except Exception as e:
                ticket_info["summary"] = f"Error fetching ticket ({str(e)})"
        
        results.append(ticket_info)

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch details of multiple Jira tickets for release sign-off")
    parser.add_argument("keys", nargs="+", help="Jira ticket keys (e.g. MB2C-1946 MB2C-1947)")
    parser.add_argument("--json", action="store_true", help="Output as raw JSON")

    args = parser.parse_args()
    tickets = fetch_ticket_details(args.keys)

    if args.json:
        print(json.dumps(tickets, indent=2))
    else:
        print("\n=== JIRA TICKETS TRACEABILITY ===")
        for i, t in enumerate(tickets, 1):
            print(f"{i}. {t['summary']}")
            print(f"   {t['url']}")
            print(f"   [Type: {t['issue_type']} | Status: {t['status']} | Assignee: {t['assignee']}]\n")
