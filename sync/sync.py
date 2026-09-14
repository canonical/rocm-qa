"""ROCm package sync: Ubuntu Launchpad -> Salsa via merge requests.

Reads sync/config.yaml, enumerates ROCm packages per series via
ubuntu-archive-tools, fetches LP and Salsa heads, rebases Salsa-only commits
on top of LP, force-pushes to a personal Salsa fork, and opens an MR back to
the rocm-team project.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import tempfile
from pathlib import Path

import yaml

from lib import git_ops, packages, reporting, salsa


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _parse_csv(value: str | None) -> list[str] | None:
    if not value:
        return None
    items = [v.strip() for v in value.split(",") if v.strip()]
    return items or None


def _build_cherry_pick_mr_description(
    pkg: str,
    series: str,
    lp_version: str | None,
    salsa_version: str | None,
    cherry_pick_result: git_ops.CherryPickResult,
) -> str:
    picked = cherry_pick_result.picked
    upstream = cherry_pick_result.upstream_picks
    already = cherry_pick_result.already_applied

    lines = [
        f"Automated sync of `{pkg}` for series `{series}`.",
        "",
        "Histories diverged; LP-only commits were cherry-picked onto"
        " Salsa-tip.",
        "",
        "## Versions",
        f"- LP `ubuntu/{series}`: `{lp_version or 'unknown'}`",
        f"- Salsa `ubuntu/{series}`: `{salsa_version or 'unknown'}`",
        "",
    ]
    if upstream:
        lines.append(
            f"## ⚠ Contains upstream changes — {len(upstream)} commit(s)"
        )
        lines.append("")
        lines.append(
            "The following cherry-picked commits touched paths outside"
            " `debian/`. This usually means a new upstream tarball was"
            " imported on LP. Verify the upstream branch / tarball state"
            " on Salsa is consistent before merging."
        )
        lines.append("")
        for sha, subj, paths in upstream[:20]:
            preview = ", ".join(paths[:5]) + (" …" if len(paths) > 5 else "")
            lines.append(f"- `{sha[:10]}` {subj}")
            lines.append(f"    - non-`debian/` paths: {preview}")
        if len(upstream) > 20:
            lines.append(f"- ...and {len(upstream) - 20} more")
        lines.append("")
    if picked:
        lines.append(f"## LP commits cherry-picked ({len(picked)})")
        for sha, subj in picked[:50]:
            lines.append(f"- `{sha[:10]}` {subj}")
        if len(picked) > 50:
            lines.append(f"- ...and {len(picked) - 50} more")
        lines.append("")
    else:
        lines.append("## LP commits cherry-picked")
        lines.append("_(none)_")
        lines.append("")
    if already:
        lines.append(
            f"## Already applied on Salsa (patch-id match) — {len(already)}"
        )
        lines.append("")
        lines.append(
            "These LP commits were skipped because the same diff is already"
            " present on Salsa under a different SHA (e.g. squashed into"
            " another commit)."
        )
        lines.append("")
        for sha, subj in already[:30]:
            lines.append(f"- `{sha[:10]}` {subj}")
        if len(already) > 30:
            lines.append(f"- ...and {len(already) - 30} more")
        lines.append("")
    lines.append("---")
    lines.append("Created by `sync/sync.py` in `canonical/rocm-qa`.")
    return "\n".join(lines)


def _build_fast_forward_mr_description(
    pkg: str,
    series: str,
    lp_version: str | None,
    salsa_version: str | None,
    commits: list[tuple[str, str, list[str]]],
) -> str:
    upstream = [c for c in commits if any(not p.startswith("debian/") for p in c[2])]
    lines = [
        f"Automated sync of `{pkg}` for series `{series}`.",
        "",
        "Salsa is a strict ancestor of LP: this is a fast-forward. Original"
        " LP commit SHAs are preserved (including any `gbp import-orig`"
        " merge commits).",
        "",
        "## Versions",
        f"- LP `ubuntu/{series}`: `{lp_version or 'unknown'}`",
        f"- Salsa `ubuntu/{series}`: `{salsa_version or 'unknown'}`",
        "",
    ]
    if upstream:
        lines.append(
            f"## ⚠ Contains upstream changes — {len(upstream)} commit(s)"
        )
        lines.append("")
        lines.append(
            "Some fast-forwarded commits touched paths outside `debian/`."
            " This usually means a new upstream tarball was imported on LP."
            " Verify the upstream branch / tarball state on Salsa is"
            " consistent before merging."
        )
        lines.append("")
        for sha, subj, paths in upstream[:20]:
            non_debian = [p for p in paths if not p.startswith("debian/")]
            preview = ", ".join(non_debian[:5]) + (
                " …" if len(non_debian) > 5 else ""
            )
            lines.append(f"- `{sha[:10]}` {subj}")
            lines.append(f"    - non-`debian/` paths: {preview}")
        if len(upstream) > 20:
            lines.append(f"- ...and {len(upstream) - 20} more")
        lines.append("")
    lines.append(f"## Commits ({len(commits)})")
    for sha, subj, _paths in commits[:50]:
        lines.append(f"- `{sha[:10]}` {subj}")
    if len(commits) > 50:
        lines.append(f"- ...and {len(commits) - 50} more")
    lines.append("")
    lines.append("---")
    lines.append("Created by `sync/sync.py` in `canonical/rocm-qa`.")
    return "\n".join(lines)


def _process_package(
    pkg: str,
    series: str,
    cfg: dict,
    workdir: Path,
    dry_run: bool,
    report: reporting.Report,
) -> None:
    salsa_user = cfg["salsa_user"]
    salsa_group = cfg["salsa_group"]
    push_branch = f"sync/ubuntu/{series}"
    lp_branch = f"ubuntu/{series}"

    try:
        repo = git_ops.prepare_repo(workdir, pkg, series, salsa_group)
    except git_ops.GitError as e:
        report.add(
            reporting.PackageOutcome(
                pkg=pkg, series=series, status="skipped", detail=str(e)
            )
        )
        return

    state = git_ops.analyze(repo)
    log.info("%s/%s analyze: %s (%s)", series, pkg, state.action, state.detail)

    if state.action == "skip-equal":
        report.add(
            reporting.PackageOutcome(
                pkg=pkg,
                series=series,
                status="up-to-date",
                detail="LP and Salsa trees identical",
            )
        )
        return

    if state.action == "skip-salsa-ahead":
        report.add(
            reporting.PackageOutcome(
                pkg=pkg,
                series=series,
                status="up-to-date",
                detail="Salsa is ahead of LP (already includes LP changes)",
            )
        )
        return

    if state.action == "skip-no-salsa-branch":
        report.add(
            reporting.PackageOutcome(
                pkg=pkg,
                series=series,
                status="skipped",
                detail="Salsa branch missing; manual setup required",
            )
        )
        return

    if state.action == "skip-no-base":
        report.add(
            reporting.PackageOutcome(
                pkg=pkg,
                series=series,
                status="skipped",
                detail="no common ancestor between LP and Salsa",
            )
        )
        return

    if state.action not in ("cherry-pick", "fast-forward"):
        report.add(
            reporting.PackageOutcome(
                pkg=pkg,
                series=series,
                status="error",
                detail=f"unknown action {state.action}",
            )
        )
        return

    assert state.merge_base is not None

    # Build the local branch to push and the MR title/body for both actions.
    title: str
    description: str
    outcome_summary: str

    lp_version = git_ops.get_changelog_version(
        repo, f"{git_ops.LP_REMOTE}/{lp_branch}"
    )
    salsa_version = (
        git_ops.get_changelog_version(repo, f"{git_ops.SALSA_REMOTE}/{lp_branch}")
        if repo.salsa_tip
        else None
    )

    if state.action == "fast-forward":
        git_ops.prepare_fast_forward(repo)
        commits = git_ops.commits_between(
            repo,
            f"{git_ops.SALSA_REMOTE}/{lp_branch}",
            f"{git_ops.LP_REMOTE}/{lp_branch}",
        )
        upstream_count = sum(
            1 for _, _, paths in commits
            if any(not p.startswith("debian/") for p in paths)
        )
        description = _build_fast_forward_mr_description(
            pkg, series, lp_version, salsa_version, commits
        )
        title = (
            f"Sync ubuntu/{series}: fast-forward {len(commits)} LP commit"
            + ("s" if len(commits) != 1 else "")
        )
        outcome_summary = (
            f"fast-forward: {len(commits)} commit(s)"
            + (f", {upstream_count} with upstream changes" if upstream_count else "")
        )
        log.info("%s: fast-forwarding %d LP commits", pkg, len(commits))
    else:
        try:
            cp_result = git_ops.cherry_pick_lp_onto_salsa(repo, state.merge_base)
        except git_ops.GitError:
            if dry_run:
                detail = "cherry-pick conflict (dry-run: issue not filed)"
            else:
                body = (
                    f"Automated cherry-pick of LP `ubuntu/{series}` commits "
                    f"onto Salsa `ubuntu/{series}` for `{pkg}` failed.\n\n"
                    "Resolve manually on Salsa, then re-run the sync."
                )
                url = reporting.create_conflict_issue(pkg, series, body)
                detail = f"cherry-pick conflict; issue: {url or 'existing'}"
            report.add(
                reporting.PackageOutcome(
                    pkg=pkg, series=series, status="conflict", detail=detail
                )
            )
            return
        log.info(
            "%s: cherry-picked %d LP commits; %d already applied (patch-id); "
            "%d with upstream changes",
            pkg,
            len(cp_result.picked),
            len(cp_result.already_applied),
            len(cp_result.upstream_picks),
        )

        # Nothing to push (all candidates were dropped as empty or matched
        # by patch-id).
        if not cp_result.picked:
            bits = []
            if cp_result.already_applied:
                bits.append(f"{len(cp_result.already_applied)} already on Salsa")
            detail = "no LP commits to apply" + (
                f" ({'; '.join(bits)})" if bits else ""
            )
            report.add(
                reporting.PackageOutcome(
                    pkg=pkg, series=series, status="up-to-date", detail=detail
                )
            )
            return

        description = _build_cherry_pick_mr_description(
            pkg, series, lp_version, salsa_version, cp_result
        )
        title = (
            f"Sync ubuntu/{series}: cherry-pick {len(cp_result.picked)} LP commit"
            + ("s" if len(cp_result.picked) != 1 else "")
        )
        outcome_summary = (
            f"cherry-pick: {len(cp_result.picked)} picked"
            + (
                f", {len(cp_result.upstream_picks)} with upstream changes"
                if cp_result.upstream_picks
                else ""
            )
        )

    if dry_run:
        report.add(
            reporting.PackageOutcome(
                pkg=pkg,
                series=series,
                status="synced",
                detail=f"dry-run: would push and create/update MR ({outcome_summary})",
            )
        )
        return

    # Ensure fork exists, then push.
    target_project = f"{salsa_group}/{pkg}"
    source_project = f"{salsa_user}/{pkg}"
    try:
        salsa.fork_repo(target_project, salsa_user)
    except Exception as e:  # noqa: BLE001
        report.add(
            reporting.PackageOutcome(
                pkg=pkg, series=series, status="error", detail=f"fork failed: {e}"
            )
        )
        return

    try:
        git_ops.push_to_fork(repo, salsa_user, push_branch)
    except Exception as e:  # noqa: BLE001
        report.add(
            reporting.PackageOutcome(
                pkg=pkg, series=series, status="error", detail=f"push failed: {e}"
            )
        )
        return

    existing = salsa.find_open_mr(
        target_project=target_project,
        source_project=source_project,
        source_branch=push_branch,
        target_branch=lp_branch,
    )
    if existing:
        url = existing.get("web_url") or existing.get("url")
        report.add(
            reporting.PackageOutcome(
                pkg=pkg,
                series=series,
                status="synced",
                detail=f"updated existing MR via force-push ({outcome_summary})",
                mr_url=url,
            )
        )
        return

    mr_url = salsa.create_mr(
        target_project=target_project,
        source_project=source_project,
        source_branch=push_branch,
        target_branch=lp_branch,
        title=title,
        description=description,
        cwd=repo.path,
    )
    if mr_url is None:
        report.add(
            reporting.PackageOutcome(
                pkg=pkg, series=series, status="error", detail="MR creation failed"
            )
        )
        return
    report.add(
        reporting.PackageOutcome(
            pkg=pkg,
            series=series,
            status="synced",
            detail=f"MR created ({outcome_summary})",
            mr_url=mr_url,
        )
    )


log = logging.getLogger("rocm-sync")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync ROCm packages from LP to Salsa")
    parser.add_argument(
        "--config",
        default=str(Path(__file__).parent / "config.yaml"),
        help="path to config.yaml",
    )
    parser.add_argument(
        "--series",
        help="comma-separated list of series to process (default: all configured)",
    )
    parser.add_argument(
        "--packages",
        help="comma-separated list of packages to process (default: full set per series)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="skip push and MR creation; only analyze and report",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument(
        "--workdir",
        help="working directory for clones (default: a fresh tempdir)",
    )
    args = parser.parse_args(argv)

    _setup_logging(args.verbose)

    with open(args.config, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    requested_series = _parse_csv(args.series)
    requested_pkgs = _parse_csv(args.packages)

    series_to_run = list(cfg.get("series", {}).keys())
    if requested_series:
        series_to_run = [s for s in series_to_run if s in requested_series]
        unknown = sorted(set(requested_series) - set(series_to_run))
        if unknown:
            log.warning("Unknown series in --series, ignored: %s", ", ".join(unknown))

    if not series_to_run:
        log.error("No series to process")
        return 2

    workdir_ctx: tempfile.TemporaryDirectory | None = None
    if args.workdir:
        workdir = Path(args.workdir).resolve()
        workdir.mkdir(parents=True, exist_ok=True)
    else:
        workdir_ctx = tempfile.TemporaryDirectory(prefix="rocm-sync-")
        workdir = Path(workdir_ctx.name)

    report = reporting.Report()

    try:
        for series in series_to_run:
            series_cfg = cfg["series"][series] or {}
            skip = set(series_cfg.get("skip_packages", []) or [])

            try:
                current_pkgs = packages.query_rocm_packages(series)
            except Exception as e:  # noqa: BLE001
                log.error("Failed to enumerate packages for %s: %s", series, e)
                continue

            pkg_set = current_pkgs
            if requested_pkgs:
                pkg_set = [p for p in pkg_set if p in requested_pkgs]
            pkg_set = [p for p in pkg_set if p not in skip]

            log.info(
                "Series %s: %d packages to process (skipped %d)",
                series,
                len(pkg_set),
                len(skip),
            )

            for pkg in pkg_set:
                try:
                    _process_package(pkg, series, cfg, workdir, args.dry_run, report)
                except Exception as e:  # noqa: BLE001
                    log.exception("Unhandled error processing %s/%s", series, pkg)
                    report.add(
                        reporting.PackageOutcome(
                            pkg=pkg,
                            series=series,
                            status="error",
                            detail=f"unhandled: {e}",
                        )
                    )
    finally:
        reporting.write_summary(report)
        if workdir_ctx is not None:
            workdir_ctx.cleanup()

    # Conflicts and errors are not hard failures (they create issues / are
    # reported) — exit non-zero only on internal errors.
    return 1 if report.by_status("error") else 0


if __name__ == "__main__":
    sys.exit(main())
