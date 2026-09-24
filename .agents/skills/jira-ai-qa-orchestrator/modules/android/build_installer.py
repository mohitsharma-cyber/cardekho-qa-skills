"""
Build Detection, Downloader & Auto-Installer for Jira AI QA Orchestrator.
Scans Jira ticket descriptions, comments, and attachments for build links (APK, S3, Jenkins, Firebase, AppCenter),
downloads the binary, and installs it onto the connected physical Android device via ADB prior to test execution.
"""

import os
import re
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple
import requests


class BuildInstaller:
    def __init__(self, download_dir: Optional[str] = None):
        self.download_dir = download_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "downloads"
        )
        os.makedirs(self.download_dir, exist_ok=True)

    def extract_build_info(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inspects ticket description, comments, and attachments for build / APK links.
        """
        desc = ticket_data.get("description") or ""
        comments = ticket_data.get("comments") or []
        attachments = ticket_data.get("attachments") or []

        # 1. Check attachments for .apk files
        for att in attachments:
            fname = att.get("filename", "")
            if fname.lower().endswith(".apk"):
                return {
                    "has_build": True,
                    "build_url": att.get("content", ""),
                    "filename": fname,
                    "source_type": "ATTACHMENT",
                    "found_in": f"Attachment ({fname})",
                    "is_attachment": True
                }

        # 2. Check comments for links (reverse order to find most recent build)
        for c in reversed(comments):
            body = c.get("body", "")
            found = self._find_build_in_text(body)
            if found:
                found["found_in"] = f"Comment by {c.get('author', 'Developer')}"
                return found

        # 3. Check description
        found_in_desc = self._find_build_in_text(desc)
        if found_in_desc:
            found_in_desc["found_in"] = "Ticket Description"
            return found_in_desc

        return {
            "has_build": False,
            "build_url": None,
            "filename": None,
            "source_type": None,
            "found_in": None
        }

    def _find_build_in_text(self, text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None

        # Regex for URLs in text
        urls = re.findall(r'https?://[^\s<>"\')]+', text)
        for u in urls:
            u_clean = u.rstrip(".,;)]")
            u_lower = u_clean.lower()

            # Direct APK URL
            if u_lower.endswith(".apk") or ".apk?" in u_lower:
                fname = os.path.basename(u_clean.split("?")[0]) or "build.apk"
                return {
                    "has_build": True,
                    "build_url": u_clean,
                    "filename": fname,
                    "source_type": "DIRECT_APK",
                    "is_attachment": False
                }

            # Firebase App Distribution
            if "appdistribution.firebase.google.com" in u_lower:
                return {
                    "has_build": True,
                    "build_url": u_clean,
                    "filename": "firebase-build.apk",
                    "source_type": "FIREBASE",
                    "is_attachment": False
                }

            # AppCenter / Diawi / Jenkins / S3
            if any(k in u_lower for k in ["diawi.com", "install.appcenter.ms", "artifacts.girnarsoft.com", "s3.amazonaws.com/girnarsoft"]):
                fname = os.path.basename(u_clean.split("?")[0]) or "ci-build.apk"
                return {
                    "has_build": True,
                    "build_url": u_clean,
                    "filename": fname,
                    "source_type": "CI_DISTRIBUTION",
                    "is_attachment": False
                }

        return None

    def download_build(self, build_info: Dict[str, Any], ticket_key: str, jira_auth: Optional[Any] = None) -> Tuple[bool, str]:
        """
        Downloads the build artifact to local cache.
        """
        url = build_info.get("build_url")
        filename = build_info.get("filename") or f"{ticket_key}_build.apk"
        dest_path = os.path.join(self.download_dir, f"{ticket_key}_{filename}")

        print(f"[BUILD] Downloading build from: {url}")
        print(f"[BUILD] Destination: {dest_path}")

        try:
            headers = {"User-Agent": "JiraAIQAOrchestrator/1.0"}
            req_auth = jira_auth if build_info.get("is_attachment") else None

            r = requests.get(url, auth=req_auth, headers=headers, stream=True, verify=False, timeout=60)
            if r.status_code == 200:
                with open(dest_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                file_size = os.path.getsize(dest_path)
                print(f"[SUCCESS] Downloaded {filename} ({file_size / (1024*1024):.2f} MB)")
                return True, dest_path
            else:
                return False, f"Failed to download build (HTTP {r.status_code})"
        except Exception as e:
            return False, f"Download error: {str(e)}"

    def install_build_on_device(self, apk_path: str, serial: str, mock_mode: bool = False) -> Tuple[bool, str]:
        """
        Installs APK onto connected Android device using ADB.
        Uses -r (reinstall), -d (allow downgrade), -g (grant all permissions).
        """
        if mock_mode:
            print(f"[MOCK ADB] Simulating APK install on device {serial}...")
            time.sleep(1.5)
            print(f"[SUCCESS] Build installed successfully on mock device {serial}.")
            return True, f"Build installed successfully on mock device ({serial})"

        if not os.path.exists(apk_path):
            return False, f"APK file not found at: {apk_path}"

        serial_arg = f"-s {serial}" if serial else ""
        print(f"[ADB] Installing {apk_path} on device {serial}...")

        # Run ADB install with flags
        cmd = f"adb {serial_arg} install -r -d -g \"{apk_path}\""
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)

        stdout = res.stdout.strip()
        stderr = res.stderr.strip()
        print(f"[ADB OUTPUT]: {stdout}")

        if "Success" in stdout:
            print(f"[SUCCESS] APK installed successfully on device {serial}!")
            return True, f"Installed successfully on {serial}"
        else:
            # Fallback if signature mismatch or downgrade blocked: uninstall then install
            if "INSTALL_FAILED_UPDATE_INCOMPATIBLE" in stdout or "INSTALL_FAILED_VERSION_DOWNGRADE" in stdout:
                print("[ADB] Reinstall failed due to signature/version conflict. Attempting clean reinstall...")
                pkg = "com.cardekho.android.debug"
                subprocess.run(f"adb {serial_arg} uninstall {pkg}", shell=True)
                retry_res = subprocess.run(f"adb {serial_arg} install -g \"{apk_path}\"", shell=True, capture_output=True, text=True)
                if "Success" in retry_res.stdout:
                    return True, f"Clean installed successfully on {serial}"

            return False, f"ADB Install Failed: {stdout} {stderr}"
