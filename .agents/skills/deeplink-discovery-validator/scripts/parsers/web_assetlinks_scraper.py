"""
Digital Asset Links and Web Route Discovery Engine.
Verifies domain association and extracts valid web routes.
"""

import json
import requests
try:
    from ..core.normalizer import infer_module_and_screen, normalize_url
except Exception:
    from core.normalizer import infer_module_and_screen, normalize_url


class WebAssetLinksScraper:
    """Discovers app links and verified domains from web sources."""

    ASSETLINKS_URL = "https://www.cardekho.com/.well-known/assetlinks.json"

    @classmethod
    def fetch_verified_packages(cls) -> List[str]:
        try:
            res = requests.get(cls.ASSETLINKS_URL, timeout=6)
            if res.status_code == 200:
                data = res.json()
                packages = []
                for entry in data:
                    target = entry.get("target", {})
                    pkg = target.get("package_name")
                    if pkg:
                        packages.append(pkg)
                return list(set(packages))
        except Exception:
            pass
        return []
