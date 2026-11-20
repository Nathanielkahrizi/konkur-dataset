#!/usr/bin/env python3
"""Crawl konkur.in year tags, extract direct PDF links, write urls.txt."""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) fetch-list/1.0"}
TIMEOUT = 30
DELAY = 1.0
PDF = re.compile(r'https?://dl\.konkur\.in/[^"\'<> ]+?\.pdf', re.I)
POST = re.compile(r'https?://konkur\.in/\d+(?:/[^"\'<> ]*?)?\.html', re.I)
GROUPS = {
    "riazi": ("ریاضی", "riazi", "riazi"),
    "tajrobi": ("تجربی", "tajrobi", "tajrobi"),
    "ensani": ("انسانی", "ensani", "ensani"),
    "zaban": ("زبان", "zaban", "zaban"),
    "honar": ("هنر", "honar", "honar"),
}


def get(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    return response.text


def collect(tag: str, group: str | None, max_posts: int, seen: set[str]) -> list[str]:
    session = requests.Session()
    session.headers.update(HEADERS)
    tag = tag if tag.startswith("http") else f"https://konkur.in/tag/{tag}"
    posts = sorted(set(POST.findall(get(session, tag))), reverse=True)[:max_posts]
    print(f"{tag}: {len(posts)} posts")
    urls: list[str] = []
    for post in posts:
        try:
            html = get(session, post)
        except Exception as error:  # noqa: BLE001
            print(f"  WARN {post}: {error}")
            continue
        for url in PDF.findall(html):
            if url in seen:
                continue
            if group and not any(word in url for word in GROUPS[group]):
                continue
            seen.add(url)
            urls.append(url)
        time.sleep(DELAY)
    return urls


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tags", nargs="+", help="e.g. konkur1404 konkur1403 or full URLs")
    parser.add_argument("--group", choices=sorted(GROUPS), help="filter by exam group")
    parser.add_argument("--max-posts", type=int, default=50, help="posts per tag")
    parser.add_argument("--out", type=Path, default=Path("urls.txt"))
    args = parser.parse_args()

    seen: set[str] = set()
    all_urls: list[str] = []
    for tag in args.tags:
        all_urls.extend(collect(tag, args.group, args.max_posts, seen))
    if not all_urls:
        print("no PDF links found", file=sys.stderr)
        return 1
    args.out.write_text("\n".join(dict.fromkeys(all_urls)) + "\n", encoding="utf-8")
    print(f"wrote {len(set(all_urls))} URLs to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
