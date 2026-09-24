"""
Canonical URL Normalizer and Parameter Sanitizer for CarDekho Deep Links.
Preserves original raw URLs while creating clean canonical comparison keys.
"""

import re
import urllib.parse
from typing import Dict, Any, Tuple, Optional


DEFAULT_VOLATILE_PARAMS = {
    "connectoid",
    "sessionid",
    "timestamp",
    "_t",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
    "_format"
}

MODULE_KEYWORD_MAP = {
    "home": ("Home", "Home Page"),
    "menu": ("Menu", "Hamburger Menu"),
    "recommend": ("New Cars", "Recommended New Cars"),
    "tuc": ("Used Cars", "Trustmark Used Cars (TUC)"),
    "newcar": ("New Cars", "New Cars Filter/Listing"),
    "newcars": ("New Cars", "New Cars Listing"),
    "latest": ("New Cars", "Latest Cars"),
    "upcoming": ("New Cars", "Upcoming Cars"),
    "popular": ("New Cars", "Popular Cars"),
    "electric": ("Electric Vehicles", "Electric Cars"),
    "charging-station": ("EV Infrastructure", "EV Charging Stations"),
    "pwamodeloverview": ("Model Overview", "Model Overview Tab"),
    "modeloverview": ("Model Overview", "Model Overview Tab"),
    "modelprice": ("Model Price", "Model Price Tab"),
    "pwamodelspecs": ("Model Specs", "Model Specs Tab"),
    "gallery": ("Model Gallery", "Model Gallery Tab"),
    "colors": ("Model Colors", "Model Colors Tab"),
    "car-variant": ("Variant Detail", "Variant Detail Page"),
    "compare": ("Compare Cars", "Compare Cars Landing/Details"),
    "news": ("News & Reviews", "News Article / Listing"),
    "user-review": ("User Reviews", "User Reviews Listing/Details"),
    "detailed-user-review": ("User Reviews", "Detailed User Review Page"),
    "road-test": ("Road Tests", "Road Test Review Page"),
    "offer": ("Offers & Discounts", "Brand Offers & Discounts"),
    "dealer": ("Dealers & Services", "Dealer / Service Center Search"),
    "spare-parts": ("Spare Parts", "Spare Parts Price Page"),
    "pwaservicecost": ("Service Cost", "Service Cost Page"),
    "search": ("Search", "Search Results Page"),
    "cities": ("Location", "City Selection Landing"),
    "videos": ("Videos", "Car Videos Page"),
    "trendingftccars": ("360 View", "Feel The Car 360"),
    "ftc": ("360 View", "Feel The Car 360")
}


def clean_text(text: Any) -> str:
    """Removes ANSI escape codes, zero-width chars, and leading/trailing whitespace."""
    if not isinstance(text, str):
        return "" if text is None else str(text).strip()
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    cleaned = ansi_escape.sub('', text)
    cleaned = "".join(ch for ch in cleaned if ch in ('\n', '\t') or ord(ch) >= 32)
    return cleaned.strip()


def infer_module_and_screen(url: str, default_page_name: str = "") -> Tuple[str, str]:
    """Infers high-level module and screen name from URL structure and baseline names."""
    if default_page_name and default_page_name.lower() not in ("nan", "none", ""):
        page_clean = default_page_name.strip()
        # Find matching module
        for kw, (mod, _) in MODULE_KEYWORD_MAP.items():
            if kw in page_clean.lower() or kw in url.lower():
                return mod, page_clean
        return "General", page_clean

    if not url:
        return "General", "Unknown Screen"

    lower_url = url.lower()
    for kw, (mod, scr) in MODULE_KEYWORD_MAP.items():
        if kw in lower_url:
            return mod, scr

    # Fallback to path segment
    try:
        parsed = urllib.parse.urlparse(url)
        path_parts = [p for p in parsed.path.split('/') if p and p not in ('api', 'v1', 'v2', 'v3', 'v5', 'v8')]
        if path_parts:
            segment = path_parts[0].replace('-', ' ').title()
            return segment, f"{segment} Page"
    except Exception:
        pass

    return "General", "General Screen"


def normalize_url(raw_url: str, strip_volatile: bool = True) -> Tuple[str, str]:
    """
    Normalizes a deep link URL into a canonical comparison key.
    
    Returns:
        (canonical_url, sanitized_display_url)
    """
    if not raw_url or not isinstance(raw_url, str):
        return "", ""

    raw_clean = clean_text(raw_url)
    if not raw_clean or raw_clean.lower() in ("nan", "none"):
        return "", ""

    # Parse scheme and components
    try:
        # Handle unescaped characters
        parsed = urllib.parse.urlparse(raw_clean)
    except Exception:
        return raw_clean, raw_clean

    scheme = parsed.scheme.lower() if parsed.scheme else "cardekho"
    netloc = parsed.netloc.lower() if parsed.netloc else ""
    path = parsed.path

    # Normalize multiple slashes in path
    path = re.sub(r'/+', '/', path)
    if len(path) > 1 and path.endswith('/'):
        path = path[:-1]

    # Parse and sort query parameters
    query_dict = urllib.parse.parse_qs(parsed.query, keep_blank_values=False)
    
    # Filter out volatile parameters for canonical key
    canonical_query_items = []
    display_query_items = []

    for k, v_list in sorted(query_dict.items()):
        k_clean = k.strip()
        v_clean = [v.strip() for v in v_list if v.strip()]
        if not v_clean:
            continue
        
        # Add to display query
        for val in v_clean:
            display_query_items.append((k_clean, val))

        # Check volatile
        if strip_volatile and k_clean.lower() in DEFAULT_VOLATILE_PARAMS:
            continue

        for val in v_clean:
            canonical_query_items.append((k_clean, val))

    canonical_query = urllib.parse.urlencode(canonical_query_items, doseq=True)
    display_query = urllib.parse.urlencode(display_query_items, doseq=True)

    # Canonicalize custom app scheme vs web scheme for cross-comparison
    # E.g. cardekho://model/nexon vs https://www.cardekho.com/model/nexon
    canonical_host = netloc
    if canonical_host in ("www.cardekho.com", "cardekho.com", "m.cardekho.com"):
        canonical_host = "cardekho.com"

    canonical_url = urllib.parse.urlunparse((
        scheme,
        canonical_host,
        path,
        parsed.params,
        canonical_query,
        ""
    ))

    sanitized_display_url = urllib.parse.urlunparse((
        parsed.scheme or "cardekho",
        netloc,
        path,
        parsed.params,
        display_query,
        parsed.fragment
    ))

    return canonical_url, sanitized_display_url
