"""
Screen Detector & UI Hierarchy Inspector.
Inspects active window focus and UI dump XML to classify the current screen/feature.
"""

import re
import xml.etree.ElementTree as ET
try:
    from .device_runner import run_adb
except Exception:
    from validation.device_runner import run_adb


class ScreenDetector:
    """Detects active Android screen and UI hierarchy components."""

    def __init__(self, serial: Optional[str] = None):
        self.serial = serial

    def get_focused_window(self) -> Dict[str, str]:
        """Gets current focused window from dumpsys window."""
        _, out, _ = run_adb("shell dumpsys window | grep -E \"mCurrentFocus|mFocusedApp\"", self.serial)
        
        info = {
            "focused_app": "",
            "activity": "",
            "package": ""
        }
        
        m = re.search(r'mCurrentFocus=Window\{[^\s]+ [^\s]+ ([^/]+)/([^}]+)\}', out)
        if m:
            info["package"] = m.group(1)
            info["activity"] = m.group(2)
            info["focused_app"] = f"{m.group(1)}/{m.group(2)}"
        return info

    def inspect_ui_hierarchy(self) -> Dict[str, Any]:
        """Dumps UI hierarchy via uiautomator and extracts titles/markers."""
        run_adb("shell uiautomator dump /sdcard/view_dump.xml", self.serial)
        rc, out, _ = run_adb("shell cat /sdcard/view_dump.xml", self.serial)

        res = {
            "screen_title": "",
            "texts_found": [],
            "has_error_dialog": False
        }

        if rc != 0 or not out or "<hierarchy" not in out:
            return res

        try:
            root = ET.fromstring(out)
            texts = []
            for node in root.iter("node"):
                text = node.get("text", "").strip()
                desc = node.get("content-desc", "").strip()
                if text:
                    texts.append(text)
                if desc and desc not in texts:
                    texts.append(desc)

                # Check for crash or error dialog
                if "isn't responding" in text.lower() or "has stopped" in text.lower() or "page not found" in text.lower():
                    res["has_error_dialog"] = True

            res["texts_found"] = texts[:15]
            if texts:
                res["screen_title"] = texts[0]
        except Exception:
            pass

        return res
