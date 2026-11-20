# konkur-dataset

Pipeline for building a Konkur (Iranian university entrance exam) text dataset:
download exam booklets (دفترچه سوالات), official SANJESH answer keys (کلید سنجش),
and prep-institute papers, OCR them into zips, and pack the text into a
JSONL + Markdown dataset.

All scripts: Python 3.10+, standard library + `requests` only.

## Files

| File | Purpose |
|---|---|
| `extract_sheet_links.py` | Extract real hyperlink URLs from public Google Sheets (XLSX export) into `urls` files |
| `crawl_konkur.py` | Crawl `konkur.in` year-tag pages, write direct PDF + post URLs |
| `fetch_list.py` | Download URLs from a list into `raw_sources/` (timeout, retries, empty-body rejection, error log) |
| `ocr_pack.py` | Pack `ocr_zips/*.zip` text pages into `ocr_pages_jsonl/<stem>.jsonl` + `parsed_md/<stem>.md` |
| `urls_sample_real.txt` | Starter list of real, live-verified direct PDFs and archive pages |

## Build the 15-year dataset (Konkur 1390–1404)

```bash
python3 -m pip install requests

# 1) gather URLs (questions + answer keys) for each year, Tajhabi group shown
python3 crawl_konkur.py konkur1390 konkur1391 konkur1392 konkur1393 konkur1394 \
    konkur1395 konkur1396 konkur1397 konkur1398 konkur1399 \
    konkur1400 konkur1401 konkur1402 konkur1403 konkur1404 \
    --group tajrobi --out urls_tajrobi.txt

# 2) optionally add Google-Sheet link sources (sheets must be public)
python3 extract_sheet_links.py \
  1cnE1hIHOibUZRnpNk8WnlG8s_zhg2tly31HKNnV9g_E \
  1SOylAZzpn5r7La0z8ic88krpqgYdfnc84uXEU1NXyok \
  --out sheets
cat sheets/*.txt >> urls_tajrobi.txt

# 3) download booklets + keys
cat urls_sample_real.txt urls_tajrobi.txt | grep -v '^\s*#' | grep . > urls.txt
python3 fetch_list.py --urls urls.txt --out raw_sources --log logs/fetch_errors.log

# 4) OCR the PDFs into per-page text zips (your tooling of choice), then pack:
python3 ocr_pack.py --zips ocr_zips --jsonl ocr_pages_jsonl --md parsed_md
```

Output dataset shape
`ocr_pages_jsonl/<booklet>.jsonl` — one JSON object per page:
`{"source_id": "<booklet>", "page": <N>, "text": "..."}`

`parsed_md/<booklet>.md` — full booklet with `<!-- PAGE: N -->` page separators.
