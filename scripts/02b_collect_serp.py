"""
02b_collect_serp.py
====================
For each query in queries.csv, fetch the top-10 organic Google SERP results
via Bright Data's SERP API zone.

Why this matters:
  By cross-referencing the organic rankings with the AI citation data (from
  01_collect_ai_mode.py and 02_collect_gemini.py), we can answer:

    • Does AI Mode preferentially cite pages that rank #1 organically?
    • At what organic rank do cited pages typically sit?
    • Does AI Mode cite pages that don't appear in the top 10 at all?
    • Do Gemini/ChatGPT/Perplexity diverge from organic rankings differently
      than Google AI Mode does?

  This gives us a real control group — pages that rank highly but are NOT
  cited — for comparing page features (structure, sentence length, domain
  authority) against cited pages.

Output:
  data/raw/serp_results.json  — one record per (query, organic_position) pair
  data/parsed/serp.csv        — parsed, flat table ready for joining with citations.csv

Joining:
  serp.csv has columns: query, organic_rank, url, domain, title, snippet
  citations.csv has column: citation_url_clean, query
  Merge on (query, url) or (query, domain) to get organic_rank for each citation.

Usage:
    python scripts/02b_collect_serp.py
    python scripts/02b_collect_serp.py --limit 5   # smoke test
    python scripts/02b_collect_serp.py --queries queries/queries.csv
"""

import argparse
import sys as _sys
try:
    _sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    _sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

# ─────────────────────────── Config ────────────────────────────────────────

API_KEY     = os.environ.get("BRIGHTDATA_API_KEY", "")
SERP_ZONE   = os.environ.get("BRIGHTDATA_SERP_ZONE", "")
COUNTRY     = os.environ.get("COUNTRY", "US")
TIMEOUT     = int(os.environ.get("REQUEST_TIMEOUT", 60))

RAW_DIR     = Path(os.environ.get("RAW_DATA_DIR", "data/raw"))
PARSED_DIR  = Path(os.environ.get("PARSED_DATA_DIR", "data/parsed"))
RAW_DIR.mkdir(parents=True, exist_ok=True)
PARSED_DIR.mkdir(parents=True, exist_ok=True)

UNLOCKER_URL  = "https://api.brightdata.com/request"
SLEEP_BETWEEN = 1.0    # be polite; SERP zone has its own rate management
MAX_RETRIES   = 2
RESULTS_PER_PAGE = 10


def check_config():
    if not API_KEY or "your_" in API_KEY:
        print("ERROR: Set BRIGHTDATA_API_KEY in .env")
        sys.exit(1)
    if not SERP_ZONE or "your_" in SERP_ZONE:
        print("ERROR: Set BRIGHTDATA_SERP_ZONE in .env")
        sys.exit(1)


# ─────────────────────────── SERP Fetcher ──────────────────────────────────

def fetch_serp_html(query: str) -> str | None:
    """Fetch Google SERP HTML for a query via Bright Data SERP zone."""
    search_url = (
        f"https://www.google.com/search"
        f"?q={quote_plus(query)}"
        f"&num={RESULTS_PER_PAGE}"
        f"&hl=en"
        f"&gl={COUNTRY.lower()}"
    )
    payload = {
        "zone": SERP_ZONE,
        "url": search_url,
        "format": "raw",
        "country": COUNTRY.lower(),
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                UNLOCKER_URL,
                json=payload,
                headers=headers,
                timeout=TIMEOUT,
            )
            if resp.status_code == 200:
                return resp.text
            else:
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** attempt)
        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)

    return None


# ─────────────────────────── SERP Parser ───────────────────────────────────

def extract_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        return domain.removeprefix("www.")
    except Exception:
        return ""


