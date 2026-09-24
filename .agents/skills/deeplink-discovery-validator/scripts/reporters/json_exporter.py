"""
Machine-Readable JSON Exporter for Deep Link Discovery & Validation.
Enables downstream integration with CI/CD, Jira Bug Creator, and Mobile Test Case Generators.
"""

import os
import json
from typing import List, Dict, Any


class JsonExporter:
    """Exports structured validation and diff results in JSON format."""

    @classmethod
    def export(
        cls,
        records: List[Dict[str, Any]],
        summary_stats: Dict[str, Any],
        output_path: str
    ) -> str:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        payload = {
            "metadata": {
                "tool": "deeplink-discovery-validator",
                "version": "1.0.0",
                "app": "CarDekho Android",
                "timestamp": summary_stats.get("timestamp", ""),
                "total_records": len(records),
                "statistics": summary_stats
            },
            "inventory": records,
            "broken_links": [r for r in records if r.get("Status") == "BROKEN"],
            "changed_links": [r for r in records if r.get("Status") == "CHANGED"],
            "new_links": [r for r in records if r.get("Status") == "NEW"]
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        return output_path
