"""
Visual & Product-Level Design Inspector for CarDekho & BikeDekho QA.
Solves the QA Automation Blind Spot: 'Functional Pass, Visual/Product Fail'.

Pillars:
1. Micro-Copy & Token Leaks (%s, ₹₹, undefined, NaN, missing spaces).
2. Automotive Terminology & Typo Dictionary (Ex-Showrom, Desiel, etc.).
3. Geometry & Bounding-Box Overlap Math (colliding badges, off-screen overflow).
4. Text Truncation & Ellipsis Detector ('Check Off...', '₹ 8,34,...').
5. Severity Tiering: VISUAL_BLOCKER (P0/P1) vs COSMETIC_POLISH (P2/P3).
"""

import re
import xml.etree.ElementTree as ET
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class VisualDefectType(str, Enum):
    TEMPLATE_TOKEN_LEAK = "TEMPLATE_TOKEN_LEAK"
    OVERLAPPING_ELEMENTS = "OVERLAPPING_ELEMENTS"
    TEXT_TRUNCATION = "TEXT_TRUNCATION"
    TYPO_MISMATCH = "TYPO_MISMATCH"
    FORMATTING_ANOMALY = "FORMATTING_ANOMALY"
    OFFSCREEN_OVERFLOW = "OFFSCREEN_OVERFLOW"
    DOMAIN_COPY_LEAK = "DOMAIN_COPY_LEAK"
    RUNTIME_ERROR_TOAST = "RUNTIME_ERROR_TOAST"


class VisualSeverity(str, Enum):
    P0 = "P0"  # Critical Blocker: Unusable / Illegal text / Runtime crash
    P1 = "P1"  # Major: Truncated price / Broken CTA / Template token / Domain copy leak / Error toast
    P2 = "P2"  # Moderate: Overlapping badge / Typo in body copy / Truncated secondary label
    P3 = "P3"  # Minor / Cosmetic Polish: Double space / minor spacing


# Cross-brand copy-paste domain leakage rules
CARDEKHO_FORBIDDEN_TERMS = {
    "riding needs": ("driving needs", "Two-wheeler 'riding needs' terminology leaked into CarDekho car platform"),
    "riding need": ("driving needs", "Two-wheeler 'riding need' terminology leaked into CarDekho car platform"),
    "rider": ("driver", "Two-wheeler 'rider' terminology used instead of 'driver' on CarDekho"),
    "two-wheeler": ("four-wheeler", "Two-wheeler terminology leaked onto CarDekho"),
    "helmet": ("seatbelt", "Two-wheeler 'helmet' terminology leaked onto CarDekho")
}

BIKEDEKHO_FORBIDDEN_TERMS = {
    "driving needs": ("riding needs", "Car 'driving needs' terminology leaked into BikeDekho two-wheeler platform"),
    "steering wheel": ("handlebar", "Car 'steering wheel' terminology leaked onto BikeDekho"),
    "boot space": ("under-seat storage", "Car 'boot space' terminology leaked onto BikeDekho")
}

# Runtime UI Error Toasts and failure banners
RUNTIME_ERROR_PATTERNS = [
    (r"\ban error occurred\b", "Generic unhandled runtime error banner displayed in UI"),
    (r"\bplease try again\b", "Retry/failure prompt indicating network or backend API failure"),
    (r"\bsomething went wrong\b", "Client or API crash fallback banner displayed to user"),
    (r"\bfailed to load\b", "Widget failed to fetch backend response"),
    (r"\bnetwork error\b", "Network connection or gateway timeout banner displayed")
]


# Automotive typos and valid corrections
AUTOMOTIVE_TYPO_MAP = {
    "ex-showrom": "Ex-Showroom",
    "ex showrom": "Ex-Showroom",
    "exshowroom": "Ex-Showroom",
    "onroad price": "On-Road Price",
    "on road price": "On-Road Price",
    "desiel": "Diesel",
    "deisel": "Diesel",
    "petrolium": "Petrol",
    "transmision": "Transmission",
    "transmisson": "Transmission",
    "milage": "Mileage",
    "mielage": "Mileage",
    "downpayment": "Down Payment",
    "per mounth": "Per Month",
    "mounth": "Month",
    "cylender": "Cylinder",
    "cylenders": "Cylinders",
    "clearence": "Clearance",
    "ground clearence": "Ground Clearance",
    "breza": "Brezza",
    "puch": "Punch",
    "safari plus": "Safari",
    "autometic": "Automatic",
    "manul": "Manual"
}


