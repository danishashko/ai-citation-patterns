"""
08_freshness_analysis.py
=========================
Extract publication and modification dates from cited source pages,
then analyse the freshness of content Google AI Mode chooses to cite.

Strategy:
  1. HTTP GET each unique source URL (with browser User-Agent)
  2. Parse HTML for structured date metadata:
     - JSON-LD schema.org (datePublished, dateModified, dateCreated)
     - Open Graph meta (article:published_time, article:modified_time)
     - Standard meta (date, DC.date.issued, pubdate, last-modified)
     - <time> elements with datetime and itemprop attributes
  3. Also capture HTTP Last-Modified header
  4. De-duplicate, validate, and output freshness analysis

Inputs : data/parsed/source_pages.csv (unique URLs)
Outputs: data/analysis/freshness_dates.csv     — per-URL extracted dates
         data/analysis/freshness_stats.json     — aggregate stats
         reports/freshness_distribution.png     — age distribution histogram
         reports/freshness_by_position.png      — content age vs cite position

Usage:
    python scripts/08_freshness_analysis.py
    python scripts/08_freshness_analysis.py --limit 100    # test with fewer
    python scripts/08_freshness_analysis.py --workers 8     # adjust parallelism
"""

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser
from dotenv import load_dotenv

load_dotenv()

PARSED_DIR = Path(os.environ.get("PARSED_DATA_DIR", "data/parsed"))
ANALYSIS_DIR = Path(os.environ.get("ANALYSIS_DATA_DIR", "data/analysis"))
CHARTS_DIR = Path("reports")
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Style ───────────────────────────────────────────────────────────────────
sns.set_theme(style="whitegrid", palette="muted", font_scale=1.2)
GOOGLE_BLUE = "#4285F4"
GOOGLE_RED = "#EA4335"
GOOGLE_YELLOW = "#FBBC05"
GOOGLE_GREEN = "#34A853"
DPI = 150
FIG_W, FIG_H = 10, 6

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

TIMEOUT = 20
MAX_WORKERS = 10
SLEEP_BETWEEN = 0.15

# Snapshot date — when the data was collected
SNAPSHOT_DATE = datetime(2025, 2, 1, tzinfo=timezone.utc)


def save_fig(fig, name: str):
    path = CHARTS_DIR / name
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ {path}")


# ─────────────────────────── Date Extraction ───────────────────────────────

def safe_parse_date(raw: str) -> datetime | None:
    """Try to parse a date string into a datetime, return None on failure."""
    if not raw or not isinstance(raw, str):
        return None
    raw = raw.strip()
    if len(raw) < 4:
        return None
    try:
        dt = dateutil_parser.parse(raw, fuzzy=True)
        # Sanity: reject dates before 1990 or after 2027
        if dt.year < 1990 or dt.year > 2027:
            return None
        return dt
    except Exception:
        return None


def extract_dates_from_html(html: str) -> dict:
    """
    Extract publication and modification dates from HTML using multiple strategies.
    Returns dict with 'published', 'modified', 'source' keys.
    """
    result = {
        "published": None,
        "modified": None,
        "published_source": None,
        "modified_source": None,
    }

    if not html:
        return result

    soup = BeautifulSoup(html, "html.parser")

    # ── Strategy 1: JSON-LD ─────────────────────────────────────────
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            _extract_jsonld_dates(data, result)
            if result["published"] and result["modified"]:
                return result
        except (json.JSONDecodeError, TypeError):
            continue

    # ── Strategy 2: Open Graph meta tags ─────────────────────────────
    og_mappings = {
        "article:published_time": ("published", "og"),
        "article:published": ("published", "og"),
        "article:modified_time": ("modified", "og"),
        "article:modified": ("modified", "og"),
    }
    for prop, (field, src) in og_mappings.items():
        if result[field]:
            continue
        tag = soup.find("meta", property=prop)
        if tag and tag.get("content"):
            dt = safe_parse_date(tag["content"])
            if dt:
                result[field] = dt.isoformat()
                result[f"{field}_source"] = src

    # ── Strategy 3: Standard meta tags ───────────────────────────────
    meta_mappings = {
        "date": ("published", "meta"),
        "pubdate": ("published", "meta"),
        "publish-date": ("published", "meta"),
        "publish_date": ("published", "meta"),
        "DC.date.issued": ("published", "dc"),
        "DC.date.created": ("published", "dc"),
        "dcterms.created": ("published", "dc"),
        "dcterms.modified": ("modified", "dc"),
        "last-modified": ("modified", "meta"),
        "revised": ("modified", "meta"),
    }
    for name, (field, src) in meta_mappings.items():
        if result[field]:
            continue
        tag = soup.find("meta", attrs={"name": re.compile(f"^{re.escape(name)}$", re.I)})
        if tag and tag.get("content"):
            dt = safe_parse_date(tag["content"])
            if dt:
                result[field] = dt.isoformat()
                result[f"{field}_source"] = src

    # ── Strategy 4: <time> elements with itemprop or datetime ────────
    for time_tag in soup.find_all("time"):
        dt_str = time_tag.get("datetime", "")
        itemprop = time_tag.get("itemprop", "").lower()

        if not dt_str:
            continue

        dt = safe_parse_date(dt_str)
        if not dt:
            continue

        if "publish" in itemprop or "created" in itemprop or "date" == itemprop:
            if not result["published"]:
                result["published"] = dt.isoformat()
                result["published_source"] = "time_tag"
        elif "modified" in itemprop or "updated" in itemprop:
            if not result["modified"]:
                result["modified"] = dt.isoformat()
                result["modified_source"] = "time_tag"
        elif not result["published"]:
            # Generic <time datetime="..."> without itemprop — assume published
            result["published"] = dt.isoformat()
            result["published_source"] = "time_tag"

    return result


