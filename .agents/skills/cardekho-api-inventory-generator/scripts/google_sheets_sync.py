"""
Google Sheets Sync Module for CarDekho API Inventory.
Syncs discovery inventory data directly to Google Sheet via Google Apps Script Webhook.
"""

import json
import os
import sys
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(os.path.dirname(SCRIPT_DIR), "config.json")
DEFAULT_WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbyKW6y2wExQcUQSrFsuo8QGDSkew4hc_QlOl_r9H1FOgZYXHEEGTBz1r6xsm2Eo4jr6NQ/exec"
GIRNAR_WEBHOOK_URL = "https://script.google.com/a/macros/girnarsoft.com/s/AKfycbyKW6y2wExQcUQSrFsuo8QGDSkew4hc_QlOl_r9H1FOgZYXHEEGTBz1r6xsm2Eo4jr6NQ/exec"


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def sync_to_google_sheet_webhook(json_path, webhook_url=None):
    config = load_config()
    webhook_url = webhook_url or config.get("google_sheet_webhook_url", DEFAULT_WEBHOOK_URL)

    if not os.path.exists(json_path):
        print(f"[ERROR] JSON inventory file not found at: {json_path}")
        return False

    with open(json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    print(f"Syncing {len(payload.get('inventory', []))} API records to Google Sheet Webhook...")
    
    # Try both standard and girnarsoft macro URLs if needed
    urls_to_try = [webhook_url, GIRNAR_WEBHOOK_URL, DEFAULT_WEBHOOK_URL]
    success = False

    for url in list(dict.fromkeys(urls_to_try)):
        try:
            headers = {"Content-Type": "application/json"}
            res = requests.post(url, json=payload, headers=headers, timeout=25, allow_redirects=True)
            if res.status_code == 200:
                print(f"[SUCCESS] Google Sheet updated successfully via Webhook!")
                print(f"Response: {res.text}")
                success = True
                break
            else:
                print(f"Webhook returned status {res.status_code}: {res.text}")
        except Exception as e:
            print(f"Attempt failed for {url}: {e}")

    return success


if __name__ == "__main__":
    js_path = sys.argv[1] if len(sys.argv) > 1 else "output/cardekho_api_inventory.json"
    hook_url = sys.argv[2] if len(sys.argv) > 2 else None
    sync_to_google_sheet_webhook(js_path, hook_url)
