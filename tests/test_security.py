"""Security tests for ingest infrastructure.

Tests defense against:
- Tar/ZIP path traversal (CVE-2007-4559 class)
- Git URL option injection
- HTTP download scheme validation
"""
from __future__ import annotations

import io
import tarfile
import zipfile

import pytest

from rop.ingest._common import (
    _is_within,
    _safe_extract_tar,
    _safe_extract_zip,
    _validate_git_url,
    _validate_http_url,
    extract_archive,
)


# ---------------------------------------------------------------------------
# Path traversal defense
# ---------------------------------------------------------------------------

class TestZipPathTraversal:
    def _make_evil_zip(self, tmp_path, member_name: str):
        """Create a ZIP containing a single member with the given name."""
        zip_path = tmp_path / "evil.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr(member_name, b"pwned")
        return zip_path

    def test_rejects_absolute_path_unix(self, tmp_path):
        zp = self._make_evil_zip(tmp_path, "/etc/passwd")
        dest = tmp_path / "extract"
        with pytest.raises(ValueError, match="absolute path"):
            _safe_extract_zip(zp, dest)
        assert not (tmp_path / "etc" / "passwd").exists()

    def test_rejects_parent_traversal(self, tmp_path):
        zp = self._make_evil_zip(tmp_path, "../../../tmp/escaped.txt")
        dest = tmp_path / "extract"
        with pytest.raises(ValueError, match="parent traversal"):
            _safe_extract_zip(zp, dest)
        # Confirm the escape didn't actually land
        assert not (tmp_path.parent / "tmp" / "escaped.txt").exists()

    def test_rejects_parent_traversal_in_middle(self, tmp_path):
        zp = self._make_evil_zip(tmp_path, "subdir/../../../etc/evil")
        dest = tmp_path / "extract"
        with pytest.raises(ValueError, match="parent traversal"):
            _safe_extract_zip(zp, dest)

    def test_accepts_normal_paths(self, tmp_path):
        zip_path = tmp_path / "good.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("data/file.txt", b"hello")
            zf.writestr("README.md", b"docs")
        dest = tmp_path / "extract"
        _safe_extract_zip(zip_path, dest)
        assert (dest / "data" / "file.txt").read_bytes() == b"hello"
        assert (dest / "README.md").read_bytes() == b"docs"


class TestTarPathTraversal:
    def _make_evil_tar(self, tmp_path, member_name: str, content: bytes = b"pwned"):
        tar_path = tmp_path / "evil.tar"
        with tarfile.open(tar_path, "w") as tf:
            data = io.BytesIO(content)
            info = tarfile.TarInfo(name=member_name)
            info.size = len(content)
            tf.addfile(info, data)
        return tar_path

    def test_rejects_absolute_path(self, tmp_path):
        tp = self._make_evil_tar(tmp_path, "/etc/passwd")
        dest = tmp_path / "extract"
        with pytest.raises(ValueError, match="absolute path"):
            _safe_extract_tar(tp, dest)
        # Defense-in-depth: even if extraction had proceeded, nothing
        # should have written to the real /etc/passwd or to tmp_path/etc
        assert not (tmp_path / "etc" / "passwd").exists()

    def test_rejects_parent_traversal(self, tmp_path):
        tp = self._make_evil_tar(tmp_path, "../../escaped.txt")
        dest = tmp_path / "extract"
        with pytest.raises(ValueError, match="parent traversal"):
            _safe_extract_tar(tp, dest)

    def test_accepts_normal_paths(self, tmp_path):
        tar_path = tmp_path / "good.tar"
        with tarfile.open(tar_path, "w") as tf:
            content = b"hello world"
            info = tarfile.TarInfo(name="docs/README.md")
            info.size = len(content)
            tf.addfile(info, io.BytesIO(content))
        dest = tmp_path / "extract"
        _safe_extract_tar(tar_path, dest)
        assert (dest / "docs" / "README.md").read_bytes() == b"hello world"


