"""Git operations for the ROCm sync flow.

All operations use `git` via subprocess; no Python git library is used.
The typical usage per package:

    repo = prepare_repo(workdir, pkg, series)
    state = analyze(repo)
    if state.action == "cherry-pick":
        cherry_pick_lp_onto_salsa(repo, state.merge_base)
"""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

LP_REMOTE = "lp"
SALSA_REMOTE = "salsa"

# Substrings that indicate a transient network/SSH failure worth retrying.
# Anything not matching is treated as a deterministic error (auth, ref not
# found, etc.) and surfaced immediately.
_TRANSIENT_PATTERNS = (
    "Connection timed out",
    "Connection reset",
    "banner exchange",
    "Could not resolve hostname",
    "Operation timed out",
    "early EOF",
    "RPC failed",
    "ssh_exchange_identification",
    "Network is unreachable",
)


class GitError(RuntimeError):
    pass


def _run(
    cmd: list[str],
    cwd: Path | None = None,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess:
    log.debug("git$ %s (cwd=%s)", " ".join(cmd), cwd)
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=check,
        capture_output=capture,
        text=True,
    )


def _is_transient(stderr: str) -> bool:
    return any(p in stderr for p in _TRANSIENT_PATTERNS)


def _run_retry(
    cmd: list[str],
    cwd: Path,
    *,
    retries: int = 2,
    backoff: float = 5.0,
) -> subprocess.CompletedProcess:
    """Run a command and retry on transient network/SSH failures. Returns
    the final CompletedProcess; caller is responsible for checking
    returncode. Non-transient errors return immediately without retry.
    """
    last: subprocess.CompletedProcess | None = None
    for attempt in range(retries + 1):
        last = _run(cmd, cwd=cwd, check=False)
        if last.returncode == 0 or not _is_transient(last.stderr or ""):
            return last
        if attempt < retries:
            delay = backoff * (2**attempt)
            tail = (last.stderr or "").strip().splitlines()
            log.warning(
                "Transient error on `%s` (attempt %d/%d): %s — retrying in %.1fs",
                " ".join(cmd[:3]),
                attempt + 1,
                retries + 1,
                tail[-1] if tail else "<no stderr>",
                delay,
            )
            time.sleep(delay)
    assert last is not None
    return last


def lp_url(pkg: str) -> str:
    return f"https://git.launchpad.net/ubuntu/+source/{pkg}"


def salsa_url(group: str, pkg: str) -> str:
    return f"git@salsa.debian.org:{group}/{pkg}.git"


@dataclass
class Repo:
    path: Path
    pkg: str
    series: str
    branch: str  # ubuntu/<series>
    lp_tip: str | None = None
    salsa_tip: str | None = None


@dataclass
class AnalysisResult:
    """What the comparison between LP and Salsa says we should do."""

    action: str  # "skip-equal", "skip-no-base", "rebase", "fast-forward"
    detail: str
    merge_base: str | None = None


def prepare_repo(
    workdir: Path,
    pkg: str,
    series: str,
    salsa_group: str,
) -> Repo:
    """Initialize a working repo with both LP and Salsa remotes and fetch
    branch `ubuntu/<series>` from each. Returns the populated Repo state.

    Raises GitError if either branch cannot be fetched.
    """
    branch = f"ubuntu/{series}"
    repo_path = workdir / pkg
    if repo_path.exists():
        # Re-use prior clone for idempotency, but reset to a clean state.
        _run(["git", "-C", str(repo_path), "reset", "--hard"], check=False)
        _run(["git", "-C", str(repo_path), "rebase", "--abort"], check=False)
        _run(["git", "-C", str(repo_path), "clean", "-fdx"], check=False)
    else:
        repo_path.mkdir(parents=True)
        _run(["git", "init", "-q", str(repo_path)])

    repo = Repo(path=repo_path, pkg=pkg, series=series, branch=branch)

    # Configure remotes (idempotent).
    for remote, url in (
        (LP_REMOTE, lp_url(pkg)),
        (SALSA_REMOTE, salsa_url(salsa_group, pkg)),
    ):
        existing = _run(
            ["git", "remote", "get-url", remote], cwd=repo_path, check=False
        )
        if existing.returncode != 0:
            _run(["git", "remote", "add", remote, url], cwd=repo_path)
        else:
            _run(["git", "remote", "set-url", remote, url], cwd=repo_path)

    # Identity for any rebase commits (shouldn't be needed, but git is picky).
    _run(["git", "config", "user.email", "rocm-sync@canonical.com"], cwd=repo_path)
    _run(["git", "config", "user.name", "ROCm Sync Bot"], cwd=repo_path)

    # Fetch both branches. LP must exist; if Salsa doesn't, the caller can
    # fork. --no-tags: tags are noise we never read. Retries handle transient
    # SSH/banner-exchange failures.
    lp_fetch = _run_retry(
        ["git", "fetch", "--no-tags", LP_REMOTE, branch],
        cwd=repo_path,
    )
    if lp_fetch.returncode != 0:
        raise GitError(
            f"LP branch {branch!r} for {pkg} could not be fetched: {lp_fetch.stderr.strip()}"
        )
    repo.lp_tip = _rev_parse(repo_path, f"{LP_REMOTE}/{branch}")

    salsa_fetch = _run_retry(
        ["git", "fetch", "--no-tags", SALSA_REMOTE, branch],
        cwd=repo_path,
    )
    if salsa_fetch.returncode == 0:
        repo.salsa_tip = _rev_parse(repo_path, f"{SALSA_REMOTE}/{branch}")
    else:
        log.warning(
            "Salsa branch %s for %s could not be fetched: %s",
            branch,
            pkg,
            salsa_fetch.stderr.strip(),
        )
        repo.salsa_tip = None

    return repo


