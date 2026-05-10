"""GitHub Actions job summary writer + GitHub issue helper.

Issue creation uses the `gh` CLI (pre-installed on GHA runners) so we don't
have to plumb a token through Python.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

GITHUB_REPO = "canonical/rocm-qa"


@dataclass
class PackageOutcome:
    pkg: str
    series: str
    status: str  # "synced" | "conflict" | "skipped" | "up-to-date" | "error"
    detail: str = ""
    mr_url: str | None = None


@dataclass
class Report:
    outcomes: list[PackageOutcome] = field(default_factory=list)

    def add(self, outcome: PackageOutcome) -> None:
        self.outcomes.append(outcome)
        log.info(
            "[%s/%s] %s — %s",
            outcome.series,
            outcome.pkg,
            outcome.status,
            outcome.detail,
        )

    def by_status(self, status: str) -> list[PackageOutcome]:
        return [o for o in self.outcomes if o.status == status]


def _md_table(rows: list[PackageOutcome]) -> str:
    if not rows:
        return "_(none)_\n"
    lines = ["| Series | Package | Detail | MR |", "|---|---|---|---|"]
    for o in rows:
        mr = f"[link]({o.mr_url})" if o.mr_url else ""
        detail = (o.detail or "").replace("|", "\\|")
        lines.append(f"| {o.series} | {o.pkg} | {detail} | {mr} |")
    return "\n".join(lines) + "\n"


def write_summary(report: Report) -> None:
    """Write a Markdown summary to $GITHUB_STEP_SUMMARY (or stdout if unset)."""
    parts: list[str] = ["# ROCm sync run\n"]

    counts = {
        "synced": len(report.by_status("synced")),
        "conflict": len(report.by_status("conflict")),
        "skipped": len(report.by_status("skipped")),
        "up-to-date": len(report.by_status("up-to-date")),
        "error": len(report.by_status("error")),
    }
    parts.append(
        "**Counts:** "
        + " · ".join(f"{k}: {v}" for k, v in counts.items())
        + "\n\n"
    )

    parts.append("## Synced (MR created/updated)\n")
    parts.append(_md_table(report.by_status("synced")))

    parts.append("## Conflicts\n")
    parts.append(_md_table(report.by_status("conflict")))

    parts.append("## Up-to-date\n")
    parts.append(_md_table(report.by_status("up-to-date")))

    parts.append("## Skipped\n")
    parts.append(_md_table(report.by_status("skipped")))

    parts.append("## Errors\n")
    parts.append(_md_table(report.by_status("error")))

    body = "".join(parts)

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(body)
    else:
        print(body)


def _gh(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["gh", *args],
        check=check,
        capture_output=True,
        text=True,
    )


def conflict_issue_title(pkg: str, series: str) -> str:
    return f"[sync] Rebase conflict: {pkg} ({series})"


def open_conflict_issue_exists(pkg: str, series: str) -> bool:
    title = conflict_issue_title(pkg, series)
    res = _gh(
        [
            "issue",
            "list",
            "--repo",
            GITHUB_REPO,
            "--state",
            "open",
            "--search",
            f'in:title "{title}"',
            "--json",
            "title,number",
        ],
        check=False,
    )
    if res.returncode != 0:
        log.warning("gh issue list failed: %s", res.stderr.strip())
        return False
    try:
        issues = json.loads(res.stdout or "[]")
    except json.JSONDecodeError:
        return False
    return any(i.get("title") == title for i in issues)


def create_conflict_issue(pkg: str, series: str, body: str) -> str | None:
    """Create a rebase-conflict issue if no open one with the same title
    exists. Returns the issue URL or None."""
    if open_conflict_issue_exists(pkg, series):
        log.info("Conflict issue already open for %s (%s); skipping", pkg, series)
        return None
    title = conflict_issue_title(pkg, series)
    res = _gh(
        [
            "issue",
            "create",
            "--repo",
            GITHUB_REPO,
            "--title",
            title,
            "--body",
            body,
        ],
        check=False,
    )
    if res.returncode != 0:
        log.error("gh issue create failed: %s", res.stderr.strip())
        return None
    for line in reversed(res.stdout.splitlines()):
        line = line.strip()
        if line.startswith("http"):
            return line
    return None
