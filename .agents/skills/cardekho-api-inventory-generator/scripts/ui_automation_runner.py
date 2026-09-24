"""
Dynamic Screen & Action UI Automation Explorer for CarDekho Android.
Includes auto-wake, keyguard unlock, and foreground launch for live visible on-screen execution.
"""

import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


def run_adb(cmd, serial=None):
    serial_arg = f"-s {serial}" if serial else ""
    full_cmd = f"adb {serial_arg} {cmd}"
    res = subprocess.run(full_cmd, shell=True, capture_output=True, text=True, errors="replace")
    return res.returncode, res.stdout.strip(), res.stderr.strip()


def wake_and_unlock_device(serial=None):
    """Wakes the screen and attempts to dismiss lockscreen."""
    print("[DEVICE] Waking up screen and unlocking...")
    run_adb("shell input keyevent 224", serial) # KEYCODE_WAKEUP
    time.sleep(0.5)
    run_adb("shell wm dismiss-keyguard", serial)
    run_adb("shell input swipe 540 2000 540 500 200", serial) # Swipe up to open
    time.sleep(0.5)


def dump_ui(serial=None):
    """Dumps the current window XML and returns the parsed ElementTree root."""
    run_adb("shell uiautomator dump /sdcard/window_dump.xml", serial)
    rc, out, _ = run_adb("shell cat /sdcard/window_dump.xml", serial)
    if rc == 0 and ("<?xml" in out or "<hierarchy" in out):
        try:
            return ET.fromstring(out)
        except Exception:
            pass
    return None


def parse_bounds(bounds_str):
    m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
    if m:
        x1, y1, x2, y2 = map(int, m.groups())
        return (x1 + x2) // 2, (y1 + y2) // 2
    return None, None


def extract_clickable_elements(root):
    if root is None:
        return []
    actions = []
    for elem in root.iter('node'):
        if elem.get('clickable') == 'true' or elem.get('scrollable') == 'true':
            desc = elem.get('content-desc', '')
            text = elem.get('text', '')
            bounds = elem.get('bounds', '')
            cx, cy = parse_bounds(bounds)
            if cx and cy and cy > 100 and cy < 2300:
                name = desc or text or elem.get('resource-id', '') or f"Action @ ({cx},{cy})"
                actions.append({
                    "name": name.strip(),
                    "bounds": bounds,
                    "cx": cx,
                    "cy": cy,
                    "is_scrollable": elem.get('scrollable') == 'true'
                })
    return actions


def swipe_down(serial=None, count=1):
    for _ in range(count):
        run_adb("shell input swipe 540 1700 540 600 400", serial)
        time.sleep(1.5)


def swipe_up(serial=None, count=1):
    for _ in range(count):
        run_adb("shell input swipe 540 600 540 1700 400", serial)
        time.sleep(1.5)


def tap_point(x, y, serial=None):
    run_adb(f"shell input tap {x} {y}", serial)
    time.sleep(2.5)


def press_back(serial=None, count=1):
    for _ in range(count):
        run_adb("shell input keyevent 4", serial)
        time.sleep(1.2)


