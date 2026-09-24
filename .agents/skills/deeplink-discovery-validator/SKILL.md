---
name: deeplink-discovery-validator
description: Enterprise QA Deep Link Discovery, Ingestion, Normalization, Device Validation, Regression Comparison & Multi-Sheet Excel/CSV Generator for CarDekho Android.
---

# Deep Link Discovery & Validator QA Agent (`deeplink-discovery-validator`)

An enterprise-grade, reusable QA automation skill for the **CarDekho Android** platform. It enables QA engineers to ingest legacy/baseline Deep Link spreadsheets (CSV, Excel, Google Sheets), extract current intent filters & routes from APKs / manifests / navigation graphs / web sources, perform on-device launch validation via ADB, capture screenshot and logcat evidence on failure, detect regressions, and generate a standardized 18-column Excel audit workbook.

---

## 🎯 Supported Modes

### Mode 1: VALIDATE EXISTING
- **Input:** Baseline Deep Link Sheet (CSV or Excel).
- **Action:** Validates every existing Deep Link via HTTP pre-flight and live ADB intent execution on connected device.
- **Output:** Execution status, screen validation, screenshot evidence for every link.
- **Command:**
  ```bash
  python .agents/skills/deeplink-discovery-validator/scripts/run_deeplink_validator.py --mode 1 --baseline input/existing_baseline_sheet.csv
  ```

### Mode 2: DISCOVER + VALIDATE
- **Input:** Baseline Deep Link Sheet + Current APK / App build.
- **Action:** Extracts all new/current Deep Links from APK / Manifest / Nav Graphs, validates both old and newly discovered links on-device, and compares against baseline.
- **Output:** Full inventory with regression tags (`UNCHANGED`, `CHANGED`, `NEW`, `BROKEN`, `REDIRECTED`, `DUPLICATE`).
- **Command:**
  ```bash
  python .agents/skills/deeplink-discovery-validator/scripts/run_deeplink_validator.py --mode 2 --baseline input/existing_baseline_sheet.csv --apk app-release.apk
  ```

### Mode 3: FULL REFRESH
- **Input:** Current APK / App and available discovery sources (Web AssetLinks, Sitemaps, Nav Graphs).
- **Action:** Discovers the complete current Deep Link universe from scratch, validates on-device, and uses old baseline as historical reference.
- **Output:** Brand new comprehensive master inventory workbook.
- **Command:**
  ```bash
  python .agents/skills/deeplink-discovery-validator/scripts/run_deeplink_validator.py --mode 3 --apk app-release.apk
  ```

---

## 📋 18 Canonical Excel Columns

The output workbook `Deep_Link_Inventory.xlsx` generates:
1. `Deep Link`
2. `Normalized Deep Link`
3. `Module`
4. `Screen`
5. `Source`
6. `Discovery Method`
7. `Expected Screen`
8. `Actual Screen`
9. `Status` (`ACTIVE`, `CHANGED`, `BROKEN`, `REDIRECTED`, `NEW`, `DUPLICATE`, `NOT_VERIFIABLE`)
10. `Redirect URL`
11. `HTTP Status`
12. `App Launch Status`
13. `Build Version`
14. `Device`
15. `OS Version`
16. `Last Verified`
17. `Evidence Path`
18. `Remarks`

---

## 🛠️ CLI Options

| Flag | Description | Default |
| :--- | :--- | :--- |
| `--mode` | Execution mode (`1`, `2`, or `3`) | `1` |
| `--baseline` | Path to baseline CSV / Excel file | `None` |
| `--apk` | Path to CarDekho Android APK | `None` |
| `--manifest` | Path to unpacked `AndroidManifest.xml` | `None` |
| `--serial` | Specific ADB device serial | Auto-detected |
| `--package` | Target package name override | Auto-detected (`com.cardekho.android`) |
| `--output-dir` | Target directory for reports & evidence | `output/deeplink_reports` |
| `--skip-device` | Run static and HTTP pre-flight only without ADB device | `False` |
| `--limit` | Limit number of links to test (for quick smoke runs) | `None` |