def _extract_jsonld_dates(data, result: dict):
    """Recursively extract date fields from JSON-LD data."""
    if isinstance(data, list):
        for item in data:
            _extract_jsonld_dates(item, result)
            if result["published"] and result["modified"]:
                return
        return

    if not isinstance(data, dict):
        return

    # Check @graph
    if "@graph" in data:
        _extract_jsonld_dates(data["@graph"], result)
        if result["published"] and result["modified"]:
            return

    for pub_key in ("datePublished", "dateCreated", "uploadDate"):
        if not result["published"] and pub_key in data:
            dt = safe_parse_date(str(data[pub_key]))
            if dt:
                result["published"] = dt.isoformat()
                result["published_source"] = "jsonld"

    for mod_key in ("dateModified", "dateUpdated"):
        if not result["modified"] and mod_key in data:
            dt = safe_parse_date(str(data[mod_key]))
            if dt:
                result["modified"] = dt.isoformat()
                result["modified_source"] = "jsonld"


# ─────────────────────────── Fetcher ───────────────────────────────────────

def fetch_and_extract(url: str, session=None) -> dict:
    """Fetch a URL and extract date metadata."""
    import requests as req

    row = {
        "url": url,
        "http_status": None,
        "last_modified_header": None,
        "published": None,
        "modified": None,
        "published_source": None,
        "modified_source": None,
        "error": None,
    }

    try:
        s = session or req
        resp = s.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        row["http_status"] = resp.status_code

        # HTTP Last-Modified header
        lm = resp.headers.get("Last-Modified")
        if lm:
            dt = safe_parse_date(lm)
            if dt:
                row["last_modified_header"] = dt.isoformat()

        if resp.status_code == 200 and resp.text:
            # Only parse if content looks like HTML
            ct = resp.headers.get("Content-Type", "")
            if "html" in ct.lower() or resp.text.strip()[:5].lower() in ("<!doc", "<html"):
                dates = extract_dates_from_html(resp.text[:500_000])  # cap at 500KB
                row.update(dates)

    except Exception as e:
        row["error"] = str(e)[:200]

    return row


# ─────────────────────────── Main Pipeline ─────────────────────────────────

def load_urls() -> list[str]:
    """Load unique citation URLs from source_pages.csv."""
    sp = pd.read_csv(PARSED_DIR / "source_pages.csv", low_memory=False)
    urls = sp["citation_url_clean"].dropna().unique().tolist()
    # Filter out non-HTTP
    urls = [u for u in urls if str(u).startswith("http")]
    print(f"  {len(urls):,} unique URLs to process")
    return urls


