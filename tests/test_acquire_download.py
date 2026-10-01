import hashlib
from pathlib import Path, PurePosixPath

import httpx2
import pytest

from preop_xai.acquire.download import download_entry
from preop_xai.acquire.plan import DownloadPlanEntry


def _entry(content: bytes) -> DownloadPlanEntry:
    return DownloadPlanEntry(
        logical_role="operations",
        relative_path=PurePosixPath("release/table.bin"),
        url="https://physionet.org/files/inspire/1.4.2/table.bin",
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
    )


@pytest.mark.anyio
async def test_download_rejects_redirect_to_foreign_host(tmp_path: Path) -> None:
    # Given
    def handler(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(302, headers={"location": "https://example.invalid/x"})

    entry = _entry(b"content")
    transport = httpx2.MockTransport(handler)

    # When / Then
    async with httpx2.AsyncClient(transport=transport) as client:
        with pytest.raises(ValueError, match="host"):
            _ = await download_entry(client, entry, tmp_path)


@pytest.mark.anyio
async def test_download_rejects_foreign_initial_url_before_request(
    tmp_path: Path,
) -> None:
    # Given
    request_sent = False

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal request_sent
        request_sent = True
        return httpx2.Response(200, content=b"content", request=request)

    entry = _entry(b"content").model_copy(
        update={"url": "https://example.invalid/content"}
    )

    # When / Then
    async with httpx2.AsyncClient(transport=httpx2.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="host"):
            _ = await download_entry(client, entry, tmp_path)
    assert not request_sent


@pytest.mark.anyio
async def test_download_resumes_from_recorded_offset(tmp_path: Path) -> None:
    # Given
    content = b"hello world"
    entry = _entry(content)
    part = tmp_path / "release" / "table.bin.part"
    part.parent.mkdir(parents=True)
    _ = part.write_bytes(b"hello ")
    observed_range = ""

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal observed_range
        observed_range = request.headers.get("range", "")
        return httpx2.Response(206, content=b"world", request=request)

    transport = httpx2.MockTransport(handler)

    # When
    async with httpx2.AsyncClient(transport=transport) as client:
        completed = await download_entry(client, entry, tmp_path)

    # Then
    assert observed_range == "bytes=6-"
    assert completed.read_bytes() == content
    assert not part.exists()
