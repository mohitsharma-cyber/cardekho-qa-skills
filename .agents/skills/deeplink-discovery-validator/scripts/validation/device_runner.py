"""
ADB Device Runner & Intent Dispatch Engine.
Executes deep links directly via ADB intent on physical Android devices / emulators.
"""

import re
import subprocess
import time
from typing import Dict, Any, Optional, Tuple


def run_adb(cmd: str, serial: Optional[str] = None) -> Tuple[int, str, str]:
    serial_arg = f"-s {serial}" if serial else ""
    full_cmd = f"adb {serial_arg} {cmd}"
    res = subprocess.run(full_cmd, shell=True, capture_output=True, text=True, errors="replace")
    return res.returncode, res.stdout.strip(), res.stderr.strip()


class DeviceRunner:
    """Manages ADB intent execution and device inspection."""

    def __init__(self, serial: Optional[str] = None, package_name: str = "com.cardekho.android.debug"):
        self.serial = serial
        self.package_name = package_name
        self.device_info = {}

    def detect_device(self) -> Optional[Dict[str, Any]]:
        """Detects connected device, OS version, and target app package."""
        rc, out, err = run_adb("devices", self.serial)
        if rc != 0 or not out:
            return None

        lines = [line.strip() for line in out.splitlines() if line.strip()]
        devices = []
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])

        if not devices:
            return None

        active_serial = self.serial if self.serial in devices else devices[0]
        self.serial = active_serial

        _, model, _ = run_adb("shell getprop ro.product.model", active_serial)
        _, brand, _ = run_adb("shell getprop ro.product.brand", active_serial)
        _, os_ver, _ = run_adb("shell getprop ro.build.version.release", active_serial)
        _, sdk_ver, _ = run_adb("shell getprop ro.build.version.sdk", active_serial)

        # Detect installed package
        known_packages = [
            "com.cardekho.android.debug",
            "com.cardekho.android",
            "com.girnarsoft.cardekho.debug",
            "com.girnarsoft.cardekho"
        ]
        installed_packages = []
        _, pkg_out, _ = run_adb("shell pm list packages cardekho", active_serial)
        for line in pkg_out.splitlines():
            if line.startswith("package:"):
                installed_packages.append(line.replace("package:", "").strip())

        found_pkg = self.package_name
        for p in known_packages + installed_packages:
            if p in installed_packages:
                found_pkg = p
                break
        self.package_name = found_pkg

        # Get build version name
        _, dump_out, _ = run_adb(f"shell dumpsys package {found_pkg} | grep versionName", active_serial)
        version_name = ""
        m = re.search(r'versionName=([^\s]+)', dump_out)
        if m:
            version_name = m.group(1)

        self.device_info = {
            "serial": active_serial,
            "brand": brand,
            "model": f"{brand} {model}".strip(),
            "os_version": f"Android {os_ver} (SDK {sdk_ver})",
            "package_name": found_pkg,
            "version_name": version_name or "Unknown"
        }
        return self.device_info

    def launch_deep_link(self, deep_link_url: str, timeout_sec: int = 10) -> Dict[str, Any]:
        """
        Dispatches VIEW intent for deep link URL with wait flag -W.
        """
        result = {
            "launch_status": "FAILED",
            "activity": "",
            "total_time_ms": 0,
            "raw_output": "",
            "error": ""
        }

        # Escape special characters for shell
        escaped_url = deep_link_url.replace("&", r"\&").replace("?", r"\?")
        
        # Command: am start -W -a android.intent.action.VIEW -d "<URI>" -p <package>
        intent_cmd = f"shell am start -W -a android.intent.action.VIEW -d \"{escaped_url}\" -p {self.package_name}"
        rc, out, err = run_adb(intent_cmd, self.serial)

        result["raw_output"] = out

        if "Status: ok" in out:
            result["launch_status"] = "SUCCESS"
        elif "Error:" in out or "Exception" in out:
            result["launch_status"] = "CRASH_OR_ERROR"
            result["error"] = out or err
        elif "Warning: Activity not started" in out:
            result["launch_status"] = "ACTIVITY_NOT_STARTED"
            result["error"] = "Activity already running or not resolved"
        else:
            result["launch_status"] = "DISPATCHED"

        # Parse Activity name
        m_act = re.search(r'Activity:\s*([^\s]+)', out)
        if m_act:
            result["activity"] = m_act.group(1)

        # Parse Launch Time
        m_time = re.search(r'TotalTime:\s*(\d+)', out)
        if m_time:
            result["total_time_ms"] = int(m_time.group(1))

        return result
