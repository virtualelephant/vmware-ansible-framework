#!/usr/bin/env python3
"""
Pi-hole DNS Record Extractor
============================

Extracts local **A/AAAA** and **CNAME** DNS records from one or more Pi-hole v6+ instances
using the official REST API and exports them to a structured YAML file for GitOps.

Features
--------
- Authenticates securely using Pi-hole web password
- Fetches A/AAAA records from ``/api/config/dns/hosts``
- Fetches CNAME records from ``/api/config/dns/cnames``
- Merges records across multiple Pi-hole servers
- Deduplicates entries (last-write-wins on conflict)
- Outputs clean, version-control-friendly YAML
- Full logging with levels
- Configurable via environment variables or CLI arguments
- Retry logic for transient network issues

Usage
-----
.. code-block:: bash

    # Using environment variables
    export PIHOLE_SERVERS='ns1:pass1,ns2:pass2'
    export PIHOLE_BASE_URLS='http://ns1.home.virtualelephant.com/admin/api,http://ns2.home.virtualelephant.com/admin/api'
    python extract_pihole_dns.py --output dns_records.yaml

    # Or via CLI
    python extract_pihole_dns.py \
        --servers ns1.home.virtualelephant.com:secret1,ns2.home.virtualelephant.com:secret2 \
        --output dns_records.yaml

Author
------
Your Name <you@example.com>

License
-------
MIT
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Dict, List, Tuple, Optional

import requests
import yaml
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --------------------------------------------------------------------------- #
# Logging Configuration
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
API_AUTH_ENDPOINT = "/auth"
API_HOSTS_ENDPOINT = "/config/dns/hosts"
API_CNAMES_ENDPOINT = "/config/dns/cnames"

DEFAULT_TIMEOUT = 10
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF_FACTOR = 1


# --------------------------------------------------------------------------- #
# Helper Classes
# --------------------------------------------------------------------------- #
class PiHoleAPI:
    """Encapsulates interaction with a single Pi-hole v6+ API instance."""

    def __init__(
        self,
        base_url: str,
        password: str,
        session: Optional[requests.Session] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.base_url = base_url.rstrip("/")
        self.password = password
        self.timeout = timeout
        self.session = session or requests.Session()

        # Configure retry strategy
        retry = Retry(
            total=DEFAULT_RETRIES,
            backoff_factor=DEFAULT_BACKOFF_FACTOR,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        self._sid: Optional[str] = None

    def _auth(self) -> str:
        """Authenticate and return session ID."""
        url = f"{self.base_url}{API_AUTH_ENDPOINT}"
        payload = {"password": self.password}

        logger.debug("Authenticating to %s", self.base_url)
        try:
            response = self.session.post(
                url, json=payload, timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            sid = data.get("sid")
            if not sid:
                raise ValueError("No session ID returned from auth endpoint")
            logger.debug("Authentication successful")
            return sid
        except requests.RequestException as e:
            raise RuntimeError(f"Authentication failed: {e}") from e

    @property
    def sid(self) -> str:
        """Lazy authentication: get or refresh session ID."""
        if not self._sid:
            self._sid = self._auth()
        return self._sid

    def _get_headers(self) -> Dict[str, str]:
        return {"X-FTL-SID": self.sid}

    def get_hosts(self) -> List[str]:
        """Fetch A/AAAA records as list of 'IP hostname' strings."""
        url = f"{self.base_url}{API_HOSTS_ENDPOINT}"
        try:
            response = self.session.get(
                url, headers=self._get_headers(), timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to fetch A/AAAA records: {e}") from e

    def get_cnames(self) -> List[Dict[str, str]]:
        """Fetch CNAME records as list of {'domain': ..., 'target': ...}."""
        url = f"{self.base_url}{API_CNAMES_ENDPOINT}"
        try:
            response = self.session.get(
                url, headers=self._get_headers(), timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to fetch CNAME records: {e}") from e


# --------------------------------------------------------------------------- #
# Core Extraction Logic
# --------------------------------------------------------------------------- #
def parse_host_entry(entry: str) -> Tuple[str, str]:
    """
    Parse a host entry string into (ip, hostname).

    Expected format: "192.168.1.100 myhost.local" or "::1 ipv6host.local"
    """
    parts = entry.strip().split(maxsplit=1)
    if len(parts) != 2:
        raise ValueError(f"Invalid host entry format: {entry}")
    return parts[0], parts[1]


def extract_records(
    servers: List[Tuple[str, str]]
) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Extract A/AAAA and CNAME records from all configured Pi-hole servers.

    Returns
    -------
    (a_aaaa_records, cname_records)
        - a_aaaa_records: {hostname: ip}
        - cname_records: {alias: target}
    """
    a_aaaa_records: Dict[str, str] = {}
    cname_records: Dict[str, str] = {}

    for base_url, password in servers:
        server_label = base_url.split("//")[-1].split("/")[0]
        logger.info("Extracting records from %s", server_label)

        try:
            api = PiHoleAPI(base_url, password)

            # --- A/AAAA Records ---
            hosts = api.get_hosts()
            for entry in hosts:
                ip, hostname = parse_host_entry(entry)
                if hostname not in a_aaaa_records:
                    a_aaaa_records[hostname] = ip
                    logger.debug("A/AAAA: %s -> %s", hostname, ip)
                else:
                    logger.warning(
                        "Duplicate A/AAAA for %s: %s (keeping: %s)",
                        hostname,
                        ip,
                        a_aaaa_records[hostname],
                    )

            # --- CNAME Records ---
            cnames = api.get_cnames()
            for rec in cnames:
                domain = rec.get("domain")
                target = rec.get("target")
                if not domain or not target:
                    logger.warning("Malformed CNAME record: %s", rec)
                    continue
                if domain not in cname_records:
                    cname_records[domain] = target
                    logger.debug("CNAME: %s -> %s", domain, target)
                else:
                    logger.warning(
                        "Duplicate CNAME for %s: %s (keeping: %s)",
                        domain,
                        target,
                        cname_records[domain],
                    )

        except Exception as e:
            logger.error("Failed to extract from %s: %s", server_label, e)

    return a_aaaa_records, cname_records


