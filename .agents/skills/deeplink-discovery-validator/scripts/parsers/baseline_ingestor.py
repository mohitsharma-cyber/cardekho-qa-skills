"""
Baseline Sheet Ingestion Engine.
Parses legacy and current Deep Link inventory spreadsheets (.csv, .xlsx) with dynamic column detection.
"""

import os
import pandas as pd
try:
    from ..core.normalizer import clean_text, infer_module_and_screen, normalize_url
except Exception:
    from core.normalizer import clean_text, infer_module_and_screen, normalize_url


class BaselineIngestor:
    """Ingests baseline deep link sheets into structured link records."""

    URL_COLUMN_CANDIDATES = [
        "urls",
        "url",
        "deep link",
        "deeplink",
        "app api",
        "app url",
        "endpoint",
        "link",
        "target url",
        "web/wap"
    ]

    PAGE_COLUMN_CANDIDATES = [
        "type",
        "page name",
        "screen name",
        "screen",
        "page",
        "feature",
        "module",
        "screen title",
        "view"
    ]

    @classmethod
    def ingest(cls, file_path: str) -> List[Dict[str, Any]]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Baseline file not found: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".csv":
            # Attempt default read first
            df = pd.read_csv(file_path)
            # If top row is banner (e.g. only 1 column has text), try reading with header row detection
            if df.columns[0].lower() not in cls.URL_COLUMN_CANDIDATES and len([c for c in df.columns if not c.startswith('Unnamed')]) <= 1:
                for skip in range(1, 5):
                    try:
                        temp_df = pd.read_csv(file_path, skiprows=skip)
                        cols = [str(c).lower().strip() for c in temp_df.columns]
                        if any(cand in cols for cand in cls.URL_COLUMN_CANDIDATES):
                            df = temp_df
                            break
                    except Exception:
                        pass
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(file_path)
        else:
            raise ValueError(f"Unsupported baseline file format: {ext}")

        records = []
        col_map = {str(col).lower().strip(): col for col in df.columns}

        # Identify URL column
        url_col = None
        for candidate in cls.URL_COLUMN_CANDIDATES:
            if candidate in col_map:
                url_col = col_map[candidate]
                break

        # Identify Page/Screen column
        page_col = None
        for candidate in cls.PAGE_COLUMN_CANDIDATES:
            if candidate in col_map:
                page_col = col_map[candidate]
                break

        # Fallback: find any column containing http or cardekho in values
        if not url_col:
            for col in df.columns:
                sample_vals = df[col].dropna().astype(str).tolist()[:5]
                if any("http" in v.lower() or "cardekho" in v.lower() for v in sample_vals):
                    url_col = col
                    break

        if not url_col:
            raise ValueError(f"Could not automatically detect URL column in {file_path}. Columns found: {list(df.columns)}")

        for idx, row in df.iterrows():
            raw_url = clean_text(row.get(url_col, ""))
            if not raw_url or raw_url.lower() in ("nan", "none", ""):
                continue

            # Secondary alternate URL (e.g. Web/Wap or Changed column)
            changed_url = ""
            if "changed" in col_map:
                changed_url = clean_text(row.get(col_map["changed"], ""))

            page_name = clean_text(row.get(page_col, "")) if page_col else ""
            module, screen = infer_module_and_screen(raw_url, page_name)
            canonical_url, norm_url = normalize_url(raw_url, strip_volatile=True)

            record = {
                "Deep Link": raw_url,
                "Normalized Deep Link": norm_url,
                "Module": module,
                "Screen": screen,
                "Source": "Baseline Sheet",
                "Discovery Method": "BASELINE_IMPORT",
                "Expected Screen": screen,
                "Actual Screen": "",
                "Status": "ACTIVE",
                "Redirect URL": changed_url if changed_url and changed_url.startswith("http") else "",
                "HTTP Status": "",
                "App Launch Status": "UNVERIFIED",
                "Build Version": "",
                "Device": "",
                "OS Version": "",
                "Last Verified": "",
                "Evidence Path": "",
                "Remarks": ""
            }
            records.append(record)

        return records
