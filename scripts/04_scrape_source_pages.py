"""
04_scrape_source_pages.py
==========================
For each cited URL, fetch the source page via Bright Data Web Unlocker
(with data_format=markdown) and analyse WHERE the cited sentence appears
within the document (relative position, element type, structured content).

Why Web Unlocker?
  A plain requests.get() is blocked by ~40-60% of high-citation sites
  (Reddit, Healthline, Stack Overflow, WebMD, Investopedia, etc.).
  Web Unlocker handles bot detection, CAPTCHAs, and fingerprinting.

Why markdown output?
  data_format=markdown strips nav/footer/ad noise before we receive the
  page, giving cleaner text for sentence matching vs. raw HTML + BS4.

Inputs : data/parsed/citations.csv
Outputs: data/parsed/source_pages.csv
         data/parsed/page_cache/  (cached .md files, one per URL)

Setup:
  1. Create a Web Unlocker zone at brightdata.com/cp/zones -> Add zone -> Web Unlocker
  2. Set BRIGHTDATA_WEB_UNLOCKER_ZONE=<zone_name> in .env

Usage:
    python scripts/04_scrape_source_pages.py
    python scripts/04_scrape_source_pages.py --limit 50   # start small to verify
    python scripts/04_scrape_source_pages.py --no-cache   # force re-fetch
"""

import argparse
import sys as _sys
try:
    _sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    _sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
import hashlib
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

#  Config 

API_KEY = os.environ.get("BRIGHTDATA_API_KEY", "")
ZONE    = os.environ.get("BRIGHTDATA_WEB_UNLOCKER_ZONE", "")

PARSED_DIR = Path(os.environ.get("PARSED_DATA_DIR", "data/parsed"))
CACHE_DIR  = PARSED_DIR / "page_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

UNLOCKER_URL  = "https://api.brightdata.com/request"
TIMEOUT       = 60
SLEEP_BETWEEN = 0.3
MAX_RETRIES   = 2
SCRAPE_WORKERS = 12  # concurrent Web Unlocker requests

AUTH_HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}


def check_config():
    if not API_KEY or "your_" in API_KEY:
        print("ERROR: Set BRIGHTDATA_API_KEY in .env")
        sys.exit(1)
    if not ZONE or "your_" in ZONE:
        print("ERROR: Set BRIGHTDATA_WEB_UNLOCKER_ZONE in .env")
        print("  Create a zone at: brightdata.com/cp/zones -> Add zone -> Web Unlocker")
        sys.exit(1)


#  Markdown Block Parser 

def get_markdown_blocks(markdown: str) -> list[str]:
    """Split markdown into non-empty content blocks separated by blank lines."""
    if not markdown:
        return []
    raw_blocks = re.split(r"\n{2,}", markdown)
    return [b.strip() for b in raw_blocks if b.strip()]


def find_sentence_in_blocks(cited_sentence: str, blocks: list[str]) -> dict:
    """Find the best matching block for the cited sentence."""
    empty = {
        "found": False,
        "block_index": None,
        "block_total": len(blocks),
        "relative_position": None,
        "block_text_preview": None,
        "match_score": 0.0,
    }

    if not cited_sentence or not blocks:
        return empty

    query = cited_sentence.lower()
    best_score = 0.0
    best_idx = None

    for idx, block in enumerate(blocks):
        block_lower = block.lower()
        if query in block_lower:
            score = len(query) / max(len(block_lower), 1)
            if score > best_score:
                best_score = score
                best_idx = idx
            continue
        q_tokens = set(query.split())
        b_tokens = set(block_lower.split())
        if q_tokens:
            overlap = len(q_tokens & b_tokens) / len(q_tokens)
            if overlap > best_score and overlap > 0.6:
                best_score = overlap
                best_idx = idx

    if best_idx is None:
        return empty

    relative_pos = best_idx / max(len(blocks) - 1, 1)
    return {
        "found": True,
        "block_index": best_idx,
        "block_total": len(blocks),
        "relative_position": round(relative_pos, 4),
        "block_text_preview": blocks[best_idx][:200],
        "match_score": round(best_score, 4),
    }


def page_features_from_markdown(markdown: str) -> dict:
    """Extract high-level page features from markdown text."""
    if not markdown:
        return {
            "page_title": "",
            "page_word_count": 0,
            "heading_count": 0,
            "paragraph_count": 0,
            "list_count": 0,
            "table_count": 0,
            "has_structured_content": False,
        }

    lines = markdown.splitlines()
    title = ""
    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip()
            break

    headings = sum(1 for l in lines if re.match(r"^#{1,6} ", l))
    list_items = sum(1 for l in lines if re.match(r"^\s*[-*+] |^\s*\d+\. ", l))
    table_rows = sum(1 for l in lines if "|" in l and l.strip().startswith("|"))
    paras = len([b for b in re.split(r"\n{2,}", markdown) if b.strip() and not b.strip().startswith("#")])
    words = len(markdown.split())

    return {
        "page_title": title,
        "page_word_count": words,
        "heading_count": headings,
        "paragraph_count": paras,
        "list_count": list_items,
        "table_count": table_rows,
        "has_structured_content": (list_items + table_rows) > 0,
    }


