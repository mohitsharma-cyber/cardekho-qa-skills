"""
Device check script to verify connected physical Android device via ADB,
retrieve device details (serial, model, Android version), and verify CarDekho app package.
"""

import json
import subprocess
import sys


def run_adb(command):
    try:
        res = subprocess.run(f"adb {command}", shell=True, capture_output=True, text=True)
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except Exception as e:
        return -1, "", str(e)


def check_connected_device():
    rc, out, err = run_adb("devices")
    if rc != 0 or not out:
        print("[ERROR] ADB is not available or ADB command failed.")
        print(f"Details: {err}")
        return None

    lines = [line.strip() for line in out.split("\n") if line.strip()]
    devices = []
    for line in lines[1:]:  # Skip 'List of devices attached'
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])

    if not devices:
        print("[ERROR] No physical Android device connected via ADB.")
        print("Please connect an Android device via USB and enable USB Debugging.")
        return None

    device_serial = devices[0]
    print(f"[SUCCESS] Connected Device Detected: {device_serial}")

    # Fetch device model and Android version
    _, model, _ = run_adb(f"-s {device_serial} shell getprop ro.product.model")
    _, brand, _ = run_adb(f"-s {device_serial} shell getprop ro.product.brand")
    _, os_ver, _ = run_adb(f"-s {device_serial} shell getprop ro.build.version.release")
    _, sdk_ver, _ = run_adb(f"-s {device_serial} shell getprop ro.build.version.sdk")

    print(f"   Model: {brand} {model}")
    print(f"   Android OS: {os_ver} (SDK {sdk_ver})")

    # Check for CarDekho packages
    known_packages = [
        "com.cardekho.android.debug",
        "com.cardekho.android",
        "com.girnarsoft.cardekho.debug",
        "com.girnarsoft.cardekho"
    ]
    installed_packages = []
    _, pkg_out, _ = run_adb(f"-s {device_serial} shell pm list packages cardekho")
    for line in pkg_out.splitlines():
        if line.startswith("package:"):
            installed_packages.append(line.replace("package:", "").strip())

    found_pkg = None
    for p in known_packages + installed_packages:
        if p in installed_packages:
            found_pkg = p
            break

    if found_pkg:
        print(f"[SUCCESS] Target Package Found: {found_pkg}")
    else:
        print(f"[WARNING] No known CarDekho package found in installed packages: {installed_packages}")
        print("Defaulting to 'com.cardekho.android.debug'")
        found_pkg = "com.cardekho.android.debug"

    device_info = {
        "serial": device_serial,
        "brand": brand,
        "model": model,
        "os_version": os_ver,
        "sdk_version": sdk_ver,
        "package_name": found_pkg,
        "installed_packages": installed_packages
    }

    return device_info


if __name__ == "__main__":
    info = check_connected_device()
    if info:
        print("\n" + json.dumps(info, indent=2))
        sys.exit(0)
    else:
        sys.exit(1)
