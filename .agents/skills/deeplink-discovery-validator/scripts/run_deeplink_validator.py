"""
Master CLI Orchestrator for CarDekho Android Deep Link Discovery & Validator.
Modes:
  Mode 1: VALIDATE EXISTING  (--mode 1 --baseline <path>)
  Mode 2: DISCOVER + VALIDATE (--mode 2 --baseline <path> --apk <path>)
  Mode 3: FULL REFRESH        (--mode 3 --apk <path>)
"""

import argparse
import datetime
import json
import os
import sys
import time

# Ensure package imports work regardless of working directory
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from parsers.baseline_ingestor import BaselineIngestor
from parsers.apk_manifest_parser import ApkManifestParser
from parsers.navigation_graph_parser import NavigationGraphParser
from parsers.web_assetlinks_scraper import WebAssetLinksScraper
from core.normalizer import normalize_url, infer_module_and_screen, clean_text
from core.deduplicator import Deduplicator
from core.comparator import DeepLinkComparator
from core.state_manager import DeviceStateManager
from validation.http_preflight import HttpPreflightChecker
from validation.device_runner import DeviceRunner
from validation.screen_detector import ScreenDetector
from validation.evidence_collector import EvidenceCollector
from reporters.excel_reporter import ExcelReporter
from reporters.json_exporter import JsonExporter


if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def parse_args():
    parser = argparse.ArgumentParser(description="CarDekho Android Deep Link Discovery & Validator CLI")
    parser.add_argument("--mode", type=int, choices=[1, 2, 3], default=1,
                        help="Execution Mode: 1=Validate Existing, 2=Discover+Validate, 3=Full Refresh")
    parser.add_argument("--baseline", type=str, default="input/existing_baseline_sheet.csv",
                        help="Path to baseline Deep Link spreadsheet (CSV or Excel)")
    parser.add_argument("--apk", type=str, default=None,
                        help="Path to CarDekho Android APK file")
    parser.add_argument("--manifest", type=str, default=None,
                        help="Path to extracted AndroidManifest.xml")
    parser.add_argument("--nav-graph", type=str, default=None,
                        help="Path to Android Navigation Graph XML")
    parser.add_argument("--serial", type=str, default=None,
                        help="Specific ADB device serial")
    parser.add_argument("--package", type=str, default="com.cardekho.android.debug",
                        help="Target CarDekho package name")
    parser.add_argument("--output-dir", type=str, default="output/deeplink_reports",
                        help="Directory to save generated reports and evidence")
    parser.add_argument("--skip-device", action="store_true",
                        help="Skip on-device ADB validation and execute HTTP preflight only")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit number of links to test (for smoke validation)")
    return parser.parse_args()


