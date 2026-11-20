#!/usr/bin/env node
/**
 * Extract per-page text from raw_sources/*.pdf using pdf-parse.
 * Extraction and normalization logic adapted from datagenerator
 * (server/src/services/pdfExtract.ts): shared normalize/estimate rules and
 * the same SCANNED_PAGE_MIN_CHARS heuristic for detecting image-only pages.
 *
 * Output: <out>/<stem>/page_<NNN>.txt files, directly consumable by
 * ocr_pack.py --text-dir (same page naming convention).
 *
 * Offline local tool; no server and no API key required.
 * Install once:  npm install pdf-parse   (or: bun add pdf-parse)
 *
 * Usage:
 *   node pdf_extract.mjs --src raw_sources --out ocr_text
 */
import { mkdir, readdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { PDFParse } from 'pdf-parse';

const CHARS_PER_TOKEN = 3;
const SCANNED_PAGE_MIN_CHARS = 40;

function normalizeExtractedText(raw) {
  return raw
    .replace(/\r\n/g, '\n')
    .replace(/\u00a0/g, ' ')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function estimateTokens(text) {
  const cleaned = text.trim();
  if (!cleaned) return 0;
  return Math.ceil(cleaned.length / CHARS_PER_TOKEN);
}

function pageFileName(num) {
  return `page_${String(num).padStart(3, '0')}.txt`;
}

async function extractPdf(pdfPath, outRoot) {
  const stem = path.basename(pdfPath).replace(/\.pdf$/i, '');
  const data = new Uint8Array(await readFile(pdfPath));
  const parser = new PDFParse({ data });
  try {
    const textResult = await parser.getText();
    const outDir = path.join(outRoot, stem);
    await mkdir(outDir, { recursive: true });
    let saved = 0;
    let totalChars = 0;
    const scanned = [];
    for (const page of textResult.pages) {
      const text = normalizeExtractedText(page.text ?? '');
      if (text.length < SCANNED_PAGE_MIN_CHARS) {
        scanned.push(page.num);
        continue;
      }
      await writeFile(path.join(outDir, pageFileName(page.num)), text + '\n');
      saved += 1;
      totalChars += text.length;
    }
    const tokens = Math.ceil(totalChars / CHARS_PER_TOKEN);
    console.log(`OK   ${stem}: ${saved}/${textResult.pages.length} pages, ~${tokens} tokens`);
    if (scanned.length > 0) {
      console.log(`SCANNED ${stem}: pages without extractable text -> ${scanned.join(', ')}`);
    }
    return saved > 0;
  } finally {
    await parser.destroy();
  }
}

async function listPdfs(srcDir) {
  const entries = await readdir(srcDir, { withFileTypes: true });
  return entries
    .filter((entry) => entry.isFile() && entry.name.toLowerCase().endsWith('.pdf'))
    .map((entry) => path.join(srcDir, entry.name))
    .sort();
}

async function main() {
  const argv = process.argv.slice(2);
  const getOption = (name, fallback) => {
    const idx = argv.indexOf(name);
    return idx >= 0 && argv[idx + 1] ? argv[idx + 1] : fallback;
  };
  const srcDir = getOption('--src', 'raw_sources');
  const outRoot = getOption('--out', 'ocr_text');

  const pdfs = await listPdfs(srcDir);
  if (pdfs.length === 0) {
    console.error(`no pdf files found in ${srcDir}/`);
    process.exitCode = 2;
    return;
  }
  let ok = 0;
  for (const pdfPath of pdfs) {
    try {
      if (await extractPdf(pdfPath, outRoot)) ok += 1;
    } catch (error) {
      console.log(`FAIL ${path.basename(pdfPath)} (${error.message})`);
      process.exitCode = 1;
    }
  }
  console.log(`done: ${ok}/${pdfs.length} pdfs extracted -> ${outRoot}/`);
}

main();
