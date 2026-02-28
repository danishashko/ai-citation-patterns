"""
05_analyze_patterns.py
=======================
Statistical analysis of the citation dataset.

Hypotheses tested:
  H1: Cited sentences are more likely to appear in the first 30% of a document
      (positional bias toward document beginning)
  H2: Cited sentences are shorter than non-cited reference text
      (preference for concise, declarative factoids)
  H3: Pages with structured content (lists/tables) are cited more often
  H4: AI Mode and Gemini cite overlapping but distinct page sets
      (platform divergence analysis)
  H5: Citation sentence length varies by query category
  H6: Domains cited repeatedly across queries have higher domain authority signals

Outputs:
  data/analysis/summary_stats.json
  data/analysis/positional_distribution.csv
  data/analysis/sentence_length_stats.csv
  data/analysis/domain_frequency.csv
  data/analysis/platform_overlap.csv
  data/analysis/category_breakdown.csv

Usage:
    python scripts/05_analyze_patterns.py
"""

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from dotenv import load_dotenv

load_dotenv()

PARSED_DIR = Path(os.environ.get("PARSED_DATA_DIR", "data/parsed"))
ANALYSIS_DIR = Path(os.environ.get("ANALYSIS_DATA_DIR", "data/analysis"))
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────── Loaders ───────────────────────────────────────

def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None, pd.DataFrame | None]:
    cite_path  = PARSED_DIR / "citations.csv"
    ans_path   = PARSED_DIR / "answers.csv"
    pages_path = PARSED_DIR / "source_pages.csv"
    serp_path  = PARSED_DIR / "serp.csv"

    if not cite_path.exists():
        raise FileNotFoundError(f"Run 03_parse_text_fragments.py first: {cite_path}")

    cite_df  = pd.read_csv(cite_path)
    ans_df   = pd.read_csv(ans_path)   if ans_path.exists()   else pd.DataFrame()
    pages_df = pd.read_csv(pages_path) if pages_path.exists() else None
    serp_df  = pd.read_csv(serp_path)  if serp_path.exists()  else None

    # Join query category from queries.csv if available
    query_meta = Path("queries/queries.csv")
    if query_meta.exists():
        qdf = pd.read_csv(query_meta)[["query", "category", "intent"]]
        cite_df = cite_df.merge(qdf, on="query", how="left")
        if not ans_df.empty:
            ans_df = ans_df.merge(qdf, on="query", how="left")

    return cite_df, ans_df, pages_df, serp_df


# ─────────────────────────── Analysis Functions ────────────────────────────

def summary_stats(cite_df: pd.DataFrame, ans_df: pd.DataFrame) -> dict:
    summary = {
        "total_queries": int(ans_df["query"].nunique()) if not ans_df.empty else int(cite_df["query"].nunique()),
        "total_citations": len(cite_df),
        "total_unique_domains": int(cite_df["domain"].nunique()),
        "total_unique_urls": int(cite_df["citation_url_clean"].nunique()),
        "fragment_coverage_pct": round(cite_df["has_text_fragment"].mean() * 100, 2),
        "avg_citations_per_query": round(cite_df.groupby("query").size().mean(), 2),
        "median_citations_per_query": round(cite_df.groupby("query").size().median(), 2),
        "avg_cited_sentence_words": round(
            cite_df[cite_df["cited_sentence_word_count"] > 0]["cited_sentence_word_count"].mean(), 2
        ),
        "platforms": sorted(cite_df["platform"].unique().tolist()),
    }
    if not ans_df.empty:
        summary["avg_answer_word_count"] = round(ans_df["answer_word_count"].mean(), 2)
    return summary


