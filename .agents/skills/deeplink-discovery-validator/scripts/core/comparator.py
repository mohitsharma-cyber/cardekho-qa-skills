"""
Regression Comparator & Diff Engine.
Compares Baseline Deep Links against Current / Discovered Links.
"""

try:
    from .normalizer import normalize_url
except Exception:
    from core.normalizer import normalize_url


class DeepLinkComparator:
    """Computes regression diffs between baseline and newly discovered/validated links."""

    @staticmethod
    def compare(
        baseline_records: List[Dict[str, Any]],
        current_records: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Performs a full diff between baseline dataset and current dataset.
        
        Outputs:
            merged_records: List containing all records with comparison status
            summary_stats: High level diff metrics
        """
        baseline_map = {}
        for r in baseline_records:
            url = r.get("Deep Link", "")
            canon_key, _ = normalize_url(url, strip_volatile=True)
            if canon_key:
                baseline_map[canon_key] = r

        current_map = {}
        for r in current_records:
            url = r.get("Deep Link", "")
            canon_key, _ = normalize_url(url, strip_volatile=True)
            if canon_key:
                current_map[canon_key] = r

        merged_results = []
        stats = {
            "baseline_count": len(baseline_records),
            "current_count": len(current_records),
            "unchanged_count": 0,
            "changed_count": 0,
            "new_count": 0,
            "removed_count": 0,
            "broken_count": 0,
            "redirected_count": 0
        }

        # 1. Process current records against baseline
        for r in current_records:
            url = r.get("Deep Link", "")
            canon_key, norm_url = normalize_url(url, strip_volatile=True)
            r["Normalized Deep Link"] = norm_url

            if canon_key in baseline_map:
                base_r = baseline_map[canon_key]
                # Inherit expected screen from baseline if missing
                if not r.get("Expected Screen") and base_r.get("Screen"):
                    r["Expected Screen"] = base_r.get("Screen")
                if not r.get("Module") and base_r.get("Module"):
                    r["Module"] = base_r.get("Module")

                # Check status
                status = r.get("Status", "ACTIVE")
                if status == "ACTIVE":
                    stats["unchanged_count"] += 1
                elif status == "REDIRECTED":
                    stats["redirected_count"] += 1
                elif status == "BROKEN":
                    stats["broken_count"] += 1
            else:
                # Newly discovered link
                if r.get("Status") not in ("BROKEN", "DUPLICATE"):
                    r["Status"] = "NEW"
                stats["new_count"] += 1
                if not r.get("Remarks"):
                    r["Remarks"] = "Newly discovered link in current build"

            merged_results.append(r)

        # 2. Check for missing baseline links (REMOVED)
        for canon_key, base_r in baseline_map.items():
            if canon_key not in current_map:
                removed_record = dict(base_r)
                removed_record["Status"] = "REMOVED"
                removed_record["Remarks"] = "Link present in baseline sheet but missing from current discovery"
                stats["removed_count"] += 1
                merged_results.append(removed_record)

        return merged_results, stats
