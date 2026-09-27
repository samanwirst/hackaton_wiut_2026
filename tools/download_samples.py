#!/usr/bin/env python3
"""Download the four official sample videos from their published Google Drive ids.

The files are large enough that Drive occasionally returns its quota page for a
normal download.  Small HTTP range requests are still served, so this downloader
uses validated chunks and can resume an interrupted ``.part`` file.

Sample videos are organiser-provided data and stay outside Git (``data/samples/`` is
ignored).  Only their public ids and exact byte sizes are recorded here.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import http.cookiejar
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Sample:
    name: str
    drive_id: str
    size: int


SAMPLES = (
    Sample("C3896.MP4", "1kR9jODA2Wotw4gwkvpRKdqFADNJNc1nS", 6_241_380_481),
    Sample("C3897.MP4", "1hp8DYeqtYHSwfM6qAo9FPSRHlpMFrIN_", 5_838_719_827),
    Sample("C3902.MP4", "10cHEReCWzO3u-Vk1CnNgHAx6egGy5MwJ", 5_838_719_827),
    Sample("C3905.MP4", "1aJ-QsAZVYJtLKHiRvKKeBq1D3GWNobRd", 2_348_992_759),
)

_CONTENT_RANGE = re.compile(r"bytes (\d+)-(\d+)/(\d+)")
_PRINT_LOCK = threading.Lock()


def _say(message: str) -> None:
    with _PRINT_LOCK:
        print(message, flush=True)


def _looks_like_mp4(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 12:
        return False
    with path.open("rb") as handle:
        return handle.read(12)[4:8] == b"ftyp"


def _fetch_range(
    sample: Sample, start: int, end: int, attempts: int = 8
) -> tuple[bytes, int]:
    # The range offset also acts as a harmless cache-buster.  Drive may cache
    # its HTML quota page for the otherwise-identical URL after the first
    # request even though byte-range responses remain available.
    for attempt in range(1, attempts + 1):
        url = (
            "https://drive.usercontent.google.com/download"
            f"?id={sample.drive_id}&export=download&confirm=t"
            f"&chunk={start}&attempt={attempt}-{time.time_ns()}"
        )
        request = urllib.request.Request(
            url,
            headers={
                "Accept-Encoding": "identity",
                "Range": f"bytes={start}-{end}",
                "User-Agent": "TrafficWatch-sample-downloader/1.0",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                content_range = response.headers.get("Content-Range", "")
                match = _CONTENT_RANGE.fullmatch(content_range)
                if response.status != 206 or not match:
                    raise RuntimeError(
                        f"expected HTTP 206 with Content-Range, got "
                        f"{response.status} {content_range!r}"
                    )
                got_start, got_end, got_total = map(int, match.groups())
                if (got_start, got_end, got_total) != (start, end, sample.size):
                    raise RuntimeError(
                        f"unexpected range {content_range!r}; expected "
                        f"bytes {start}-{end}/{sample.size}"
                    )
                payload = response.read()
                if len(payload) != end - start + 1:
                    raise RuntimeError(
                        f"short chunk: received {len(payload)} of {end - start + 1} bytes"
                    )
                return payload, end
        except (OSError, RuntimeError, urllib.error.HTTPError) as exc:
            requested = end - start + 1
            if "expected HTTP 206" in str(exc) and requested > 2**20:
                reduced = max(2**20, requested // 2)
                end = min(sample.size - 1, start + reduced - 1)
                _say(
                    f"{sample.name}: Drive limited this range; "
                    f"reducing chunks to {reduced / 2**20:.0f} MiB"
                )
                continue
            if attempt == attempts:
                raise RuntimeError(
                    f"{sample.name}: range {start}-{end} failed after {attempts} attempts"
                ) from exc
            delay = min(30, 2**attempt)
            _say(f"{sample.name}: retry {attempt}/{attempts} in {delay}s ({exc})")
            time.sleep(delay)
    raise AssertionError("unreachable")


def download(sample: Sample, destination: Path, chunk_size: int) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / sample.name
    partial = destination / f"{sample.name}.part"

    if target.is_file() and target.stat().st_size == sample.size and _looks_like_mp4(target):
        _say(f"{sample.name}: already complete")
        return target
    if target.exists():
        target.unlink()

    offset = partial.stat().st_size if partial.exists() else 0
    if offset > sample.size or (offset and not _looks_like_mp4(partial)):
        partial.unlink()
        offset = 0

    initial_offset = offset
    mode = "ab" if offset else "wb"
    started = time.monotonic()
    with partial.open(mode) as handle:
        while offset < sample.size:
            end = min(sample.size - 1, offset + chunk_size - 1)
            payload, end = _fetch_range(sample, offset, end)
            chunk_size = min(chunk_size, len(payload))
            handle.write(payload)
            handle.flush()
            offset = end + 1
            elapsed = max(time.monotonic() - started, 1e-6)
            completed = offset / sample.size * 100
            speed = (offset - initial_offset) / elapsed
            _say(
                f"{sample.name}: {completed:5.1f}% "
                f"({offset / 2**30:.2f}/{sample.size / 2**30:.2f} GiB, "
                f"{speed / 2**20:.1f} MiB/s)"
            )

    if partial.stat().st_size != sample.size or not _looks_like_mp4(partial):
        raise RuntimeError(f"{sample.name}: completed file failed size/header validation")
    os.replace(partial, target)
    _say(f"{sample.name}: complete")
    return target


def _preview_url(
    sample: Sample, opener: urllib.request.OpenerDirector | None = None
) -> tuple[str, str]:
    """Return Drive's best MP4 preview URL and a human-readable format."""
    opener = opener or urllib.request.build_opener()
    # DRIVE_STREAM is set while opening the viewer and is required by the
    # signed videoplayback URL (without it Google returns HTTP 403).
    viewer_url = f"https://drive.google.com/file/d/{sample.drive_id}/view"
    with opener.open(viewer_url, timeout=60) as response:
        response.read()
    for player in ("embedded", "leanback", "detailpage"):
        info_url = (
            "https://drive.google.com/get_video_info"
            f"?docid={sample.drive_id}&el={player}&cache={time.time_ns()}"
        )
        try:
            with opener.open(info_url, timeout=60) as response:
                info = urllib.parse.parse_qs(response.read().decode("utf-8"))
        except (OSError, UnicodeError, urllib.error.HTTPError):
            continue
        if info.get("status", [""])[0] != "ok" or not info.get("fmt_stream_map"):
            continue
        streams = {
            int(item.split("|", 1)[0]): item.split("|", 1)[1]
            for item in info["fmt_stream_map"][0].split(",")
            if "|" in item
        }
        formats = {
            int(item.split("/", 1)[0]): item.split("/", 2)[1]
            for item in info.get("fmt_list", [""])[0].split(",")
            if "/" in item
        }
        if streams:
            itag = 37 if 37 in streams else max(streams)
            return streams[itag], formats.get(itag, f"itag {itag}")
    raise RuntimeError(f"{sample.name}: Google Drive preview is not available")