def positional_analysis(pages_df: pd.DataFrame) -> pd.DataFrame:
    """Distribution of relative_position (0=top, 1=bottom of document)."""
    found_df = pages_df[pages_df["found"] == True].copy()
    if found_df.empty:
        return pd.DataFrame()

    # Bin into deciles
    found_df["position_decile"] = pd.cut(
        found_df["relative_position"], bins=10,
        labels=[f"{i*10}-{i*10+10}%" for i in range(10)]
    )
    dist = (
        found_df.groupby("position_decile", observed=True)
        .size()
        .reset_index(name="count")
    )
    dist["pct"] = (dist["count"] / dist["count"].sum() * 100).round(2)
    return dist


def test_positional_bias(pages_df: pd.DataFrame) -> dict:
    """H1: Are cited sentences biased toward the top of documents?"""
    found = pages_df[pages_df["found"] == True]["relative_position"].dropna()
    if len(found) < 10:
        return {"test": "H1_positional_bias", "result": "insufficient_data"}

    # One-sample t-test: mean position < 0.5?
    t_stat, p_value = stats.ttest_1samp(found, popmean=0.5, alternative="less")
    mean_pos = found.mean()

    return {
        "test": "H1_positional_bias",
        "n": len(found),
        "mean_position": round(mean_pos, 4),
        "t_statistic": round(t_stat, 4),
        "p_value": round(p_value, 6),
        "significant": p_value < 0.05,
        "interpretation": (
            f"Cited sentences appear on average at {mean_pos:.0%} through the document. "
            f"{'Significant top bias detected.' if p_value < 0.05 else 'No significant positional bias.'}"
        ),
    }


def sentence_length_analysis(cite_df: pd.DataFrame) -> dict:
    lengths = cite_df[cite_df["cited_sentence_word_count"] > 0]["cited_sentence_word_count"]
    if len(lengths) < 5:
        return {}

    return {
        "n": len(lengths),
        "mean": round(lengths.mean(), 2),
        "median": float(lengths.median()),
        "std": round(lengths.std(), 2),
        "min": int(lengths.min()),
        "max": int(lengths.max()),
        "p25": float(lengths.quantile(0.25)),
        "p75": float(lengths.quantile(0.75)),
        "distribution_by_bucket": {
            "1-5 words": int((lengths <= 5).sum()),
            "6-10 words": int(((lengths > 5) & (lengths <= 10)).sum()),
            "11-20 words": int(((lengths > 10) & (lengths <= 20)).sum()),
            "21-30 words": int(((lengths > 20) & (lengths <= 30)).sum()),
            "31+ words": int((lengths > 30).sum()),
        },
    }


def platform_overlap(cite_df: pd.DataFrame) -> dict:
    """H4: Overlap between AI Mode and Gemini cited domains."""
    if "platform" not in cite_df.columns:
        return {}

    ai_domains = set(cite_df[cite_df["platform"] == "ai_mode"]["domain"].dropna())
    gem_domains = set(cite_df[cite_df["platform"] == "gemini"]["domain"].dropna())

    if not ai_domains or not gem_domains:
        return {"note": "Only one platform present in data."}

    overlap = ai_domains & gem_domains
    jaccard = len(overlap) / len(ai_domains | gem_domains)

    return {
        "ai_mode_unique_domains": len(ai_domains),
        "gemini_unique_domains": len(gem_domains),
        "overlap_domains": len(overlap),
        "jaccard_similarity": round(jaccard, 4),
        "top_shared_domains": sorted(overlap)[:20],
    }


def domain_frequency(cite_df: pd.DataFrame, top_n: int = 50) -> pd.DataFrame:
    freq = (
        cite_df.groupby("domain")
        .agg(
            citation_count=("query", "count"),
            query_count=("query", "nunique"),
            platform_count=("platform", "nunique"),
        )
        .reset_index()
        .sort_values("citation_count", ascending=False)
        .head(top_n)
    )
    return freq


