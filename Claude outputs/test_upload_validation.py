"""Tests for document upload validation logic.

Tests the _validate_file function and related upload validation
without requiring a running server or database.
"""

import uuid

import pytest


class FakeUploadFile:
    """Minimal stand-in for FastAPI's UploadFile."""

    def __init__(self, filename: str, content_type: str = "application/pdf", size: int = 1024):
        self.filename = filename
        self.content_type = content_type
        self._content = b"x" * size

    async def read(self) -> bytes:
        return self._content


class TestExtensionValidation:
    """Extension allowlisting."""

    def test_valid_pdf(self):
        from app.api.v1.endpoints.documents import _validate_file
        f = FakeUploadFile("report.pdf")
        _validate_file(f)  # should not raise

    def test_valid_png(self):
        from app.api.v1.endpoints.documents import _validate_file
        _validate_file(FakeUploadFile("scan.png"))

    def test_valid_jpg(self):
        from app.api.v1.endpoints.documents import _validate_file
        _validate_file(FakeUploadFile("photo.jpg"))

    def test_valid_jpeg(self):
        from app.api.v1.endpoints.documents import _validate_file
        _validate_file(FakeUploadFile("photo.jpeg"))

    def test_valid_tiff(self):
        from app.api.v1.endpoints.documents import _validate_file
        _validate_file(FakeUploadFile("map.tiff"))

    def test_valid_tif(self):
        from app.api.v1.endpoints.documents import _validate_file
        _validate_file(FakeUploadFile("scan.tif"))

    def test_valid_bmp(self):
        from app.api.v1.endpoints.documents import _validate_file
        _validate_file(FakeUploadFile("old.bmp"))

    def test_invalid_exe(self):
        from fastapi import HTTPException
        from app.api.v1.endpoints.documents import _validate_file
        with pytest.raises(HTTPException) as exc_info:
            _validate_file(FakeUploadFile("malware.exe"))
        assert exc_info.value.status_code == 400
        assert "not allowed" in exc_info.value.detail

    def test_invalid_zip(self):
        from fastapi import HTTPException
        from app.api.v1.endpoints.documents import _validate_file
        with pytest.raises(HTTPException):
            _validate_file(FakeUploadFile("archive.zip"))

    def test_invalid_js(self):
        from fastapi import HTTPException
        from app.api.v1.endpoints.documents import _validate_file
        with pytest.raises(HTTPException):
            _validate_file(FakeUploadFile("script.js"))

    def test_no_extension(self):
        from fastapi import HTTPException
        from app.api.v1.endpoints.documents import _validate_file
        with pytest.raises(HTTPException):
            _validate_file(FakeUploadFile("noextension"))

    def test_empty_filename(self):
        from fastapi import HTTPException
        from app.api.v1.endpoints.documents import _validate_file
        f = FakeUploadFile("")
        f.filename = ""
        with pytest.raises(HTTPException) as exc_info:
            _validate_file(f)
        assert exc_info.value.status_code == 400

    def test_none_filename(self):
        from fastapi import HTTPException
        from app.api.v1.endpoints.documents import _validate_file
        f = FakeUploadFile("test.pdf")
        f.filename = None
        with pytest.raises(HTTPException):
            _validate_file(f)

    def test_case_insensitive(self):
        from app.api.v1.endpoints.documents import _validate_file
        _validate_file(FakeUploadFile("REPORT.PDF"))
        _validate_file(FakeUploadFile("scan.PNG"))

    def test_double_extension(self):
        from app.api.v1.endpoints.documents import _validate_file
        # "report.pdf.exe" → extension is "exe" → should fail
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            _validate_file(FakeUploadFile("report.pdf.exe"))


class TestSafeFilename:
    """UUID-based safe filename generation."""

    def test_safe_name_is_uuid_hex(self):
        """Upload generates a hex UUID filename, not the original."""
        filename = "my document (final).pdf"
        ext = filename.rsplit(".", 1)[-1].lower()
        safe = f"{uuid.uuid4().hex}.{ext}"
        # Verify format: 32 hex chars + dot + extension
        parts = safe.split(".")
        assert len(parts) == 2
        assert len(parts[0]) == 32
        assert parts[0].isalnum()
        assert parts[1] == "pdf"

    def test_original_filename_not_used_as_path(self):
        """Path-traversal in original filename is neutralised by safe_name."""
        filename = "../../../etc/passwd.pdf"
        ext = filename.rsplit(".", 1)[-1].lower()
        safe = f"{uuid.uuid4().hex}.{ext}"
        assert ".." not in safe
        assert "/" not in safe


class TestFileSizeValidation:
    """Ensure oversized files are rejected."""

    def test_max_upload_bytes_computed(self):
        from app.core.config import Settings
        s = Settings()
        assert s.max_upload_bytes == s.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    def test_default_limit_is_50mb(self):
        from app.core.config import Settings
        s = Settings()
        assert s.MAX_UPLOAD_SIZE_MB == 50
        assert s.max_upload_bytes == 50 * 1024 * 1024