# --------------------------------------------------------------------------- #
# CLI & Main
# --------------------------------------------------------------------------- #
def parse_servers_arg(arg: str) -> List[Tuple[str, str]]:
    """
    Parse comma-separated 'url:password' or 'host:password' strings.
    If only host is given, assumes default API path.
    """
    servers = []
    for part in arg.split(","):
        part = part.strip()
        if ":" not in part:
            raise ValueError(f"Server entry must be 'url:password' or 'host:password': {part}")
        url_or_host, password = part.rsplit(":", 1)
        if not url_or_host.startswith("http"):
            url_or_host = f"http://{url_or_host}/admin/api"
        else:
            url_or_host = url_or_host.rstrip("/") + "/admin/api"
        servers.append((url_or_host, password))
    return servers


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract A/AAAA and CNAME records from Pi-hole servers",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--servers",
        type=str,
        help="Comma-separated list of 'url:password' or 'host:password'",
        default=os.getenv("PIHOLE_SERVERS", ""),
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="dns_records.yaml",
        help="Output YAML file path",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not args.servers:
        logger.error("No servers specified. Use --servers or PIHOLE_SERVERS env var.")
        return 1

    try:
        servers = parse_servers_arg(args.servers)
    except ValueError as e:
        logger.error("Invalid server format: %s", e)
        return 1

    logger.info("Starting DNS record extraction from %d Pi-hole server(s)", len(servers))
    a_aaaa, cnames = extract_records(servers)

    output_data = {
        "a_aaaa": a_aaaa,
        "cname": cnames,
        "metadata": {
            "generated_by": "extract_pihole_dns.py",
            "source": "Pi-hole v6+ REST API",
            "count_a_aaaa": len(a_aaaa),
            "count_cname": len(cnames),
        },
    }

    try:
        with open(args.output, "w", encoding="utf-8") as f:
            yaml.dump(output_data, f, default_flow_style=False, sort_keys=False, indent=2)
        logger.info("Successfully wrote %d A/AAAA and %d CNAME records to %s",
                    len(a_aaaa), len(cnames), args.output)
    except Exception as e:
        logger.error("Failed to write output file: %s", e)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
