import subprocess
import time
import os

serial = "e305529"
pkg = "com.girnarsoft.cardekho"

# 1. Wake & unlock
subprocess.run(f"adb -s {serial} shell input keyevent 224", shell=True)
subprocess.run(f"adb -s {serial} shell input keyevent 82", shell=True)
subprocess.run(f"adb -s {serial} shell wm dismiss-keyguard", shell=True)
time.sleep(1)

# 2. Grant permissions
perms = [
    "android.permission.POST_NOTIFICATIONS",
    "android.permission.ACCESS_FINE_LOCATION",
    "android.permission.ACCESS_COARSE_LOCATION",
    "android.permission.READ_MEDIA_IMAGES",
    "android.permission.CAMERA",
    "android.permission.READ_EXTERNAL_STORAGE",
    "android.permission.WRITE_EXTERNAL_STORAGE"
]
print("Granting permissions...")
for p in perms:
    r = subprocess.run(f"adb -s {serial} shell pm grant {pkg} {p}", shell=True, capture_output=True, text=True)

# 3. Bring app to foreground
main_activity = "com.cardekho.android.debug/com.cardekho.android.activity.SplashActivity"
subprocess.run(f"adb -s {serial} shell am start -n {main_activity}", shell=True)
time.sleep(3)

# 4. Verify foreground package
res = subprocess.run(f"adb -s {serial} shell dumpsys window displays", shell=True, capture_output=True, text=True)
is_in_focus = pkg in (res.stdout or "")
print(f"App in foreground: {is_in_focus}")

# 5. Capture screenshot
os.makedirs("evidence", exist_ok=True)
sc_local = os.path.join("evidence", "mb2c_1979_01_app_launch.png")
subprocess.run(f"adb -s {serial} shell screencap -p /sdcard/sc.png", shell=True)
subprocess.run(f"adb -s {serial} pull /sdcard/sc.png \"{sc_local}\"", shell=True)
print(f"Screenshot saved: {sc_local}")
