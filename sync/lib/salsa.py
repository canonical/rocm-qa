"""Salsa (Debian GitLab) operations via the `glab` CLI.

`glab` is expected to be configured for `salsa.debian.org` (via the
GITLAB_HOST env var or `glab auth login --hostname salsa.debian.org`).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess

log = logging.getLogger(__name__)

SALSA_HOST = "salsa.debian.org"


def _glab(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.setdefault("GITLAB_HOST", SALSA_HOST)
    log.debug("glab$ %s", " ".join(args))
    return subprocess.run(
        ["glab", *args],
        check=check,
        capture_output=True,
        text=True,
        env=env,
    )


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
            "--state",
            "opened",
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
    for mr in mrs:
        # Filter by source project namespace too: glab's source-branch filter
        # alone matches across projects in the same namespace tree.
        src_ns = (
            mr.get("source_project", {}).get("path_with_namespace")
            or mr.get("references", {}).get("full")
            or ""
        )
        if not src_ns or src_ns.startswith(source_project):
            return mr
    return None


def create_mr(
    target_project: str,
    source_project: str,
    source_branch: str,
    target_branch: str,
    title: str,
    description: str,
) -> str | None:
    """Create an MR. Returns the web URL on success, None on failure.

    `target_project` is the upstream (e.g. rocm-team/<pkg>); the MR is created
    against it from the fork's branch.
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
    res = _glab(args, check=False)
    if res.returncode != 0:
        log.error("glab mr create failed: %s", res.stderr.strip())
        return None
    # glab prints the MR URL on the last non-empty line.
    for line in reversed(res.stdout.splitlines()):
        line = line.strip()
        if line.startswith("http"):
            return line
    return None