def _rev_parse(repo_path: Path, ref: str) -> str:
    return _run(["git", "rev-parse", ref], cwd=repo_path).stdout.strip()


def trees_equal(repo: Repo, ref_a: str, ref_b: str) -> bool:
    """True if the two refs point at trees with identical content."""
    res = _run(
        ["git", "diff", "--quiet", ref_a, ref_b],
        cwd=repo.path,
        check=False,
    )
    return res.returncode == 0


def analyze(repo: Repo) -> AnalysisResult:
    """Decide what action to take based on LP vs Salsa state."""
    lp_ref = f"{LP_REMOTE}/{repo.branch}"

    if repo.salsa_tip is None:
        return AnalysisResult(
            action="skip-no-salsa-branch",
            detail="salsa branch missing",
        )

    salsa_ref = f"{SALSA_REMOTE}/{repo.branch}"

    if trees_equal(repo, lp_ref, salsa_ref):
        return AnalysisResult(action="skip-equal", detail="trees identical")

    # LP is fully an ancestor of Salsa: Salsa already has every LP commit
    # plus its own work on top. Nothing to bring from LP.
    if _is_ancestor(repo.path, lp_ref, salsa_ref):
        return AnalysisResult(
            action="skip-salsa-ahead",
            detail="salsa is ahead of LP (already includes LP changes)",
        )

    merge_base_proc = _run(
        ["git", "merge-base", lp_ref, salsa_ref],
        cwd=repo.path,
        check=False,
    )
    if merge_base_proc.returncode != 0 or not merge_base_proc.stdout.strip():
        return AnalysisResult(
            action="skip-no-base",
            detail="LP and Salsa share no common ancestor",
        )

    # Either Salsa is strictly behind LP (degenerate cherry-pick = ff) or
    # the two have diverged. Both are handled the same way: cherry-pick LP-
    # only commits onto Salsa-tip, filtered to ones touching only debian/.
    return AnalysisResult(
        action="cherry-pick",
        detail="LP has commits not in Salsa",
        merge_base=merge_base_proc.stdout.strip(),
    )


def _is_ancestor(repo_path: Path, ancestor: str, descendant: str) -> bool:
    res = _run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=repo_path,
        check=False,
    )
    return res.returncode == 0


def _merge_base(repo_path: Path, a: str, b: str) -> str:
    return _run(["git", "merge-base", a, b], cwd=repo_path).stdout.strip()


@dataclass
class CherryPickResult:
    head: str
    picked: list[tuple[str, str]] = field(default_factory=list)  # (orig_sha, subject)
    skipped_non_debian: list[tuple[str, str, list[str]]] = field(
        default_factory=list
    )  # (sha, subject, paths)
    already_applied: list[tuple[str, str]] = field(
        default_factory=list
    )  # (orig_sha, subject) — patch-id-equivalent already in salsa


def _commit_paths(repo_path: Path, sha: str) -> list[str]:
    res = _run(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", sha],
        cwd=repo_path,
    )
    return [p for p in res.stdout.splitlines() if p.strip()]


def _commit_subject(repo_path: Path, sha: str) -> str:
    res = _run(["git", "log", "-1", "--format=%s", sha], cwd=repo_path)
    return res.stdout.strip()


def _classify_lp_commits(
    repo_path: Path,
    salsa_ref: str,
    lp_ref: str,
    merge_base: str,
) -> dict[str, str]:
    """Run `git cherry` to classify each LP-only commit by patch-id against
    Salsa. Returns {sha: status} where status is '+' (needs apply) or '-'
    (patch-id-equivalent already in salsa under a different SHA).
    """
    res = _run(
        ["git", "cherry", salsa_ref, lp_ref, merge_base],
        cwd=repo_path,
    )
    out: dict[str, str] = {}
    for line in res.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        prefix, _, sha = line.partition(" ")
        if prefix in ("+", "-") and sha:
            out[sha] = prefix
    return out


