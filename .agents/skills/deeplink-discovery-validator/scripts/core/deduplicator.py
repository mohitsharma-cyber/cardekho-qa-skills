"""
Duplicate Detection and Redundancy Consolidation Engine.
Identifies exact URI duplicates and semantic clones across discovery sources.
"""

from typing import List, Dict, Any, Tuple
from collections import defaultdict

try:
    from .normalizer import normalize_url
except Exception:
    from core.normalizer import normalize_url


class Deduplicator:
    """Consolidates deep link inventories and tags duplicate items."""

    def __init__(self):
        self.seen_canonical = {}
        self.seen_raw = set()

    def process_links(self, link_records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Deduplicates a list of link records.
        Marks redundant links with Status='DUPLICATE' and attaches references to the primary canonical record.
        """
        unique_records = []
        duplicate_records = []
        stats = {
            "total_input": len(link_records),
            "unique_canonical": 0,
            "duplicates_flagged": 0
        }

        canonical_map = defaultdict(list)

        for record in link_records:
            raw_url = record.get("Deep Link", "").strip()
            if not raw_url:
                continue

            canonical_key, normalized_display = normalize_url(raw_url, strip_volatile=True)
            record["Normalized Deep Link"] = normalized_display

            # Check if we already have this canonical key
            if canonical_key in canonical_map:
                primary = canonical_map[canonical_key][0]
                record["Status"] = "DUPLICATE"
                record["Remarks"] = f"Duplicate of primary entry (Row {primary.get('Index', 1)}): {primary.get('Deep Link')}"
                duplicate_records.append(record)
                stats["duplicates_flagged"] += 1
            else:
                record["_canonical_key"] = canonical_key
                canonical_map[canonical_key].append(record)
                unique_records.append(record)

        stats["unique_canonical"] = len(unique_records)
        
        # Combine unique items and flagged duplicates
        combined = unique_records + duplicate_records
        return combined, stats
