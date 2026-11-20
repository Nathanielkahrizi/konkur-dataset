#!/usr/bin/env python3
"""Extract real hyperlink URLs from public Google Sheets into download lists.

Works around the CSV-export limitation (CSV keeps only link display text).
Downloads each sheet's XLSX export, then pulls URLs from two places:
  1. cell-level hyperlinks stored as worksheet relationships,
  2. HYPERLINK("url","text") formula string literals.

Usage:
  python3 extract_sheet_links.py ID1 ID2 ... [--out DIR]

Each sheet gets <ID>.txt in DIR with one URL per line (comments=list row text).
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

import requests

TIMEOUT = 30
RETRIES = 3
BACKOFF = 2.0
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
FORMULA_URL = re.compile(r'HYPERLINK\s*\(\s*"([^"]+)"', re.I)
VALID_SCHEMES = {"http", "https"}
SKIP_HOSTS = ("docs.google.com/spreadsheets",)


def get(url: str) -> requests.Response:
    last = None
    for attempt in range(1, RETRIES + 1):
        try:
            resp = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "fetch-list/1.0"})
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            last = exc
            if attempt < RETRIES:
                import time
                time.sleep(BACKOFF * 2 ** (attempt - 1))
    raise SystemExit(f"download failed: {url} ({last})")


def shared_strings(data: bytes) -> list[str]:
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return []
    out = []
    for si in root.findall("m:si", NS):
        out.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))
    return out


def rel_index(data: bytes) -> dict[str, str]:
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return {}
    return {r.get("Id"): (r.get("Target", ""), r.get("TargetMode")) for r in root.findall(f"{{{REL_NS}}}Relationship")}


def rel_targets(data: bytes) -> dict[str, str]:
    return {rid: tgt for rid, (tgt, mode) in rel_index(data).items() if rid and mode == "External"}


def row_text(row: ET.Element, strings: list[str]) -> str:
    cells = []
    for c in row.findall("m:c", NS):
        v = c.find("m:v", NS)
        if v is None or v.text is None:
            continue
        if c.get("t") == "s":
            try:
                cells.append(string_sanitize(strings[int(v.text)]))
            except (ValueError, IndexError):
                pass
        else:
            cells.append(v.text)
    return " | ".join(x for x in cells if x)


def string_sanitize(text: str, limit: int = 120) -> str:
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def accepted(url: str) -> bool:
    try:
        scheme = urlparse(url).scheme.lower()
    except ValueError:
        return False
    if scheme not in VALID_SCHEMES:
        return False
    return not any(skip in url for skip in SKIP_HOSTS)


def extract(xlsx_path: Path) -> list[tuple[str, str]]:
    z = zipfile.ZipFile(xlsx_path)
    strings = shared_strings(z.read("xl/sharedStrings.xml")) if "xl/sharedStrings.xml" in z.namelist() else []
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rel_map = {rid: tgt for rid, (tgt, _)
               in rel_index(z.read("xl/_rels/workbook.xml.rels")).items()}
    sheet_map = {s.get("name"): rel_map.get(s.get(
        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id", ""))
        for s in wb.find("m:sheets", NS)}
    rows_out: list[tuple[str, str]] = []
    for sheet in wb.find("m:sheets", NS):
        name = sheet.get("name", "sheet")
        path = (sheet_map.get(name) or "").lstrip("/")
        path = path if path in z.namelist() else "xl/" + path
        if not path or path not in z.namelist():
            continue
        targets = rel_targets(z.read(f"xl/worksheets/_rels/{Path(path).name}.rels")) \
            if f"xl/worksheets/_rels/{Path(path).name}.rels" in z.namelist() else {}
        root = ET.fromstring(z.read(path))
        for row in root.iter(f"{{{NS['m']}}}row"):
            label = row_text(row, strings)
            urls: list[str] = []
            for c in row.findall("m:c", NS):
                rid = c.get(f"{{{NS['r']}}}id")
                if rid and rid in targets and accepted(targets[rid]):
                    urls.append(targets[rid])
                f = c.find("m:f", NS)
                if f is not None and f.text:
                    for u in FORMULA_URL.findall(f.text):
                        u = u.replace("&amp;", "&")
                        if accepted(u):
                            urls.append(u)
            seen: set[str] = set()
            for u in urls:
                if u not in seen:
                    seen.add(u)
                    rows_out.append((label, u))
    return rows_out


def run(sheet_ids: list[str], out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    failures = 0
    for sid in sheet_ids:
        url = f"https://docs.google.com/spreadsheets/d/{sid}/export?format=xlsx"
        dest = out_dir / f"{sid}.xlsx"
        print(f"OK   {sid} -> {dest}")
        try:
            resp = get(url)
            dest.write_bytes(resp.content)
        except SystemExit as exc:
            print(f"FAIL {sid} {exc}", file=sys.stderr)
            failures += 1
            continue
        links_path = out_dir / f"{sid}.txt"
        lines: list[str] = []
        for label, link in extract(dest):
            marker = "" if not label else f"  # {string_sanitize(label)}"
            lines.append(link + marker)
        links_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        print(f"OK   {sid}: {len(lines)} links -> {links_path}")
    return 1 if failures else 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract hyperlinks from public Google Sheets")
    ap.add_argument("ids", nargs="+", help="spreadsheet IDs")
    ap.add_argument("--out", default="", help="output directory (default: current)")
    args = ap.parse_args()
    raise SystemExit(run(args.ids, Path(args.out or ".")))


if __name__ == "__main__":
    main()
