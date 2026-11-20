#!/usr/bin/env python3
"""Download files listed in urls.txt into raw_sources/ with timeout and retries."""
from __future__ import annotations

import argparse
import hashlib
import logging
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

TIMEOUT = 30
RETRIES = 3
BACKOFF = 2.0
CHUNK = 1 << 16


def build_logger(log_path: Path) -> logging.Logger:
    logger = logging.getLogger("fetch_list")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s\t%(levelname)s\t%(message)s"))
    logger.addHandler(handler)
    return logger


def target_name(url: str, seen: set[str]) -> str:
    name = Path(urlparse(url).path).name
    if not name or name in seen:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
        name = f"{name}_{digest}" if name else digest
    seen.add(name)
    return name


def fetch(url: str) -> bytes:
    last_error: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            response = requests.get(url, timeout=TIMEOUT, stream=True)
            response.raise_for_status()
            content = b"".join(response.iter_content(chunk_size=CHUNK))
            if not content:
                raise ValueError("empty response body")
            return content
        except Exception as error:  # noqa: BLE001 - log every failure mode
            last_error = error
            if attempt < RETRIES:
                time.sleep(BACKOFF * (2 ** (attempt - 1)))
    raise last_error  # type: ignore[misc]


def run(urls_file: Path, out_dir: Path, log_path: Path) -> tuple[int, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = build_logger(log_path)
    seen: set[str] = set()
    ok = fail = 0
    for line in urls_file.read_text(encoding="utf-8").splitlines():
        url = line.strip()
        if not url or url.startswith("#"):
            continue
        dest = out_dir / target_name(url, seen)
        try:
            dest.write_bytes(fetch(url))
            ok += 1
            print(f"OK   {url} -> {dest.name}")
        except Exception as error:  # noqa: BLE001
            fail += 1
            logger.error("%s\t%s", url, error)
            print(f"FAIL {url} ({error})")
    return ok, fail


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--urls", type=Path, default=Path("urls.txt"))
    parser.add_argument("--out", type=Path, default=Path("raw_sources"))
    parser.add_argument("--log", type=Path, default=Path("logs/fetch_errors.log"))
    args = parser.parse_args()
    if not args.urls.exists():
        print(f"missing {args.urls}", file=__import__("sys").stderr)
        return 2
    ok, fail = run(args.urls, args.out, args.log)
    print(f"done: {ok} fetched, {fail} failed")
    return 1 if fail and not ok else 0


if __name__ == "__main__":
    raise SystemExit(main())
