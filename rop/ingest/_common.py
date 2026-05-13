"""Common utilities for source-authority ingest pipelines.

Provides three layers of shared infrastructure:

1. Download — fetch a source release (ZIP, tarball, OBO file) to a local
   staging directory, with caching and content verification.
2. Parse — normalize various source formats (CSV, TSV, OBO, JSON, XML)
   into a common iterable-of-dicts intermediate.
3. Build — convert parsed dicts into validated RoPElement instances with
   provenance fully populated.

All ingest modules in this package depend on these utilities.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import subprocess
import tarfile
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Iterator, Iterable, Any
from urllib.parse import urlparse
from urllib.request import urlopen, Request

logger = logging.getLogger(__name__)


# Default directory layout for source staging. Can be overridden per call.
DEFAULT_SOURCES_DIR = Path("data/sources")
DEFAULT_STAGING_DIR = Path("data/foundation/staging")


# ---------------------------------------------------------------------------
# Download layer
# ---------------------------------------------------------------------------

@dataclass
class DownloadResult:
    """Outcome of a single source download."""
    source_name: str
    local_path: Path
    bytes_downloaded: int
    sha256: str
    cached: bool  # True if pre-existing file was reused
    download_url: str
    retrieved_at: datetime = field(default_factory=datetime.utcnow)


_ALLOWED_HTTP_SCHEMES = frozenset({"http", "https"})


def _validate_http_url(url: str) -> str:
    """Reject non-HTTP(S) URLs and URLs that could be option-injected.

    Returns the validated URL stripped of leading/trailing whitespace.
    Refuses file://, ftp://, gopher://, javascript:, data:, etc. — these
    have no business in a download path and historically have been used
    to exfiltrate local files or trigger SSRF.
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError("Empty or non-string download URL")
    url = url.strip()
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in _ALLOWED_HTTP_SCHEMES:
        raise ValueError(
            f"Refusing download URL with scheme {scheme!r}: only "
            f"{sorted(_ALLOWED_HTTP_SCHEMES)} allowed"
        )
    if not parsed.netloc:
        raise ValueError(f"Download URL has no host: {url!r}")
    return url


def http_download(
    url: str,
    dest: Path,
    *,
    user_agent: str = "RoP-ingest/0.13 (+https://github.com/datatecnica)",
    chunk_size: int = 1024 * 1024,
    overwrite: bool = False,
    timeout: float = 300.0,
) -> DownloadResult:
    """Download a file over HTTP(S) with chunked streaming and SHA-256 hashing.

    Idempotent: if dest exists and overwrite is False, returns the existing
    file's hash without re-downloading. This is critical for weekend-long
    pipelines that may restart partway.

    Security:
      - URL scheme limited to {http, https} (no file://, ftp://, etc.)
      - Connection times out after `timeout` seconds (default 5 min) so a
        misbehaving server can't hang the orchestrator indefinitely
    """
    url = _validate_http_url(url)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists() and not overwrite:
        sha256 = _file_sha256(dest)
        return DownloadResult(
            source_name=dest.name,
            local_path=dest,
            bytes_downloaded=dest.stat().st_size,
            sha256=sha256,
            cached=True,
            download_url=url,
        )

    logger.info("Downloading %s → %s", url, dest)
    req = Request(url, headers={"User-Agent": user_agent})
    hasher = hashlib.sha256()
    bytes_total = 0

    with urlopen(req, timeout=timeout) as resp, dest.open("wb") as out:
        while chunk := resp.read(chunk_size):
            out.write(chunk)
            hasher.update(chunk)
            bytes_total += len(chunk)

    return DownloadResult(
        source_name=dest.name,
        local_path=dest,
        bytes_downloaded=bytes_total,
        sha256=hasher.hexdigest(),
        cached=False,
        download_url=url,
    )


