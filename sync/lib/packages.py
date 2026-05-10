"""Enumerate the ROCm package set for an Ubuntu series via the Launchpad
REST API. Anonymous read; no auth required."""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request

log = logging.getLogger(__name__)

LP_API_BASE = "https://api.launchpad.net/1.0"


def _lp_get(url: str) -> dict | list:
    log.debug("GET %s", url)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def query_rocm_packages(series: str) -> list[str]:
    """Return the sorted list of source package names in the `rocm` package
    set for the given Ubuntu series."""
    log.info("Querying rocm package set for series=%s", series)

    distroseries = f"{LP_API_BASE}/ubuntu/{series}"
    params = urllib.parse.urlencode(
        {"ws.op": "getByName", "name": "rocm", "distroseries": distroseries}
    )
    pkg_set = _lp_get(f"{LP_API_BASE}/package-sets?{params}")
    if not isinstance(pkg_set, dict) or "self_link" not in pkg_set:
        raise RuntimeError(
            f"Unexpected getByName response for series={series}: {pkg_set!r}"
        )

    sources_url = f"{pkg_set['self_link']}?ws.op=getSourcesIncluded"
    sources = _lp_get(sources_url)
    if not isinstance(sources, list):
        raise RuntimeError(
            f"Unexpected getSourcesIncluded response for series={series}: "
            f"{type(sources).__name__}"
        )

    pkgs = sorted({str(s).strip() for s in sources if str(s).strip()})
    log.info("Found %d packages in rocm set for %s", len(pkgs), series)
    return pkgs
