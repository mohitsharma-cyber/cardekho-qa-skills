"""
Device & App State Management for Deterministic Deep Link Execution.
Wakes screen, dismisses dialogs, unlocks keyguard, and cleanly resets app state.
"""

import subprocess
import time
from typing import Tuple, Optional


def run_adb(cmd: str, serial: Optional[str] = None) -> Tuple[int, str, str]:
    serial_arg = f"-s {serial}" if serial else ""
    full_cmd = f"adb {serial_arg} {cmd}"
    res = subprocess.run(full_cmd, shell=True, capture_output=True, text=True, errors="replace")
    return res.returncode, res.stdout.strip(), res.stderr.strip()


class DeviceStateManager:
    """Manages physical Android device and app lifecycle state."""

    def __init__(self, serial: Optional[str] = None, package_name: str = "com.cardekho.android"):
        self.serial = serial
        self.package_name = package_name

    def wake_and_unlock(self):
        """Wakes screen and unlocks keyguard."""
        run_adb("shell input keyevent 224", self.serial)  # KEYCODE_WAKEUP
        time.sleep(0.3)
        run_adb("shell wm dismiss-keyguard", self.serial)
        run_adb("shell input swipe 540 2000 540 500 150", self.serial)  # Dismiss lockscreen swipe
        time.sleep(0.3)

    def dismiss_system_dialogs(self):
        """Dismisses common system dialogs or location/permission prompts."""
        # Press back key if a modal is visible
        run_adb("shell input keyevent 4", self.serial)  # KEYCODE_BACK

    def reset_app_state(self, soft: bool = True):
        """
        Resets app to clean state.
        If soft=True, navigates back or sends Home intent.
        If soft=False, force stops package and relaunches.
        """
        if soft:
            # Press back twice and home
            run_adb("shell input keyevent 4", self.serial)
            time.sleep(0.2)
            run_adb("shell input keyevent 3", self.serial)  # KEYCODE_HOME
        else:
            run_adb(f"shell am force-stop {self.package_name}", self.serial)
            time.sleep(0.5)
