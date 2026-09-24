"""
Evidence Vault Collector.
Captures screenshots and filtered logcat crash dumps for failed or changed Deep Links.
"""

import os
import hashlib
import time
try:
    from .device_runner import run_adb
except Exception:
    from validation.device_runner import run_adb


class EvidenceCollector:
    """Manages screenshot capture and logcat diagnostics for deep link validation."""

    def __init__(self, output_dir: str = "output/deeplink_reports/evidence", serial: Optional[str] = None):
        self.output_dir = output_dir
        self.serial = serial
        os.makedirs(self.output_dir, exist_ok=True)

    def _generate_hash(self, url: str) -> str:
        return hashlib.md5(url.encode("utf-8")).hexdigest()[:8]

    def capture_screenshot(self, url: str, status: str = "VALIDATED") -> str:
        """Captures a device screenshot and stores it locally."""
        url_hash = self._generate_hash(url)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{status.lower()}_{url_hash}.png"
        device_tmp = f"/sdcard/{filename}"
        local_path = os.path.join(self.output_dir, filename)

        # Capture on device
        run_adb(f"shell screencap -p {device_tmp}", self.serial)
        # Pull to host
        run_adb(f"pull {device_tmp} \"{local_path}\"", self.serial)
        # Cleanup device
        run_adb(f"shell rm {device_tmp}", self.serial)

        if os.path.exists(local_path):
            return local_path
        return ""

    def capture_logcat(self, url: str, package_name: str = "com.cardekho.android") -> str:
        """Dumps recent fatal/error logcat traces for debugging."""
        url_hash = self._generate_hash(url)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_error_{url_hash}_logcat.txt"
        local_path = os.path.join(self.output_dir, filename)

        # Dump error logcat
        rc, out, _ = run_adb(f"logcat -d -v time *:E ActivityManager:I {package_name}:V", self.serial)
        if out:
            # Keep last 100 lines
            recent_logs = "\n".join(out.splitlines()[-100:])
            with open(local_path, "w", encoding="utf-8") as f:
                f.write(f"Deep Link: {url}\nTimestamp: {timestamp}\n\n{recent_logs}")
            return local_path
        return ""
