"""Salsa (Debian GitLab) operations via the `glab` CLI.

`glab` is expected to be configured for `salsa.debian.org` (via the
GITLAB_HOST env var or `glab auth login --hostname salsa.debian.org`).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from urllib.parse import quote

log = logging.getLogger(__name__)

SALSA_HOST = "salsa.debian.org"


def _glab(
    args: list[str],
    check: bool = True,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.setdefault("GITLAB_HOST", SALSA_HOST)
    log.debug("glab$ %s (cwd=%s)", " ".join(args), cwd)
    return subprocess.run(
        ["glab", *args],
        check=check,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(cwd) if cwd else None,
    )


def project_id(project: str) -> int | None:
    """Resolve a project path (e.g. 'tchavadar/amdsmi') to its numeric ID."""
    res = _glab(["api", f"projects/{quote(project, safe='')}"], check=False)
    if res.returncode != 0:
        log.warning(
            "glab api projects/%s failed: %s", project, res.stderr.strip()
        )
        return None
    try:
        return json.loads(res.stdout).get("id")
    except json.JSONDecodeError:
        return None


def repo_exists(project: str) -> bool:
    """project is like 'tchavadar/rocm-runtime'."""
    res = _glab(["repo", "view", project, "-F", "json"], check=False)
    return res.returncode == 0


def fork_repo(source: str, namespace: str) -> None:
    """Fork `source` (e.g. 'rocm-team/rocm-runtime') into `namespace`
    (e.g. 'tchavadar'). Idempotent: silently no-ops if the fork already exists."""
    target = f"{namespace}/{source.split('/', 1)[1]}"
    if repo_exists(target):
        log.info("Fork %s already exists", target)
        return
    log.info("Forking %s into %s", source, namespace)
    res = _glab(
        ["repo", "fork", source, "--clone=false"],
        check=False,
    )
    if res.returncode != 0:
        # Older glab versions may not support --clone=false; fall back.
        log.warning("glab fork failed: %s", res.stderr.strip())
        raise RuntimeError(f"Failed to fork {source}: {res.stderr.strip()}")


def find_open_mr(
    target_project: str,
    source_project: str,
    source_branch: str,
    target_branch: str,
) -> dict | None:
    """Return the first open MR matching the given source→target, or None."""
    # `glab mr list` returns open MRs by default (there is no --state flag).
    res = _glab(
        [
            "mr",
            "list",
            "--repo",
            target_project,
            "--source-branch",
            source_branch,
            "--target-branch",
            target_branch,
            "-F",
            "json",
        ],
        check=False,
    )
    if res.returncode != 0:
        log.warning("glab mr list failed: %s", res.stderr.strip())
        return None
    try:
        mrs = json.loads(res.stdout or "[]")
    except json.JSONDecodeError:
        return None
    # Filter by source project too: the source-branch filter alone also
    # matches MRs from other forks that use the same branch name. The MR
    # JSON only carries the numeric source_project_id, so resolve ours.
    src_id = project_id(source_project)
    for mr in mrs:
        if src_id is None or mr.get("source_project_id") == src_id:
            return mr
    return None


def create_mr(
    target_project: str,
    source_project: str,
    source_branch: str,
    target_branch: str,
    title: str,
    description: str,
    cwd: Path,
) -> str | None:
    """Create an MR. Returns the web URL on success, None on failure.

    `target_project` is the upstream (e.g. rocm-team/<pkg>); the MR is created
    against it from the fork's branch.

    `cwd` must be a git clone with a salsa.debian.org remote (the package
    clone from git_ops): `glab mr create` resolves the local repo's remotes
    against GITLAB_HOST even when --repo and --head are given, and fails
    outside such a clone.
    """
    args = [
        "mr",
        "create",
        "--repo",
        target_project,
        "--source-branch",
        source_branch,
        "--target-branch",
        target_branch,
        "--head",
        source_project,
        "--title",
        title,
        "--description",
        description,
        "--no-editor",
        "--yes",
    ]
    res = _glab(args, check=False, cwd=cwd)
    if res.returncode != 0:
        log.error("glab mr create failed: %s", res.stderr.strip())
        return None
    # glab prints the MR URL on the last non-empty line.
    for line in reversed(res.stdout.splitlines()):
        line = line.strip()
        if line.startswith("http"):
            return line
    return None
