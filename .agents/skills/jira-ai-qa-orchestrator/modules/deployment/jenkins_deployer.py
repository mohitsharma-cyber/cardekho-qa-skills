"""
Enterprise Jenkins Deployer & Branch Detection for Jira AI QA Orchestrator.
Detects API / PWA branches in Jira tickets and provides automated deployment
triggers to testing servers (testingpwa2.cardekho.com) via Jenkins REST API.
"""

import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple
import requests
from requests.auth import HTTPBasicAuth
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class JenkinsDeployer:
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        j_cfg = self.config.get("jenkins", {})
        self.jenkins_url = j_cfg.get("jenkins_url", "http://192.168.39.13:8080").rstrip("/")
        self.username = j_cfg.get("username", "mohitsharma")
        self.password = j_cfg.get("password", "mohit.sharma@girnarsoft.com")
        self.default_target_env = j_cfg.get("default_target_env", "testingpwa2")
        self.bikedekho_jobs = j_cfg.get("bikedekho_jobs", {
            "api": "Bikedekho-Build-Deploy-Desktop-Testing-API-Latest",
            "pwa": "Bikedekho-Build-Deploy-Desktop-Testing-PWA,PWA1,PWA2"
        })
        self.cardekho_jobs = j_cfg.get("cardekho_jobs", {
            "api": "CarDekho-QATeam-Deployment-testingpwa2",
            "pwa": "CarDekho-QATeam-Build-Deployment-testingpwa2"
        })

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        if not config_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            config_path = os.path.join(base_dir, "config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _get_crumb(self, auth: HTTPBasicAuth) -> Dict[str, str]:
        """Fetches CSRF crumb from Jenkins."""
        try:
            crumb_url = f"{self.jenkins_url}/crumbIssuer/api/json"
            res = requests.get(crumb_url, auth=auth, verify=False, timeout=5)
            if res.status_code == 200:
                data = res.json()
                return {data.get("crumbRequestField", "Jenkins-Crumb"): data.get("crumb", "")}
        except Exception:
            pass
        return {}

    def extract_branch_info(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scans description and comments for API and PWA branch indicators.
        """
        desc = ticket.get("description") or ""
        comments = [c.get("body", "") if isinstance(c, dict) else str(c) for c in ticket.get("comments", [])]
        combined_text = desc + "\n" + "\n".join(comments)

        api_branches = []
        pwa_branches = []
        generic_branches = []

        # 1. API branch patterns
        api_patterns = [
            r'(?:CD\s*)?API\s+Branch(?:\s+Name)?\s*[:=]\s*([A-Za-z0-9_\-\.\/]+)',
            r'API\s+branch\s*[:=]\s*([A-Za-z0-9_\-\.\/]+)',
            r'api[\-_]branch\s*[:=]\s*([A-Za-z0-9_\-\.\/]+)',
        ]
        for pat in api_patterns:
            matches = re.findall(pat, combined_text, re.IGNORECASE)
            for m in matches:
                clean = m.strip().strip("'").strip('"')
                if clean and clean not in api_branches:
                    api_branches.append(clean)

        # 2. PWA / Web branch patterns
        pwa_patterns = [
            r'(?:PWA|Web|App)\s+Branch(?:\s+Name)?\s*[:=]\s*([A-Za-z0-9_\-\.\/]+)',
            r'(?:pwa|web|app)[\-_]branch\s*[:=]\s*([A-Za-z0-9_\-\.\/]+)',
        ]
        for pat in pwa_patterns:
            matches = re.findall(pat, combined_text, re.IGNORECASE)
            for m in matches:
                clean = m.strip().strip("'").strip('"')
                if clean and clean not in pwa_branches:
                    pwa_branches.append(clean)

        # 3. Generic branch patterns
        generic_patterns = [
            r'branch\s*[:=]\s*([A-Za-z0-9_\-\.\/]+)',
            r'feature\/([A-Za-z0-9_\-\.]+)',
            r'bugfix\/([A-Za-z0-9_\-\.]+)',
        ]
        for pat in generic_patterns:
            matches = re.findall(pat, combined_text, re.IGNORECASE)
            for m in matches:
                clean = m.strip().strip("'").strip('"')
                if clean and clean not in generic_branches and clean not in api_branches and clean not in pwa_branches:
                    generic_branches.append(clean)

        has_branch = bool(api_branches or pwa_branches or generic_branches)
        primary_branch = api_branches[0] if api_branches else (pwa_branches[0] if pwa_branches else (generic_branches[0] if generic_branches else None))
        branch_type = "API" if api_branches else ("PWA" if pwa_branches else ("Generic" if generic_branches else "None"))

        # Brand awareness: Check if ticket or branch belongs to BikeDekho
        ticket_key = ticket.get("key", "").upper()
        summary = (ticket.get("summary") or "").lower()
        combined_lower = combined_text.lower()
        is_bikedekho = (
            ticket_key.startswith("BD") or
            ticket_key.startswith("BDCV") or
            "bikedekho" in summary or
            "bikedekhowap" in combined_lower or
            "bikedekhoweb" in combined_lower or
            "bikedekho" in combined_lower
        )

        domain_suffix = "bikedekho.com" if is_bikedekho else "cardekho.com"
        suggested_servers = (
            ["testingapi2", "testingapi3", "testingapi5", "testingapi4", "testingapi1"]
            if is_bikedekho else
            ["testingapi2", "testingapi3", "testingpwa2", "testingpwa1"]
        )
        default_server = "testingapi5" if is_bikedekho else "testingpwa2"

        return {
            "has_branch": has_branch,
            "branch_type": branch_type,
            "primary_branch": primary_branch,
            "api_branches": api_branches,
            "pwa_branches": pwa_branches,
            "other_branches": generic_branches,
            "is_bikedekho": is_bikedekho,
            "brand": "BikeDekho" if is_bikedekho else "CarDekho",
            "requires_server_choice": True,  # Section 10: Never guess server for any brand
            "suggested_servers": suggested_servers,
            "target_server": default_server,
            "target_url": f"https://{default_server}.{domain_suffix}"
        }

    @staticmethod
    def format_deployment_verified_banner(ticket_key: str, branch: str, commit: str = "HEAD", build_num: Any = 142, server: str = "testingapi2") -> str:
        """Formats the explicit Master Prompt Section 12 verification banner."""
        return (
            "========================================================\n"
            "DEPLOYMENT SUCCESSFUL & VERIFIED\n"
            "========================================================\n"
            f"Jira:\n{ticket_key}\n\n"
            f"Branch:\n{branch}\n\n"
            f"Commit:\n{commit}\n\n"
            f"Build:\n#{build_num}\n\n"
            f"Server:\n{server}\n\n"
            "Deployment:\nVERIFIED\n"
            "========================================================"
        )

    def trigger_deployment(self, branch_name: str, branch_type: str = "api", target_env: str = "testingapi5", is_bikedekho: bool = False, mock_mode: bool = False) -> Dict[str, Any]:
        """
        Triggers Jenkins deployment job for the given branch to target server.
        """
        b_type = branch_type.lower()
        if is_bikedekho:
            job_name = self.bikedekho_jobs.get(b_type, self.bikedekho_jobs.get("api", "Bikedekho-Build-Deploy-Desktop-Testing-API-Latest"))
        else:
            job_name = self.cardekho_jobs.get(b_type, self.cardekho_jobs.get("api", "CarDekho-QATeam-Deployment-testingpwa2"))

        build_url = f"{self.jenkins_url}/job/{job_name}/buildWithParameters"

        domain_suffix = "bikedekho.com" if is_bikedekho else "cardekho.com"
        deploy_target = f"{target_env}.{domain_suffix}" if not target_env.endswith(f".{domain_suffix}") else target_env

        if mock_mode:
            return {
                "status": "SUCCESS",
                "mock_mode": True,
                "job_name": job_name,
                "branch": branch_name,
                "target_env": target_env,
                "target_url": f"https://{deploy_target}",
                "build_number": 142,
                "build_url": f"{self.jenkins_url}/job/{job_name}/142/",
                "message": f"Successfully deployed branch '{branch_name}' ({branch_type.upper()}) to {target_env} ({deploy_target})."
            }

        try:
            auth = HTTPBasicAuth(self.username, self.password)
            headers = self._get_crumb(auth)

            if is_bikedekho:
                if b_type == "pwa":
                    # BikeDekho PWA job parameters
                    deploy_env = target_env.upper().replace(".", "")
                    params = {
                        "BRANCHNAME": branch_name,
                        "DEPLOYENV": deploy_env if "BDPWA" in deploy_env else "BDPWA",
                        "CENTRAL": "YES"
                    }
                else:
                    # BikeDekho API job parameters
                    api_endpoint = deploy_target if deploy_target.endswith(".bikedekho.com") else f"{deploy_target}.bikedekho.com"
                    params = {
                        "BRANCH_NAME": branch_name,
                        "API_ENDPOINT": api_endpoint,
                        "COMPOSER_UPDATE": "false",
                        "RUN_MIGRATION": "true",
                        "SERVER_IP": "192.168.33.42",
                        "SERVER_USER": "bikedekho"
                    }
            else:
                # CarDekho deployment parameters
                params = {
                    "BRANCH_NAME": branch_name,
                    "TARGET_ENV": target_env,
                    "DEPLOY_TARGET": deploy_target,
                    "BUILD_ID": "dontKillMe"
                }

            res = requests.post(build_url, auth=auth, headers=headers, data=params, verify=False, timeout=15)
            if res.status_code in [200, 201]:
                queue_url = res.headers.get("Location", "")
                return {
                    "status": "SUCCESS",
                    "mock_mode": False,
                    "job_name": job_name,
                    "branch": branch_name,
                    "target_env": target_env,
                    "queue_url": queue_url,
                    "build_url": f"{self.jenkins_url}/job/{job_name}/",
                    "message": f"Deployment triggered LIVE on Jenkins for branch '{branch_name}' on {target_env}."
                }
            else:
                return {
                    "status": "ERROR",
                    "mock_mode": False,
                    "job_name": job_name,
                    "branch": branch_name,
                    "target_env": target_env,
                    "http_status": res.status_code,
                    "error": res.text[:300],
                    "message": f"Jenkins returned HTTP {res.status_code} for branch '{branch_name}'."
                }
        except Exception as e:
            return {
                "status": "ERROR",
                "mock_mode": False,
                "job_name": job_name,
                "branch": branch_name,
                "target_env": target_env,
                "error": str(e),
                "message": f"Error triggering Jenkins deployment: {str(e)}"
            }

    def wait_for_build_completion(self, queue_url: str = "", job_name: str = "", timeout_secs: int = 180, poll_interval: int = 5, mock_mode: bool = False) -> Dict[str, Any]:
        """
        Monitors Jenkins build until completion (SUCCESS, FAILURE, or ABORTED).
        Follows Master Prompt Rule 12: Deployment is a HARD GATE.
        """
        if mock_mode:
            return {
                "status": "SUCCESS",
                "mock_mode": True,
                "build_number": 142,
                "result": "SUCCESS",
                "message": "Jenkins build #142 completed with SUCCESS (Mock Mode)."
            }

        start_time = time.time()
        auth = HTTPBasicAuth(self.username, self.password)
        build_number = None

        # 1. If queue_url given, poll queue item until build starts
        if queue_url:
            queue_api = queue_url.rstrip("/") + "/api/json"
            while time.time() - start_time < timeout_secs:
                try:
                    res = requests.get(queue_api, auth=auth, verify=False, timeout=8)
                    if res.status_code == 200:
                        data = res.json()
                        executable = data.get("executable")
                        if executable and executable.get("number"):
                            build_number = executable.get("number")
                            break
                        if data.get("cancelled"):
                            return {"status": "ABORTED", "build_number": None, "result": "ABORTED", "message": "Jenkins build was cancelled in queue."}
                    time.sleep(poll_interval)
                except Exception:
                    time.sleep(poll_interval)

        # 2. Fallback to latest build of job if build_number not found from queue
        if not build_number and job_name:
            try:
                job_api = f"{self.jenkins_url}/job/{job_name}/lastBuild/api/json"
                res = requests.get(job_api, auth=auth, verify=False, timeout=8)
                if res.status_code == 200:
                    build_number = res.json().get("number")
            except Exception:
                pass

        if not build_number:
            return {
                "status": "TIMEOUT",
                "build_number": None,
                "result": "UNKNOWN",
                "message": f"Timed out waiting for Jenkins build to start after {timeout_secs}s."
            }

        # 3. Monitor build execution until building == False
        build_api = f"{self.jenkins_url}/job/{job_name}/{build_number}/api/json"
        while time.time() - start_time < timeout_secs:
            try:
                res = requests.get(build_api, auth=auth, verify=False, timeout=8)
                if res.status_code == 200:
                    b_data = res.json()
                    is_building = b_data.get("building", False)
                    result = b_data.get("result")
                    if not is_building and result:
                        status = "SUCCESS" if result.upper() == "SUCCESS" else "FAILURE"
                        return {
                            "status": status,
                            "build_number": build_number,
                            "result": result,
                            "build_url": f"{self.jenkins_url}/job/{job_name}/{build_number}/",
                            "message": f"Jenkins build #{build_number} finished with status: {result}."
                        }
                time.sleep(poll_interval)
            except Exception:
                time.sleep(poll_interval)

        return {
            "status": "TIMEOUT",
            "build_number": build_number,
            "result": "RUNNING",
            "message": f"Jenkins build #{build_number} exceeded {timeout_secs}s timeout."
        }

    def verify_target_deployment(self, target_server: str, is_bikedekho: bool = False, expected_endpoint: Optional[str] = None, mock_mode: bool = False) -> Dict[str, Any]:
        """
        Independently verifies that the target server is online and accessible.
        Follows Master Prompt Rule 13: Jenkins SUCCESS != Correct code deployed.
        """
        domain_suffix = "bikedekho.com" if is_bikedekho else "cardekho.com"
        clean_target = target_server.replace(f".{domain_suffix}", "").strip()
        target_url = f"https://{clean_target}.{domain_suffix}"

        if mock_mode:
            return {
                "verified": True,
                "target_server": clean_target,
                "target_url": target_url,
                "http_status": 200,
                "message": f"Deployment independently verified: {target_url} is active and responsive (Mock Mode)."
            }

        check_url = f"{target_url}/{expected_endpoint.lstrip('/')}" if expected_endpoint else target_url
        headers = {"User-Agent": "Mozilla/5.0 (Android; Mobile; QA-Verification)"}

        try:
            res = requests.get(check_url, headers=headers, verify=False, timeout=10)
            # Accept valid responses (e.g. 200, 301, 302, 404 with server alive, etc.)
            if res.status_code < 500:
                return {
                    "verified": True,
                    "target_server": clean_target,
                    "target_url": target_url,
                    "check_url": check_url,
                    "http_status": res.status_code,
                    "message": f"Target server {target_url} verified online (HTTP {res.status_code})."
                }
            else:
                return {
                    "verified": False,
                    "target_server": clean_target,
                    "target_url": target_url,
                    "check_url": check_url,
                    "http_status": res.status_code,
                    "message": f"Target server {target_url} returned server error HTTP {res.status_code}."
                }
        except Exception as e:
            return {
                "verified": False,
                "target_server": clean_target,
                "target_url": target_url,
                "check_url": check_url,
                "http_status": None,
                "error": str(e),
                "message": f"Could not reach target server {target_url}: {str(e)}"
            }
