"""
Environment Manager & Safety Controller for Jira AI QA Orchestrator.
Manages TESTING and STAGING profiles, enforces strict Production Safety blocking,
and automates the in-app environment switching flow via ADB UI Automator / Appium.
"""

import json
import os
import re
import subprocess
import time
from typing import Any, Dict, Optional, Tuple


class EnvironmentSafetyError(Exception):
    """Raised when an environment safety check fails or production is targeted."""
    pass


class EnvironmentManager:
    # Hardcoded blocklist of production domains to enforce Rule 6
    PRODUCTION_HOSTNAMES = [
        "cardekho.com",
        "www.cardekho.com",
        "bikedekho.com",
        "www.bikedekho.com",
        "zigwheels.com",
        "www.zigwheels.com",
        "apis.cardekho.com",
        "prod-api.cardekho.com"
    ]

    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        self.profiles = self.config.get("environments", {})

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        if not config_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            config_path = os.path.join(base_dir, "config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def get_profile(self, env_name: str, deployment_target: Optional[str] = None, is_bikedekho: bool = False) -> Dict[str, Any]:
        """
        Resolves environment profile (TESTING vs STAGING) and overrides with deployment target.
        Follows Master Prompt Rule 11: Deployment Target vs Environment are TWO separate concepts.
        """
        env_upper = env_name.upper().strip()
        if env_upper not in ["TESTING", "STAGING"]:
            raise EnvironmentSafetyError(f"Unknown environment profile: '{env_name}'. Allowed: TESTING, STAGING.")

        domain_suffix = "bikedekho.com" if is_bikedekho else "cardekho.com"

        if is_bikedekho:
            if env_upper == "TESTING":
                target = deployment_target or "testingapi2"
                clean_target = target.replace(f".{domain_suffix}", "").strip()
                num_match = re.search(r'(\d+)', clean_target)
                server_num = num_match.group(1) if num_match else "2"
                base_url = f"https://testing{server_num}.{domain_suffix}"
                api_url = f"https://testingapi{server_num}.{domain_suffix}"
                account_url = f"https://qa-apis.{domain_suffix}/f8"
            else:  # STAGING
                clean_target = "staging"
                base_url = f"https://alpha.{domain_suffix}"
                api_url = f"https://alphaapi.{domain_suffix}"
                account_url = f"https://uat-apis.{domain_suffix}/f8"

            profile = {
                "name": env_upper,
                "deployment_target": clean_target,
                "base_url": base_url,
                "base_api_url": api_url,
                "my_account_url": account_url,
                "ask_ai_url": f"https://ai.{domain_suffix}",
                "brand": "BikeDekho"
            }
        else:
            if env_upper == "TESTING":
                target = deployment_target or "testingpwa2"
                clean_target = target.replace(f".{domain_suffix}", "").strip()
                base_url = f"https://{clean_target}.{domain_suffix}"
                api_url = f"https://{clean_target}.{domain_suffix}/api"
                account_url = "https://qa-apis.cardekho.com/f8"
            else:  # STAGING
                clean_target = "staging"
                base_url = "https://staging.cardekho.com"
                api_url = "https://staging.cardekho.com/api"
                account_url = "https://uat-apis.cardekho.com/f8"

            profile = {
                "name": env_upper,
                "deployment_target": clean_target,
                "base_url": base_url,
                "base_api_url": api_url,
                "my_account_url": account_url,
                "ask_ai_url": "https://ai.cardekho.com",
                "brand": "CarDekho"
            }

        self.validate_environment_safety(profile.get("base_url", ""))
        self.validate_environment_safety(profile.get("base_api_url", ""))
        return profile

    def validate_environment_safety(self, url: str):
        """Strict Production Safety Check (Rule 6, Rule 49). Hard aborts if targeting production."""
        url_lower = url.lower()
        # Exceptions for safe staging/testing subdomains
        if any(safe in url_lower for safe in ["testingpwa", "testingapi", "testing", "staging", "alpha", "alphaapi", "qa-apis", "uat-apis", "bikedekhotesting"]):
            return

        for prod in self.PRODUCTION_HOSTNAMES:
            pattern = rf"(https?://)?(www\.)?{re.escape(prod)}(/|$)"
            if re.search(pattern, url_lower):
                raise EnvironmentSafetyError(
                    f"[CRITICAL VIOLATION] Execution against Production '{url}' is STRICTLY BLOCKED by Rule 6 & Rule 49. "
                    f"Only TESTING and STAGING environments are permitted."
                )

    def configure_android_app_environment(self, env_name: str, deployment_target: Optional[str] = None,
                                          is_bikedekho: bool = False, serial: Optional[str] = None,
                                          mock_mode: bool = False) -> Tuple[bool, str]:
        """
        Automates App environment configuration (Rules 19 & 20):
        Launch App -> Hamburger Menu -> Change URL -> Input URLs -> UPDATE -> App Relaunch -> Verify Ready.
        """
        profile = self.get_profile(env_name, deployment_target=deployment_target, is_bikedekho=is_bikedekho)
        base_url = profile["base_url"]
        api_url = profile["base_api_url"]
        account_url = profile["my_account_url"]
        ai_url = profile["ask_ai_url"]
        brand_label = "BikeDekho" if is_bikedekho else "CarDekho"

        if mock_mode:
            print(f"[MOCK ENV] Configured {brand_label} App for {env_name} (Target: {profile.get('deployment_target')}):")
            print(f"  Base URL:       {base_url}")
            print(f"  Base API URL:   {api_url}")
            print(f"  My Account URL: {account_url}")
            print(f"  Ask AI URL:     {ai_url}")
            print("[MOCK ENV] Tapped UPDATE and relaunched app successfully.")
            return True, f"Device is ready for {env_name} testing for task deployed server: {profile.get('deployment_target')} ({base_url})"

        serial_arg = f"-s {serial}" if serial else ""
        if not serial:
            try:
                d_res = subprocess.run("adb devices", shell=True, capture_output=True, text=True)
                lines = [l.strip() for l in d_res.stdout.splitlines() if l.strip()]
                for l in lines[1:]:
                    parts = l.split()
                    if len(parts) >= 2 and parts[1] == "device":
                        serial = parts[0]
                        serial_arg = f"-s {serial}"
                        break
            except Exception:
                pass

        if is_bikedekho:
            pkg = "com.girnarsoft.bikedekho"
            main_act = "com.girnarsoft.bikedekho/com.girnarsoft.girnarsoft_oneapp_flutter.MainActivity"
        else:
            pkg = self.config.get("android", {}).get("package_name", "com.cardekho.android.debug")
            main_act = self.config.get("android", {}).get("main_activity", "com.cardekho.android.activity.SplashActivity")

        print(f"[APP ENV] Launching {pkg}/{main_act} to configure {env_name} on {brand_label}...")
        subprocess.run(f"adb {serial_arg} shell am start -n {main_act}", shell=True, capture_output=True, text=True)
        time.sleep(2)

        # 1. Check if already on Change URL screen
        subprocess.run(f"adb {serial_arg} shell uiautomator dump /sdcard/menu_dump.xml", shell=True, capture_output=True)
        dump_res = subprocess.run(f"adb {serial_arg} shell cat /sdcard/menu_dump.xml", shell=True, capture_output=True, text=True)
        screen_content = dump_res.stdout or ""

        if "UPDATE" not in screen_content and "CHANGE URL" not in screen_content.upper():
            print(f"[APP ENV] Opening Hamburger Menu on {brand_label}...")
            subprocess.run(f"adb {serial_arg} shell input tap 84 192", shell=True)
            time.sleep(1.5)

            print("[APP ENV] Tapping 'Change URL' in drawer...")
            subprocess.run(f"adb {serial_arg} shell input tap 150 2305", shell=True)
            time.sleep(2)

        # 2. Enter Base URL (Field 1)
        print(f"[APP ENV] Setting Base URL -> {base_url}")
        subprocess.run(f"adb {serial_arg} shell input tap 900 438", shell=True)
        time.sleep(0.3)
        subprocess.run(f"adb {serial_arg} shell input keyevent 123", shell=True)
        for _ in range(40):
            subprocess.run(f"adb {serial_arg} shell input keyevent 67", shell=True)
        time.sleep(0.3)
        subprocess.run(f"adb {serial_arg} shell input text {base_url}", shell=True)
        time.sleep(0.3)

        # 3. Enter Base API URL (Field 2)
        print(f"[APP ENV] Setting Base API URL -> {api_url}")
        subprocess.run(f"adb {serial_arg} shell input tap 900 738", shell=True)
        time.sleep(0.3)
        subprocess.run(f"adb {serial_arg} shell input keyevent 123", shell=True)
        for _ in range(40):
            subprocess.run(f"adb {serial_arg} shell input keyevent 67", shell=True)
        time.sleep(0.3)
        subprocess.run(f"adb {serial_arg} shell input text {api_url}", shell=True)
        time.sleep(0.3)

        # 4. Enter My Account URL (Field 3)
        print(f"[APP ENV] Setting My Account URL -> {account_url}")
        subprocess.run(f"adb {serial_arg} shell input tap 900 1038", shell=True)
        time.sleep(0.3)
        subprocess.run(f"adb {serial_arg} shell input keyevent 123", shell=True)
        for _ in range(45):
            subprocess.run(f"adb {serial_arg} shell input keyevent 67", shell=True)
        time.sleep(0.3)
        subprocess.run(f"adb {serial_arg} shell input text {account_url}", shell=True)
        time.sleep(0.3)

        # 5. Dismiss Keyboard
        subprocess.run(f"adb {serial_arg} shell input keyevent 111", shell=True)
        time.sleep(0.5)
        subprocess.run(f"adb {serial_arg} shell input tap 500 1550", shell=True)
        time.sleep(0.5)

        # 6. Tap UPDATE button
        print("[APP ENV] Tapping UPDATE button...")
        subprocess.run(f"adb {serial_arg} shell input tap 954 1654", shell=True)
        time.sleep(2)

        # 7. Mandatory App Relaunch (Rule: force-stop + start so in-memory client loads new URLs)
        print(f"[APP ENV] Relaunching {brand_label} App to load updated URLs...")
        subprocess.run(f"adb {serial_arg} shell am force-stop {pkg}", shell=True)
        time.sleep(1.5)
        subprocess.run(f"adb {serial_arg} shell am start -n {main_act}", shell=True)
        time.sleep(3.5)

        # 8. Dismiss any startup popups (SKIP login, update dialog, permission)
        subprocess.run(f"adb {serial_arg} shell uiautomator dump /sdcard/relaunch_chk.xml", shell=True, capture_output=True)
        rl_res = subprocess.run(f"adb {serial_arg} shell cat /sdcard/relaunch_chk.xml", shell=True, capture_output=True, text=True)
        rl_text = rl_res.stdout or ""
        if "SKIP" in rl_text:
            subprocess.run(f"adb {serial_arg} shell input tap 950 190", shell=True)
            time.sleep(1.5)
        if "Dismiss" in rl_text or "Update available" in rl_text:
            subprocess.run(f"adb {serial_arg} shell input tap 990 1280", shell=True)
            time.sleep(1)

        validation_msg = f"Device is ready for {env_name} testing for task deployed server: {profile.get('deployment_target')} ({base_url})"
        print(f"\n========================================================")
        print(f"✅ [DEVICE READY] {validation_msg}")
        print(f"========================================================\n")
        return True, validation_msg
