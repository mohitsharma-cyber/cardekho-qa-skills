"""
Enterprise Script to fetch release details from a Parent/Release Jira ticket
or a list of tickets, extracting linked issues, build links, and comments.
"""

import argparse
import json
import os
import re
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


def extract_jira_keys_and_urls(text):
    if not text:
        return [], []
    # Match Jira keys like MB2C-1234, CD-123, etc.
    jira_keys = re.findall(r'\b[A-Z][A-Z0-9]+-\d+\b', text)
    # Match URLs (Firebase, App Distribution, APK/IPA, Jira)
    urls = re.findall(r'https?://[^\s<>"\']+', text)
    build_urls = [u for u in urls if any(k in u.lower() for k in ["firebase", "appdistribution", "testflight", "drive.google", "bitrise", "jenkins", ".apk", ".aab", ".ipa", "diawi"])]
    return list(set(jira_keys)), build_urls


def fetch_release_ticket_data(release_key, jira_url=None, username=None, password=None):
    config = load_config()
    jira_url = jira_url or config.get("jira_url", "https://jira.girnarsoft.com")
    username = username or config.get("username", "mohit.sharma@girnarsoft.com")
    password = password or config.get("password", "Mohit@2026")

    auth = HTTPBasicAuth(username, password) if username and password else None
    headers = {"Accept": "application/json"}

    release_key = release_key.strip().upper()
    api_url = f"{jira_url.rstrip('/')}/rest/api/2/issue/{release_key}?expand=names,renderedFields,comments"

    print(f"Fetching Release Ticket '{release_key}' from Jira...")
    r = requests.get(api_url, auth=auth, headers=headers, verify=False, timeout=15)
    if r.status_code != 200:
        print(f"Error fetching release ticket {release_key}: Status {r.status_code}")
        return None

    data = r.json()
    fields = data.get("fields", {})

    release_summary = fields.get("summary", "")
    release_desc = fields.get("description", "") or ""
    issue_type = fields.get("issuetype", {}).get("name", "") if fields.get("issuetype") else ""
    status = fields.get("status", {}).get("name", "") if fields.get("status") else ""

    # Collect linked issues
    linked_keys = []
    # 1. Check issuelinks
    for link in fields.get("issuelinks", []):
        if "outwardIssue" in link:
            linked_keys.append(link["outwardIssue"]["key"])
        if "inwardIssue" in link:
            linked_keys.append(link["inwardIssue"]["key"])

    # 2. Check subtasks
    for st in fields.get("subtasks", []):
        linked_keys.append(st["key"])

    # 3. Check text in description & comments
    all_comments = []
    comment_data = fields.get("comment", {}).get("comments", []) if fields.get("comment") else []
    for c in comment_data:
        c_body = c.get("body", "")
        all_comments.append(c_body)

    combined_text = release_desc + "\n" + "\n".join(all_comments)
    extracted_keys, extracted_build_urls = extract_jira_keys_and_urls(combined_text)

    # Combine all keys excluding the release ticket itself
    all_child_keys = list(set([k for k in (linked_keys + extracted_keys) if k != release_key]))

    print(f"Found {len(all_child_keys)} linked/mentioned ticket(s): {', '.join(all_child_keys)}")
    if extracted_build_urls:
        print(f"Found Build URL(s): {extracted_build_urls[0]}")

    # Fetch details for each child ticket
    child_tickets = []
    for ckey in sorted(all_child_keys):
        capi_url = f"{jira_url.rstrip('/')}/rest/api/2/issue/{ckey}"
        cr = requests.get(capi_url, auth=auth, headers=headers, verify=False, timeout=10)
        if cr.status_code == 200:
            cdata = cr.json()
            cfields = cdata.get("fields", {})
            assignee_obj = cfields.get("assignee")
            assignee_name = assignee_obj.get("displayName", "Unassigned") if assignee_obj else "Unassigned"
            status_obj = cfields.get("status")
            status_name = status_obj.get("name", "Unknown") if status_obj else "Unknown"
            type_obj = cfields.get("issuetype")
            type_name = type_obj.get("name", "Unknown") if type_obj else "Unknown"

            child_tickets.append({
                "key": ckey,
                "url": f"{jira_url.rstrip('/')}/browse/{ckey}",
                "summary": cfields.get("summary", "No summary"),
                "status": status_name,
                "type": type_name,
                "assignee": assignee_name
            })
        else:
            child_tickets.append({
                "key": ckey,
                "url": f"{jira_url.rstrip('/')}/browse/{ckey}",
                "summary": f"Ticket {ckey}",
                "status": "Unknown",
                "type": "Unknown",
                "assignee": "Unknown"
            })

    result = {
        "release_key": release_key,
        "release_url": f"{jira_url.rstrip('/')}/browse/{release_key}",
        "release_summary": release_summary,
        "release_description": release_desc,
        "release_type": issue_type,
        "release_status": status,
        "build_url": extracted_build_urls[0] if extracted_build_urls else None,
        "child_tickets": child_tickets,
        "comments": all_comments
    }

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch Release Ticket details and auto-extract linked issues and build links")
    parser.add_argument("release_key", help="Parent/Release Jira ticket key (e.g. MB2C-1950)")
    parser.add_argument("--json", action="store_true", help="Output as raw JSON")

    args = parser.parse_args()
    data = fetch_release_ticket_data(args.release_key)

    if data:
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            print("\n==============================")
            print(f"RELEASE TICKET: {data['release_key']} - {data['release_summary']}")
            print(f"Build URL: {data['build_url'] or 'Not found in ticket'}")
            print(f"Total Changes: {len(data['child_tickets'])}")
            print("==============================")
            for i, t in enumerate(data['child_tickets'], 1):
                print(f"{i}. {t['summary']}")
                print(f"   {t['url']}\n")