def parse_organic_results(html: str, query: str) -> list[dict]:
    """
    Parse Google SERP HTML and extract organic results.
    Returns list of dicts with: query, organic_rank, url, domain, title, snippet
    """
    soup = BeautifulSoup(html, "lxml")
    results = []
    rank = 1

    # Google organic results live in <div class="g"> or similar containers.
    # We look for the most reliable signal: <a> tags with h3 headings that
    # link to non-Google URLs, in document order.
    seen_urls = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]

        # Skip Google-internal URLs, ads, images, etc.
        if not href.startswith("http"):
            continue
        if "google.com" in href:
            continue
        if href in seen_urls:
            continue

        # Must contain an h3 (title) to qualify as an organic result
        h3 = a_tag.find("h3")
        if not h3:
            continue

        title = h3.get_text(strip=True)
        if not title:
            continue

        # Try to grab the snippet from the surrounding <div>
        snippet = ""
        parent = a_tag.parent
        for _ in range(5):   # walk up at most 5 levels
            if parent is None:
                break
            # Look for a sibling or descendant div with descriptive text
            candidate = parent.find("div", recursive=False)
            if candidate:
                text = candidate.get_text(" ", strip=True)
                if len(text) > 30 and text != title:
                    snippet = text[:300]
                    break
            parent = parent.parent

        seen_urls.add(href)
        results.append({
            "query": query,
            "organic_rank": rank,
            "url": href,
            "domain": extract_domain(href),
            "title": title,
            "snippet": snippet,
        })
        rank += 1

        if rank > RESULTS_PER_PAGE:
            break

    return results


# ─────────────────────────── Main ──────────────────────────────────────────

def collect_serp(queries_csv: str, limit: int | None) -> tuple[list[dict], pd.DataFrame]:
    df = pd.read_csv(queries_csv)
    if limit:
        df = df.head(limit)

    # ── Resume: load existing results ──────────────────────────────────────
    raw_out = RAW_DIR / "serp_results.json"
    all_raw: list[dict] = []
    already_done: set[str] = set()
    if raw_out.exists():
        try:
            with open(raw_out, encoding="utf-8") as f:
                all_raw = json.load(f)
            already_done = {r["query"] for r in all_raw}
            print(f"  Resuming: {len(already_done)} queries already in {raw_out}")
        except Exception:
            all_raw = []

    all_results: list[dict] = [r for rec in all_raw for r in rec.get("results", [])]

    new_df = df[~df["query"].isin(already_done)]
    if new_df.empty:
        print("  All queries already collected. Nothing to do.")
        return all_raw, pd.DataFrame(all_results)

    print(f"  Collecting {len(new_df)} new queries (skipping {len(already_done)} done).")

    raw_out_path = RAW_DIR / "serp_results.json"
    SAVE_EVERY = 50
    since_save = 0

    for _, row in tqdm(new_df.iterrows(), total=len(new_df), desc="SERP queries"):
        query = str(row["query"])

        html = fetch_serp_html(query)
        if not html:
            print(f"  ✗ Failed: {query[:60]}")
            continue

        parsed = parse_organic_results(html, query)
        all_results.extend(parsed)

        all_raw.append({
            "query": query,
            "category": row.get("category", ""),
            "result_count": len(parsed),
            "results": parsed,
        })

        since_save += 1
        if since_save >= SAVE_EVERY:
            tmp_path = raw_out_path.with_suffix(".json.tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(all_raw, f, ensure_ascii=False)
            os.replace(tmp_path, raw_out_path)
            since_save = 0

        time.sleep(SLEEP_BETWEEN)

    return all_raw, pd.DataFrame(all_results)


def main():
    parser = argparse.ArgumentParser(
        description="Collect organic Google SERP rankings via Bright Data SERP zone."
    )
    parser.add_argument("--queries", default="queries/queries.csv")
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Max queries to collect (omit for all 100)"
    )
    args = parser.parse_args()

    check_config()

    print(f"Collecting organic SERP data for queries in {args.queries}…")
    if args.limit:
        print(f"  Limited to {args.limit} queries.")

    raw_records, serp_df = collect_serp(args.queries, args.limit)

    # Save raw JSON
    raw_out = RAW_DIR / "serp_results.json"
    with open(raw_out, "w", encoding="utf-8") as f:
        json.dump(raw_records, f, ensure_ascii=False, indent=2)
    print(f"\n✓ Raw JSON → {raw_out}")

    # Save parsed CSV
    csv_out = PARSED_DIR / "serp.csv"
    serp_df.to_csv(csv_out, index=False)
    print(f"✓ Parsed CSV → {csv_out}  ({len(serp_df)} rows)")

    if not serp_df.empty:
        avg_results = serp_df.groupby("query").size().mean()
        print(f"\n  Queries collected      : {serp_df['query'].nunique()}")
        print(f"  Avg organic results    : {avg_results:.1f}")
        print(f"  Unique domains         : {serp_df['domain'].nunique()}")
        print(f"\nNext: run 05_analyze_patterns.py — it will merge serp.csv with")
        print(f"citations.csv to compute organic_rank for each citation.")


if __name__ == "__main__":
    main()
