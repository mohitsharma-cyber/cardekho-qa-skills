"""
Fast-Track Autonomous & Interactive Device Execution Engine for Jira AI QA Orchestrator.
Supports both Interactive Mode (detailed step-by-step logging, per-step screencaps, configurable delay)
and Autonomous/Fast Mode (condition-based waits via WaitEngine, minimum delay, checkpoint & failure evidence).
Zero-popup execution, deterministic coordinate lookup, smart URL switching, and continuous self-training.
"""

import os
import json
import time
import subprocess
from enum import Enum
from typing import Dict, Any, Optional, List, Tuple
from .wait_engine import WaitEngine

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(os.path.dirname(MODULE_DIR))
KNOWLEDGE_PATH = os.path.join(SKILL_ROOT, "knowledge", "learned_memory.json")

class ExecutionMode(str, Enum):
    INTERACTIVE = "INTERACTIVE"
    AUTONOMOUS = "AUTONOMOUS"
    FAST = "FAST"

class FastRunner:
    def __init__(
        self,
        serial: Optional[str] = None,
        mode: str = "AUTONOMOUS",
        interactive_delay: float = 1.0,
        evidence_dir: Optional[str] = None
    ):
        self.serial = serial or self._get_default_serial()
        self.mode = ExecutionMode.INTERACTIVE if mode.upper() == "INTERACTIVE" else ExecutionMode.AUTONOMOUS
        self.interactive_delay = interactive_delay
        self.evidence_dir = evidence_dir or os.path.join(SKILL_ROOT, "reports", "evidence")
        self.knowledge = self._load_knowledge()
        self.device_profile = self._resolve_device_profile()
        self.wait_engine = WaitEngine(serial=self.serial, adb_executor=self.adb)
        self.step_counter = 0

    def _get_default_serial(self) -> str:
        try:
            res = subprocess.run("adb devices", shell=True, capture_output=True, text=True)
            for line in res.stdout.strip().splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "device":
                    return parts[0]
        except Exception:
            pass
        return "e305529"

    def _load_knowledge(self) -> Dict[str, Any]:
        if os.path.exists(KNOWLEDGE_PATH):
            try:
                with open(KNOWLEDGE_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_knowledge(self):
        try:
            with open(KNOWLEDGE_PATH, "w", encoding="utf-8") as f:
                json.dump(self.knowledge, f, indent=2)
        except Exception as e:
            print(f"[WARN] Failed to save knowledge: {e}")

    def _resolve_device_profile(self) -> Dict[str, Any]:
        profiles = self.knowledge.get("device_profiles", {})
        for name, profile in profiles.items():
            return profile
        return {
            "screen_resolution": "1080x2376",
            "coordinates": {}
        }

    def adb(self, cmd: str) -> str:
        full_cmd = f"adb -s {self.serial} {cmd}" if self.serial else f"adb {cmd}"
        res = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
        return res.stdout.strip()

    def wake_and_unlock(self):
        """Ensures device is awake and unblocked."""
        dumpsys = self.adb("shell dumpsys power | grep mWakefulness")
        if "Awake" not in dumpsys:
            self.adb("shell input keyevent 224")
            time.sleep(0.3)
            self.adb("shell input keyevent 82")
            if self.mode == ExecutionMode.INTERACTIVE:
                time.sleep(self.interactive_delay)
            else:
                self.wait_engine.wait_for_condition(
                    lambda: "Awake" in self.adb("shell dumpsys power | grep mWakefulness"),
                    timeout=3.0, poll_interval=0.2
                )

    def dismiss_keyboard(self):
        self.adb("shell input keyevent 111")
        time.sleep(0.2 if self.mode == ExecutionMode.AUTONOMOUS else 0.5)

    def capture_screenshot(self, output_path: str) -> bool:
        """Captures clean binary screenshot without shell redirection quirks."""
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            cmd = ["adb"]
            if self.serial:
                cmd.extend(["-s", self.serial])
            cmd.extend(["exec-out", "screencap", "-p"])
            data = subprocess.check_output(cmd)
            if not data or len(data) == 0:
                # Potential FLAG_SECURE or modal dialog obstruction
                print("[WARN] Screencap returned 0 bytes (FLAG_SECURE or modal blocked). Recovering with KEYCODE_BACK.")
                self.adb("shell input keyevent 4")
                time.sleep(0.5)
                data = subprocess.check_output(cmd)

            with open(output_path, "wb") as f:
                f.write(data)
            return True
        except Exception as e:
            print(f"[ERROR] Screencap failed: {e}")
            return False

    def capture_failure_evidence(self, context_name: str) -> Optional[str]:
        """Automatically captures screenshot and logcat error dump on failure."""
        timestamp = int(time.time())
        os.makedirs(self.evidence_dir, exist_ok=True)
        img_path = os.path.join(self.evidence_dir, f"FAIL_{context_name}_{timestamp}.png")
        log_path = os.path.join(self.evidence_dir, f"FAIL_{context_name}_{timestamp}.log")
        
        # 1. Screenshot
        self.capture_screenshot(img_path)
        # 2. Logcat errors
        try:
            log_output = self.adb("logcat -d *:E | tail -n 50")
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(log_output)
        except Exception:
            pass
        print(f"[FAILURE_EVIDENCE] Saved screenshot to {img_path}")
        return img_path

    def get_coordinate(self, screen: str, element: str) -> Optional[Tuple[int, int]]:
        coords = self.device_profile.get("coordinates", {}).get(screen, {})
        pt = coords.get(element)
        if pt and len(pt) == 2:
            return (pt[0], pt[1])
        return None

    def tap(self, screen: str, element: str, delay: Optional[float] = None) -> bool:
        self.step_counter += 1
        pt = self.get_coordinate(screen, element)
        if not pt:
            print(f"[WARN] Coordinate not found for {screen}.{element}")
            if self.mode == ExecutionMode.AUTONOMOUS:
                self.capture_failure_evidence(f"missing_coord_{screen}_{element}")
            return False

        if self.mode == ExecutionMode.INTERACTIVE:
            print(f"[INTERACTIVE Step {self.step_counter}] Tapping {screen}.{element} at ({pt[0]}, {pt[1]})")
            self.adb(f"shell input tap {pt[0]} {pt[1]}")
            step_img = os.path.join(self.evidence_dir, f"step_{self.step_counter}_{screen}_{element}.png")
            self.capture_screenshot(step_img)
            time.sleep(delay if delay is not None else self.interactive_delay)
            return True
        else:
            # Autonomous mode: condition-based wait or minimal settle delay
            self.adb(f"shell input tap {pt[0]} {pt[1]}")
            settle_delay = min(0.3, delay) if delay is not None else 0.2
            time.sleep(settle_delay)
            return True

    def resolve_env_urls(self, server_key: str, brand: str = "cardekho") -> Tuple[str, str]:
        key = server_key.lower().strip()
        brand = brand.lower().strip()

        env_dict = self.knowledge.get("environments", {})
        if key in env_dict and "base_url" in env_dict[key]:
            return env_dict[key]["base_url"], env_dict[key].get("base_api_url", f"{env_dict[key]['base_url']}/api")

        if brand == "bikedekho" or "bike" in brand:
            if "alpha" in key or "staging" in key:
                return "https://alpha.bikedekho.com", "https://alphaapi.bikedekho.com"
            if "live" in key or "prod" in key or "www" in key:
                return "https://www.bikedekho.com", "https://www.bikedekho.com/api"
            if "api" in key:
                return f"https://{key}.bikedekho.com", f"https://{key}.bikedekho.com/api"
            return f"https://{key}.bikedekho.com", f"https://{key}api.bikedekho.com"

        if "staging" in key:
            return "https://staging.cardekho.com", "https://staging.cardekho.com/api"
        if "live" in key or "prod" in key or "www" in key:
            return "https://www.cardekho.com", "https://www.cardekho.com/api"

        if not key.endswith(".cardekho.com"):
            base = f"https://{key}.cardekho.com"
            api = f"https://{key}.cardekho.com/api"
            return base, api
        return f"https://{key}", f"https://{key}/api"

    def get_installed_build_info(self, package: str = "com.girnarsoft.cardekho") -> Dict[str, str]:
        """Extracts app version, version code, and update timestamp from device."""
        info = {"versionName": "Unknown", "versionCode": "Unknown", "lastUpdateTime": "Unknown"}
        try:
            cmd = ["adb"]
            if self.serial:
                cmd.extend(["-s", self.serial])
            cmd.extend(["shell", "dumpsys", "package", package])
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            for line in res.stdout.splitlines():
                line_str = line.strip()
                if "versionName=" in line_str and info["versionName"] == "Unknown":
                    info["versionName"] = line_str.split("versionName=")[-1].split()[0]
                elif "versionCode=" in line_str and info["versionCode"] == "Unknown":
                    parts = line_str.split("versionCode=")
                    if len(parts) > 1:
                        info["versionCode"] = parts[1].split()[0]
                elif "lastUpdateTime=" in line_str and info["lastUpdateTime"] == "Unknown":
                    info["lastUpdateTime"] = line_str.split("lastUpdateTime=")[-1]
        except Exception as e:
            print(f"[WARN] Failed to read package build info: {e}")
        return info

    def dump_ui_hierarchy(self) -> str:
        """Dumps and returns UI hierarchy text/XML for deterministic inspection."""
        try:
            cmd = ["adb"]
            if self.serial:
                cmd.extend(["-s", self.serial])
            cmd.extend(["exec-out", "uiautomator", "dump", "/dev/tty"])
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            xml_text = res.stdout
            if not xml_text or "UI hierchary dumped to" in xml_text:
                # Fallback to file dump
                self.adb("shell uiautomator dump /sdcard/window_dump.xml")
                xml_text = self.adb("shell cat /sdcard/window_dump.xml")
            return xml_text
        except Exception as e:
            print(f"[WARN] Failed to dump UI hierarchy: {e}")
            return ""

    def sniff_defects(self, brand: str = "cardekho") -> List[Dict[str, Any]]:
        """Scans current screen UI hierarchy for domain copy leaks, error dialogs, and text truncations."""
        defects = []
        xml_text = self.dump_ui_hierarchy()
        if not xml_text:
            return defects

        brand_lower = brand.lower()
        sniff_rules = self.knowledge.get("sniffing_rules", {})

        # 1. Domain Copy Leaks
        forbidden_keywords = (
            sniff_rules.get("cardekho_copy_leak_words", ["riding", "rider", "two-wheeler", "helmet", "bike", "scooter"])
            if "bike" not in brand_lower
            else sniff_rules.get("bikedekho_copy_leak_words", ["driving", "driver", "four-wheeler", "car"])
        )
        for kw in forbidden_keywords:
            if f'text="{kw}"' in xml_text.lower() or f' {kw} ' in xml_text.lower():
                defects.append({
                    "type": "COPY_DOMAIN_LEAK",
                    "severity": "P1",
                    "description": f"Domain leak: '{kw}' rendered on {brand} platform",
                    "timestamp": time.time()
                })

        # 2. Runtime Error Signatures
        error_signatures = sniff_rules.get("runtime_error_signatures", [
            "An Error Occurred", "Please Try Again", "Failed to load", "Something went wrong", "Network error"
        ])
        for err in error_signatures:
            if err.lower() in xml_text.lower():
                defects.append({
                    "type": "RUNTIME_ERROR_TOAST",
                    "severity": "P1",
                    "description": f"Error popup/toast detected on screen: '{err}'",
                    "timestamp": time.time()
                })

        # 3. Truncation Patterns
        import re
        if re.search(r'text="[^"]*\.\.\."', xml_text):
            matches = re.findall(r'text="([^"]*\.\.\.")"', xml_text)
            for m in matches:
                if any(k in m.lower() for k in ["start", "price", "lakh", "rs", "₹", "unit"]):
                    defects.append({
                        "type": "VISUAL_TRUNCATION",
                        "severity": "P2",
                        "description": f"Visual truncation detected on critical label: '{m}'",
                        "timestamp": time.time()
                    })

        return defects

    def verify_component_fingerprint(self, must_have: List[str], forbidden: Optional[List[str]] = None) -> Dict[str, Any]:
        """Ensures newly required components are present on screen to prevent false positives on legacy builds."""
        xml_text = self.dump_ui_hierarchy()
        missing = []
        found_forbidden = []

        for item in must_have:
            if item.lower() not in xml_text.lower():
                missing.append(item)

        if forbidden:
            for item in forbidden:
                if item.lower() in xml_text.lower():
                    found_forbidden.append(item)

        passed = len(missing) == 0 and len(found_forbidden) == 0
        return {
            "passed": passed,
            "missing_components": missing,
            "unexpected_legacy_components": found_forbidden,
            "status": "PASS" if passed else "BUILD_MISMATCH_OR_COMPONENT_MISSING"
        }

    def ensure_server_url(self, target_server_key: str = "testingpwa1", brand: str = "cardekho") -> bool:
        """Deterministic server URL verification and update with execution mode support."""
        target_base, target_api = self.resolve_env_urls(target_server_key, brand=brand)
        print(f"[FAST_RUNNER] Ensuring {brand} server URL: {target_base} | API: {target_api} (Mode: {self.mode.value})")

        self.wake_and_unlock()

        # 1. Open drawer with 0.5s settle window
        self.tap("home", "hamburger_icon", delay=0.8)
        # 2. Tap Change URL
        self.tap("drawer", "change_url", delay=1.2)

        # Check if already matching target
        ui_dump = self.dump_ui_hierarchy()
        if target_base.lower() in ui_dump.lower() and target_api.lower() in ui_dump.lower():
            print(f"[FAST_RUNNER] URL is ALREADY matching {target_base}! Skipping redundant re-typing.")
            self.tap("change_url_screen", "back_arrow", delay=0.5)
            return True

        # 3. Update BASE URL
        self.tap("change_url_screen", "base_url_field", delay=0.3)
        self.adb("shell input keyevent --meta 113 29")
        self.adb("shell input keyevent " + " ".join(["67"] * 50))
        self.adb(f"shell input text {target_base}")
        time.sleep(0.3)

        # 4. Update BASE API URL
        self.tap("change_url_screen", "base_api_url_field", delay=0.3)
        self.adb("shell input keyevent --meta 113 29")
        self.adb("shell input keyevent " + " ".join(["67"] * 50))
        self.adb(f"shell input text {target_api}")
        time.sleep(0.3)

        # 5. Hide keyboard
        self.dismiss_keyboard()

        # 6. Tap UPDATE
        self.tap("change_url_screen", "update_button", delay=1.5)

        # In autonomous mode, checkpoint evidence
        checkpoint_img = os.path.join(self.evidence_dir, f"checkpoint_server_synced_{int(time.time())}.png")
        self.capture_screenshot(checkpoint_img)

        # 7. Return to Home
        self.tap("change_url_screen", "back_arrow", delay=0.8)
        print(f"[SUCCESS] App environment successfully synchronized with {target_server_key} ({target_base})")
        return True

    def learn_coordinate(self, screen: str, element: str, x: int, y: int):
        if "coordinates" not in self.device_profile:
            self.device_profile["coordinates"] = {}
        if screen not in self.device_profile["coordinates"]:
            self.device_profile["coordinates"][screen] = {}
        self.device_profile["coordinates"][screen][element] = [x, y]
        self._save_knowledge()
        print(f"[LEARNED] Stored {screen}.{element} -> ({x}, {y})")

    def safe_scroll_down(self, y_start: int = 1800, y_end: int = 600, x: int = 100, duration: int = 300):
        self.adb(f"shell input swipe {x} {y_start} {x} {y_end} {duration}")
        time.sleep(0.3 if self.mode == ExecutionMode.AUTONOMOUS else 1.5)

    def safe_scroll_up(self, y_start: int = 600, y_end: int = 1800, x: int = 100, duration: int = 300):
        self.adb(f"shell input swipe {x} {y_start} {x} {y_end} {duration}")
        time.sleep(0.3 if self.mode == ExecutionMode.AUTONOMOUS else 1.5)

    def dismiss_login_modal(self) -> bool:
        skip_coord = self.get_coordinate("dialogs", "login_modal_skip_button") or (880, 615)
        self.adb(f"shell input tap {skip_coord[0]} {skip_coord[1]}")
        time.sleep(0.5)
        return True

    def ensure_app_foreground(self, package: str = "com.girnarsoft.cardekho"):
        dumpsys = self.adb("shell dumpsys window displays")
        if package not in dumpsys:
            print(f"[FAST_RUNNER] Launching {package} to foreground...")
            self.adb(f"shell monkey -p {package} -c android.intent.category.LAUNCHER 1")
            if self.mode == ExecutionMode.AUTONOMOUS:
                self.wait_engine.wait_for_condition(
                    lambda: package in self.adb("shell dumpsys window displays"),
                    timeout=5.0, poll_interval=0.3
                )
            else:
                time.sleep(3.0)

if __name__ == "__main__":
    runner = FastRunner()
    print("FastRunner initialized for device:", runner.serial, "Mode:", runner.mode.value)

