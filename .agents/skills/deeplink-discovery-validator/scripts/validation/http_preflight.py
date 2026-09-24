"""
HTTP Pre-Flight Network & Redirection Checker.
Performs non-destructive HTTP pre-flight checks for HTTP/HTTPS web endpoints.
"""

import requests
from typing import Dict, Any, Tuple


class HttpPreflightChecker:
    """Pre-flights HTTP/HTTPS endpoints to test live response and redirection chains."""

    def __init__(self, timeout: int = 8):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; Mobile; CarDekhoQA/1.0)",
            "Accept": "application/json, text/html, */*"
        })

    def check_url(self, url: str) -> Dict[str, Any]:
        result = {
            "http_status": "N/A",
            "redirect_url": "",
            "is_live": False,
            "remarks": ""
        }

        if not url or not url.startswith(("http://", "https://")):
            result["remarks"] = "Custom app scheme (Non-HTTP)"
            return result

        try:
            resp = self.session.get(url, timeout=self.timeout, allow_redirects=False)
            result["http_status"] = str(resp.status_code)

            if resp.status_code == 200:
                result["is_live"] = True
                result["remarks"] = "Endpoint Live (200 OK)"
            elif resp.status_code in (301, 302, 307, 308):
                result["redirect_url"] = resp.headers.get("Location", "")
                result["is_live"] = True
                result["remarks"] = f"HTTP {resp.status_code} Redirect to {result['redirect_url']}"
            elif resp.status_code in (404, 410):
                result["is_live"] = False
                result["remarks"] = f"HTTP {resp.status_code} Not Found / Deprecated"
            else:
                result["is_live"] = False
                result["remarks"] = f"HTTP {resp.status_code}"
        except requests.exceptions.Timeout:
            result["http_status"] = "TIMEOUT"
            result["remarks"] = "HTTP Preflight Request Timed Out"
        except requests.exceptions.ConnectionError:
            result["http_status"] = "CONN_ERR"
            result["remarks"] = "Connection Failed / DNS Error"
        except Exception as e:
            result["http_status"] = "ERROR"
            result["remarks"] = f"Network Exception: {str(e)}"

        return result