def run_extraction(urls: list[str], max_workers: int = MAX_WORKERS) -> pd.DataFrame:
    """Fetch all URLs and extract dates in parallel."""
    import requests as req

    results = []
    session = req.Session()
    session.headers.update(HEADERS)

    total = len(urls)
    done = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for url in urls:
            future = executor.submit(fetch_and_extract, url, session)
            futures[future] = url

        for future in as_completed(futures):
            done += 1
            try:
                row = future.result()
                results.append(row)
                if row.get("error"):
                    failed += 1
            except Exception as e:
                results.append({"url": futures[future], "error": str(e)[:200]})
                failed += 1

            if done % 100 == 0 or done == total:
                extracted = sum(1 for r in results if r.get("published") or r.get("modified") or r.get("last_modified_header"))
                print(f"  {done:,}/{total:,} done | {extracted:,} dates found | {failed:,} errors")

    return pd.DataFrame(results)


def compute_freshness_stats(df: pd.DataFrame) -> dict:
    """Compute aggregate freshness statistics."""
    stats = {
        "total_urls": len(df),
        "urls_with_published": int(df["published"].notna().sum()),
        "urls_with_modified": int(df["modified"].notna().sum()),
        "urls_with_last_modified_header": int(df["last_modified_header"].notna().sum()),
        "urls_with_any_date": int(
            (df["published"].notna() | df["modified"].notna() | df["last_modified_header"].notna()).sum()
        ),
        "urls_with_errors": int(df["error"].notna().sum()),
    }

    # Compute age in days from best available date
    # Prioritise published date (content creation) over modified (often updated post-collection)
    df = df.copy()
    df["best_date"] = df["published"].fillna(df["modified"]).fillna(df["last_modified_header"])
    has_date = df[df["best_date"].notna()].copy()

    if len(has_date) > 0:
        has_date["best_dt"] = has_date["best_date"].apply(
            lambda x: safe_parse_date(x) if isinstance(x, str) else None
        )
        has_date = has_date[has_date["best_dt"].notna()]

        if len(has_date) > 0:
            has_date["age_days"] = has_date["best_dt"].apply(
                lambda dt: (SNAPSHOT_DATE - dt.replace(tzinfo=timezone.utc)).days
                if dt.tzinfo is None else (SNAPSHOT_DATE - dt).days
            )
            # Filter out unreasonable ages
            has_date = has_date[(has_date["age_days"] >= 0) & (has_date["age_days"] < 365 * 35)]

            ages = has_date["age_days"]
            stats["age_stats"] = {
                "n": int(len(ages)),
                "mean_days": round(float(ages.mean()), 1),
                "median_days": round(float(ages.median()), 1),
                "std_days": round(float(ages.std()), 1),
                "min_days": int(ages.min()),
                "max_days": int(ages.max()),
                "p25_days": round(float(ages.quantile(0.25)), 1),
                "p75_days": round(float(ages.quantile(0.75)), 1),
            }

            # Age buckets
            def age_bucket(days):
                if days <= 30:
                    return "< 1 month"
                elif days <= 90:
                    return "1–3 months"
                elif days <= 180:
                    return "3–6 months"
                elif days <= 365:
                    return "6–12 months"
                elif days <= 730:
                    return "1–2 years"
                elif days <= 1825:
                    return "2–5 years"
                else:
                    return "5+ years"

            bucket_counts = has_date["age_days"].apply(age_bucket).value_counts().to_dict()
            stats["age_distribution"] = bucket_counts

            # Year distribution
            year_counts = has_date["best_dt"].apply(lambda dt: dt.year).value_counts().sort_index().to_dict()
            stats["year_distribution"] = {str(k): int(v) for k, v in year_counts.items()}

    # Source breakdown
    pub_src = df["published_source"].dropna().value_counts().to_dict()
    mod_src = df["modified_source"].dropna().value_counts().to_dict()
    stats["published_source_breakdown"] = pub_src
    stats["modified_source_breakdown"] = mod_src

    return stats


# ─────────────────────────── Charts ────────────────────────────────────────