#  Fetcher 

def url_to_cache_path(url: str) -> Path:
    h = hashlib.md5(url.encode()).hexdigest()
    return CACHE_DIR / f"{h}.md"


def fetch_as_markdown(url: str, use_cache: bool = True) -> str | None:
    """Fetch a URL via Bright Data Web Unlocker and return markdown content."""
    cache_path = url_to_cache_path(url)
    if use_cache and cache_path.exists():
        return cache_path.read_text(encoding="utf-8", errors="replace")

    payload = {
        "zone": ZONE,
        "url": url,
        "format": "raw",
        "data_format": "markdown",
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                UNLOCKER_URL,
                headers=AUTH_HEADERS,
                json=payload,
                timeout=TIMEOUT,
            )
            if resp.status_code == 200:
                md = resp.text
                cache_path.write_text(md, encoding="utf-8", errors="replace")
                return md
            else:
                if attempt == MAX_RETRIES:
                    print(f"  HTTP {resp.status_code} for {url[:80]}")
                time.sleep(2 * attempt)
        except Exception as e:
            if attempt == MAX_RETRIES:
                print(f"  Fetch error {url[:80]}: {e}")
            time.sleep(2 * attempt)

    time.sleep(SLEEP_BETWEEN)
    return None


#  Main Analysis 

def analyse_citations(cite_df: pd.DataFrame, limit: int | None = None, use_cache: bool = True) -> pd.DataFrame:
    """Scrape each cited URL and compute positional/structural features."""
    work_df = cite_df[
        cite_df["cited_sentence"].notna() &
        (cite_df["cited_sentence"] != "") &
        cite_df["citation_url_clean"].notna()
    ].copy()

    if limit:
        work_df = work_df.head(limit)

    results = []

    def _process_row(row):
        url = str(row["citation_url_clean"])
        cited_sentence = str(row["cited_sentence"])

        md = fetch_as_markdown(url, use_cache=use_cache)
        if not md:
            return {
                **row.to_dict(),
                "scrape_error": True,
                "found": False, "block_index": None, "block_total": 0,
                "relative_position": None, "block_text_preview": None, "match_score": 0.0,
                "page_title": "", "page_word_count": 0, "heading_count": 0,
                "paragraph_count": 0, "list_count": 0, "table_count": 0,
                "has_structured_content": False,
            }

        blocks = get_markdown_blocks(md)
        pos_info = find_sentence_in_blocks(cited_sentence, blocks)
        feats = page_features_from_markdown(md)
        return {**row.to_dict(), "scrape_error": False, **pos_info, **feats}

    rows = [row for _, row in work_df.iterrows()]
    with ThreadPoolExecutor(max_workers=SCRAPE_WORKERS) as executor:
        futures = {executor.submit(_process_row, row): row for row in rows}
        for fut in tqdm(as_completed(futures), total=len(futures), desc="Scraping pages"):
            result = fut.result()
            if result is not None:
                results.append(result)

    return pd.DataFrame(results)


#  CLI 

def main():
    parser = argparse.ArgumentParser(description="Scrape source pages via Web Unlocker and find cited sentence positions.")
    parser.add_argument("--citations", default=str(PARSED_DIR / "citations.csv"))
    parser.add_argument("--out", default=str(PARSED_DIR / "source_pages.csv"))
    parser.add_argument("--limit", type=int, default=None, help="Limit rows to scrape (for testing)")
    parser.add_argument("--no-cache", action="store_true", help="Force re-fetch (ignore cache)")
    args = parser.parse_args()

    check_config()

    if not Path(args.citations).exists():
        print(f"ERROR: {args.citations} not found. Run 03_parse_text_fragments.py first.")
        return

    cite_df = pd.read_csv(args.citations)
    print(f"Loaded {len(cite_df)} citations. Scraping source pages via Web Unlocker...")

    result_df = analyse_citations(cite_df, args.limit, use_cache=not args.no_cache)
    result_df.to_csv(args.out, index=False)
    print(f"\n  {len(result_df)} rows -> {args.out}")

    if "found" in result_df.columns and len(result_df) > 0:
        print(f"  Sentence found rate:  {result_df['found'].fillna(False).mean():.1%}")
        print(f"  Non-zero match rate:  {result_df['match_score'].fillna(0).gt(0).mean():.1%}")
        print(f"  Scrape error rate:    {result_df['scrape_error'].fillna(False).mean():.1%}")


if __name__ == "__main__":
    main()