def main():
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)
    evidence_dir = os.path.join(args.output_dir, "evidence")
    os.makedirs(evidence_dir, exist_ok=True)

    print("=" * 75)
    print(" [TOOL] CarDekho Android Deep Link Discovery & Validator ")
    print(f" Execution Mode : Mode {args.mode}")
    print(f" Output Target  : {args.output_dir}")
    print("=" * 75)

    # 1. Device Setup & Pre-check
    device_info = None
    device_runner = None
    screen_detector = None
    state_manager = None
    evidence_collector = EvidenceCollector(evidence_dir, serial=args.serial)

    if not args.skip_device:
        device_runner = DeviceRunner(serial=args.serial, package_name=args.package)
        device_info = device_runner.detect_device()
        if device_info:
            print(f"[DEVICE] Connected: {device_info['model']} ({device_info['os_version']})")
            print(f"[DEVICE] Target Package: {device_info['package_name']} (Build: {device_info['version_name']})")
            screen_detector = ScreenDetector(serial=device_info['serial'])
            state_manager = DeviceStateManager(serial=device_info['serial'], package_name=device_info['package_name'])
            state_manager.wake_and_unlock()
        else:
            print("[WARNING] No ADB device connected. Falling back to HTTP Preflight & Static validation.")

    # 2. Ingestion & Discovery Phase
    baseline_records = []
    discovered_records = []

    # Ingest Baseline (Modes 1 and 2, or optional for Mode 3)
    if args.baseline and os.path.exists(args.baseline):
        print(f"\n[INGEST] Ingesting baseline sheet: {args.baseline}")
        try:
            baseline_records = BaselineIngestor.ingest(args.baseline)
            print(f"[INGEST] Successfully loaded {len(baseline_records)} baseline links.")
        except Exception as e:
            print(f"[ERROR] Failed to ingest baseline: {e}")

    # Discovery (Modes 2 and 3)
    if args.mode in (2, 3):
        print(f"\n[DISCOVERY] Initiating Deep Link discovery...")
        
        # Manifest parsing
        if args.manifest and os.path.exists(args.manifest):
            print(f"[DISCOVERY] Parsing AndroidManifest.xml: {args.manifest}")
            manifest_links = ApkManifestParser.parse_manifest_xml(args.manifest)
            discovered_records.extend(manifest_links)
            print(f"[DISCOVERY] Found {len(manifest_links)} links from manifest.")

        # Nav Graph parsing
        if args.nav_graph and os.path.exists(args.nav_graph):
            print(f"[DISCOVERY] Parsing Navigation Graph: {args.nav_graph}")
            nav_links = NavigationGraphParser.parse_nav_graph(args.nav_graph)
            discovered_records.extend(nav_links)
            print(f"[DISCOVERY] Found {len(nav_links)} links from nav graph.")

    # Determine Active Evaluation Set
    if args.mode == 1:
        target_records = baseline_records
    elif args.mode == 2:
        target_records = baseline_records + discovered_records
    else:  # Mode 3
        target_records = discovered_records if discovered_records else baseline_records

    if not target_records:
        print("[ERROR] No deep links available for validation. Please supply --baseline or --manifest / --apk.")
        sys.exit(1)

    # Apply limit if specified
    if args.limit and args.limit > 0:
        print(f"[INFO] Limiting execution to top {args.limit} links for smoke run.")
        target_records = target_records[:args.limit]

    # 3. Deduplication & Canonicalization
    print(f"\n[DEDUPLICATION] Normalizing and deduplicating {len(target_records)} links...")
    deduplicator = Deduplicator()
    deduped_records, dedup_stats = deduplicator.process_links(target_records)
    print(f"[DEDUPLICATION] Unique canonical links: {dedup_stats['unique_canonical']}, Redundant: {dedup_stats['duplicates_flagged']}")

    # 4. Validation Engine (HTTP Pre-flight + On-Device Intent Launch)
    http_checker = HttpPreflightChecker()
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"\n[VALIDATION] Starting deep link validation pipeline...")
    for idx, record in enumerate(deduped_records, 1):
        raw_url = record.get("Deep Link", "").strip()
        screen_name = record.get("Screen", "Unknown")
        status = record.get("Status", "ACTIVE")

        # Skip execution for duplicate records
        if status == "DUPLICATE":
            continue

        print(f" [{idx:02d}/{len(deduped_records)}] Validating: {screen_name:<25} ({raw_url[:50]}...)")

        # Step 4a: HTTP Preflight Check
        preflight = http_checker.check_url(raw_url)
        record["HTTP Status"] = preflight["http_status"]
        if preflight["redirect_url"]:
            record["Redirect URL"] = preflight["redirect_url"]
            record["Status"] = "REDIRECTED"

        # Step 4b: Device Intent Execution
        if device_info and device_runner:
            # Clean state before launch
            state_manager.reset_app_state(soft=True)
            time.sleep(0.3)

            launch_res = device_runner.launch_deep_link(raw_url)
            record["App Launch Status"] = launch_res["launch_status"]
            record["Build Version"] = device_info.get("version_name", "")
            record["Device"] = device_info.get("model", "")
            record["OS Version"] = device_info.get("os_version", "")
            record["Last Verified"] = current_time

            # Wait for UI render
            time.sleep(1.5)

            # Inspect screen focus
            focus_info = screen_detector.get_focused_window()
            record["Actual Screen"] = focus_info.get("activity") or launch_res.get("activity") or "UnknownActivity"

            # Check UI hierarchy for errors
            ui_info = screen_detector.inspect_ui_hierarchy()
            if ui_info["has_error_dialog"] or launch_res["launch_status"] == "CRASH_OR_ERROR":
                record["Status"] = "BROKEN"
                # Capture failure evidence
                evidence_img = evidence_collector.capture_screenshot(raw_url, status="BROKEN")
                evidence_log = evidence_collector.capture_logcat(raw_url, package_name=device_info["package_name"])
                record["Evidence Path"] = evidence_img or evidence_log
                record["Remarks"] = f"App Crash or Error Dialog encountered. Top Activity: {record['Actual Screen']}"
            elif launch_res["launch_status"] == "SUCCESS":
                if record["Status"] != "REDIRECTED":
                    record["Status"] = "ACTIVE"
                    record["Remarks"] = f"Launched in {launch_res.get('total_time_ms', 0)}ms"
        else:
            record["App Launch Status"] = "SKIPPED (No Device)"
            record["Last Verified"] = current_time
            if record["Status"] != "REDIRECTED":
                record["Status"] = "ACTIVE" if preflight["is_live"] else "NOT_VERIFIABLE"
                record["Remarks"] = preflight["remarks"] or "Static / Preflight Verified"

    # 5. Regression Comparison vs Baseline
    print(f"\n[COMPARISON] Computing regression diff against baseline...")
    final_records, diff_stats = DeepLinkComparator.compare(baseline_records, deduped_records)
    diff_stats["timestamp"] = current_time

    # 6. Report Generation
    excel_path = os.path.join(args.output_dir, "Deep_Link_Inventory.xlsx")
    json_path = os.path.join(args.output_dir, "deeplink_inventory.json")

    print(f"\n[REPORTING] Building Excel Workbook: {excel_path}")
    ExcelReporter.generate_report(final_records, diff_stats, excel_path)

    print(f"[REPORTING] Exporting JSON Summary: {json_path}")
    JsonExporter.export(final_records, diff_stats, json_path)

    # 7. Summary Display
    print("\n" + "=" * 75)
    print(" [SUMMARY] DEEP LINK VALIDATION SUMMARY ")
    print("=" * 75)
    print(f" Total Links Audited   : {len(final_records)}")
    print(f" Active (Live/Passing) : {sum(1 for r in final_records if r.get('Status') == 'ACTIVE')}")
    print(f" Broken (Failing)      : {sum(1 for r in final_records if r.get('Status') == 'BROKEN')}")
    print(f" Changed / Divergent   : {sum(1 for r in final_records if r.get('Status') == 'CHANGED')}")
    print(f" Redirected            : {sum(1 for r in final_records if r.get('Status') == 'REDIRECTED')}")
    print(f" Newly Discovered      : {sum(1 for r in final_records if r.get('Status') == 'NEW')}")
    print(f" Duplicate Aliases     : {sum(1 for r in final_records if r.get('Status') == 'DUPLICATE')}")
    print(f" Not Verifiable        : {sum(1 for r in final_records if r.get('Status') == 'NOT_VERIFIABLE')}")
    print("-" * 75)
    print(f" [REPORT] Excel Report : {os.path.abspath(excel_path)}")
    print(f" [REPORT] JSON Report  : {os.path.abspath(json_path)}")
    print("=" * 75)


if __name__ == "__main__":
    main()