def serp_rank_analysis(cite_df: pd.DataFrame, serp_df: pd.DataFrame) -> dict:
    """
    H7: Do AI platforms preferentially cite pages that rank highly in organic Google results?

    Merges citations.csv with serp.csv on (query, url) and (query, domain).
    Returns:
      - Distribution of organic_rank for cited URLs (URL-level match)
      - Distribution of organic_rank for cited domains (domain-level match)
      - % of citations where the cited URL appears in top-10 organic results
      - % of citations where the cited domain appears in top-10 organic results
      - Mean organic rank of cited pages (lower = higher ranking)
      - Per-platform breakdown
    """
    if serp_df is None or serp_df.empty:
        return {"note": "serp.csv not found — run 02b_collect_serp.py first."}
    if cite_df.empty:
        return {"note": "No citation data."}

    # ── URL-level join ──────────────────────────────────────────────────────
    cite_work = cite_df[["query", "citation_url_clean", "domain", "platform"]].copy()
    cite_work = cite_work.rename(columns={"citation_url_clean": "cite_url"})

    serp_work = serp_df[["query", "url", "domain", "organic_rank"]].copy()
    serp_work = serp_work.rename(columns={"domain": "serp_domain"})

    url_merged = cite_work.merge(
        serp_work[["query", "url", "organic_rank"]].rename(
            columns={"url": "cite_url", "organic_rank": "organic_rank_url"}
        ),
        on=["query", "cite_url"],
        how="left",
    )

    # ── Domain-level join (broader signal) ─────────────────────────────────
    serp_domain_best = (
        serp_df.groupby(["query", "domain"])["organic_rank"]
        .min()
        .reset_index()
        .rename(columns={"organic_rank": "organic_rank_domain"})
    )
    full_merged = url_merged.merge(
        serp_domain_best,
        on=["query", "domain"],
        how="left",
    )

    n_total = len(full_merged)
    url_found   = full_merged["organic_rank_url"].notna()
    domain_found = full_merged["organic_rank_domain"].notna()

    result = {
        "n_citations": n_total,
        "n_queries_with_serp": int(serp_df["query"].nunique()),
        # URL-level
        "url_in_top10_count": int(url_found.sum()),
        "url_in_top10_pct": round(url_found.mean() * 100, 2),
        "mean_organic_rank_url": round(full_merged.loc[url_found, "organic_rank_url"].mean(), 2) if url_found.any() else None,
        "median_organic_rank_url": float(full_merged.loc[url_found, "organic_rank_url"].median()) if url_found.any() else None,
        # Domain-level
        "domain_in_top10_count": int(domain_found.sum()),
        "domain_in_top10_pct": round(domain_found.mean() * 100, 2),
        "mean_organic_rank_domain": round(full_merged.loc[domain_found, "organic_rank_domain"].mean(), 2) if domain_found.any() else None,
        # Rank distribution breakdown (URL matches only)
        "rank_distribution": {},
    }

    for pos in range(1, 11):
        count = int((full_merged["organic_rank_url"] == pos).sum())
        result["rank_distribution"][f"rank_{pos}"] = count

    # ── Per-platform breakdown ──────────────────────────────────────────────
    if "platform" in full_merged.columns:
        by_platform = []
        for platform, grp in full_merged.groupby("platform"):
            uf = grp["organic_rank_url"].notna()
            df_ = grp["organic_rank_domain"].notna()
            by_platform.append({
                "platform": platform,
                "n_citations": len(grp),
                "url_in_top10_pct": round(uf.mean() * 100, 2),
                "domain_in_top10_pct": round(df_.mean() * 100, 2),
                "mean_organic_rank_url": round(grp.loc[uf, "organic_rank_url"].mean(), 2) if uf.any() else None,
            })
        result["by_platform"] = by_platform

    # Save the merged table for charts
    full_merged_out = full_merged.drop(columns=[col for col in ["_merge"] if col in full_merged.columns])
    full_merged_out.to_csv(ANALYSIS_DIR / "citation_vs_serp_rank.csv", index=False)

    return result