class VisualDesignInspector:
    """Detects designer and product-level UI/UX, copy, and layout defects."""

    def __init__(self):
        pass

    def check_microcopy_tokens(self, text: str) -> List[Dict[str, Any]]:
        """
        Pillar 1: Detects unrendered template tokens, duplicate currency symbols,
        missing concatenation spaces, and translation leaks.
        """
        defects = []
        if not text:
            return defects

        # 1. Unrendered template tokens: %s, %d, {0}, {name}, undefined, null, NaN
        token_patterns = [
            (r"%s", "Unrendered '%s' format string token visible to user", VisualSeverity.P1.value),
            (r"%d", "Unrendered '%d' format integer token visible to user", VisualSeverity.P1.value),
            (r"\{[0-9a-zA-Z_]+\}", "Unreplaced template variable token visible to user", VisualSeverity.P1.value),
            (r"\bundefined\b", "JavaScript / Frontend 'undefined' token rendered in UI", VisualSeverity.P1.value),
            (r"\bnull\b", "Raw backend 'null' string rendered in UI", VisualSeverity.P1.value),
            (r"\bNaN\b", "'NaN' (Not a Number) calculation error rendered in UI", VisualSeverity.P1.value),
        ]
        for pat, desc, sev in token_patterns:
            matches = re.findall(pat, text, re.IGNORECASE if "undefined" in pat or "nan" in pat or "null" in pat else 0)
            if matches:
                defects.append({
                    "type": VisualDefectType.TEMPLATE_TOKEN_LEAK.value,
                    "severity": sev,
                    "actual_value": matches[0],
                    "expected_value": "Properly formatted business value",
                    "description": desc,
                    "remediation": "Ensure backend or client string formatter populates dynamic token."
                })

        # 2. Duplicate currency symbols (e.g. ₹₹, Rs. Rs., ₹ Rs.)
        dup_currency_patterns = [
            (r"₹\s*₹", "Duplicate rupee symbol '₹₹' rendered", VisualSeverity.P1.value),
            (r"Rs\.?\s*Rs\.?", "Duplicate currency symbol 'Rs. Rs.' rendered", VisualSeverity.P1.value),
            (r"₹\s*Rs\.?", "Redundant mixed currency symbol '₹ Rs.' rendered", VisualSeverity.P1.value)
        ]
        for pat, desc, sev in dup_currency_patterns:
            matches = re.findall(pat, text, re.IGNORECASE)
            if matches:
                defects.append({
                    "type": VisualDefectType.FORMATTING_ANOMALY.value,
                    "severity": sev,
                    "actual_value": matches[0],
                    "expected_value": "Single '₹' symbol",
                    "description": desc,
                    "remediation": "Remove redundant currency symbol prefix in layout or response."
                })

        # 3. Missing concatenation spaces (e.g. "Save up to ₹50,000on Maruti")
        concat_patterns = [
            (r"\d+([a-zA-Z]{2,})", "Missing space between numeric amount and following word"),
            (r"(?:save|from|at|to)₹", "Missing space before currency symbol '₹'")
        ]
        for pat, desc in concat_patterns:
            matches = re.finditer(pat, text, re.IGNORECASE)
            for m in matches:
                matched_str = m.group(0)
                # Filter out valid units like 1200cc, 150bhp, 18kmpl, 240Nm
                if re.match(r"^\d+(?:cc|bhp|kmpl|km|nm|ps|l|kg|rpm|m)$", matched_str, re.IGNORECASE):
                    continue
                defects.append({
                    "type": VisualDefectType.FORMATTING_ANOMALY.value,
                    "severity": VisualSeverity.P2.value,
                    "actual_value": matched_str,
                    "expected_value": "Properly spaced words",
                    "description": f"{desc} in '{matched_str}'",
                    "remediation": "Add space delimiter in string formatting."
                })

        # 4. Unrendered translation / resource keys (e.g. text_model_disclaimer_v2, placeholder)
        raw_key_pattern = r"\b(?:text|title|label|desc|btn|button)_[a-zA-Z0-9_]{3,}\b"
        raw_keys = re.findall(raw_key_pattern, text)
        for rk in raw_keys:
            defects.append({
                "type": VisualDefectType.TEMPLATE_TOKEN_LEAK.value,
                "severity": VisualSeverity.P1.value,
                "actual_value": rk,
                "expected_value": "Localized human-readable copy",
                "description": f"Raw unrendered translation key '{rk}' leaked into UI",
                "remediation": "Check strings.xml resource mapping."
            })

        # 5. Punctuation glitches & double spaces
        if "  " in text:
            defects.append({
                "type": VisualDefectType.FORMATTING_ANOMALY.value,
                "severity": VisualSeverity.P3.value,
                "actual_value": "Multiple consecutive spaces",
                "expected_value": "Single space",
                "description": "Double space detected in UI text",
                "remediation": "Trim duplicate whitespace."
            })
        if re.search(r"\s+[,.!?:;]", text):
            defects.append({
                "type": VisualDefectType.FORMATTING_ANOMALY.value,
                "severity": VisualSeverity.P3.value,
                "actual_value": "Space before punctuation",
                "expected_value": "No space before punctuation",
                "description": "Floating punctuation mark with leading space",
                "remediation": "Remove space preceding punctuation."
            })

        return defects

    def check_automotive_spelling(self, text: str) -> List[Dict[str, Any]]:
        """
        Pillar 2: Checks text against known automotive copy typos.
        """
        defects = []
        if not text:
            return defects

        text_lower = text.lower()
        for typo, correction in AUTOMOTIVE_TYPO_MAP.items():
            pattern = r"\b" + re.escape(typo) + r"\b"
            if re.search(pattern, text_lower):
                defects.append({
                    "type": VisualDefectType.TYPO_MISMATCH.value,
                    "severity": VisualSeverity.P2.value,
                    "actual_value": typo,
                    "expected_value": correction,
                    "description": f"Automotive copy typo '{typo}' detected (Expected: '{correction}')",
                    "remediation": f"Update copy to standard brand term '{correction}'."
                })

        return defects

    def check_domain_terminology(self, text: str, brand: str = "cardekho") -> List[Dict[str, Any]]:
        """
        Pillar 2.1: Checks for cross-brand/platform terminology leaks.
        Flags two-wheeler/bike terms on CarDekho, and car terms on BikeDekho.
        """
        defects = []
        if not text:
            return defects

        text_lower = text.lower()
        is_bike = "bike" in str(brand).lower()

        forbidden_map = BIKEDEKHO_FORBIDDEN_TERMS if is_bike else CARDEKHO_FORBIDDEN_TERMS
        platform_name = "BikeDekho" if is_bike else "CarDekho"

        for term, (expected, desc) in forbidden_map.items():
            pattern = r"\b" + re.escape(term) + r"\b"
            if re.search(pattern, text_lower):
                defects.append({
                    "type": VisualDefectType.DOMAIN_COPY_LEAK.value,
                    "severity": VisualSeverity.P1.value,
                    "actual_value": term,
                    "expected_value": expected,
                    "description": f"Domain terminology leak on {platform_name}: '{term}' used (Expected: '{expected}'). {desc}",
                    "remediation": f"Replace '{term}' with '{expected}' appropriate for {platform_name}."
                })

        return defects

    def check_runtime_error_toasts(self, text: str) -> List[Dict[str, Any]]:
        """
        Pillar 2.2: Scans for on-screen runtime error toasts, failure banners,
        and unhandled client/API fallback messages.
        """
        defects = []
        if not text:
            return defects

        text_lower = text.lower()
        for pat, desc in RUNTIME_ERROR_PATTERNS:
            m = re.search(pat, text_lower)
            if m:
                defects.append({
                    "type": VisualDefectType.RUNTIME_ERROR_TOAST.value,
                    "severity": VisualSeverity.P1.value,
                    "actual_value": m.group(0),
                    "expected_value": "Successful UI rendering without runtime error toast",
                    "description": f"Runtime error toast detected on screen: '{m.group(0)}'. {desc}",
                    "remediation": "Investigate failing API endpoint or missing network error handling."
                })

        return defects

    @staticmethod
    def parse_bounds(bounds_str: str) -> Optional[Tuple[int, int, int, int]]:
        """
        Parses Android bounds string: '[x1,y1][x2,y2]' -> (x1, y1, x2, y2).
        """
        if not bounds_str:
            return None
        m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", str(bounds_str).strip())
        if m:
            return int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        return None

    def check_bounding_box_overlaps(
        self,
        elements: List[Dict[str, Any]],
        screen_width: int = 1080,
        screen_height: int = 2400
    ) -> List[Dict[str, Any]]:
        """
        Pillar 3: Calculates geometric collisions between interactive elements,
        badges, and text views; checks for off-screen overflow.
        """
        defects = []
        parsed_elements = []

        for el in elements:
            b_str = el.get("bounds", "")
            coords = self.parse_bounds(b_str)
            if not coords:
                continue
            x1, y1, x2, y2 = coords
            width = x2 - x1
            height = y2 - y1

            # Ignore 0-dimension invisible elements
            if width <= 0 or height <= 0:
                continue

            # 1. Off-screen horizontal overflow (Long city names, wide cards)
            if x2 > screen_width + 10:
                defects.append({
                    "type": VisualDefectType.OFFSCREEN_OVERFLOW.value,
                    "severity": VisualSeverity.P1.value if "button" in el.get("class", "").lower() or "cta" in str(el).lower() else VisualSeverity.P2.value,
                    "element": el.get("text", el.get("resource-id", "Unknown Element")),
                    "actual_value": f"Bounds [{x1},{y1}][{x2},{y2}] exceeds screen width {screen_width}",
                    "expected_value": f"Width <= {screen_width}px",
                    "description": f"Element '{el.get('text', '')[:30]}' overflows screen right edge ({x2}px > {screen_width}px)",
                    "remediation": "Add text wrapping, ellipsize, or max-width constraints."
                })

            parsed_elements.append({
                "info": el,
                "rect": (x1, y1, x2, y2),
                "text": el.get("text", ""),
                "id": el.get("resource-id", ""),
                "class": el.get("class", "")
            })

        # 2. Overlap / Collision Check between siblings
        n = len(parsed_elements)
        for i in range(n):
            for j in range(i + 1, n):
                a = parsed_elements[i]
                b = parsed_elements[j]

                # Do not compare parent-child or identical IDs
                if a["id"] and b["id"] and a["id"] == b["id"]:
                    continue

                ax1, ay1, ax2, ay2 = a["rect"]
                bx1, by1, bx2, by2 = b["rect"]

                # Calculate intersection rectangle
                ix1 = max(ax1, bx1)
                iy1 = max(ay1, by1)
                ix2 = min(ax2, bx2)
                iy2 = min(ay2, by2)

                iw = ix2 - ix1
                ih = iy2 - iy1

                if iw > 0 and ih > 0:
                    intersection_area = iw * ih
                    area_a = (ax2 - ax1) * (ay2 - ay1)
                    area_b = (bx2 - bx1) * (by2 - by1)
                    min_area = min(area_a, area_b)

                    # Substantial overlap (>40% of smaller element) indicates collision
                    if min_area > 0 and (intersection_area / min_area) > 0.40:
                        # Exclude natural layouts (e.g. TextView inside CardView container)
                        is_container_a = "layout" in a["class"].lower() or "viewgroup" in a["class"].lower()
                        is_container_b = "layout" in b["class"].lower() or "viewgroup" in b["class"].lower()
                        if not (is_container_a or is_container_b):
                            t_a = a["text"] or a["id"]
                            t_b = b["text"] or b["id"]
                            defects.append({
                                "type": VisualDefectType.OVERLAPPING_ELEMENTS.value,
                                "severity": VisualSeverity.P1.value if ("btn" in str(a) or "btn" in str(b) or "button" in str(a) or "button" in str(b)) else VisualSeverity.P2.value,
                                "element": f"{t_a} vs {t_b}",
                                "actual_value": f"Collision overlap area: {intersection_area}px² ({int(intersection_area/min_area*100)}%)",
                                "expected_value": "Zero collision / 0px overlap",
                                "description": f"Elements '{t_a[:25]}' and '{t_b[:25]}' visually collide/overlap on screen",
                                "remediation": "Adjust relative constraints or z-index margins."
                            })

        return defects

    def check_text_truncation(self, elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Pillar 4: Detects awkward text truncation or ellipsis ('...' / '…') on
        critical components such as buttons, prices, or header titles.
        """
        defects = []
        for el in elements:
            text = str(el.get("text", "")).strip()
            if not text:
                continue

            # Check if text ends with ellipsis
            if text.endswith("...") or text.endswith("…"):
                cls_name = el.get("class", "").lower()
                res_id = el.get("resource-id", "").lower()
                is_critical = (
                    "button" in cls_name or "btn" in res_id or
                    "price" in res_id or "emi" in res_id or
                    "cta" in res_id or "₹" in text
                )
                defects.append({
                    "type": VisualDefectType.TEXT_TRUNCATION.value,
                    "severity": VisualSeverity.P1.value if is_critical else VisualSeverity.P3.value,
                    "element": el.get("resource-id", el.get("class", "TextView")),
                    "actual_value": text,
                    "expected_value": "Complete, untruncated text",
                    "description": f"Text '{text}' is cut off with ellipsis on {'critical CTA/Price' if is_critical else 'secondary view'}",
                    "remediation": "Increase view container width, reduce font size, or allow multi-line rendering."
                })

        return defects

    def parse_hierarchy_xml(self, xml_content: str) -> List[Dict[str, Any]]:
        """Extracts UI elements and bounds from Android uiautomator dump XML."""
        elements = []
        if not xml_content:
            return elements
        try:
            root = ET.fromstring(xml_content)
            for node in root.iter("node"):
                attribs = node.attrib
                if attribs.get("bounds"):
                    elements.append({
                        "text": attribs.get("text", ""),
                        "resource-id": attribs.get("resource-id", ""),
                        "class": attribs.get("class", ""),
                        "content-desc": attribs.get("content-desc", ""),
                        "bounds": attribs.get("bounds", ""),
                        "clickable": attribs.get("clickable", "false") == "true"
                    })
        except Exception:
            pass
        return elements

    def audit_screen(
        self,
        ui_elements: Optional[List[Dict[str, Any]]] = None,
        hierarchy_xml: Optional[str] = None,
        page_text: str = "",
        screen_width: int = 1080,
        screen_height: int = 2400,
        brand: str = "cardekho"
    ) -> Dict[str, Any]:
        """
        Unified Visual & Product Quality Audit:
        Runs all pillars and classifies defects into Blockers and Polish items.
        """
        elements = list(ui_elements) if ui_elements else []
        if hierarchy_xml:
            elements.extend(self.parse_hierarchy_xml(hierarchy_xml))

        # Aggregate text across elements and page_text
        all_text_chunks = [page_text]
        for el in elements:
            if el.get("text"):
                all_text_chunks.append(el["text"])
            if el.get("content-desc"):
                all_text_chunks.append(el["content-desc"])
        combined_text = " \n ".join([t for t in all_text_chunks if t])

        defects: List[Dict[str, Any]] = []

        # Pillar 1: Micro-copy & tokens
        defects.extend(self.check_microcopy_tokens(combined_text))

        # Pillar 2: Automotive spelling & typos
        defects.extend(self.check_automotive_spelling(combined_text))

        # Pillar 2.1: Domain terminology leak (e.g. 'riding needs' on CarDekho)
        defects.extend(self.check_domain_terminology(combined_text, brand=brand))

        # Pillar 2.2: Runtime error toasts / banners (e.g. 'An Error Occurred')
        defects.extend(self.check_runtime_error_toasts(combined_text))

        # Pillar 3: Overlaps & bounds collisions
        if elements:
            defects.extend(self.check_bounding_box_overlaps(elements, screen_width, screen_height))

        # Pillar 4: Truncations
        if elements:
            defects.extend(self.check_text_truncation(elements))

        blockers = [d for d in defects if d.get("severity") in [VisualSeverity.P0.value, VisualSeverity.P1.value]]
        cosmetic = [d for d in defects if d.get("severity") in [VisualSeverity.P2.value, VisualSeverity.P3.value]]

        return {
            "has_visual_defects": len(defects) > 0,
            "has_blockers": len(blockers) > 0,
            "total_defects": len(defects),
            "blockers_count": len(blockers),
            "cosmetic_count": len(cosmetic),
            "blockers": blockers,
            "cosmetic": cosmetic,
            "all_defects": defects,
            "summary": (
                f"Visual Audit: {len(blockers)} visual blocker(s), {len(cosmetic)} cosmetic polish item(s) detected."
                if defects else "Visual Audit: Clean layout, typography, and copy (0 visual defects)."
            )
        }