class TestExtractArchiveDispatch:
    def test_dispatches_zip(self, tmp_path):
        zip_path = tmp_path / "x.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("a.txt", b"x")
        dest = tmp_path / "out"
        extract_archive(zip_path, dest)
        assert (dest / "a.txt").exists()

    def test_dispatches_tar_gz(self, tmp_path):
        tar_path = tmp_path / "x.tar.gz"
        with tarfile.open(tar_path, "w:gz") as tf:
            content = b"x"
            info = tarfile.TarInfo(name="a.txt")
            info.size = len(content)
            tf.addfile(info, io.BytesIO(content))
        dest = tmp_path / "out"
        extract_archive(tar_path, dest)
        assert (dest / "a.txt").exists()

    def test_unrecognized_format_raises(self, tmp_path):
        bogus = tmp_path / "x.rar"
        bogus.write_bytes(b"\x00")
        with pytest.raises(ValueError, match="Unrecognized"):
            extract_archive(bogus, tmp_path / "out")


# ---------------------------------------------------------------------------
# Git URL option injection defense
# ---------------------------------------------------------------------------

class TestGitURLValidation:
    def test_accepts_https(self):
        _validate_git_url("https://github.com/foo/bar.git")  # no raise

    def test_accepts_http(self):
        _validate_git_url("http://example.com/repo")  # no raise

    def test_accepts_ssh_git_protocol(self):
        _validate_git_url("git@github.com:foo/bar.git")
        _validate_git_url("git://github.com/foo/bar.git")
        _validate_git_url("ssh://git@github.com/foo/bar")

    def test_rejects_option_like_url(self):
        with pytest.raises(ValueError, match="begins with '-'"):
            _validate_git_url("--upload-pack=evil")
        with pytest.raises(ValueError, match="begins with '-'"):
            _validate_git_url("-u")

    def test_rejects_file_scheme(self):
        with pytest.raises(ValueError, match="unrecognized scheme"):
            _validate_git_url("file:///etc/passwd")

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="Empty"):
            _validate_git_url("")
        with pytest.raises(ValueError, match="Empty"):
            _validate_git_url("   ")

    def test_rejects_non_string(self):
        with pytest.raises(ValueError, match="Empty or non-string"):
            _validate_git_url(None)


# ---------------------------------------------------------------------------
# HTTP URL validation
# ---------------------------------------------------------------------------

class TestHTTPURLValidation:
    def test_accepts_https(self):
        out = _validate_http_url("https://example.com/file.csv")
        assert out == "https://example.com/file.csv"

    def test_accepts_http(self):
        _validate_http_url("http://example.com/file.csv")

    def test_strips_whitespace(self):
        assert _validate_http_url("  https://example.com/x  ") == "https://example.com/x"

    def test_rejects_file_scheme(self):
        with pytest.raises(ValueError, match="scheme"):
            _validate_http_url("file:///etc/passwd")

    def test_rejects_ftp(self):
        with pytest.raises(ValueError, match="scheme"):
            _validate_http_url("ftp://example.com/file.csv")

    def test_rejects_javascript(self):
        with pytest.raises(ValueError, match="scheme"):
            _validate_http_url("javascript:alert(1)")

    def test_rejects_data_url(self):
        with pytest.raises(ValueError, match="scheme"):
            _validate_http_url("data:text/plain,hello")

    def test_rejects_no_host(self):
        with pytest.raises(ValueError, match="no host"):
            _validate_http_url("https://")

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="Empty"):
            _validate_http_url("")


# ---------------------------------------------------------------------------
# is_within helper used by extraction validators
# ---------------------------------------------------------------------------

class TestIsWithin:
    def test_child_inside(self, tmp_path):
        parent = tmp_path
        child = tmp_path / "sub" / "file.txt"
        assert _is_within(child, parent)

    def test_child_equals_parent(self, tmp_path):
        assert _is_within(tmp_path, tmp_path)

    def test_child_outside(self, tmp_path):
        parent = tmp_path / "a"
        parent.mkdir()
        outside = tmp_path / "b" / "file.txt"
        assert not _is_within(outside, parent)