def chart_age_distribution(df: pd.DataFrame):
    """Histogram of content age in days."""
    df = df.copy()
    df["best_date"] = df["published"].fillna(df["modified"]).fillna(df["last_modified_header"])
    has_date = df[df["best_date"].notna()].copy()
    has_date["best_dt"] = has_date["best_date"].apply(
        lambda x: safe_parse_date(x) if isinstance(x, str) else None
    )
    has_date = has_date[has_date["best_dt"].notna()]
    has_date["age_days"] = has_date["best_dt"].apply(
        lambda dt: (SNAPSHOT_DATE - dt.replace(tzinfo=timezone.utc)).days
        if dt.tzinfo is None else (SNAPSHOT_DATE - dt).days
    )
    has_date = has_date[(has_date["age_days"] >= 0) & (has_date["age_days"] < 365 * 10)]

    if len(has_date) < 10:
        print("  (skip) Not enough date data for age distribution chart")
        return

    ages = has_date["age_days"]

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    ax.hist(ages, bins=40, color=GOOGLE_BLUE, edgecolor="white", linewidth=0.5)
    ax.axvline(ages.median(), color=GOOGLE_RED, linestyle="--", linewidth=2,
               label=f"Median: {ages.median():.0f} days ({ages.median()/365:.1f} yrs)")
    ax.axvline(ages.mean(), color=GOOGLE_YELLOW, linestyle="--", linewidth=2,
               label=f"Mean: {ages.mean():.0f} days ({ages.mean()/365:.1f} yrs)")

    ax.set_xlabel("Content Age (days since publication/modification)", fontweight="bold")
    ax.set_ylabel("Number of Cited Pages", fontweight="bold")
    ax.set_title("How Old Is the Content Google AI Mode Cites?\n(Age at time of data collection, Feb 2025)",
                 fontsize=13)
    ax.legend(framealpha=0.9, fontsize=10)
    fig.tight_layout()
    save_fig(fig, "freshness_distribution.png")


def chart_freshness_by_position(df: pd.DataFrame, source_pages: pd.DataFrame):
    """Scatter: content age vs document position."""
    df = df.copy()
    df["best_date"] = df["published"].fillna(df["modified"]).fillna(df["last_modified_header"])
    has_date = df[df["best_date"].notna()].copy()
    has_date["best_dt"] = has_date["best_date"].apply(
        lambda x: safe_parse_date(x) if isinstance(x, str) else None
    )
    has_date = has_date[has_date["best_dt"].notna()]
    has_date["age_days"] = has_date["best_dt"].apply(
        lambda dt: (SNAPSHOT_DATE - dt.replace(tzinfo=timezone.utc)).days
        if dt.tzinfo is None else (SNAPSHOT_DATE - dt).days
    )
    has_date = has_date[(has_date["age_days"] >= 0) & (has_date["age_days"] < 365 * 10)]

    # Merge with positional data
    pos = source_pages[source_pages["relative_position"].notna()][
        ["citation_url_clean", "relative_position"]
    ].drop_duplicates(subset=["citation_url_clean"])

    merged = has_date.merge(pos, left_on="url", right_on="citation_url_clean", how="inner")

    if len(merged) < 10:
        print(f"  (skip) Only {len(merged)} rows for freshness vs position chart")
        return

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    ax.scatter(
        merged["age_days"] / 365,
        merged["relative_position"] * 100,
        alpha=0.3, s=15, color=GOOGLE_BLUE, edgecolors="none"
    )

    # Trend line
    z = np.polyfit(merged["age_days"] / 365, merged["relative_position"] * 100, 1)
    p = np.poly1d(z)
    x_line = np.linspace(0, merged["age_days"].max() / 365, 100)
    ax.plot(x_line, p(x_line), color=GOOGLE_RED, linewidth=2, linestyle="--",
            label=f"Trend (slope: {z[0]:.2f})")

    ax.set_xlabel("Content Age (years)", fontweight="bold")
    ax.set_ylabel("Citation Position in Document (%)", fontweight="bold")
    ax.set_title("Does Content Age Affect Where Sentences Are Cited From?",
                 fontsize=13)
    ax.legend(framealpha=0.9)
    fig.tight_layout()
    save_fig(fig, "freshness_by_position.png")


def chart_year_distribution(stats: dict):
    """Bar chart of publication years."""
    year_dist = stats.get("year_distribution", {})
    if not year_dist:
        print("  (skip) No year distribution data")
        return

    years = sorted(year_dist.keys())
    counts = [year_dist[y] for y in years]

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    colors = [GOOGLE_BLUE if int(y) >= 2024 else
              GOOGLE_GREEN if int(y) >= 2022 else
              GOOGLE_YELLOW if int(y) >= 2020 else
              GOOGLE_RED for y in years]
    bars = ax.bar(years, counts, color=colors, edgecolor="white")
    ax.bar_label(bars, fmt="%d", padding=4, fontsize=9)

    ax.set_xlabel("Publication/Modification Year", fontweight="bold")
    ax.set_ylabel("Number of Cited Pages", fontweight="bold")
    ax.set_title("When Was the Content Google AI Mode Cites Published?",
                 fontsize=13)
    plt.xticks(rotation=45, ha="right")
    ax.set_ylim(0, max(counts) * 1.15 if counts else 10)
    fig.tight_layout()
    save_fig(fig, "freshness_year_distribution.png")


