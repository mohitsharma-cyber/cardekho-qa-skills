"""
Android Navigation Graph & Route Annotation Parser.
Parses Jetpack Navigation XML files and Jetpack Compose/Kotlin route declarations.
"""

import os
import re
import xml.etree.ElementTree as ET
try:
    from ..core.normalizer import infer_module_and_screen, normalize_url
except Exception:
    from core.normalizer import infer_module_and_screen, normalize_url


class NavigationGraphParser:
    """Parses Android Navigation graph XML files."""

    @classmethod
    def parse_nav_graph(cls, file_path: str) -> List[Dict[str, Any]]:
        if not os.path.exists(file_path):
            return []

        links = []
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            ns = {"app": "http://schemas.android.com/apk/res-auto"}

            for deeplink in root.findall(".//deepLink") + root.findall(".//{http://schemas.android.com/apk/res-auto}deepLink"):
                uri = deeplink.get("{http://schemas.android.com/apk/res-auto}uri") or deeplink.get("uri")
                if uri:
                    module, screen = infer_module_and_screen(uri)
                    _, norm_url = normalize_url(uri)
                    links.append({
                        "Deep Link": uri,
                        "Normalized Deep Link": norm_url,
                        "Module": module,
                        "Screen": screen,
                        "Source": "Navigation Graph",
                        "Discovery Method": "NAV_GRAPH_PARSER",
                        "Expected Screen": screen,
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
                        "Remarks": f"Discovered in {os.path.basename(file_path)}"
                    })
        except Exception:
            pass

        return links
