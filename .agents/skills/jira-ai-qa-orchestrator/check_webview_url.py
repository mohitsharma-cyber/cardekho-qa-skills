import subprocess
import re

serial = "e305529"
res = subprocess.run(f"adb -s {serial} logcat -d -t 300", shell=True, capture_output=True, text=True, errors="replace")
lines = res.stdout.split("\n")
matches = [l for l in lines if any(k in l.lower() for k in ["sell", "origin", "webview", "url", "cardekho"])]
for m in matches[-30:]:
    print(m)
