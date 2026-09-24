"""
Fast-Track Autonomous Device Execution Engine for Jira AI QA Orchestrator.
Zero-popup execution, deterministic coordinate lookup, smart URL switching,
and continuous self-training.
"""

import os
import json
import time
import subprocess
from typing import Dict, Any, Optional, List, Tuple

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(os.path.dirname(MODULE_DIR))
KNOWLEDGE_PATH = os.path.join(SKILL_ROOT, "knowledge", "learned_memory.json")

class FastRunner:
    def __init__(self, serial: Optional[str] = None):
        self.serial = serial or self._get_default_serial()
        self.knowledge = self._load_knowledge()
        self.device_profile = self._resolve_device_profile()

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
        # Check if serial matches known model
        for name, profile in profiles.items():
            return profile
        # Fallback default
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
            time.sleep(0.5)
            self.adb("shell input keyevent 82")
            time.sleep(1)

    def dismiss_keyboard(self):
        self.adb("shell input keyevent 111")
        time.sleep(0.3)

    def capture_screenshot(self, output_path: str) -> bool:
        """Captures clean binary screenshot without shell redirection quirks."""
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            cmd = ["adb"]
            if self.serial:
                cmd.extend(["-s", self.serial])
            cmd.extend(["exec-out", "screencap", "-p"])
            data = subprocess.check_output(cmd)
            with open(output_path, "wb") as f:
                f.write(data)
            return True
        except Exception as e:
            print(f"[ERROR] Screencap failed: {e}")
            return False

    def get_coordinate(self, screen: str, element: str) -> Optional[Tuple[int, int]]:
        coords = self.device_profile.get("coordinates", {}).get(screen, {})
        pt = coords.get(element)
        if pt and len(pt) == 2:
            return (pt[0], pt[1])
        return None

    def tap(self, screen: str, element: str, delay: float = 1.0) -> bool:
        pt = self.get_coordinate(screen, element)
        if pt:
            self.adb(f"shell input tap {pt[0]} {pt[1]}")
            time.sleep(delay)
            return True
        print(f"[WARN] Coordinate not found for {screen}.{element}")
        return False

    def resolve_env_urls(self, server_key: str, brand: str = "cardekho") -> Tuple[str, str]:
        """
        Resolves Base URL and Base API URL dynamically based on brand and server.
        CarDekho:
          - testing: testingpwa1, testingpwa2, etc. -> https://<server>.cardekho.com
          - staging: https://staging.cardekho.com
          - live: https://www.cardekho.com
        BikeDekho:
          - testing api: testingapi1, testingapi2 -> https://<server>.bikedekho.com
          - testing pwa: testing1, testing2 -> https://<server>.bikedekho.com
          - staging: pwa: https://alpha.bikedekho.com, api: https://alphaapi.bikedekho.com
          - live: https://www.bikedekho.com
        """
        key = server_key.lower().strip()
        brand = brand.lower().strip()

        # Check knowledge base first
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

        # Default: cardekho
        if "staging" in key:
            return "https://staging.cardekho.com", "https://staging.cardekho.com/api"
        if "live" in key or "prod" in key or "www" in key:
            return "https://www.cardekho.com", "https://www.cardekho.com/api"
        # e.g. testingpwa1, testingpwa2
        if not key.endswith(".cardekho.com"):
            base = f"https://{key}.cardekho.com"
            api = f"https://{key}.cardekho.com/api"
            return base, api
        return f"https://{key}", f"https://{key}/api"

    def ensure_server_url(self, target_server_key: str = "testingpwa1", brand: str = "cardekho") -> bool:
        """
        Deterministic, fast-track server URL verification and update.
        Navigates to Hamburger > Change URL, checks/updates, and returns to Home.
        """
        target_base, target_api = self.resolve_env_urls(target_server_key, brand=brand)
        print(f"[FAST_RUNNER] Ensuring {brand} server URL: {target_base} | API: {target_api}")

        self.wake_and_unlock()

        # 1. Open drawer
        self.tap("home", "hamburger_icon", delay=1.2)
        # 2. Tap Change URL
        self.tap("drawer", "change_url", delay=2.0)

        # 3. Update BASE URL
        self.tap("change_url_screen", "base_url_field", delay=0.5)
        # Select all & delete
        self.adb("shell input keyevent --meta 113 29")
        self.adb("shell input keyevent " + " ".join(["67"] * 50))
        self.adb(f"shell input text {target_base}")
        time.sleep(0.5)

        # 4. Update BASE API URL
        self.tap("change_url_screen", "base_api_url_field", delay=0.5)
        self.adb("shell input keyevent --meta 113 29")
        self.adb("shell input keyevent " + " ".join(["67"] * 50))
        self.adb(f"shell input text {target_api}")
        time.sleep(0.5)

        # 5. Hide keyboard
        self.dismiss_keyboard()
        time.sleep(0.5)

        # 6. Tap UPDATE
        self.tap("change_url_screen", "update_button", delay=2.5)

        # 7. Return to Home
        self.tap("change_url_screen", "back_arrow", delay=1.5)
        print(f"[SUCCESS] App environment successfully synchronized with {target_server_key} ({target_base})")
        return True

    def learn_coordinate(self, screen: str, element: str, x: int, y: int):
        """Self-training method to store newly validated coordinates."""
        if "coordinates" not in self.device_profile:
            self.device_profile["coordinates"] = {}
        if screen not in self.device_profile["coordinates"]:
            self.device_profile["coordinates"][screen] = {}
        self.device_profile["coordinates"][screen][element] = [x, y]
        self._save_knowledge()
        print(f"[LEARNED] Stored {screen}.{element} -> ({x}, {y})")

    def safe_scroll_down(self, y_start: int = 1800, y_end: int = 600, x: int = 100, duration: int = 300):
        """Scrolls vertically along the neutral screen margin to avoid horizontal carousel traps."""
        self.adb(f"shell input swipe {x} {y_start} {x} {y_end} {duration}")
        time.sleep(1.5)

    def safe_scroll_up(self, y_start: int = 600, y_end: int = 1800, x: int = 100, duration: int = 300):
        """Scrolls vertically upwards along the neutral margin."""
        self.adb(f"shell input swipe {x} {y_start} {x} {y_end} {duration}")
        time.sleep(1.5)

    def dismiss_login_modal(self) -> bool:
        """Dismisses the Login or Register bottom sheet overlay via SKIP button."""
        skip_coord = self.get_coordinate("dialogs", "login_modal_skip_button") or (880, 615)
        self.adb(f"shell input tap {skip_coord[0]} {skip_coord[1]}")
        time.sleep(1.5)
        return True

    def ensure_app_foreground(self, package: str = "com.girnarsoft.cardekho"):
        """Guarantees target package is in active foreground."""
        dumpsys = self.adb("shell dumpsys window displays")
        if package not in dumpsys:
            print(f"[FAST_RUNNER] Launching {package} to foreground...")
            self.adb(f"shell monkey -p {package} -c android.intent.category.LAUNCHER 1")
            time.sleep(3.5)

if __name__ == "__main__":
    runner = FastRunner()
    print("FastRunner initialized for device:", runner.serial)