def category_breakdown(cite_df: pd.DataFrame) -> pd.DataFrame:
    if "category" not in cite_df.columns:
        return pd.DataFrame()
    breakdown = (
        cite_df.groupby("category")
        .agg(
            total_citations=("query", "count"),
            unique_queries=("query", "nunique"),
            unique_domains=("domain", "nunique"),
            avg_sentence_words=("cited_sentence_word_count", "mean"),
            fragment_coverage=("has_text_fragment", "mean"),
        )
        .reset_index()
        .sort_values("total_citations", ascending=False)
    )
    breakdown["avg_sentence_words"] = breakdown["avg_sentence_words"].round(2)
    breakdown["fragment_coverage"] = (breakdown["fragment_coverage"] * 100).round(2)
    return breakdown


# ─────────────────────────── Main ──────────────────────────────────────────

def main():
    print("Loading data…")
    cite_df, ans_df, pages_df, serp_df = load_data()
    print(f"  Citations: {len(cite_df)}, Answers: {len(ans_df)}")
    if serp_df is not None:
        print(f"  SERP rows: {len(serp_df)} ({serp_df['query'].nunique()} queries)")

    report = {}

    # Summary stats
    report["summary"] = summary_stats(cite_df, ans_df)
    print(f"\n── Summary ──")
    for k, v in report["summary"].items():
        print(f"  {k}: {v}")

    # Positional analysis (requires source_pages.csv)
    if pages_df is not None and "relative_position" in pages_df.columns:
        pos_dist = positional_analysis(pages_df)
        pos_dist.to_csv(ANALYSIS_DIR / "positional_distribution.csv", index=False)
        bias_result = test_positional_bias(pages_df)
        report["h1_positional_bias"] = bias_result
        print(f"\n── H1 Positional Bias ──")
        print(f"  {bias_result.get('interpretation', 'N/A')}")

    # Sentence length
    sent_len = sentence_length_analysis(cite_df)
    report["sentence_length"] = sent_len
    if sent_len:
        sent_df = pd.DataFrame([{"bucket": k, "count": v} for k, v in sent_len["distribution_by_bucket"].items()])
        sent_df.to_csv(ANALYSIS_DIR / "sentence_length_stats.csv", index=False)
        print(f"\n── Sentence Length ──")
        print(f"  Mean: {sent_len['mean']} words, Median: {sent_len['median']} words")

    # Platform overlap
    overlap = platform_overlap(cite_df)
    report["platform_overlap"] = overlap
    if overlap and "jaccard_similarity" in overlap:
        pd.DataFrame([overlap]).to_csv(ANALYSIS_DIR / "platform_overlap.csv", index=False)
        print(f"\n── Platform Overlap ──")
        print(f"  Jaccard similarity: {overlap['jaccard_similarity']}")

    # Domain frequency
    dom_freq = domain_frequency(cite_df)
    dom_freq.to_csv(ANALYSIS_DIR / "domain_frequency.csv", index=False)
    print(f"\n── Top Domains (by citation count) ──")
    for _, row in dom_freq.head(10).iterrows():
        print(f"  {row['domain']}: {row['citation_count']} citations across {row['query_count']} queries")

    # Category breakdown
    cat_df = category_breakdown(cite_df)
    if not cat_df.empty:
        cat_df.to_csv(ANALYSIS_DIR / "category_breakdown.csv", index=False)

    # H7: Citation vs organic SERP rank
    serp_result = serp_rank_analysis(cite_df, serp_df)
    report["h7_citation_vs_organic_rank"] = serp_result
    print(f"\n── H7 Citation vs Organic Rank ──")
    if "url_in_top10_pct" in serp_result:
        print(f"  Cited URLs that also appear in organic top-10 : {serp_result['url_in_top10_pct']}%")
        print(f"  Cited domains in organic top-10              : {serp_result['domain_in_top10_pct']}%")
        print(f"  Mean organic rank of cited URLs              : {serp_result['mean_organic_rank_url']}")
    else:
        print(f"  {serp_result.get('note', 'No SERP data.')}")

    # Save full report
    report_path = ANALYSIS_DIR / "summary_stats.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\n✅ Full report → {report_path}")


if __name__ == "__main__":
    main()