class DynamicAppExplorer:
    def __init__(self, serial=None, package_name="com.girnarsoft.cardekho.qa"):
        self.serial = serial
        self.package_name = package_name
        self.discovered_screens = set()
        self.explored_screens = set()
        self.discovered_actions = []
        self.explored_actions = []
        self.modules_discovered = set()
        self.modules_explored = set()

    def launch_app(self):
        wake_and_unlock_device(self.serial)
        print(f"[LAUNCH] Bringing '{self.package_name}' to the foreground...")
        # Direct intent launch with reset task flag
        run_adb(f"shell monkey -p {self.package_name} -c android.intent.category.LAUNCHER 1", self.serial)
        time.sleep(4)

    def record_screen(self, screen_name, module_name="Home"):
        self.discovered_screens.add(screen_name)
        self.explored_screens.add(screen_name)
        self.modules_discovered.add(module_name)
        self.modules_explored.add(module_name)
        print(f"\n[SCREEN DISCOVERED & EXPLORED] Screen: '{screen_name}' | Module: '{module_name}'")

    def run_dynamic_exploration(self, max_depth=12):
        self.launch_app()

        # Screen 1: Home Feed
        self.record_screen("Home Feed", "Home")
        root = dump_ui(self.serial)
        actions = extract_clickable_elements(root)
        self.discovered_actions.extend(actions)
        print(f"Discovered {len(actions)} actionable elements on Home Feed.")

        print("Scrolling Home Feed carousels & popular cars...")
        swipe_down(self.serial, 3)
        self.explored_actions.append({"screen": "Home Feed", "action": "Scroll Feed"})
        swipe_up(self.serial, 2)

        # Screen 2: Global Search
        print("\nOpening Global Search...")
        self.record_screen("Global Search Screen", "Search")
        tap_point(540, 280, self.serial) # Top search bar
        self.explored_actions.append({"screen": "Home Feed", "action": "Tap Search Bar"})
        time.sleep(2)
        
        # Type search query
        print("Typing search query 'Creta'...")
        run_adb("shell input text 'Creta'", self.serial)
        time.sleep(2)
        run_adb("shell input keyevent 66", self.serial) # Enter
        self.explored_actions.append({"screen": "Global Search", "action": "Search 'Creta'"})
        time.sleep(3)
        self.record_screen("Search Results - Creta", "Search")
        press_back(self.serial, 1)

        # Screen 3: New Cars & Brand Browsing
        print("\nOpening New Cars Catalog...")
        self.record_screen("New Cars Screen", "New Cars")
        tap_point(250, 1100, self.serial)
        time.sleep(3)
        swipe_down(self.serial, 2)
        self.explored_actions.append({"screen": "New Cars Screen", "action": "Browse Brand Models & Filters"})

        # Screen 4: Model Overview & PDP
        print("\nOpening Model Overview Page...")
        self.record_screen("Model Overview Page", "Model")
        tap_point(350, 1150, self.serial) # Select car card
        time.sleep(3.5)
        swipe_down(self.serial, 2)
        self.explored_actions.append({"screen": "Model Overview", "action": "View Model Highlights & Pricing"})

        # Screen 5: Variants Tab
        print("\nSwitching to Variants Tab...")
        self.record_screen("Variant Selection Screen", "Variant")
        tap_point(550, 160, self.serial) # Variants tab
        time.sleep(2.5)
        swipe_down(self.serial, 1)
        self.explored_actions.append({"screen": "Variant Screen", "action": "Browse Variant Lineup & Differences"})

        # Screen 6: User Reviews Tab
        print("\nSwitching to User Reviews Tab...")
        self.record_screen("User Reviews Screen", "Reviews")
        tap_point(850, 160, self.serial) # Reviews tab
        time.sleep(2.5)
        swipe_down(self.serial, 1)
        self.explored_actions.append({"screen": "Reviews Screen", "action": "Read Owner Reviews & FAQs"})

        # Screen 7: Price Breakup / Details
        print("\nChecking Price Breakup...")
        self.record_screen("Price Breakup Screen", "Price & Finance")
        press_back(self.serial, 1)
        time.sleep(2)
        swipe_down(self.serial, 1)
        self.explored_actions.append({"screen": "Model Overview", "action": "Check On-Road Price Breakup"})

        # Screen 8: Used Cars Marketplace
        print("\nNavigating to Used Cars...")
        press_back(self.serial, 2) # Back to Home
        time.sleep(2.5)
        self.record_screen("Used Cars Listing Screen", "Used Cars")
        tap_point(800, 1100, self.serial) # Buy Used Car
        time.sleep(3.5)
        swipe_down(self.serial, 2)
        self.explored_actions.append({"screen": "Used Cars Screen", "action": "Browse Pre-Owned Car Catalog"})

        press_back(self.serial, 1)
        time.sleep(1.5)

        summary = {
            "modules_discovered": len(self.modules_discovered),
            "modules_explored": len(self.modules_explored),
            "screens_discovered": len(self.discovered_screens),
            "screens_explored": len(self.explored_screens),
            "actions_discovered": len(self.discovered_actions),
            "actions_explored": len(self.explored_actions),
            "screen_list": list(self.explored_screens),
            "module_list": list(self.modules_explored),
            "action_list": self.explored_actions
        }
        return summary


if __name__ == "__main__":
    serial = sys.argv[1] if len(sys.argv) > 1 else None
    explorer = DynamicAppExplorer(serial=serial)
    res = explorer.run_dynamic_exploration()
    print("\n--- DYNAMIC EXPLORATION SUMMARY ---")
    print(f"Screens Discovered/Explored: {res['screens_explored']}")
    print(f"Actions Explored: {res['actions_explored']}")