def _validate_git_url(url: str) -> None:
    """Reject URLs that could be option-injected into git invocations.

    Git treats arguments starting with '-' as options. A URL like
    '--upload-pack=evil' executes attacker-controlled commands on clone.
    Limit to known-safe schemes.
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError("Empty or non-string git URL")
    url = url.strip()
    if url.startswith("-"):
        raise ValueError(
            f"Refusing git URL that begins with '-' (option-injection risk): {url!r}"
        )
    # Allowed schemes: https, git (rsync-style git@host:path), ssh
    allowed_prefixes = ("https://", "http://", "git@", "git://", "ssh://")
    if not any(url.startswith(p) for p in allowed_prefixes):
        raise ValueError(
            f"Refusing git URL with unrecognized scheme: {url!r}. "
            f"Allowed: {allowed_prefixes}"
        )


def git_clone(
    repo_url: str,
    dest: Path,
    *,
    depth: int = 1,
    branch: str | None = None,
    overwrite: bool = False,
) -> DownloadResult:
    """Shallow-clone a git repository to the staging directory.

    Used for OBO-Foundry ontologies (HPO, Mondo, DUO, UBERON, CL) which
    publish releases as git repos. Shallow clone keeps the staging size
    manageable; we only need the latest release artifact.
    """
    _validate_git_url(repo_url)
    if branch is not None:
        if not isinstance(branch, str) or branch.startswith("-"):
            raise ValueError(
                f"Refusing branch name that begins with '-': {branch!r}"
            )

    dest = Path(dest)
    if dest.exists() and not overwrite:
        head = _git_head_sha(dest)
        size = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file())
        return DownloadResult(
            source_name=dest.name,
            local_path=dest,
            bytes_downloaded=size,
            sha256=head,
            cached=True,
            download_url=repo_url,
        )
    if dest.exists():
        # Refuse to delete paths that don't look like staging (must contain .git
        # or be empty) — defense against accidental dest=/home/user
        is_git_repo = (dest / ".git").exists()
        is_empty = not any(dest.iterdir())
        if not (is_git_repo or is_empty):
            raise ValueError(
                f"Refusing to overwrite non-empty non-git directory: {dest}"
            )
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Build cmd with `--` separator so repo_url and dest can never be
    # interpreted as options even if validation above is bypassed
    cmd = ["git", "clone", "--depth", str(depth)]
    if branch:
        cmd += ["--branch", branch]
    cmd += ["--", repo_url, str(dest)]
    logger.info("git clone %s → %s", repo_url, dest)
    subprocess.run(cmd, check=True, capture_output=True, timeout=300)

    head = _git_head_sha(dest)
    size = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file())
    return DownloadResult(
        source_name=dest.name,
        local_path=dest,
        bytes_downloaded=size,
        sha256=head,
        cached=False,
        download_url=repo_url,
    )


def _file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def _git_head_sha(repo_dir: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def _is_within(child: Path, parent: Path) -> bool:
    """Return True if `child` resolves to a path under `parent`.

    Used to validate archive members before extraction. Rejects absolute
    paths, parent-traversal sequences, and symlinks pointing outside the
    destination directory.
    """
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _safe_extract_zip(zip_path: Path, dest_dir: Path) -> None:
    """Extract ZIP with path-traversal protection.

    Each member is validated to resolve under dest_dir before extraction.
    Members with absolute paths, parent-traversal (..), or that point
    outside dest_dir via symlinks are rejected outright.
    """
    dest_resolved = dest_dir.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            # Reject absolute paths and Windows drive letters
            name = member.filename
            if name.startswith("/") or name.startswith("\\") or ":" in name[:3]:
                raise ValueError(
                    f"Refusing to extract ZIP member with absolute path: {name!r}"
                )
            # Reject parent-traversal anywhere in the path
            parts = Path(name).parts
            if any(p == ".." for p in parts):
                raise ValueError(
                    f"Refusing to extract ZIP member with parent traversal: {name!r}"
                )
            # Validate the resolved target stays inside dest_dir
            target = (dest_resolved / name).resolve()
            try:
                target.relative_to(dest_resolved)
            except ValueError:
                raise ValueError(
                    f"ZIP member {name!r} would extract outside {dest_resolved}"
                )
        # All members validated; extract
        zf.extractall(dest_dir)


def _safe_extract_tar(tar_path: Path, dest_dir: Path) -> None:
    """Extract tarball with path-traversal protection.

    Validates every member's path before extraction:
      - rejects absolute paths (Unix and Windows)
      - rejects parent-traversal (..) anywhere in the path
      - rejects symlinks/hardlinks pointing outside dest_dir
      - clears setuid/setgid/sticky bits (matches Python 3.12 'data' filter)

    Behavior is consistent across Python 3.10+. We don't delegate to
    Python 3.12's `filter='data'` here because that filter silently
    strips leading slashes (turning '/etc/passwd' into 'etc/passwd')
    rather than rejecting — preventing escape but altering paths in a
    way callers may not expect. Strict rejection is the predictable
    contract.
    """
    dest_resolved = dest_dir.resolve()
    with tarfile.open(tar_path) as tf:
        members = tf.getmembers()
        for member in members:
            name = member.name
            if name.startswith("/") or name.startswith("\\"):
                raise ValueError(
                    f"Refusing to extract tar member with absolute path: {name!r}"
                )
            parts = Path(name).parts
            if any(p == ".." for p in parts):
                raise ValueError(
                    f"Refusing to extract tar member with parent traversal: {name!r}"
                )
            target = (dest_resolved / name).resolve()
            try:
                target.relative_to(dest_resolved)
            except ValueError:
                raise ValueError(
                    f"Tar member {name!r} would extract outside {dest_resolved}"
                )
            # Reject symlinks / hardlinks pointing outside dest_dir
            if member.issym() or member.islnk():
                link_target = (target.parent / member.linkname).resolve()
                try:
                    link_target.relative_to(dest_resolved)
                except ValueError:
                    raise ValueError(
                        f"Tar member {name!r} contains link pointing outside "
                        f"{dest_resolved}"
                    )
            # Strip setuid/setgid/sticky bits (matches the 3.12 'data' filter)
            member.mode &= 0o755

        # All members validated. Extract with stdlib 'data' filter as
        # belt-and-suspenders defense (and future-proofs for Python 3.14
        # where filter is required). On 3.10/3.11 the filter parameter is
        # supported but uses a fallback validator.
        if hasattr(tarfile, "data_filter"):
            tf.extractall(dest_dir, filter="data")
        else:
            tf.extractall(dest_dir)


def extract_archive(archive_path: Path, dest_dir: Path) -> Path:
    """Extract a ZIP or tarball into dest_dir; returns dest_dir.

    Path-traversal-safe: archive members are validated to resolve under
    dest_dir before any file is written. Rejects:
      - absolute paths in member names
      - parent-traversal (..) sequences
      - symlinks pointing outside dest_dir
      - setuid/setgid/sticky bits on tar members (3.12+ filter='data',
        manual reset for older Pythons)
    """
    archive_path = Path(archive_path)
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    if archive_path.suffix.lower() == ".zip":
        _safe_extract_zip(archive_path, dest_dir)
    elif archive_path.name.endswith((".tar.gz", ".tgz", ".tar.bz2", ".tar.xz", ".tar")):
        _safe_extract_tar(archive_path, dest_dir)
    else:
        raise ValueError(f"Unrecognized archive format: {archive_path}")

    logger.info("Extracted %s → %s", archive_path, dest_dir)
    return dest_dir


# ---------------------------------------------------------------------------
# Parse layer — common normalizations
# ---------------------------------------------------------------------------

def normalize_pipe_delimited(*candidates: str | None) -> str | None:
    """Combine multiple synonym-list strings into a single pipe-delimited
    string with deduplication and stripping. Used for alternate_names.
    """
    seen: set[str] = set()
    out: list[str] = []
    for cand in candidates:
        if not cand:
            continue
        # Tolerate input using comma, semicolon, or pipe
        for sep in (";", ","):
            cand = cand.replace(sep, "|")
        for tok in cand.split("|"):
            tok = tok.strip()
            if tok and tok not in seen:
                seen.add(tok)
                out.append(tok)
    return "|".join(out) if out else None


def normalize_id(raw: str) -> str:
    """Strip whitespace, normalize case for vocabulary IDs.
    Examples: 'HP:0001234 ' → 'HP:0001234'; 'mondo:0005180' → 'MONDO:0005180'.
    """
    raw = raw.strip()
    if ":" in raw:
        prefix, rest = raw.split(":", 1)
        return f"{prefix.upper()}:{rest}"
    return raw


# OBO file parser — minimal, handles the term-stanza fields we care about.
# We avoid a heavy dependency on `pronto` which is overkill for our needs.
def parse_obo(path: Path | str) -> Iterator[dict[str, Any]]:
    """Yield one dict per [Term] stanza in an OBO file.

    Captures: id, name, def, synonym, xref, is_a, is_obsolete, replaced_by.
    Multi-valued fields (synonym, xref, is_a) are returned as lists.
    """
    path = Path(path)
    current: dict[str, Any] | None = None
    in_term = False

    with path.open(encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n").strip()
            if not line:
                if current is not None:
                    yield current
                    current = None
                in_term = False
                continue

            if line == "[Term]":
                if current is not None:
                    yield current
                current = {"_kind": "Term"}
                in_term = True
                continue

            if line.startswith("[") and line.endswith("]"):
                # Other stanza types (Typedef, Instance) — ignore for now
                if current is not None:
                    yield current
                    current = None
                in_term = False
                continue

            if not in_term or current is None:
                continue

            if ": " not in line:
                continue
            key, _, value = line.partition(": ")

            # Inline comments after the value are stripped
            value = re.sub(r"\s*!\s*.*$", "", value).strip()

            if key in ("synonym", "xref", "is_a", "alt_id", "subset",
                      "property_value", "consider", "intersection_of"):
                current.setdefault(key, []).append(value)
            else:
                current[key] = value

        if current is not None:
            yield current


def obo_extract_synonyms(term: dict[str, Any]) -> list[str]:
    """Pull synonym strings out of an OBO term dict, stripping the OBO scope tags."""
    out = []
    for s in term.get("synonym", []):
        # OBO synonyms look like: "Synonym name" EXACT [SOURCE:CODE]
        m = re.match(r'^"([^"]+)"', s)
        if m:
            out.append(m.group(1))
    return out


def obo_extract_xrefs(term: dict[str, Any]) -> list[str]:
    """Pull database cross-references from xref lines."""
    out = []
    for x in term.get("xref", []):
        # xref values look like: 'OMIM:168600' or 'MESH:D010300 "Parkinson Disease"'
        x = x.split(" ")[0].rstrip(",")
        if ":" in x:
            out.append(normalize_id(x))
    return out


def obo_extract_definition(term: dict[str, Any]) -> str:
    """Pull the definition string out of an OBO term, stripping citation."""
    raw = term.get("def", "")
    m = re.match(r'^"([^"]+)"', raw)
    return m.group(1) if m else raw


# ---------------------------------------------------------------------------
# Build layer — common RoPElement scaffolding
# ---------------------------------------------------------------------------

def build_alternate_codes_jsonb(
    primary: tuple[str, str] | None,
    crossrefs: Iterable[tuple[str, str]] = (),
) -> list[dict[str, str]]:
    """Build an alternate_codes JSONB array.

    Each entry is {vocabulary, code} where vocabulary is the source-authority
    name and code is the source-vocabulary identifier. Used to populate
    ClinicalConceptAlternativeCodes-style fields.
    """
    out = []
    if primary:
        out.append({"vocabulary": primary[0], "code": primary[1]})
    for vocab, code in crossrefs:
        if not vocab or not code:
            continue
        out.append({"vocabulary": vocab, "code": code})
    return out


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

@dataclass
class IngestStats:
    """Aggregate counters from one ingest run."""
    source_name: str
    rows_yielded: int = 0
    rows_skipped: int = 0
    parse_errors: int = 0
    elapsed_seconds: float = 0.0
    output_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_name": self.source_name,
            "rows_yielded": self.rows_yielded,
            "rows_skipped": self.rows_skipped,
            "parse_errors": self.parse_errors,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "output_path": str(self.output_path) if self.output_path else None,
        }


def write_manifest(
    sources_dir: Path,
    downloads: list[DownloadResult],
    stats: list[IngestStats],
) -> Path:
    """Write a JSON manifest summarizing what was downloaded and ingested.
    Used at the end of a Monday-morning bulk ingest run.
    """
    sources_dir = Path(sources_dir)
    sources_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "manifest_version": 1,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "downloads": [
            {
                "source_name": d.source_name,
                "local_path": str(d.local_path),
                "bytes_downloaded": d.bytes_downloaded,
                "sha256": d.sha256,
                "cached": d.cached,
                "download_url": d.download_url,
                "retrieved_at": d.retrieved_at.isoformat() + "Z",
            }
            for d in downloads
        ],
        "ingests": [s.to_dict() for s in stats],
    }
    out = sources_dir / "manifest.json"
    out.write_text(json.dumps(payload, indent=2))
    logger.info("Wrote ingest manifest: %s", out)
    return out