# ─────────────────────────── Main ──────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="Limit URLs to process (0=all)")
    ap.add_argument("--workers", type=int, default=MAX_WORKERS, help="Parallel workers")
    args = ap.parse_args()

    print("=" * 60)
    print("FRESHNESS ANALYSIS — DATE EXTRACTION FROM SOURCE PAGES")
    print("=" * 60)

    # Load URLs
    print("\nLoading URLs…")
    urls = load_urls()

    if args.limit > 0:
        urls = urls[:args.limit]
        print(f"  (limited to {args.limit} URLs)")

    # Check for existing results to resume
    out_csv = ANALYSIS_DIR / "freshness_dates.csv"
    existing = set()
    if out_csv.exists():
        prev = pd.read_csv(out_csv)
        existing = set(prev["url"].dropna().values)
        remaining = [u for u in urls if u not in existing]
        print(f"  {len(existing):,} already processed, {len(remaining):,} remaining")
        urls = remaining
        if len(urls) == 0:
            print("\n  All URLs already processed! Regenerating stats and charts…")
            df = prev
        else:
            df = None  # will be set after extraction
    else:
        df = None

    if df is None and len(urls) > 0:
        # Run extraction
        print(f"\nFetching {len(urls):,} URLs with {args.workers} workers…")
        new_df = run_extraction(urls, max_workers=args.workers)

        # Merge with existing if resuming
        if existing:
            prev = pd.read_csv(out_csv)
            df = pd.concat([prev, new_df], ignore_index=True)
        else:
            df = new_df

        # Save
        df.to_csv(out_csv, index=False)
        print(f"\n  ✓ Saved {out_csv} ({len(df):,} rows)")

    # Load source pages for positional join
    sp = pd.read_csv(PARSED_DIR / "source_pages.csv", low_memory=False)

    # Compute stats
    print("\nComputing freshness statistics…")
    stats = compute_freshness_stats(df)

    out_json = ANALYSIS_DIR / "freshness_stats.json"
    with open(out_json, "w") as f:
        json.dump(stats, f, indent=2)
    print(f"  ✓ Saved {out_json}")

    # Print summary
    print("\n" + "─" * 60)
    print("FRESHNESS SUMMARY")
    print("─" * 60)
    print(f"  Total URLs:             {stats['total_urls']:,}")
    print(f"  URLs with published:    {stats['urls_with_published']:,}")
    print(f"  URLs with modified:     {stats['urls_with_modified']:,}")
    print(f"  URLs with HTTP L-M:     {stats['urls_with_last_modified_header']:,}")
    print(f"  URLs with ANY date:     {stats['urls_with_any_date']:,} "
          f"({stats['urls_with_any_date']/stats['total_urls']*100:.1f}%)")
    print(f"  URLs with errors:       {stats['urls_with_errors']:,}")

    if "age_stats" in stats:
        a = stats["age_stats"]
        print(f"\n  Content Age (n={a['n']:,}):")
        print(f"    Mean: {a['mean_days']:.0f} days ({a['mean_days']/365:.1f} years)")
        print(f"    Median: {a['median_days']:.0f} days ({a['median_days']/365:.1f} years)")
        print(f"    IQR: [{a['p25_days']:.0f}, {a['p75_days']:.0f}] days")
        print(f"    Range: [{a['min_days']}, {a['max_days']}] days")

    if "age_distribution" in stats:
        print("\n  Age Distribution:")
        for bucket, count in sorted(stats["age_distribution"].items()):
            pct = count / stats.get("age_stats", {}).get("n", 1) * 100
            print(f"    {bucket}: {count:,} ({pct:.1f}%)")

    if "year_distribution" in stats:
        print("\n  Year Distribution:")
        for year, count in sorted(stats["year_distribution"].items()):
            print(f"    {year}: {count:,}")

    # Generate charts
    print("\nGenerating charts…")
    chart_age_distribution(df)
    chart_freshness_by_position(df, sp)
    chart_year_distribution(stats)

    any_date_count = stats['urls_with_any_date']
    total = stats['total_urls']
    print(f"\n✅ Freshness analysis complete. Dates extracted for {any_date_count:,}/{total:,} URLs "
          f"({any_date_count/total*100:.1f}%)")


if __name__ == "__main__":
    main()
