"""URL video downloader — supports YouTube and any yt-dlp compatible source.

Downloads video from a URL to a local temp file and returns the path.
Requires yt-dlp to be installed (included in core dependencies).
"""
from __future__ import annotations

import asyncio
import logging
import re
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

_YOUTUBE_RE = re.compile(
    r"(?:https?://)?(?:www\.|m\.)?(?:youtube\.com/watch\?.*v=|youtu\.be/)[\w-]+",
    re.I,
)

_SUPPORTED_URL_PREFIXES = ("http://", "https://")


def is_supported_url(value: str) -> bool:
    """Return True if the value looks like a downloadable video URL."""
    return any(value.startswith(p) for p in _SUPPORTED_URL_PREFIXES)


def download_video(url: str, output_dir: str | Path) -> str:
    """Download a video from *url* into *output_dir*.

    Returns the absolute path of the downloaded file.
    Uses yt-dlp under the hood — works with YouTube, Vimeo, Loom, and
    hundreds of other platforms.

    Raises:
        ImportError: if yt-dlp is not installed.
        RuntimeError: if the download fails.
    """
    try:
        import yt_dlp  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "yt-dlp is required for URL ingestion. "
            "Install it with: pip install yt-dlp"
        ) from exc

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Use a tempfile name so we know the exact output path regardless of
    # what yt-dlp decides to call the file.
    tmp = tempfile.NamedTemporaryFile(
        dir=output_dir, suffix=".mp4", delete=False
    )
    tmp.close()
    output_template = tmp.name  # yt-dlp will overwrite this file

    ydl_opts: dict = {
        # Prefer a single mp4 with audio; fall back to best available
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        # Write directly to the pre-created temp file
        "outtmpl": output_template,
        # Merge audio+video when needed
        "merge_output_format": "mp4",
        # Don't write any extra metadata files
        "writeinfojson": False,
        "writedescription": False,
        "writesubtitles": False,
        # Quiet but show errors
        "quiet": True,
        "no_warnings": False,
        # Respect rate limits to avoid bans
        "ratelimit": 5_000_000,  # 5 MB/s cap
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                raise RuntimeError(f"yt-dlp returned no info for URL: {url}")
    except Exception as exc:
        raise RuntimeError(f"Failed to download video from {url}: {exc}") from exc

    # yt-dlp may have renamed the file; find it
    downloaded = Path(output_template)
    if not downloaded.exists():
        # Search for the most recently modified mp4 in output_dir
        candidates = sorted(
            output_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True
        )
        if not candidates:
            raise RuntimeError(
                f"Download appeared to succeed but no .mp4 found in {output_dir}"
            )
        downloaded = candidates[0]

    logger.info("Downloaded %s → %s (%.1f MB)", url, downloaded,
                downloaded.stat().st_size / 1_048_576)
    return str(downloaded)


async def download_video_async(url: str, output_dir: str | Path) -> str:
    """Async wrapper — runs the blocking yt-dlp download in a thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, download_video, url, output_dir)
