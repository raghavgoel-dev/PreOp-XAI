"""Resumable host-locked transfer."""

from pathlib import Path
from urllib.parse import urljoin

import anyio
import httpx2

from preop_xai.acquire.paths import resolve_under_root
from preop_xai.acquire.plan import DownloadPlanEntry, require_official_url

MAX_REDIRECTS = 5


async def download_entry(
    client: httpx2.AsyncClient,
    entry: DownloadPlanEntry,
    raw_root: Path,
) -> Path:
    """Download one entry through a caller-authenticated client."""
    require_official_url(entry.url)
    target = resolve_under_root(raw_root, entry.relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(f"{target.name}.part")
    offset = part.stat().st_size if part.exists() else 0
    headers = {"accept-encoding": "identity"}
    if offset > 0:
        headers["range"] = f"bytes={offset}-"

    current_url = entry.url
    for _ in range(MAX_REDIRECTS + 1):
        async with client.stream("GET", current_url, headers=headers) as response:
            if response.is_redirect:
                location = response.headers.get("location")
                if location is None:
                    message = "redirect response is missing a location"
                    raise ValueError(message)
                next_url = urljoin(current_url, location)
                require_official_url(next_url)
                current_url = next_url
                continue

            expected_status = 206 if offset > 0 else 200
            if response.status_code != expected_status:
                message = (
                    f"expected HTTP {expected_status}, received {response.status_code}"
                )
                raise ValueError(message)
            mode = "ab" if offset > 0 else "wb"
            async with await anyio.open_file(part, mode) as stream:
                if response.is_stream_consumed:
                    _ = await stream.write(response.content)
                else:
                    async for chunk in response.aiter_raw():
                        _ = await stream.write(chunk)
            _ = part.replace(target)
            return target

    message = f"redirect limit exceeded after {MAX_REDIRECTS} redirects"
    raise ValueError(message)
