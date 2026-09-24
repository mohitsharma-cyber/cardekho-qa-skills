"""
APK & AndroidManifest.xml Static Intent Filter Parser.
Extracts confirmed VIEW intent-filters and maps them to concrete testable URIs.
"""

import os
import re
import subprocess
import xml.etree.ElementTree as ET
try:
    from ..core.normalizer import infer_module_and_screen, normalize_url
except Exception:
    from core.normalizer import infer_module_and_screen, normalize_url


class ApkManifestParser:
    """Extracts Deep Link intent filters from APKs or AndroidManifest.xml."""

    @classmethod
    def parse_manifest_xml(cls, manifest_path: str, fixtures: Dict[str, str] = None) -> List[Dict[str, Any]]:
        if not os.path.exists(manifest_path):
            raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

        fixtures = fixtures or {
            "brandSlug": "tata",
            "modelSlug": "nexon",
            "variantSlug": "tata-nexon-fearless-plus-s-dark",
            "citySlug": "jaipur",
            "cityId": "269"
        }

        try:
            tree = ET.parse(manifest_path)
            root = tree.getroot()
        except Exception as e:
            # Try parsing with regex if raw binary or corrupted XML
            return cls._parse_manifest_text_fallback(manifest_path, fixtures)

        links = []
        ns = {"android": "http://schemas.android.com/apk/res/android"}

        for activity in root.findall(".//activity") + root.findall(".//activity-alias"):
            activity_name = activity.get("{http://schemas.android.com/apk/res/android}name", "UnknownActivity")

            for intent_filter in activity.findall("intent-filter"):
                # Check for VIEW action
                has_view = False
                for action in intent_filter.findall("action"):
                    if action.get("{http://schemas.android.com/apk/res/android}name") == "android.intent.action.VIEW":
                        has_view = True
                        break

                if not has_view:
                    continue

                # Collect data tags
                schemes = []
                hosts = []
                paths = []
                path_prefixes = []
                path_patterns = []

                for data in intent_filter.findall("data"):
                    s = data.get("{http://schemas.android.com/apk/res/android}scheme")
                    h = data.get("{http://schemas.android.com/apk/res/android}host")
                    p = data.get("{http://schemas.android.com/apk/res/android}path")
                    pp = data.get("{http://schemas.android.com/apk/res/android}pathPrefix")
                    pat = data.get("{http://schemas.android.com/apk/res/android}pathPattern")

                    if s: schemes.append(s)
                    if h: hosts.append(h)
                    if p: paths.append(p)
                    if pp: path_prefixes.append(pp)
                    if pat: path_patterns.append(pat)

                if not schemes:
                    continue

                # Build concrete links
                for scheme in set(schemes):
                    host_list = hosts if hosts else [""]
                    for host in set(host_list):
                        all_routes = paths + path_prefixes + path_patterns
                        if not all_routes:
                            all_routes = ["/"]

                        for route in all_routes:
                            is_pattern = ".*" in route or "{" in route
                            # Replace placeholders with fixtures if pattern
                            concrete_route = route
                            if is_pattern:
                                concrete_route = route.replace(".*", fixtures.get("modelSlug", "nexon"))

                            full_url = f"{scheme}://{host}{concrete_route}"
                            module, screen = infer_module_and_screen(full_url, activity_name)
                            _, norm_url = normalize_url(full_url)

                            links.append({
                                "Deep Link": full_url,
                                "Normalized Deep Link": norm_url,
                                "Module": module,
                                "Screen": screen,
                                "Source": "APK Manifest",
                                "Discovery Method": "STATIC_MANIFEST_ANALYSIS" if not is_pattern else "INFERRED_PATTERN_EXPANSION",
                                "Expected Screen": activity_name,
                                "Actual Screen": "",
                                "Status": "ACTIVE",
                                "Redirect URL": "",
                                "HTTP Status": "",
                                "App Launch Status": "UNVERIFIED",
                                "Build Version": "",
                                "Device": "",
                                "OS Version": "",
                                "Last Verified": "",
                                "Evidence Path": "",
                                "Remarks": f"Extracted from Activity: {activity_name}"
                            })

        return links

    @classmethod
    def _parse_manifest_text_fallback(cls, file_path: str, fixtures: Dict[str, str]) -> List[Dict[str, Any]]:
        """Regex fallback for parsed aapt2 dumps or raw text manifest."""
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        links = []
        # Find schemes and hosts
        schemes = re.findall(r'scheme="([^"]+)"', content)
        hosts = re.findall(r'host="([^"]+)"', content)

        for s in set(schemes):
            if s in ("cardekho", "http", "https"):
                for h in set(hosts) or [""]:
                    url = f"{s}://{h}/"
                    module, screen = infer_module_and_screen(url)
                    links.append({
                        "Deep Link": url,
                        "Normalized Deep Link": url,
                        "Module": module,
                        "Screen": screen,
                        "Source": "APK Manifest Text",
                        "Discovery Method": "STATIC_MANIFEST_ANALYSIS",
                        "Expected Screen": "MainActivity",
                        "Actual Screen": "",
                        "Status": "ACTIVE",
                        "Remarks": "Extracted via text fallback"
                    })
        return links
