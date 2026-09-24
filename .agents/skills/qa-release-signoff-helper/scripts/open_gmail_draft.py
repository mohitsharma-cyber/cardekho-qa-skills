"""
Script to manage release mail recipients, copy email to clipboard, and automatically open browser compose window.
Persists last-used TO and CC recipient addresses so they are automatically pre-filled on every future release mail.
"""

import argparse
import json
import os
import subprocess
import urllib.parse
import webbrowser

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SEARCH_RECIPIENT_PATHS = [
    os.path.join(os.path.expanduser("~"), ".gemini", "antigravity", "release_mail_recipients.json"),
    os.path.join(os.path.expanduser("~"), ".agents", "release_mail_recipients.json"),
    os.path.join(os.path.dirname(SCRIPT_DIR), "recipients.json"),
]


def load_saved_recipients():
    for p in SEARCH_RECIPIENT_PATHS:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception:
                pass
    return {"to": "", "cc": ""}


def save_recipients(to_emails=None, cc_emails=None):
    recipients = load_saved_recipients()
    if to_emails is not None and to_emails.strip():
        recipients["to"] = to_emails.strip()
    if cc_emails is not None and cc_emails.strip():
        recipients["cc"] = cc_emails.strip()

    # Save to user home config and local skill folder
    for target in [SEARCH_RECIPIENT_PATHS[0], SEARCH_RECIPIENT_PATHS[2]]:
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                json.dump(recipients, f, indent=2)
        except Exception as e:
            pass
    return recipients


DEFAULT_SENDER = "mohit.sharma@girnarsoft.com"


def handle_mail_draft(subject, body, to_emails=None, cc_emails=None, sender_email=DEFAULT_SENDER, auto_open_browser=True):
    # 1. Resolve recipients (use provided, or fallback to saved last-used)
    saved = load_saved_recipients()

    if to_emails and to_emails.strip():
        resolved_to = to_emails.strip()
        save_recipients(to_emails=resolved_to)
    else:
        resolved_to = saved.get("to", "")

    if cc_emails and cc_emails.strip():
        resolved_cc = cc_emails.strip()
        save_recipients(cc_emails=resolved_cc)
    else:
        resolved_cc = saved.get("cc", "")

    sender_email = sender_email or DEFAULT_SENDER

    # 2. Copy formatted text to Windows Clipboard automatically
    try:
        process = subprocess.Popen(['powershell', '-Command', '$input | Set-Clipboard'], stdin=subprocess.PIPE, text=True)
        process.communicate(input=body)
        print("[SUCCESS] Email body copied to Windows Clipboard (Ctrl+V ready)!")
    except Exception as e:
        print(f"[WARN] Clipboard copy failed: {e}")

    # 3. Build Gmail Compose URL with authuser, TO, CC, Subject, and Body
    encoded_subject = urllib.parse.quote(subject)
    encoded_body = urllib.parse.quote(body)
    encoded_to = urllib.parse.quote(resolved_to)
    encoded_cc = urllib.parse.quote(resolved_cc)
    encoded_sender = urllib.parse.quote(sender_email)

    # Note: When authuser is in query params of mail/?view=cm, modern Gmail sometimes ignores the body param
    # Using mail/u/0/?view=cm or standard mail/?view=cm ensures body is rendered properly.
    gmail_url = f"https://mail.google.com/mail/?view=cm&fs=1&to={encoded_to}&su={encoded_subject}&body={encoded_body}"
    if encoded_sender:
        gmail_url += f"&authuser={encoded_sender}"
    if resolved_cc:
        gmail_url += f"&cc={encoded_cc}"

    print(f"[SENDER] FROM: {sender_email}")
    print(f"[RECIPIENTS] TO: {resolved_to if resolved_to else '(None set yet)'}")
    if resolved_cc:
        print(f"[RECIPIENTS] CC: {resolved_cc}")

    # 4. Auto-open in default browser
    if auto_open_browser:
        try:
            webbrowser.open(gmail_url)
            print(f"[SUCCESS] Launched Gmail compose tab for account '{sender_email}' with pre-filled recipients!")
        except Exception as e:
            print(f"[WARN] Could not auto-launch browser: {e}")

    return gmail_url, resolved_to, resolved_cc


def main():
    parser = argparse.ArgumentParser(description="Handle release mail draft with persistent recipient memory")
    parser.add_argument("--subject", help="Email Subject")
    parser.add_argument("--body", help="Email Body")
    parser.add_argument("--sender", default=DEFAULT_SENDER, help=f"Sender Google email account (default: {DEFAULT_SENDER})")
    parser.add_argument("--to", help="Recipient TO emails (comma-separated). Automatically remembered for future emails.")
    parser.add_argument("--cc", help="Recipient CC emails (comma-separated). Automatically remembered for future emails.")
    parser.add_argument("--set-to", help="Set/Update default TO mailing addresses without sending email")
    parser.add_argument("--set-cc", help="Set/Update default CC mailing addresses without sending email")
    parser.add_argument("--show-recipients", action="store_true", help="Print currently saved TO and CC recipients")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically launch browser tab")

    args = parser.parse_args()

    if args.set_to or args.set_cc:
        saved = save_recipients(to_emails=args.set_to, cc_emails=args.set_cc)
        print(f"[SUCCESS] Saved default recipients:")
        print(f"  - TO: {saved.get('to')}")
        print(f"  - CC: {saved.get('cc')}")
        return

    if args.show_recipients:
        saved = load_saved_recipients()
        print(f"Saved Release Mail Recipients:")
        print(f"  - TO: {saved.get('to', '(None)')}")
        print(f"  - CC: {saved.get('cc', '(None)')}")
        return

    if not args.subject or not args.body:
        print("[ERROR] --subject and --body are required to compose an email draft.")
        return

    url, to_res, cc_res = handle_mail_draft(
        subject=args.subject,
        body=args.body,
        to_emails=args.to,
        cc_emails=args.cc,
        sender_email=args.sender,
        auto_open_browser=not args.no_browser
    )
    print(f"GMAIL_URL:{url}")


if __name__ == "__main__":
    main()
