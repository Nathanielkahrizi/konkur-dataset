#!/usr/bin/env python3
"""Pack markdown/text pages from ocr_zips/*.zip into JSONL and merged markdown."""
from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path

TEXT_EXTS = {".md", ".markdown", ".txt"}
DIGITS = re.compile(r"\d+")


def natural_key(name: str) -> tuple:
    return tuple(
        (1, int(part)) if part.isdigit() else (0, part)
        for part in re.split(r"(\d+)", name.lower())
        if part != ""
    )


def page_number(stem: str, fallback: int) -> int:
    numbers = DIGITS.findall(stem)
    return int(numbers[-1]) if numbers else fallback


def iter_booklet_members(booklet_dir: Path) -> list[Path]:
    return sorted(
        (
            child
            for child in booklet_dir.iterdir()
            if child.is_file() and child.suffix.lower() in TEXT_EXTS
        ),
        key=lambda p: natural_key(p.name),
    )


def unpack_pages(names, read) -> list[tuple[int, str]]:
    pages: list[tuple[int, str]] = []
    seen: set[int] = set()
    sequential = 0
    for member in names:
        sequential += 1
        stem = Path(member).stem
        text = read(member).decode("utf-8", errors="replace")
        if not text.strip():
            continue
        page = page_number(stem, sequential)
        while page in seen:
            page = sequential
            sequential += 1
        seen.add(page)
        pages.append((page, text))
    return pages


def unpack(zip_path: Path) -> list[tuple[int, str]]:
    with zipfile.ZipFile(zip_path) as archive:
        names = [
            info.filename
            for info in archive.infolist()
            if not info.is_dir()
            and Path(info.filename).suffix.lower() in TEXT_EXTS
        ]
        names.sort(key=natural_key)
        return unpack_pages(names, archive.read)


def unpack_dir(booklet_dir: Path) -> list[tuple[int, str]]:
    names = [p for p in iter_booklet_members(booklet_dir)]
    return unpack_pages(names, lambda p: Path(p).read_bytes())


def write_outputs(stem: str, pages: list[tuple[int, str]], jsonl_dir: Path, md_dir: Path) -> None:
    jsonl_dir.mkdir(parents=True, exist_ok=True)
    md_dir.mkdir(parents=True, exist_ok=True)
    with (jsonl_dir / f"{stem}.jsonl").open("w", encoding="utf-8") as jsonl:
        for page, text in pages:
            jsonl.write(json.dumps({"source_id": stem, "page": page, "text": text}, ensure_ascii=False) + "\n")
    (md_dir / f"{stem}.md").write_text(
        "\n\n".join(f"<!-- PAGE: {page} -->\n\n{text.strip()}" for page, text in pages) + "\n",
        encoding="utf-8",
    )


def run(zips_dir: Path, jsonl_dir: Path, md_dir: Path, text_dir: Path | None = None) -> tuple[int, int]:
    ok = fail = 0
    sources: list[tuple[str, Path]] = [
        (p.stem, p) for p in sorted(zips_dir.glob("*.zip"), key=lambda p: natural_key(p.name))
    ]
    if text_dir is not None:
        sources += [
            (d.name, d)
            for d in sorted(text_dir.iterdir(), key=lambda p: natural_key(p.name))
            if d.is_dir()
        ]
    for stem, path in sources:
        try:
            pages = unpack_dir(path) if path.is_dir() else unpack(path)
            if not pages:
                raise ValueError("no text pages found")
            write_outputs(stem, pages, jsonl_dir, md_dir)
            ok += 1
            print(f"OK   {path.name}: {len(pages)} pages")
        except Exception as error:  # noqa: BLE001
            fail += 1
            print(f"FAIL {path.name} ({error})")
    return ok, fail


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zips", type=Path, default=Path("ocr_zips"))
    parser.add_argument("--text-dir", type=Path, default=None, help="alternative source: <dir>/<stem>/page_N.txt trees")
    parser.add_argument("--jsonl", type=Path, default=Path("ocr_pages_jsonl"))
    parser.add_argument("--md", type=Path, default=Path("parsed_md"))
    args = parser.parse_args()
    if not args.zips.is_dir() and args.text_dir is None:
        print(f"missing {args.zips}/ (or pass --text-dir)", file=__import__("sys").stderr)
        return 2
    ok, fail = run(args.zips, args.jsonl, args.md, args.text_dir)
    print(f"done: {ok} packed, {fail} failed")
    return 1 if fail and not ok else 0


if __name__ == "__main__":
    raise SystemExit(main())
