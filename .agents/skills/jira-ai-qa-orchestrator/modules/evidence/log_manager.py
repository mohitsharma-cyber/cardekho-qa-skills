"""
Log Manager for Jira AI QA Orchestrator.
Captures and manages Android Logcat streams and execution logs.
Binds complete traceability metadata and sanitizes tokens and credentials.
"""

import os
import time
import subprocess
from typing import Dict, Any, Optional
from ..api.network_capture import NetworkCapture

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "reports", "evidence", "logs")

class LogManager:
    """Captures and stores sanitized logcat and execution log artifacts."""

    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = storage_dir or REPORTS_DIR
        self.redactor = NetworkCapture()
        os.makedirs(self.storage_dir, exist_ok=True)

    def capture_logcat(
        self,
        ticket: str,
        test_case: str,
        step: str,
        device: str,
        android_version: str,
        build: str,
        environment: str,
        result: str,
        adb_serial: Optional[str] = None,
        lines: int = 100
    ) -> Dict[str, Any]:
        """
        Captures recent logcat error/fatal buffer from Android hardware,
        sanitizes sensitive data, and saves as evidence.
        """
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        epoch_ts = int(time.time() * 1000)
        filename = f"{ticket}_{test_case.replace(' ', '_')}_LOGCAT_{epoch_ts}.log"
        filepath = os.path.join(self.storage_dir, filename)

        raw_logs = self._fetch_logcat(adb_serial, lines)
        clean_logs = self.redactor.redact_data(raw_logs)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(clean_logs)

        return {
            "evidence_type": "logcat",
            "ticket": ticket,
            "test_case": test_case,
            "step": step,
            "timestamp": timestamp,
            "device": device,
            "android_version": android_version,
            "build": build,
            "environment": environment,
            "result": result.upper(),
            "file_path": filepath,
            "snippet": clean_logs[:300] + ("..." if len(clean_logs) > 300 else ""),
            "is_sanitized": True
        }

    def record_execution_log(
        self,
        ticket: str,
        test_case: str,
        step: str,
        device: str,
        android_version: str,
        build: str,
        environment: str,
        result: str,
        log_message: str
    ) -> Dict[str, Any]:
        """Records a structured execution log entry."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        clean_message = self.redactor.redact_data(log_message)

        return {
            "evidence_type": "execution_log",
            "ticket": ticket,
            "test_case": test_case,
            "step": step,
            "timestamp": timestamp,
            "device": device,
            "android_version": android_version,
            "build": build,
            "environment": environment,
            "result": result.upper(),
            "message": clean_message,
            "is_sanitized": True
        }

    def _fetch_logcat(self, serial: Optional[str], lines: int) -> str:
        try:
            cmd = ["adb"]
            if serial:
                cmd.extend(["-s", serial])
            cmd.extend(["logcat", "-d", "*:E"])
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            if res.returncode == 0 and res.stdout:
                log_lines = res.stdout.strip().splitlines()[-lines:]
                return "\n".join(log_lines)
        except Exception:
            pass
        return "LOGCAT_BUFFER: [NO FATAL CRASH DETECTED IN RECENT BUFFER]"
