#!/usr/bin/env python3
"""Deep breadth-first crawler for konkur.in: seeds -> pages -> direct PDF URLs.

Walks every konkur.in page reachable from the seed URLs (archive posts,
categories, tags, pagination) and harvests every dl.konkur.in PDF link,
covering the whole on-site file database instead of single year tags.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) crawl-deep/1.0"}
TIMEOUT = 30
HOSTS = {"konkur.in", "dl.konkur.in"}
SKIP_EXT = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".ico", ".css", ".js", ".xml", ".zip", ".mp3", ".mp4")
PDF = re.compile(r'https?://dl\.konkur\.in/[^"\'<> ]+?\.pdf', re.I)
HREF = re.compile(r'''href=["']([^"']+)["']''', re.I)


def same_site(url: str) -> bool:
    return urlsplit(url).hostname in HOSTS


def is_page(url: str) -> bool:
    return not url.lower().endswith(SKIP_EXT)


def normalize(url: str, base: str) -> str | None:
    clean = urljoin(base, url).split("#", 1)[0].split("?", 1)[0].strip()
    if not clean.startswith("http") or not same_site(clean) or not is_page(clean):
        return None
    return clean


def fetch(session: requests.Session, url: str, retries: int = 2) -> str:
    for attempt in range(retries + 1):
        try:
            response = session.get(url, timeout=TIMEOUT)
            if response.status_code == 404:
                return ""
            response.raise_for_status()
            return response.text
        except Exception:  # noqa: BLE001
            if attempt == retries:
                return ""
            time.sleep(2 * (attempt + 1))
    return ""


def crawl(seeds: list[str], max_pages: int, delay: float) -> tuple[list[str], int]:
    session = requests.Session()
    session.headers.update(HEADERS)
    queue: deque[str] = deque(dict.fromkeys(seeds))
    visited: set[str] = set()
    pdfs: list[str] = []
    while queue and len(visited) < max_pages:
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)
        html = fetch(session, url)
        if not html:
            print(f"  WARN {url}: fetch failed")
            continue
        found = PDF.findall(html)
        for pdf in found:
            if pdf not in pdfs:
                pdfs.append(pdf)
        for href in HREF.findall(html):
            page = normalize(href, url)
            if page and page not in visited and page not in queue:
                queue.append(page)
        print(f"[{len(visited)}/{max_pages}] {url}: +{len(found)} pdf total={len(pdfs)}", file=sys.stderr)
        time.sleep(delay)
    return pdfs, len(visited)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("seeds", nargs="+", help="konkur.in URLs: archive/category/tag/post pages")
    parser.add_argument("--max-pages", type=int, default=300, help="max HTML pages fetched")
    parser.add_argument("--delay", type=float, default=0.5, help="seconds between requests")
    parser.add_argument("--out", type=Path, default=Path("urls_deep.txt"))
    args = parser.parse_args()

    pdfs, pages = crawl(args.seeds, args.max_pages, args.delay)
    if not pdfs:
        print("no PDF links found", file=sys.stderr)
        return 1
    args.out.write_text("\n".join(dict.fromkeys(pdfs)) + "\n", encoding="utf-8")
    print(f"crawled {pages} pages; wrote {len(pdfs)} PDF URLs to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