def download_preview(sample: Sample, destination: Path) -> Path:
    """Download Drive's official 1080p transcode for analysis and website assets."""
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / sample.name
    partial = destination / f"{sample.name}.part"
    if target.is_file() and _looks_like_mp4(target):
        _say(f"{sample.name}: preview already complete")
        return target
    if target.exists():
        target.unlink()
    if partial.exists() and not _looks_like_mp4(partial):
        partial.unlink()

    offset = partial.stat().st_size if partial.exists() else 0
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
    opener.addheaders = [
        (
            "User-Agent",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "Chrome/140.0 Safari/537.36",
        )
    ]
    url, label = _preview_url(sample, opener)
    headers: dict[str, str] = {}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    request = urllib.request.Request(url, headers=headers)
    started = time.monotonic()
    with opener.open(request, timeout=120) as response:
        if offset and response.status != 206:
            partial.unlink(missing_ok=True)
            return download_preview(sample, destination)
        remaining = int(response.headers.get("Content-Length", "0"))
        total = offset + remaining if remaining else 0
        mode = "ab" if offset else "wb"
        with partial.open(mode) as handle:
            while True:
                block = response.read(2**20)
                if not block:
                    break
                handle.write(block)
                offset += len(block)
                elapsed = max(time.monotonic() - started, 1e-6)
                if total:
                    progress = f"{offset / total * 100:5.1f}%"
                else:
                    progress = f"{offset / 2**20:.0f} MiB"
                if offset % (16 * 2**20) < len(block):
                    _say(
                        f"{sample.name}: {progress} ({label}, "
                        f"{offset / elapsed / 2**20:.1f} MiB/s)"
                    )

    if not _looks_like_mp4(partial) or (total and partial.stat().st_size != total):
        raise RuntimeError(f"{sample.name}: preview failed size/header validation")
    os.replace(partial, target)
    _say(f"{sample.name}: preview complete ({label})")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("data/samples"))
    parser.add_argument("--jobs", type=int, default=2, choices=range(1, 5))
    # Drive applies a smaller range cap to some of the organiser files.
    parser.add_argument("--chunk-mib", type=int, default=16)
    parser.add_argument(
        "--preview",
        action="store_true",
        help="download Drive's smaller 1080p transcodes (EDA/website, not exact benchmarking)",
    )
    args = parser.parse_args()
    if args.chunk_mib < 1 or args.chunk_mib > 128:
        parser.error("--chunk-mib must be between 1 and 128")

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            if args.preview:
                futures = [pool.submit(download_preview, sample, args.out) for sample in SAMPLES]
            else:
                futures = [
                    pool.submit(download, sample, args.out, args.chunk_mib * 2**20)
                    for sample in SAMPLES
                ]
            for future in concurrent.futures.as_completed(futures):
                future.result()
    except (OSError, RuntimeError) as exc:
        print(f"download failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
