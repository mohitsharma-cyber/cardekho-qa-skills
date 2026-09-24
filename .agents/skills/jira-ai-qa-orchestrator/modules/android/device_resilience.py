"""
Device Resilience Helper for Jira AI QA Orchestrator.
Eliminates real-world runtime Android test flakiness and execution blockers:
1. Overlay Sweeper & Modal Interceptor (e.g. Truecaller, Google/App rating dialogs)
2. Deterministic Keyboard Dismissal (mInputShown inspection + keyevent)
3. Dynamic Element Bounds & Center Resolver (uiautomator XML bounds parser)
4. Deterministic Shimmer & Content Poller
5. Logcat Crash & Fatal Exception Sniffer
"""

import os
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple


class DeviceResilienceHelper:
    """Provides atomic, self-healing ADB execution helpers for physical and mock Android devices."""

    def __init__(self, mock_mode: bool = False):
        self.mock_mode = mock_mode

    # -------------------------------------------------------------------------
    # 1. Overlay Sweeper & Modal Interceptor
    # -------------------------------------------------------------------------
    def sweep_overlays(self, serial: str, target_package: Optional[str] = None) -> Dict[str, Any]:
        """
        Detects and clears intrusive 3rd-party overlays (e.g. Truecaller popups)
        or dismissible in-app promo/rating modal dialogs that steal touch events.
        """
        if self.mock_mode:
            return {"status": "CLEAN", "dismissed_overlays": [], "focus_restored": True}

        serial_arg = f"-s {serial}"
        dismissed = []

        try:
            # A. Check foreground package
            cmd = f"adb {serial_arg} shell dumpsys window displays"
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
            output = res.stdout or ""

            # Check for Truecaller caller ID or overlay
            if "com.truecaller" in output:
                subprocess.run(f"adb {serial_arg} shell am force-stop com.truecaller", shell=True, timeout=5)
                dismissed.append("com.truecaller (force-stopped)")

            # B. Dismiss known nuisance modal tokens if present in UI dump
            dismiss_tokens = [
                "not now", "cancel", "dismiss", "later", "close", "no thanks",
                "remind me later", "maybe later", "skip"
            ]
            dump_res = self.dump_ui_xml(serial)
            if dump_res is not None:
                tree = dump_res
                for node in tree.iter("node"):
                    t = (node.attrib.get("text") or "").strip().lower()
                    d = (node.attrib.get("content-desc") or "").strip().lower()
                    for tok in dismiss_tokens:
                        if tok == t or tok == d:
                            bounds = node.attrib.get("bounds", "")
                            m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
                            if m:
                                x1, y1, x2, y2 = map(int, m.groups())
                                cx = (x1 + x2) // 2
                                cy = (y1 + y2) // 2
                                subprocess.run(f"adb {serial_arg} shell input tap {cx} {cy}", shell=True, timeout=3)
                                dismissed.append(f"Dismissed modal button '{tok}' at ({cx},{cy})")
                                time.sleep(0.8)
                                break
                    if len(dismissed) >= 2:
                        break

            # C. If target package specified and lost focus, restore it
            if target_package:
                current_focus_cmd = f"adb {serial_arg} shell dumpsys activity activities"
                f_res = subprocess.run(current_focus_cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
                if target_package not in (f_res.stdout or ""):
                    subprocess.run(f"adb {serial_arg} shell monkey -p {target_package} -c android.intent.category.LAUNCHER 1", shell=True, timeout=5)
                    dismissed.append(f"Restored foreground focus to {target_package}")

        except Exception as e:
            return {"status": "ERROR", "error": str(e), "dismissed_overlays": dismissed}

        return {
            "status": "CLEAN",
            "dismissed_overlays": dismissed,
            "focus_restored": True
        }

    # -------------------------------------------------------------------------
    # 2. Deterministic Keyboard Dismissal
    # -------------------------------------------------------------------------
    def is_keyboard_shown(self, serial: str) -> bool:
        """Inspects dumpsys input_method to verify if the software keyboard is currently active."""
        if self.mock_mode:
            return False

        serial_arg = f"-s {serial}"
        try:
            cmd = f"adb {serial_arg} shell dumpsys input_method"
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
            out = res.stdout or ""
            return "mInputShown=true" in out or "mIsInputViewShown=true" in out
        except Exception:
            return False

    def dismiss_keyboard_if_shown(self, serial: str, max_retries: int = 2) -> bool:
        """
        Dismisses soft keyboard deterministically using KEYCODE_BACK / KEYCODE_ESCAPE.
        Verifies keyboard is actually hidden to prevent CTA occlusion on Android 14.
        """
        if self.mock_mode:
            return True

        serial_arg = f"-s {serial}"
        for _ in range(max_retries):
            if not self.is_keyboard_shown(serial):
                return True
            subprocess.run(f"adb {serial_arg} shell input keyevent 111", shell=True, timeout=3)
            time.sleep(0.5)
            if not self.is_keyboard_shown(serial):
                return True
            subprocess.run(f"adb {serial_arg} shell input keyevent 4", shell=True, timeout=3)
            time.sleep(0.5)

        return not self.is_keyboard_shown(serial)

    # -------------------------------------------------------------------------
    # 3. Dynamic Element Bounds & Center Resolver
    # -------------------------------------------------------------------------
    def dump_ui_xml(self, serial: str) -> Optional[ET.Element]:
        """Dumps UI hierarchy via ADB and returns parsed XML ElementTree root."""
        if self.mock_mode:
            root = ET.Element("hierarchy")
            ET.SubElement(root, "node", {
                "text": "CHANGE URL",
                "resource-id": "com.girnarsoft.cardekho:id/tv_change_url",
                "bounds": "[100,200][300,260]"
            })
            return root

        serial_arg = f"-s {serial}"
        remote_xml = "/sdcard/window_dump.xml"
        local_xml = os.path.join(os.getcwd(), "evidence", f"resilience_dump_{int(time.time()*1000)}.xml")
        try:
            os.makedirs(os.path.dirname(local_xml), exist_ok=True)
            subprocess.run(f"adb {serial_arg} shell uiautomator dump {remote_xml}", shell=True, timeout=6, capture_output=True)
            subprocess.run(f"adb {serial_arg} pull {remote_xml} \"{local_xml}\"", shell=True, timeout=6, capture_output=True)
            if os.path.exists(local_xml) and os.path.getsize(local_xml) > 0:
                tree = ET.parse(local_xml)
                try:
                    os.remove(local_xml)
                except Exception:
                    pass
                return tree.getroot()
        except Exception:
            pass
        return None

    def resolve_element_center(
        self,
        serial: str,
        text: Optional[str] = None,
        resource_id: Optional[str] = None,
        content_desc: Optional[str] = None,
        fallback_coords: Optional[Tuple[int, int]] = None
    ) -> Optional[Tuple[int, int]]:
        """
        Dynamically finds element bounds in live UI hierarchy and returns center (cx, cy).
        Eliminates device resolution / DPI coordinate breakage.
        """
        root = self.dump_ui_xml(serial)
        if root is not None:
            text_l = text.lower() if text else None
            rid_l = resource_id.lower() if resource_id else None
            desc_l = content_desc.lower() if content_desc else None

            for node in root.iter("node"):
                node_text = (node.attrib.get("text") or "").strip().lower()
                node_rid = (node.attrib.get("resource-id") or "").strip().lower()
                node_desc = (node.attrib.get("content-desc") or "").strip().lower()

                match = False
                if text_l and (text_l == node_text or text_l in node_text):
                    match = True
                elif rid_l and (rid_l == node_rid or rid_l in node_rid):
                    match = True
                elif desc_l and (desc_l == node_desc or desc_l in node_desc):
                    match = True

                if match:
                    bounds = node.attrib.get("bounds", "")
                    m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
                    if m:
                        x1, y1, x2, y2 = map(int, m.groups())
                        return ((x1 + x2) // 2, (y1 + y2) // 2)

        return fallback_coords

    # -------------------------------------------------------------------------
    # 4. Deterministic Shimmer & Content Poller
    # -------------------------------------------------------------------------
    def wait_for_content_or_shimmer(
        self,
        serial: str,
        expected_token: Optional[str] = None,
        timeout_secs: int = 10,
        min_text_len: int = 30,
        poll_interval: float = 1.0
    ) -> Tuple[bool, str]:
        """
        Deterministically polls the screen until actual UI content renders and
        all loading shimmers / spinners disappear. Prevents premature assertion on blank screens.
        """
        if self.mock_mode:
            return True, "Content rendered and shimmer cleared (Mock Mode)"

        start = time.time()
        loading_keywords = ["loading", "please wait", "fetching data", "buffering"]

        while time.time() - start < timeout_secs:
            root = self.dump_ui_xml(serial)
            if root is not None:
                all_texts = []
                for node in root.iter("node"):
                    t = (node.attrib.get("text") or "").strip()
                    d = (node.attrib.get("content-desc") or "").strip()
                    if t:
                        all_texts.append(t)
                    if d:
                        all_texts.append(d)

                full_text = " ".join(all_texts)
                full_text_lower = full_text.lower()

                token_matched = True
                if expected_token:
                    token_matched = expected_token.lower() in full_text_lower

                is_loading = any(kw in full_text_lower for kw in loading_keywords)

                if token_matched and not is_loading and len(full_text) >= min_text_len:
                    return True, f"Content rendered successfully ({len(full_text)} chars parsed, shimmer cleared)"

            time.sleep(poll_interval)

        return False, f"APPLICATION_ERROR: Screen remained in shimmer/loading state after {timeout_secs}s"

    # -------------------------------------------------------------------------
    # 5. Logcat Crash & Fatal Exception Sniffer
    # -------------------------------------------------------------------------
    def capture_logcat_fatal_errors(
        self,
        serial: str,
        package_name: str,
        max_lines: int = 150
    ) -> List[Dict[str, str]]:
        """
        Scans Android system logcat for fatal crashes, ANRs, NullPointerExceptions,
        or unhandled exceptions affecting the tested package.
        """
        if self.mock_mode:
            return []

        serial_arg = f"-s {serial}"
        fatal_errors = []
        try:
            cmd = f"adb {serial_arg} logcat -d -t {max_lines} *:E"
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
            lines = (res.stdout or "").split("\n")

            crash_patterns = [
                r"FATAL EXCEPTION",
                r"Process:\s*" + re.escape(package_name),
                r"java\.lang\.NullPointerException",
                r"java\.lang\.RuntimeException",
                r"ANR in\s*" + re.escape(package_name),
                r"AndroidRuntime:\s*FATAL"
            ]

            current_crash = []
            capturing = False

            for line in lines:
                l_strip = line.strip()
                if any(re.search(pat, l_strip, re.IGNORECASE) for pat in crash_patterns):
                    capturing = True
                    current_crash.append(l_strip)
                elif capturing:
                    if l_strip.startswith("at ") or l_strip.startswith("Caused by:") or "Exception" in l_strip:
                        current_crash.append(l_strip)
                        if len(current_crash) >= 8:
                            fatal_errors.append({
                                "type": "FATAL_EXCEPTION",
                                "package": package_name,
                                "stacktrace": "\n".join(current_crash)
                            })
                            current_crash = []
                            capturing = False
                    else:
                        if current_crash:
                            fatal_errors.append({
                                "type": "FATAL_EXCEPTION",
                                "package": package_name,
                                "stacktrace": "\n".join(current_crash)
                            })
                            current_crash = []
                        capturing = False

            if current_crash:
                fatal_errors.append({
                    "type": "FATAL_EXCEPTION",
                    "package": package_name,
                    "stacktrace": "\n".join(current_crash)
                })

        except Exception as e:
            print(f"[WARN] Error reading logcat: {e}")

        return fatal_errors