def cherry_pick_lp_onto_salsa(repo: Repo, merge_base: str) -> CherryPickResult:
    """Start from Salsa-tip on a fresh local branch, then cherry-pick each
    LP-only commit (merge_base..lp-tip, oldest first) that exclusively
    touches `debian/` and isn't already on Salsa by patch-id.

    Buckets in the returned result:
      - picked: applied successfully
      - already_applied: patch-id matches an existing salsa commit; skipped
      - skipped_non_debian: touched paths outside debian/; skipped + flagged

    Raises GitError on a real cherry-pick conflict; the local branch is
    reset to Salsa-tip so the working state is clean for the next run.
    """
    local = f"sync/{repo.branch}"
    lp_ref = f"{LP_REMOTE}/{repo.branch}"
    salsa_ref = f"{SALSA_REMOTE}/{repo.branch}"

    _run(["git", "checkout", "-B", local, salsa_ref], cwd=repo.path)

    log_proc = _run(
        ["git", "log", "--reverse", "--format=%H", f"{merge_base}..{lp_ref}"],
        cwd=repo.path,
    )
    candidates = [s for s in log_proc.stdout.split() if s]
    classification = _classify_lp_commits(
        repo.path, salsa_ref, lp_ref, merge_base
    )

    result = CherryPickResult(head=_rev_parse(repo.path, "HEAD"))
    for sha in candidates:
        subject = _commit_subject(repo.path, sha)
        if classification.get(sha) == "-":
            log.info(
                "Skipping %s (%s): patch-id already in salsa", sha[:10], subject
            )
            result.already_applied.append((sha, subject))
            continue
        paths = _commit_paths(repo.path, sha)
        if not paths:
            log.info("Skipping %s (%s): empty commit", sha[:10], subject)
            continue
        if not all(p.startswith("debian/") for p in paths):
            log.warning(
                "Skipping %s (%s): touches non-debian/ paths: %s",
                sha[:10],
                subject,
                ", ".join(paths[:5]) + (" …" if len(paths) > 5 else ""),
            )
            result.skipped_non_debian.append((sha, subject, paths))
            continue
        pick = _run(
            ["git", "cherry-pick", "-x", "--empty=drop", sha],
            cwd=repo.path,
            check=False,
        )
        if pick.returncode != 0:
            log.warning(
                "Cherry-pick failed at %s (%s): %s",
                sha[:10],
                subject,
                pick.stderr.strip() or pick.stdout.strip(),
            )
            _run(["git", "cherry-pick", "--abort"], cwd=repo.path, check=False)
            _run(["git", "reset", "--hard", salsa_ref], cwd=repo.path, check=False)
            raise GitError(
                f"cherry-pick conflict for {repo.pkg} on {repo.branch} at {sha[:10]}"
            )
        # If --empty=drop dropped the commit, HEAD didn't move. Detect by
        # comparing HEAD after to the last picked commit (or salsa-tip if
        # nothing picked yet). Simpler: compare the diff vs HEAD's parent.
        head_after = _rev_parse(repo.path, "HEAD")
        if head_after == result.head:
            log.info(
                "Skipping %s (%s): cherry-pick produced empty commit (dropped)",
                sha[:10],
                subject,
            )
            result.already_applied.append((sha, subject))
            continue
        result.head = head_after
        result.picked.append((sha, subject))

    result.head = _rev_parse(repo.path, "HEAD")
    return result


def push_to_fork(
    repo: Repo,
    salsa_user: str,
    push_branch: str,
) -> None:
    """Force-push the local sync branch to the user's Salsa fork."""
    fork_url = f"git@salsa.debian.org:{salsa_user}/{repo.pkg}.git"
    _run(
        ["git", "remote", "remove", "fork"],
        cwd=repo.path,
        check=False,
    )
    _run(["git", "remote", "add", "fork", fork_url], cwd=repo.path)
    push = _run_retry(
        ["git", "push", "--force", "fork", f"HEAD:refs/heads/{push_branch}"],
        cwd=repo.path,
    )
    if push.returncode != 0:
        raise GitError(
            f"push to fork failed for {repo.pkg}: {push.stderr.strip()}"
        )


def get_changelog_version(repo: Repo, ref: str) -> str | None:
    """Best-effort: return the topmost version from debian/changelog at the
    given ref. Returns None if the file isn't present."""
    res = _run(
        ["git", "show", f"{ref}:debian/changelog"],
        cwd=repo.path,
        check=False,
    )
    if res.returncode != 0 or not res.stdout:
        return None
    first = res.stdout.splitlines()[0] if res.stdout.splitlines() else ""
    # Format: "package (version) suite; urgency=..."
    if "(" in first and ")" in first:
        return first.split("(", 1)[1].split(")", 1)[0]
    return None
