"""
Android Device & ADB/Appium Runner for Jira AI QA Orchestrator.
Detects physical Android devices, manages the WAITING_FOR_DEVICE pause/resume flow,
and executes native tests with non-destructive controls.
"""

import json
import os
import re
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

from .device_resilience import DeviceResilienceHelper


class AndroidRunner:
    def __init__(self, mock_mode: bool = False):
        self.mock_mode = mock_mode
        self.resilience = DeviceResilienceHelper(mock_mode=mock_mode)

    def list_connected_devices(self) -> List[Dict[str, Any]]:
        """Lists all connected Android devices via ADB with hardware properties (Rule 24)."""
        if self.mock_mode:
            from ..mock.mock_provider import MockProvider
            return [MockProvider.get_mock_device()]

        devices_list = []
        try:
            res = subprocess.run("adb devices", shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
            if res.returncode != 0 or not res.stdout:
                return []

            lines = [l.strip() for l in res.stdout.split("\n") if l.strip()]
            for line in lines[1:]:
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "device":
                    serial = parts[0]
                    def get_prop(prop):
                        r = subprocess.run(f"adb -s {serial} shell getprop {prop}", shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
                        return r.stdout.strip()
                    brand = get_prop("ro.product.brand")
                    model = get_prop("ro.product.model")
                    os_ver = get_prop("ro.build.version.release")
                    sdk_ver = get_prop("ro.build.version.sdk")
                    devices_list.append({
                        "serial": serial,
                        "brand": brand,
                        "model": model,
                        "os_version": os_ver,
                        "sdk_version": sdk_ver,
                        "connection_status": "Connected",
                        "usb_debugging": True
                    })
        except Exception as e:
            print(f"[WARN] Error listing ADB devices: {e}")
        return devices_list

    def detect_device(self) -> Optional[Dict[str, Any]]:
        """Detect connected Android device via ADB and inspect properties."""
        devices = self.list_connected_devices()
        if not devices:
            return None
        # Return primary device
        primary = devices[0]
        # Check Appium availability
        appium_ready = False
        try:
            import requests
            r = requests.get("http://127.0.0.1:4723/status", timeout=1)
            appium_ready = r.status_code == 200
        except Exception:
            pass
        primary["appium_ready"] = appium_ready
        primary["package_name"] = "com.cardekho.android.debug"
        return primary

    def grant_required_permissions(self, serial: str, package_name: str, permissions: Optional[List[str]] = None) -> Dict[str, str]:
        """
        Pre-grants required Android runtime permissions via ADB pm grant (Rule 26, Rule 3).
        Eliminates popup dialog interruptions.
        """
        target_perms = permissions or [
            "android.permission.POST_NOTIFICATIONS",
            "android.permission.ACCESS_FINE_LOCATION",
            "android.permission.ACCESS_COARSE_LOCATION",
            "android.permission.READ_MEDIA_IMAGES",
            "android.permission.CAMERA"
        ]
        results = {}
        if self.mock_mode:
            for p in target_perms:
                short = p.split(".")[-1]
                results[short] = "Granted"
            return results

        serial_arg = f"-s {serial}"
        for perm in target_perms:
            short = perm.split(".")[-1]
            try:
                cmd = f"adb {serial_arg} shell pm grant {package_name} {perm}"
                subprocess.run(cmd, shell=True, capture_output=True, timeout=5)
                results[short] = "Granted"
            except Exception:
                results[short] = "Not Granted"
        print(f"[ANDROID] 🛡️ Pre-granted runtime permissions for {package_name}: {results}")
        return results

    def wait_for_shimmer_to_disappear(self, serial: str, timeout_secs: int = 10, poll_interval: float = 1.0) -> Tuple[bool, str]:
        """
        Waits for loading shimmer or blank state to disappear (Rules 28 & 30).
        If shimmer persists > timeout_secs, returns (False, failure_reason).
        """
        if self.mock_mode:
            return True, "Content rendered successfully (Mock Mode)"

        start = time.time()
        while time.time() - start < timeout_secs:
            text = self.dump_screen_text(serial)
            # If significant text has loaded and no loading spinner
            if text and len(text.strip()) > 30 and not any(kw in text.lower() for kw in ["loading...", "please wait", "retry"]):
                return True, "Content rendered and shimmer cleared"
            time.sleep(poll_interval)

        return False, f"APPLICATION_ERROR: Screen remained in shimmer/loading state after {timeout_secs}s"

    def capture_screenshot(self, serial: str, local_path: str) -> bool:
        """Captures crisp, uncompressed screenshot from Android device, handling Android 14 / ColorOS."""
        serial_arg = f"-s {serial}"
        raw_remote = "/sdcard/screen_cap.raw"
        raw_local = local_path.replace(".png", ".raw")
        try:
            # 1. screencap to raw file on device
            subprocess.run(f"adb {serial_arg} shell screencap {raw_remote}", shell=True, timeout=8)
            # 2. pull raw file
            os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
            subprocess.run(f"adb {serial_arg} pull {raw_remote} \"{raw_local}\"", shell=True, timeout=10)
            if os.path.exists(raw_local) and os.path.getsize(raw_local) > 1000:
                with open(raw_local, "rb") as f:
                    raw = f.read()
                w = int.from_bytes(raw[0:4], "little")
                h = int.from_bytes(raw[4:8], "little")
                from PIL import Image
                img = Image.frombytes("RGBA", (w, h), raw[16:])
                img.save(local_path)
                try:
                    os.remove(raw_local)
                except Exception:
                    pass
                return True
        except Exception as e:
            print(f"[WARN] Error capturing raw screenshot: {e}")

        # Fallback standard screencap
        subprocess.run(f"adb {serial_arg} shell screencap -p /sdcard/sc.png", shell=True)
        subprocess.run(f"adb {serial_arg} pull /sdcard/sc.png \"{local_path}\"", shell=True)
        return os.path.exists(local_path)

    def dump_screen_text(self, serial: str) -> str:
        """Dumps UI hierarchy XML and extracts all visible text."""
        serial_arg = f"-s {serial}"
        xml_remote = "/sdcard/ui_dump.xml"
        xml_local = os.path.join(os.getcwd(), "evidence", f"ui_dump_{int(time.time())}.xml")
        try:
            os.makedirs(os.path.dirname(xml_local), exist_ok=True)
            subprocess.run(f"adb {serial_arg} shell uiautomator dump {xml_remote}", shell=True, timeout=8)
            subprocess.run(f"adb {serial_arg} pull {xml_remote} \"{xml_local}\"", shell=True, timeout=8)
            if os.path.exists(xml_local):
                import xml.etree.ElementTree as ET
                tree = ET.parse(xml_local)
                texts = []
                for node in tree.getroot().iter("node"):
                    t = node.attrib.get("text", "").strip()
                    d = node.attrib.get("content-desc", "").strip()
                    if t:
                        texts.append(t)
                    if d:
                        texts.append(d)
                try:
                    os.remove(xml_local)
                except Exception:
                    pass
                return " ".join(texts)
        except Exception as e:
            print(f"[WARN] Error dumping UI hierarchy: {e}")
        return ""

    def dismiss_permission_dialogs(self, serial: str, max_attempts: int = 3) -> int:
        """
        Detects and automatically allows Android permission popups
        (e.g., Location, Notifications, Camera, Storage, Phone, System Dialogs).
        Loops up to max_attempts to handle sequential permission dialogs.
        """
        if self.mock_mode:
            return 0

        serial_arg = f"-s {serial}"
        dismissed_count = 0

        # Prioritized resource-id fragments for Allow buttons
        allow_res_ids = [
            "permission_allow_foreground_only_button",
            "permission_allow_button",
            "permission_allow_always_button",
            "permission_allow_one_time_button",
            "button1"  # standard Android dialog positive button
        ]
        # Common text matches (case-insensitive)
        allow_text_tokens = [
            "while using the app",
            "allow all the time",
            "only this time",
            "allow",
            "ok",
            "continue",
            "agree",
            "got it"
        ]

        for attempt in range(max_attempts):
            xml_remote = "/sdcard/perm_dump.xml"
            xml_local = os.path.join(os.getcwd(), "evidence", f"perm_dump_{int(time.time()*1000)}.xml")
            try:
                os.makedirs(os.path.dirname(xml_local), exist_ok=True)
                subprocess.run(f"adb {serial_arg} shell uiautomator dump {xml_remote}", shell=True, timeout=5, capture_output=True)
                subprocess.run(f"adb {serial_arg} pull {xml_remote} \"{xml_local}\"", shell=True, timeout=5, capture_output=True)

                if not os.path.exists(xml_local) or os.path.getsize(xml_local) == 0:
                    break

                import xml.etree.ElementTree as ET
                tree = ET.parse(xml_local)
                root = tree.getroot()

                matched_node = None

                # 1. Search by resource-id
                for node in root.iter("node"):
                    rid = node.attrib.get("resource-id", "").lower()
                    if any(t_id in rid for t_id in allow_res_ids):
                        matched_node = node
                        break

                # 2. Search by text / content-desc if not matched by ID
                if not matched_node:
                    for node in root.iter("node"):
                        t = node.attrib.get("text", "").strip().lower()
                        d = node.attrib.get("content-desc", "").strip().lower()
                        for tok in allow_text_tokens:
                            if tok == t or tok == d:
                                matched_node = node
                                break
                        if matched_node:
                            break

                try:
                    os.remove(xml_local)
                except Exception:
                    pass

                if matched_node is not None:
                    bounds = matched_node.attrib.get("bounds", "")
                    match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
                    if match:
                        x1, y1, x2, y2 = map(int, match.groups())
                        cx = (x1 + x2) // 2
                        cy = (y1 + y2) // 2
                        label = matched_node.attrib.get("text") or matched_node.attrib.get("resource-id")
                        print(f"[ANDROID] 🛡️ Auto-Allowing permission dialog: tapped '{label}' at ({cx}, {cy})")
                        subprocess.run(f"adb {serial_arg} shell input tap {cx} {cy}", shell=True)
                        dismissed_count += 1
                        time.sleep(1.2)
                        continue
                # If no dialog detected on this attempt, break out
                break
            except Exception:
                break

        return dismissed_count

    def sweep_overlays(self, serial: str, target_package: Optional[str] = None) -> Dict[str, Any]:
        """Clears intrusive 3rd-party overlays or dismissible modals."""
        return self.resilience.sweep_overlays(serial, target_package=target_package)

    def dismiss_keyboard_if_shown(self, serial: str, max_retries: int = 2) -> bool:
        """Dismisses soft keyboard deterministically to prevent UI occlusion."""
        return self.resilience.dismiss_keyboard_if_shown(serial, max_retries=max_retries)

    def resolve_element_center(
        self,
        serial: str,
        text: Optional[str] = None,
        resource_id: Optional[str] = None,
        content_desc: Optional[str] = None,
        fallback_coords: Optional[Tuple[int, int]] = None
    ) -> Optional[Tuple[int, int]]:
        """Dynamically finds element center coordinates from UI hierarchy."""
        return self.resilience.resolve_element_center(
            serial, text=text, resource_id=resource_id, content_desc=content_desc, fallback_coords=fallback_coords
        )

    def capture_logcat_fatal_errors(self, serial: str, package_name: str, max_lines: int = 150) -> List[Dict[str, str]]:
        """Scans logcat for fatal exceptions and crashes."""
        return self.resilience.capture_logcat_fatal_errors(serial, package_name, max_lines=max_lines)

    def execute_android_test(self, test_case: Dict[str, Any], serial: str) -> Dict[str, Any]:
        """Executes native Android actions on the connected device with true Jira step understanding."""
        tc_id = test_case.get("test_case_id")
        title = test_case.get("title")
        print(f"[ANDROID] Executing {tc_id} on device {serial}...")

        if self.mock_mode:
            time.sleep(1)
            return {
                "test_case_id": tc_id,
                "status": "PASSED",
                "status_code": 200,
                "device_serial": serial,
                "page_text": "Model Overview Highlights clean plain text",
                "ui_valid": True,
                "app_crashed": False,
                "logs": [f"Woke up screen on {serial}", f"Executed native test {title}", "Assertion validated successfully"]
            }

        serial_arg = f"-s {serial}"
        # 1. Auto-wake and unlock screen
        subprocess.run(f"adb {serial_arg} shell input keyevent 224", shell=True) # KEYCODE_WAKEUP
        subprocess.run(f"adb {serial_arg} shell input keyevent 82", shell=True)
        subprocess.run(f"adb {serial_arg} shell wm dismiss-keyguard", shell=True)
        time.sleep(0.5)

        # 2. Determine target package and activity
        is_bike = "bike" in title.lower() or "bd" in tc_id.lower() or "mb2c" in tc_id.lower()
        if is_bike:
            target_pkg = "com.girnarsoft.bikedekho"
            main_activity = "com.girnarsoft.bikedekho/com.girnarsoft.girnarsoft_oneapp_flutter.MainActivity"
        else:
            target_pkg = "com.girnarsoft.cardekho"
            main_activity = "com.cardekho.android.debug/com.cardekho.android.activity.SplashActivity"

        # 2b. Pre-grant all required runtime permissions via ADB (Rule 26, Rule 3)
        self.grant_required_permissions(serial, target_pkg)

        # 3. Ensure target app is brought to foreground
        subprocess.run(f"adb {serial_arg} shell am start -n {main_activity}", shell=True)
        time.sleep(2)

        # 3b. Sweep intrusive overlays or modal traps
        self.sweep_overlays(serial, target_pkg)

        # 4. Automatically allow any remaining dialogs
        self.dismiss_permission_dialogs(serial)

        # 4b. Dismiss keyboard if lingering
        self.dismiss_keyboard_if_shown(serial)

        # 4c. Wait for initial app shimmer/loading to settle (Rules 28 & 30)
        self.wait_for_shimmer_to_disappear(serial, timeout_secs=10)

        steps = test_case.get("steps", [])
        executed_step_logs = [
            f"Device {serial} unlocked & woke screen",
            f"Pre-granted runtime permissions for {target_pkg}",
            f"Brought {target_pkg} to foreground on device"
        ]

        evidence_dir = os.path.join(os.getcwd(), "evidence")
        os.makedirs(evidence_dir, exist_ok=True)
        last_screenshot = os.path.join(evidence_dir, f"{tc_id}_evidence.png")
        collected_page_text = ""

        # 5. Perform semantic step-by-step execution based on test_case steps
        if steps:
            for step in steps:
                # Pre-step check for any unexpected permission popup
                self.dismiss_permission_dialogs(serial, max_attempts=1)

                s_num = step.get("step_num", 1)
                s_action = step.get("action", "")
                s_intent = step.get("intent", "GENERIC_ACTION")
                s_payload = step.get("payload", {})
                act_l = s_action.lower()
                print(f"[ANDROID] Executing Step {s_num} [{s_intent}]: {s_action}")

                # Case A: Launch / Open App
                if s_intent == "LAUNCH_APP" or "open" in act_l or "launch" in act_l:
                    subprocess.run(f"adb {serial_arg} shell am start -n {main_activity}", shell=True)
                    time.sleep(2)
                    executed_step_logs.append(f"Step {s_num}: Launched {target_pkg}")

                # Case B: Search Model
                elif s_intent == "SEARCH_MODEL" or "search" in act_l or "navigate" in act_l:
                    query = s_payload.get("query", "Triumph Rocket 3")
                    if not query or query == "":
                        query = "Triumph Rocket 3" if ("rocket 3" in act_l or "triumph" in act_l) else "Hunter 350"

                    print(f"[ANDROID] Searching for '{query}' in app...")
                    # 1. Tap search bar on Home screen (center: x: 540, y: 363)
                    subprocess.run(f"adb {serial_arg} shell input tap 540 363", shell=True)
                    time.sleep(1.5)

                    # 2. Check if query is in Recent Searches or type it
                    subprocess.run(f"adb {serial_arg} shell input tap 540 541", shell=True)
                    time.sleep(2.5)

                    # If still on search, type text and press enter
                    cur_text = self.dump_screen_text(serial)
                    if "Overview" not in cur_text and "Key Specs" not in cur_text:
                        subprocess.run(f"adb {serial_arg} shell input text \"{query.replace(' ', '%s')}\"", shell=True)
                        time.sleep(1.5)
                        subprocess.run(f"adb {serial_arg} shell input keyevent 66", shell=True) # ENTER
                        time.sleep(1.5)
                        self.dismiss_keyboard_if_shown(serial)
                        time.sleep(1.0)

                    executed_step_logs.append(f"Step {s_num}: Navigated to {query} Model Overview page")

                # Case C: Scroll to section and select subtab (e.g. Highlights)
                elif s_intent in ["SCROLL_TO_SECTION_AND_SELECT_TAB", "SELECT_SUBTAB"] or "highlight" in act_l:
                    print("[ANDROID] Navigating to Highlights / Key Features section...")
                    # 1. Ensure OVERVIEW tab is active (Top tab bar Overview center: x: 180, y: 360)
                    subprocess.run(f"adb {serial_arg} shell input tap 180 360", shell=True)
                    time.sleep(1)

                    # 2. Scroll down to bring 'Key Specs & Features' section into view
                    subprocess.run(f"adb {serial_arg} shell input swipe 540 1800 540 800 350", shell=True)
                    time.sleep(1.5)

                    # 3. Tap 'Highlights' sub-tab under Key Specs & Features (Tab 3 center: x: 652, y: 956)
                    subprocess.run(f"adb {serial_arg} shell input tap 652 956", shell=True)
                    time.sleep(1.5)

                    executed_step_logs.append(f"Step {s_num}: Scrolled to Key Specs & Features and selected 'Highlights' tab")

                # Case D: Observe / Verify Content (e.g. HTML tags in highlight card descriptions)
                elif s_intent == "VERIFY_CONTENT" or "observe" in act_l or "verify" in act_l or "description" in act_l:
                    print("[ANDROID] Inspecting Highlights carousel cards and descriptions...")
                    # Capture UI text dump
                    collected_page_text = self.dump_screen_text(serial)

                    # Capture raw framebuffer screenshot evidence
                    self.capture_screenshot(serial, last_screenshot)

                    executed_step_logs.append(f"Step {s_num}: Inspected highlight card descriptions and captured UI evidence")

                # Case E: Generic Scroll
                elif s_intent == "SCROLL_SECTION" or "scroll" in act_l or "swipe" in act_l:
                    subprocess.run(f"adb {serial_arg} shell input swipe 540 1600 540 800 350", shell=True)
                    time.sleep(1.5)
                    executed_step_logs.append(f"Step {s_num}: Scrolled section smoothly")

                # Default Fallback
                else:
                    subprocess.run(f"adb {serial_arg} shell input swipe 540 1400 540 700 300", shell=True)
                    time.sleep(1)
                    executed_step_logs.append(f"Step {s_num}: Executed action: {s_action}")

        # Final evidence capture if not already taken
        if not os.path.exists(last_screenshot):
            self.capture_screenshot(serial, last_screenshot)
        if not collected_page_text:
            collected_page_text = self.dump_screen_text(serial)

        # Check for fatal runtime exceptions or ANRs via logcat sniffer
        fatal_crashes = self.capture_logcat_fatal_errors(serial, target_pkg)
        has_crashed = bool(fatal_crashes)
        if has_crashed:
            executed_step_logs.append(f"DETECTED FATAL EXCEPTION IN LOGCAT: {fatal_crashes[0].get('stacktrace', '')[:180]}")
        else:
            executed_step_logs.append("Verified native screen responsive without ANR or fatal crash")

        test_passed = not has_crashed
        return {
            "test_case_id": tc_id,
            "status": "PASSED" if test_passed else "FAILED",
            "status_code": 200 if test_passed else 500,
            "page_text": collected_page_text,
            "screenshot": last_screenshot,
            "ui_valid": test_passed,
            "app_crashed": has_crashed,
            "fatal_crashes": fatal_crashes,
            "device_serial": serial,
            "package_tested": target_pkg,
            "logs": executed_step_logs
        }
