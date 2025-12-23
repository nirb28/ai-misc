import argparse
import base64
import os
import sys
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple

import urllib.request
import urllib.error


@dataclass
class GitHubClient:
    token: Optional[str]
    api_base: str = "https://api.github.com"

    def _request(self, url: str) -> dict:
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("User-Agent", "ai-misc-github-changes-downloader")
        # Using a token avoids strict rate limits and allows private repos.
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read().decode("utf-8")
                import json

                return json.loads(data)
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8")
            except Exception:
                pass
            raise RuntimeError(f"GitHub API error {e.code} for {url}: {body}") from e

    def compare(self, owner: str, repo: str, base: str, head: str) -> dict:
        # https://docs.github.com/en/rest/commits/commits#compare-two-commits
        url = f"{self.api_base}/repos/{owner}/{repo}/compare/{base}...{head}"
        return self._request(url)

    def get_commit(self, owner: str, repo: str, sha: str) -> dict:
        url = f"{self.api_base}/repos/{owner}/{repo}/commits/{sha}"
        return self._request(url)

    def get_content(self, owner: str, repo: str, path: str, ref: str) -> dict:
        # https://docs.github.com/en/rest/repos/contents#get-repository-content
        # Note: path must be URL-encoded.
        from urllib.parse import quote

        enc_path = quote(path)
        url = f"{self.api_base}/repos/{owner}/{repo}/contents/{enc_path}?ref={quote(ref)}"
        return self._request(url)


def parse_repo(repo: str) -> Tuple[str, str]:
    if repo.count("/") != 1:
        raise ValueError("--repo must be in the form owner/repo")
    owner, name = repo.split("/", 1)
    owner = owner.strip()
    name = name.strip()
    if not owner or not name:
        raise ValueError("--repo must be in the form owner/repo")
    return owner, name


def parse_repo_and_optional_commit(value: str) -> Tuple[str, str, Optional[str]]:
    """Parse repo (owner/repo) and optionally extract commit sha.

    Supported inputs:
    - owner/repo
    - owner/repo/commit/<sha>
    - https://github.com/owner/repo/commit/<sha>
    """
    raw = (value or "").strip()
    if not raw:
        raise ValueError("--repo is required")

    if raw.startswith("http://") or raw.startswith("https://"):
        from urllib.parse import urlparse

        p = urlparse(raw)
        path = (p.path or "").strip("/")
    else:
        path = raw.strip("/")

    parts = [p for p in path.split("/") if p]
    if len(parts) >= 4 and parts[2].lower() == "commit":
        owner = parts[0]
        repo = parts[1]
        sha = parts[3]
        if not owner or not repo or not sha:
            raise ValueError("Invalid combined repo/commit format")
        return owner, repo, sha

    if len(parts) == 2:
        owner, repo = parse_repo("/".join(parts))
        return owner, repo, None

    raise ValueError(
        "--repo must be one of: owner/repo, owner/repo/commit/<sha>, or https://github.com/owner/repo/commit/<sha>"
    )


def ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def safe_write_bytes(target_path: str, data: bytes, overwrite: bool) -> None:
    if (not overwrite) and os.path.exists(target_path):
        return
    ensure_parent_dir(target_path)
    with open(target_path, "wb") as f:
        f.write(data)


def extract_changed_paths(compare_payload: dict, include_removed: bool) -> Set[str]:
    # compare API returns a 'files' array with per-file status.
    files = compare_payload.get("files") or []
    changed: Set[str] = set()
    for f in files:
        filename = f.get("filename")
        status = (f.get("status") or "").lower()
        if not filename:
            continue
        if status == "removed" and not include_removed:
            continue
        # We download by 'filename' at the target ref; for renamed files this is the new path.
        changed.add(filename)
    return changed


def extract_paths_from_commit(commit_payload: dict, include_removed: bool) -> Set[str]:
    # single commit API returns a 'files' array similar to compare API.
    files = commit_payload.get("files") or []
    changed: Set[str] = set()
    for f in files:
        filename = f.get("filename")
        status = (f.get("status") or "").lower()
        if not filename:
            continue
        if status == "removed" and not include_removed:
            continue
        changed.add(filename)
    return changed


