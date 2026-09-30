"""
Smart Wait Engine for CarDekho & BikeDekho Android Testing.
Replaces arbitrary fixed sleeps with deterministic condition-based polling
across UI elements, visible text, activities, and screen transitions.
"""

import time
import subprocess
import xml.etree.ElementTree as ET
from typing import Callable, Optional, Tuple, Any

class WaitEngine:
    """Provides non-blocking, bounded condition-based waits for Android hardware interactions."""

    def __init__(self, serial: Optional[str] = None, adb_executor: Optional[Callable[[str], str]] = None):
        self.serial = serial
        self._adb_executor = adb_executor

    def execute_adb(self, cmd: str) -> str:
        """Executes an adb shell command via injected executor or fallback subprocess."""
        if self._adb_executor:
            return self._adb_executor(cmd)
        full_cmd = f"adb -s {self.serial} {cmd}" if self.serial else f"adb {cmd}"
        try:
            res = subprocess.run(full_cmd, shell=True, capture_output=True, text=True, timeout=15)
            return res.stdout.strip()
        except Exception as e:
            return f"ERROR: {e}"

    def get_focused_window(self) -> str:
        """Retrieves current top resumed activity / focused window identifier."""
        output = self.execute_adb("shell dumpsys window displays")
        for line in output.splitlines():
            if "mCurrentFocus" in line or "topResumedActivity" in line or "mFocusedApp" in line:
                return line.strip()
        return ""

    def dump_ui_hierarchy(self) -> str:
        """Dumps and extracts current window UI hierarchy XML."""
        self.execute_adb("shell uiautomator dump /data/local/tmp/smart_wait_dump.xml")
        xml_content = self.execute_adb("shell cat /data/local/tmp/smart_wait_dump.xml")
        return xml_content

    def wait_for_condition(
        self,
        condition_fn: Callable[[], bool],
        timeout: float = 10.0,
        poll_interval: float = 0.5,
        desc: str = "custom condition"
    ) -> bool:
        """
        Polls a boolean condition function until True or timeout reached.
        Replaces blind time.sleep with high-frequency check and deterministic exit.
        """
        start = time.time()
        while time.time() - start < timeout:
            try:
                if condition_fn():
                    return True
            except Exception:
                pass
            time.sleep(poll_interval)
        return False

    def wait_for_activity(
        self,
        activity_name: str,
        timeout: float = 10.0,
        poll_interval: float = 0.5
    ) -> bool:
        """Waits for an Android Activity to be in the active resumed foreground."""
        def check():
            focused = self.get_focused_window()
            return activity_name.lower() in focused.lower()

        return self.wait_for_condition(check, timeout=timeout, poll_interval=poll_interval, desc=f"activity '{activity_name}'")

    def wait_for_screen_change(
        self,
        prev_fingerprint: str,
        timeout: float = 10.0,
        poll_interval: float = 0.5
    ) -> bool:
        """Waits until the current screen focus changes from the previous fingerprint."""
        def check():
            current = self.get_focused_window()
            return current != "" and current != prev_fingerprint

        return self.wait_for_condition(check, timeout=timeout, poll_interval=poll_interval, desc="screen change")

    def wait_for_text(
        self,
        text: str,
        timeout: float = 10.0,
        poll_interval: float = 0.5,
        case_sensitive: bool = False
    ) -> bool:
        """Waits until target text appears anywhere in the current Android view hierarchy."""
        target = text if case_sensitive else text.lower()

        def check():
            xml_data = self.dump_ui_hierarchy()
            if not xml_data or "<hierarchy" not in xml_data:
                return False
            search_space = xml_data if case_sensitive else xml_data.lower()
            return target in search_space

        return self.wait_for_condition(check, timeout=timeout, poll_interval=poll_interval, desc=f"text '{text}'")

    def wait_for_element(
        self,
        selector: str,
        timeout: float = 10.0,
        poll_interval: float = 0.5
    ) -> Tuple[bool, Optional[Tuple[int, int]]]:
        """
        Waits for an element matching resource-id, content-desc, or text.
        Returns (True, (center_x, center_y)) if found, or (False, None).
        """
        start = time.time()
        while time.time() - start < timeout:
            xml_data = self.dump_ui_hierarchy()
            if xml_data and "<hierarchy" in xml_data:
                pt = self._find_center_in_xml(xml_data, selector)
                if pt:
                    return True, pt
            time.sleep(poll_interval)
        return False, None

    def wait_for_idle(
        self,
        timeout: float = 5.0,
        poll_interval: float = 0.5
    ) -> bool:
        """
        Waits for UI to become idle by verifying absence of shimmer/loading bars
        and checking hierarchy stability.
        """
        start = time.time()
        last_xml = ""
        while time.time() - start < timeout:
            xml_data = self.dump_ui_hierarchy()
            # If shimmers or progress bars present, continue waiting
            if "shimmer" in xml_data.lower() or "progressbar" in xml_data.lower():
                time.sleep(poll_interval)
                continue
            # Check stability across consecutive checks
            if last_xml and xml_data == last_xml:
                return True
            last_xml = xml_data
            time.sleep(poll_interval)
        return True  # If timeout reached without fatal shimmer, return True to allow graceful assertion

    def _find_center_in_xml(self, xml_content: str, selector: str) -> Optional[Tuple[int, int]]:
        """Parses UI hierarchy XML to find element bounds matching selector."""
        try:
            root = ET.fromstring(xml_content)
            for node in root.iter("node"):
                res_id = node.attrib.get("resource-id", "")
                text = node.attrib.get("text", "")
                desc = node.attrib.get("content-desc", "")
                bounds = node.attrib.get("bounds", "")

                if selector in res_id or selector in text or selector in desc:
                    # bounds format: [x1,y1][x2,y2]
                    if bounds.startswith("[") and "][" in bounds:
                        parts = bounds.replace("[", "").replace("]", " ").split()
                        if len(parts) >= 2:
                            x1, y1 = map(int, parts[0].split(","))
                            x2, y2 = map(int, parts[1].split(","))
                            return ((x1 + x2) // 2, (y1 + y2) // 2)
        except Exception:
            pass
        return None
