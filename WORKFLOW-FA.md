# راهنمای کامل ورک‌فلو konkur-dataset

این سند سه چیز را پوشش می‌دهد: (۱) اجرای شب اول روی سیستم خودت، (۲) اتوماسیون ۲۴/۷ با GitHub Actions (سرور رایگان)، (۳) مرحلهٔ تولید سوال و درسنامه با کد پروژهٔ datagenerator روی API رایگان — بدون سرور.

---

## ۱) اجرای همین امشب روی سیستم خودت (یک مسیر، ۴ دستور)

پیش‌نیاز: Python 3.10+، Node 18+، اینترنت.

```bash
# ۱. کراول: از ریشهٔ آرشیو ۱۳۸۱-۱۳۹۸ + تگ‌های سالانه، لینک‌های PDF مستقیم استخراج می‌شود
python3 crawl_konkur.py https://konkur.in/57190/ konkur1404 konkur1403 konkur1402 konkur1401 konkur1400 پاسخ-تشریحی-کنکور-99 کنکور11399 --max-posts 40 --out urls_expanded.txt

# ۲. دانلود دفترچه‌ها (timeout + retry + لاگ خطاها در logs/fetch_errors.log)
python3 fetch_list.py --urls urls_expanded.txt --out raw_sources --log logs/fetch_errors.log

# ۳. استخراج متن PDF (کد اقتباس‌شده از datagenerator/server/src/services/pdfExtract.ts)
npm install
npm run extract

# ۴. بسته‌بندی خروجی نهایی
npm run pack
# خروجی:  ocr_pages_jsonl/<stem>.jsonl   (source_id, page, text)
#          parsed_md/<stem>.md            (با جداکننده <!-- PAGE: N -->)
```

اگر `crawl_konkur.py` تگ و پستی را پیدا نکرد، لینک‌های مستقیم `urls_catalog.txt` را مستقیم بده:
`python3 fetch_list.py --urls urls_catalog.txt --out raw_sources --log logs/fetch_errors.log`

**لیست دانلود دستی (بدون ترمینال):** فایل `sources_catalog.csv` منابع دسته‌بندی‌شده دارد (سال × گروه × جلسه × نوع). ستون `url` را در مرورگر باز کن، در هر پست دکمه‌های «دانلود دفترچه» و «کلید سنجش» یا لینک `dl.konkur.in` را بزن و PDFها را در پوشهٔ `raw_sources/` بریز، سپس از مرحلهٔ ۳ ادامه بده. برای OCR خارج از این اسکریپت‌ها (مثلاً با `ocrmypdf`) خروجی ZIP را در `ocr_zips/` بگذار و اجرا کن:
`python3 ocr_pack.py --zips ocr_zips --jsonl ocr_pages_jsonl --md parsed_md`

## ۲) اتوماسیون ۲۴/۷ — سرور رایگان: GitHub Actions

`.github/workflows/nightly_pipeline.yml` هر شب ساعت ۰۳:۳۰ UTC (۰۷:۰۰ صبح ایران) خودکار اجرا می‌شود:

```
کراول konkur.in → دانلود → استخراج متن PDF → بسته‌بندی JSONL/MD
→ فقط فایل‌های متنی (ocr_text/ ocr_pages_jsonl/ parsed_md/) با پیام "data:" کامیت می‌شوند
```

نکته‌ها:
- PDFهای خام در ریپو ذخیره نمی‌شوند (حجم/حق نشر)؛ فقط متن استخراج‌شده کامیت می‌شود.
- اجرای دستی هم ممکن است: تب **Actions → nightly-pipeline → Run workflow**.
- اگر ۶۰ روز هیچ فعالیتی در ریپو نباشد GitHub اسکچول را غیرفعال می‌کند؛ کافی است دوباره Enable کنی.
- هر مرحلهٔ خطا را ادامه می‌دهد (`continue-on-error`) تا یک سایتِ شلوغ کار کل شب را خراب نکند؛ لاگ واقعی در `logs/fetch_errors.log` و در لاگ ورک‌فلو دیده می‌شود.

## ۳) تولید سوال و درسنامه (کد datagenerator، لوکال، API رایگان)

ساختار canonical دیتاست از datagenerator گرفته شده:

- **۲۱ ستون CSV** (`src/utils/csvDataset.ts`): `id, questionType, question, option_1..4, correctOptionIndex, correctAnswer, explanation, difficulty, bloomLevel, topicTag, approved, status, subject, gradeLevel, topic, language, sourceCitation, qualityScore`
- **سطح بلوم**: `remember | understand | apply | analyze` — **انواع سوال**: `mcq | true_false | fill_blank | short_answer | essay`
- **پرامپت‌ها**: `src/prompts/` (questionGenerate, questionReview, questionRegenerate, examGenerate, system)
- **پرووایدرها**: `server/providers/geminiProvider.ts` (کلید رایگان Google AI Studio: `GEMINI_API_KEY`) و `openaiCompatibleProvider.ts` برای هر API سازگار با OpenAI.

اسکریپت محلی پیشنهادی (رایگان، بدون سرور) — هر شب بعد از `npm run pack`:

```bash
# یک صفحهٔ نمونه از خروجی واقعی به مدل بده:
# ورودی:  ocr_pages_jsonl/<stem>.jsonl  (source_id, page, text)
# پرامپت system: src/prompts/system + src/prompts/questionGenerate از datagenerator
# خروجی: questions.csv با ۲۱ ستون بالا، sourceCitation = نام فایل + شماره صفحه
```

با کلید رایگان Gemini (سهمیهٔ روزانهٔ استاندارد رایگان) و پرامپت‌های آمادهٔ datagenerator، هر شب صد‌ها سوال برچسب‌خورده (بوم + تاپیک + استناد به منبع) تولید و در `questions.csv` انباشته می‌شود — دیتابیس غنی و رشد پیوسته، همیشه و بدون سرور.

## ۴) موارد باز

- **شیت ۳ (خصوصی)**: `1a9U-bECJWfShhf8bGL7lDK4REf-OCflWStXIV6fqMT8` هنوز گیت لاگین دارد؛ در Google Sheets بخش Share گزینهٔ «Anyone with the link → Viewer» را فعال کن تا `extract_sheet_links.py` بتواند لینک‌های داخل سلول‌ها را بخواند.
- پست‌های `candidate` در `sources_catalog.csv` (عنوان: «نیازمند تکمیل عنوان») با همان فرمان کراولِ شبانه به‌طور خودکار متادیتا و PDF می‌گیرند.
- `pdf-parse` واقعی فقط روی سیستم خودت (بعد از `npm install`) تست می‌شود؛ در محیط سندباکس امکان نصب بسته وجود ندارد.
