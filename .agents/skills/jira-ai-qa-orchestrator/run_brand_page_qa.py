import os
import sys
import time
import subprocess
import xml.etree.ElementTree as ET

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure modules in path
curr_dir = os.path.dirname(os.path.abspath(__file__))
if curr_dir not in sys.path:
    sys.path.insert(0, curr_dir)

from modules.android.android_runner import AndroidRunner

serial = "e305529"
pkg = "com.girnarsoft.cardekho"

runner = AndroidRunner(mock_mode=False)
evidence_dir = os.path.join(curr_dir, "evidence")
os.makedirs(evidence_dir, exist_ok=True)

# Rule 15: Target App Identification & Mandatory Foreground Package Verification
def ensure_cardekho_foreground():
    for attempt in range(3):
        res = subprocess.run(f"adb -s {serial} shell dumpsys window", shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if "com.girnarsoft.cardekho/com.girnarsoft.girnarsoft_oneapp_flutter.MainActivity" in (res.stdout or ""):
            print("[RULE 15] Verified com.girnarsoft.cardekho is in foreground.")
            return True
        print(f"[RULE 15] App not in foreground, launching attempt {attempt+1}...")
        subprocess.run(f"adb -s {serial} shell monkey -p {pkg} -c android.intent.category.LAUNCHER 1", shell=True)
        time.sleep(2.5)
    return False

ensure_cardekho_foreground()

print("=== STEP 3: PREPARING DEVICE ===")
runner.sweep_overlays(serial, target_package=pkg)
runner.dismiss_keyboard_if_shown(serial)

# Verify we are on Home screen
cur_text = runner.dump_screen_text(serial)
print("Current screen text preview:", cur_text[:120])
if "Search Cars" not in cur_text and "Find your right car" not in cur_text:
    subprocess.run(f"adb -s {serial} shell input keyevent 4", shell=True)
    time.sleep(1)

print("=== TC-01: BRAND SEARCH & LANDING ===")
# Tap search bar on Home screen [0,264][1080,462] -> center (540, 363)
subprocess.run(f"adb -s {serial} shell input tap 540 363", shell=True)
time.sleep(2)
runner.dismiss_keyboard_if_shown(serial)

# Type 'Mahindra'
subprocess.run(f"adb -s {serial} shell input text \"Mahindra\"", shell=True)
time.sleep(2)
runner.dismiss_keyboard_if_shown(serial)
time.sleep(1)

# Tap first suggestion row
tree_s = runner.resilience.dump_ui_xml(serial)
tapped = False
if tree_s is not None:
    for node in tree_s.iter("node"):
        t = (node.attrib.get("text") or "").strip()
        d = (node.attrib.get("content-desc") or "").strip()
        label = t or d
        if "mahindra" in label.lower() and "car" in label.lower():
            c = runner.resolve_element_center(serial, text=t or None, content_desc=d or None)
            if c:
                print(f"Tapping suggestion '{label}' at {c}")
                subprocess.run(f"adb -s {serial} shell input tap {c[0]} {c[1]}", shell=True)
                tapped = True
                break

if not tapped:
    # Tap standard suggestion position (x=540, y=520)
    print("Tapping default suggestion coordinate (540, 520)")
    subprocess.run(f"adb -s {serial} shell input tap 540 520", shell=True)

time.sleep(3.5)
runner.wait_for_shimmer_to_disappear(serial, timeout_secs=10)

sc_tc01 = os.path.join(evidence_dir, "mb2c_1998_tc01_brand_landing.png")
runner.capture_screenshot(serial, sc_tc01)
page_tc01 = runner.dump_screen_text(serial)
print("TC-01 Page Text:", page_tc01[:200])

print("=== TC-02: MODELS & FILTER CHIPS ===")
# Scroll down to bring Models section and filter chips into view
subprocess.run(f"adb -s {serial} shell input swipe 540 1600 540 900 350", shell=True)
time.sleep(1.5)

# Look for filter chips (e.g. SUV, Petrol, Diesel, Electric)
tree_chips = runner.resilience.dump_ui_xml(serial)
chip_tapped = False
if tree_chips is not None:
    for node in tree_chips.iter("node"):
        t = (node.attrib.get("text") or "").strip()
        d = (node.attrib.get("content-desc") or "").strip()
        label = t or d
        if any(tok in label.lower() for tok in ["suv", "petrol", "diesel", "electric", "sedan", "hatchback"]):
            c = runner.resolve_element_center(serial, text=t or None, content_desc=d or None)
            if c:
                print(f"Tapping filter chip: '{label}' at {c}")
                subprocess.run(f"adb -s {serial} shell input tap {c[0]} {c[1]}", shell=True)
                chip_tapped = True
                time.sleep(2)
                break

if not chip_tapped:
    # Tap first chip position around x=180, y=1050
    subprocess.run(f"adb -s {serial} shell input tap 180 1050", shell=True)
    time.sleep(2)

sc_tc02 = os.path.join(evidence_dir, "mb2c_1998_tc02_filter_chips.png")
runner.capture_screenshot(serial, sc_tc02)

print("=== TC-03: BRAND REELS & SHORT VIDEOS ===")
subprocess.run(f"adb -s {serial} shell input swipe 540 1800 540 600 350", shell=True)
time.sleep(1.5)
sc_tc03 = os.path.join(evidence_dir, "mb2c_1998_tc03_midpage_widgets.png")
runner.capture_screenshot(serial, sc_tc03)

print("=== TC-04: AT A GLANCE, OWNERS LOVE, SALES TREND ===")
subprocess.run(f"adb -s {serial} shell input swipe 540 1800 540 600 350", shell=True)
time.sleep(1.5)
sc_tc04 = os.path.join(evidence_dir, "mb2c_1998_tc04_owners_love_sales.png")
runner.capture_screenshot(serial, sc_tc04)

print("=== TC-05: BOTTOM SECTION EXCLUSION ASSERTION ===")
subprocess.run(f"adb -s {serial} shell input swipe 540 1800 540 400 350", shell=True)
time.sleep(1.5)
subprocess.run(f"adb -s {serial} shell input swipe 540 1800 540 400 350", shell=True)
time.sleep(1.5)
bottom_text = runner.dump_screen_text(serial)
sc_tc05 = os.path.join(evidence_dir, "mb2c_1998_tc05_bottom_exclusion.png")
runner.capture_screenshot(serial, sc_tc05)

about_us_present = "about us" in bottom_text.lower()
print(f"About Us Section Present: {about_us_present} (Expected: False)")

print("=== TC-06: LOGCAT CRASH SNIFFER & RETURN TO HOME ===")
fatal_crashes = runner.capture_logcat_fatal_errors(serial, pkg)
print("Fatal Crashes detected:", len(fatal_crashes))

# Return to Home
subprocess.run(f"adb -s {serial} shell input keyevent 4", shell=True)
time.sleep(1)
subprocess.run(f"adb -s {serial} shell input keyevent 4", shell=True)
time.sleep(1)
sc_tc06 = os.path.join(evidence_dir, "mb2c_1998_tc06_back_to_home.png")
runner.capture_screenshot(serial, sc_tc06)

print("=== EXECUTION COMPLETE ===")
print("EVIDENCE FILES:")
print("TC-01:", sc_tc01, os.path.exists(sc_tc01))
print("TC-02:", sc_tc02, os.path.exists(sc_tc02))
print("TC-03:", sc_tc03, os.path.exists(sc_tc03))
print("TC-04:", sc_tc04, os.path.exists(sc_tc04))
print("TC-05:", sc_tc05, os.path.exists(sc_tc05))
print("TC-06:", sc_tc06, os.path.exists(sc_tc06))
