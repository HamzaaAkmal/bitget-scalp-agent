---
name: web-reader
description: Read web pages, articles, and document links through Exa Contents. Use the `read_url` tool directly, without bash.
category: tool
---
# Web Reading

## Purpose

Converts any URL into clean article text, removing ads, navigation, styling, and other distractions. Suitable for:
- Reading API documentation (`tushare`, `Coinbase`, `yfinance`, and similar)
- Reading technical articles and blogs
- Retrieving research reports and announcements
- Reading GitHub README / Wiki pages

## Usage

**Call the `read_url` tool directly (do not use bash + requests, call the tool directly):**

```
read_url(url="https://tushare.pro/document/2?doc_id=27")
```

Returns JSON:
```json
{
  "status": "ok",
  "title": "Page title",
  "url": "Original URL",
  "content": "Page content in Markdown format",
  "length": 12345
}
```

## Notes

- Content longer than 8000 characters will be truncated, with the total length noted at the end
- Dynamically rendered SPA pages may return only skeleton HTML
- Content is returned in English when Exa can summarize or extract it that way.

## Privacy & freshness

- **Third-party dependency:** `read_url` forwards the full target URL
  (including any query string) to Exa Contents. Do **not** pass URLs
  containing credentials, tokens, or private/internal addresses.
- **Caching/staleness:** results may be a cached snapshot, not live data.
  When stale, the JSON includes `"cached": true`; pass `no_cache=true` to
  force a fresh fetch (slower — use only when freshness matters).
- **Bash fallback caveat:** if a site blocks the reader, a manual
  `bash + requests` fetch is possible, but it bypasses this tool's URL
  safety guard. Use sparingly and never for internal/authenticated URLs.

## Common Usage

### Read API Documentation
```
read_url(url="https://tushare.pro/document/2?doc_id=27")
```

### Read Technical Articles
```
read_url(url="https://blog.example.com/quantitative-trading-guide")
```

### Retrieve GitHub Project Information
```
read_url(url="https://github.com/PaddlePaddle/PaddleOCR")
```
