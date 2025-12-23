# GitHub Changed Files Downloader

This script downloads the **union of all files changed** from a given commit up to a target ref (branch/tag/SHA) in a GitHub repository.

It is useful when you have a starting commit SHA and want to fetch *all files that changed since then* (across many commits), saving the **current versions** of those files at the target ref.

## What it does

- Computes the set of changed file paths using GitHub's **Compare API** for the range:
  - `base = --commit`
  - `head = --ref` (or default branch `HEAD` if omitted)
- Downloads each changed file's content at the **target ref** (not historical per-commit versions)
- Writes files under an output folder, preserving repository paths

## Requirements

- Python 3.8+
- Network access to `api.github.com`
- For private repos and/or higher rate limits: a GitHub token

## Usage

### Help

```bash
python scripts/github_changed_files_download.py -h
```

### Basic

```bash
python scripts/github_changed_files_download.py --repo owner/repo --commit <sha>
```

### Combined repo + commit

You can combine repo and commit into a single value, in either of these forms:

```bash
python scripts/github_changed_files_download.py --repo owner/repo/commit/<sha>
```

or:

```bash
python scripts/github_changed_files_download.py --repo https://github.com/owner/repo/commit/<sha>
```

When using these forms, `--commit` is optional because the SHA is inferred.

### Specify target ref

```bash
python scripts/github_changed_files_download.py --repo owner/repo --commit <sha> --ref main
```

### Provide a token (recommended)

Option A (environment variable):

PowerShell:
```powershell
$env:GITHUB_TOKEN="ghp_..."
python scripts/github_changed_files_download.py --repo owner/repo --commit <sha> --ref main
```

Option B (explicit argument):

```bash
python scripts/github_changed_files_download.py --repo owner/repo --commit <sha> --ref main --token ghp_...
```

### Output directory

```bash
python scripts/github_changed_files_download.py --repo owner/repo --commit <sha> --ref main --out .\downloads
```

### Overwrite existing files

```bash
python scripts/github_changed_files_download.py --repo owner/repo --commit <sha> --ref main --overwrite
```

## Notes / limitations

- **Base commit must be reachable from head**: GitHub Compare requires `--commit` to be an ancestor of `--ref` (or comparable in a straight line). If you see a compare status like `diverged`, pick the correct `--ref`.
- **Large ranges**: For very large commit ranges, GitHub may truncate compare results depending on API limits. If you hit this, the script can be extended to iterate commit-by-commit with pagination.
- **Renames**: The changed-path set uses the *new* path (`filename`) as reported by GitHub.
- **Removed files**: By default removed files are excluded; you can include them with `--include-removed` (they will usually be skipped on download because they no longer exist at the target ref).

## Output

By default, output is written to:

```
./downloads/<owner>_<repo>_<shortsha>_<ref>/
```

with repository paths preserved beneath that folder.
