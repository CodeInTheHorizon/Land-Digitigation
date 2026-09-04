"""Tests for storage abstraction – LocalStorageService."""

import os
import shutil
import tempfile

import pytest

# These tests run against LocalStorageService, which needs no external deps.


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp(prefix="test_storage_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def local_storage(tmp_dir):
    from app.services.storage import LocalStorageService
    return LocalStorageService(base_dir=tmp_dir)


class TestLocalStorageUpload:
    @pytest.mark.asyncio
    async def test_upload_creates_file(self, local_storage, tmp_dir):
        path = await local_storage.upload("docs/test.pdf", b"PDF_CONTENT", "application/pdf")
        assert path == "docs/test.pdf"
        assert os.path.isfile(os.path.join(tmp_dir, "docs", "test.pdf"))

    @pytest.mark.asyncio
    async def test_upload_and_download_roundtrip(self, local_storage):
        data = b"\x89PNG fake image data"
        await local_storage.upload("images/photo.png", data, "image/png")
        result = await local_storage.download("images/photo.png")
        assert result == data

    @pytest.mark.asyncio
    async def test_upload_overwrites(self, local_storage):
        await local_storage.upload("file.txt", b"v1", "text/plain")
        await local_storage.upload("file.txt", b"v2", "text/plain")
        result = await local_storage.download("file.txt")
        assert result == b"v2"


class TestLocalStorageDelete:
    @pytest.mark.asyncio
    async def test_delete_removes_file(self, local_storage):
        await local_storage.upload("remove_me.txt", b"data", "text/plain")
        assert await local_storage.exists("remove_me.txt")
        await local_storage.delete("remove_me.txt")
        assert not await local_storage.exists("remove_me.txt")

    @pytest.mark.asyncio
    async def test_delete_nonexistent_is_noop(self, local_storage):
        # Should not raise
        await local_storage.delete("no_such_file.txt")


class TestLocalStorageExists:
    @pytest.mark.asyncio
    async def test_exists_true(self, local_storage):
        await local_storage.upload("check.pdf", b"data", "application/pdf")
        assert await local_storage.exists("check.pdf")

    @pytest.mark.asyncio
    async def test_exists_false(self, local_storage):
        assert not await local_storage.exists("nonexistent.pdf")


class TestPathTraversal:
    @pytest.mark.asyncio
    async def test_traversal_with_dotdot(self, local_storage):
        with pytest.raises(ValueError, match="traversal"):
            await local_storage.upload("../../etc/passwd", b"hack", "text/plain")

    @pytest.mark.asyncio
    async def test_traversal_download(self, local_storage):
        with pytest.raises(ValueError, match="traversal"):
            await local_storage.download("../../../etc/shadow")

    @pytest.mark.asyncio
    async def test_absolute_path_rejected(self, local_storage):
        with pytest.raises(ValueError, match="traversal"):
            await local_storage.upload("/etc/passwd", b"hack", "text/plain")


class TestPresignedUrl:
    @pytest.mark.asyncio
    async def test_local_presigned_url(self, local_storage):
        url = await local_storage.get_presigned_url("docs/file.pdf")
        assert url.startswith("/storage/")
        assert "file.pdf" in url


class TestFactory:
    def test_local_backend(self, monkeypatch):
        monkeypatch.setenv("STORAGE_BACKEND", "local")
        from app.services.storage import reset_storage_service, get_storage_service, LocalStorageService
        reset_storage_service()
        svc = get_storage_service()
        assert isinstance(svc, LocalStorageService)
        reset_storage_service()

    def test_unknown_backend_falls_back_to_local(self, monkeypatch):
        monkeypatch.setenv("STORAGE_BACKEND", "unknown")
        from app.services.storage import reset_storage_service, get_storage_service, LocalStorageService
        reset_storage_service()
        svc = get_storage_service()
        assert isinstance(svc, LocalStorageService)
        reset_storage_service()