def download_file_at_ref(
    gh: GitHubClient,
    owner: str,
    repo: str,
    path: str,
    ref: str,
    out_root: str,
    overwrite: bool,
) -> Tuple[bool, str]:
    """Returns (downloaded, message)."""
    target_path = os.path.join(out_root, path.replace("/", os.sep))

    # Skip existing if not overwriting
    if (not overwrite) and os.path.exists(target_path):
        return False, f"exists: {path}"

    try:
        content = gh.get_content(owner, repo, path, ref)
    except RuntimeError as e:
        # If the file was removed, GitHub returns 404.
        return False, f"skip: {path} ({e})"

    if content.get("type") != "file":
        return False, f"skip: {path} (not a file type={content.get('type')})"

    encoding = content.get("encoding")
    body = content.get("content")

    if encoding == "base64" and isinstance(body, str):
        # GitHub includes line breaks in base64 content.
        data = base64.b64decode(body)
        safe_write_bytes(target_path, data, overwrite=overwrite)
        return True, f"downloaded: {path}"

    # Fallback to download_url if provided
    download_url = content.get("download_url")
    if isinstance(download_url, str) and download_url:
        req = urllib.request.Request(download_url)
        req.add_header("User-Agent", "ai-misc-github-changes-downloader")
        if gh.token:
            req.add_header("Authorization", f"Bearer {gh.token}")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            safe_write_bytes(target_path, data, overwrite=overwrite)
            return True, f"downloaded: {path}"
        except Exception as e:
            return False, f"skip: {path} (download_url failed: {e})"

    return False, f"skip: {path} (unknown content encoding)"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Download the union of all files changed since a given GitHub commit, "
            "and save the current versions of those files at a target ref."
        )
    )
    parser.add_argument(
        "--repo",
        required=True,
        help=(
            "GitHub repository in the form owner/repo (e.g. elastic/elasticsearch) OR a combined commit path "
            "like owner/repo/commit/<sha> (also supports full GitHub commit URLs)."
        ),
    )
    parser.add_argument(
        "--commit",
        required=False,
        help=(
            "Base commit SHA. The script collects changes from this commit up to the target ref (inclusive). "
            "If --repo is provided in the form owner/repo/commit/<sha>, this can be omitted."
        ),
    )
    parser.add_argument(
        "--ref",
        default=None,
        help=(
            "Target ref/branch/commit to compare against (default: repo default branch head). "
            "Examples: main, master, a SHA, or a tag."
        ),
    )
    parser.add_argument(
        "--out",
        default=None,
        help=(
            "Output folder (default: ./downloads/<owner>_<repo>_<shortsha>_<ref>/). "
            "Files are written preserving their repository paths."
        ),
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN"),
        help=(
            "GitHub token (recommended). Defaults to env var GITHUB_TOKEN if present. "
            "Needed for private repos and higher rate limits."
        ),
    )
    parser.add_argument(
        "--include-removed",
        action="store_true",
        help="Include removed files in the changed-path set (they will likely be skipped during download).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files in the output directory.",
    )
    parser.add_argument(
        "--api-base",
        default="https://api.github.com",
        help="GitHub API base URL (default: https://api.github.com).",
    )

    args = parser.parse_args(argv)

    owner, repo, repo_sha = parse_repo_and_optional_commit(args.repo)
    gh = GitHubClient(token=args.token, api_base=args.api_base)

    base_sha = (repo_sha or (args.commit or "").strip())
    if not base_sha:
        raise ValueError("--commit is required unless --repo includes /commit/<sha>")

    # Determine target ref SHA if not provided.
    if args.ref:
        head_ref = args.ref.strip()
    else:
        # Use repository info via commit endpoint? GitHub doesn't provide repo info here without another endpoint.
        # Instead, use the compare endpoint with '...HEAD' by resolving HEAD via default branch commit.
        # We'll fetch base commit first just to validate it exists.
        gh.get_commit(owner, repo, base_sha)
        head_ref = "HEAD"

    compare_payload = gh.compare(owner, repo, base_sha, head_ref)

    # If base is not an ancestor of head, GitHub compare returns status 'diverged'.
    status = (compare_payload.get("status") or "").lower()
    if status not in {"ahead", "identical", "behind"}:
        raise RuntimeError(
            f"Compare status was '{status}'. Ensure --commit is reachable from --ref (or default branch)."
        )

    changed_paths = extract_changed_paths(compare_payload, include_removed=args.include_removed)

    # GitHub compare(base...head) does NOT include the base commit's own diff.
    # To make the range inclusive ("including and after"), union the base commit's changed files.
    base_commit_payload = gh.get_commit(owner, repo, base_sha)
    changed_paths |= extract_paths_from_commit(base_commit_payload, include_removed=args.include_removed)

    # Compute a default output path.
    short_sha = base_sha[:7]
    safe_ref = (args.ref or "HEAD").replace("/", "_")
    out_root = args.out or os.path.join(
        os.getcwd(), "downloads", f"{owner}_{repo}_{short_sha}_{safe_ref}"
    )

    os.makedirs(out_root, exist_ok=True)

    total = len(changed_paths)
    downloaded = 0
    skipped = 0

    # Deterministic order
    for i, path in enumerate(sorted(changed_paths)):
        ok, msg = download_file_at_ref(
            gh=gh,
            owner=owner,
            repo=repo,
            path=path,
            ref=(args.ref or "HEAD"),
            out_root=out_root,
            overwrite=args.overwrite,
        )
        if ok:
            downloaded += 1
        else:
            skipped += 1

        # Lightweight progress (avoid excessive output)
        if (i + 1) % 50 == 0 or (i + 1) == total:
            print(f"[{i+1}/{total}] downloaded={downloaded} skipped={skipped}")

    print(f"\nDone.")
    print(f"Repo: {owner}/{repo}")
    print(f"Base commit: {base_sha}")
    print(f"Target ref: {args.ref or 'default branch HEAD'}")
    print(f"Changed files (unique): {total}")
    print(f"Downloaded: {downloaded}")
    print(f"Skipped: {skipped}")
    print(f"Output: {out_root}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
