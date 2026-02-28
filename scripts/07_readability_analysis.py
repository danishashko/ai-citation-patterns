"""
07_readability_analysis.py
===========================
Readability analysis of cited sentences from AI Mode / Gemini text fragments.

Computes per-sentence readability metrics for all 11,672 decoded text fragments:
  - Flesch Reading Ease (higher = easier)
  - Flesch-Kincaid Grade Level
  - Gunning Fog Index
  - Coleman-Liau Index
  - Automated Readability Index (ARI)
  - Syllable density (syllables per word)

Outputs:
  data/analysis/readability_stats.json       — aggregate statistics
  data/analysis/readability_per_sentence.csv — per-sentence scores
  reports/readability_distribution.png       — histogram of Flesch Reading Ease
  reports/readability_vs_position.png        — readability vs document position
  reports/readability_vs_wordcount.png       — readability vs sentence length
  reports/readability_grade_breakdown.png    — grade level distribution

Usage:
    python scripts/07_readability_analysis.py
"""

import json
import os
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import textstat
from dotenv import load_dotenv

load_dotenv()
warnings.filterwarnings("ignore", category=RuntimeWarning)

PARSED_DIR = Path(os.environ.get("PARSED_DATA_DIR", "data/parsed"))
ANALYSIS_DIR = Path(os.environ.get("ANALYSIS_DATA_DIR", "data/analysis"))
CHARTS_DIR = Path("reports")
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

# Ensure English
textstat.set_lang("en")

# ── Style ───────────────────────────────────────────────────────────────────
sns.set_theme(style="whitegrid", palette="muted", font_scale=1.2)
GOOGLE_BLUE = "#4285F4"
GOOGLE_RED = "#EA4335"
GOOGLE_YELLOW = "#FBBC05"
GOOGLE_GREEN = "#34A853"
DPI = 150
FIG_W, FIG_H = 10, 6


def save_fig(fig, name: str):
    path = CHARTS_DIR / name
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ {path}")


# ─────────────────────────── Data Loading ──────────────────────────────────

def load_data():
    """Load citations with text fragments and optionally source pages."""
    cite_path = PARSED_DIR / "citations.csv"
    pages_path = PARSED_DIR / "source_pages.csv"

    print("Loading citations…")
    df = pd.read_csv(cite_path, low_memory=False)

    # Filter to rows with actual text fragments
    frag = df[df["has_text_fragment"] == True].copy()
    frag = frag[frag["cited_sentence"].notna() & (frag["cited_sentence"].str.strip() != "")]
    print(f"  {len(frag):,} sentences with text fragments")

    pages = None
    if pages_path.exists():
        pages = pd.read_csv(pages_path, low_memory=False)
        pages = pages[pages["found"] == True].copy()
        print(f"  {len(pages):,} source pages with validated positions")

    return frag, pages


# ─────────────────────────── Readability Computation ───────────────────────

def compute_readability(sentences: pd.Series) -> pd.DataFrame:
    """
    Compute readability metrics for a series of sentences.
    Returns a DataFrame with one row per sentence.
    """
    results = []
    total = len(sentences)

    for i, (idx, text) in enumerate(sentences.items()):
        if i % 2000 == 0:
            print(f"  Processing {i:,}/{total:,}…")

        text = str(text).strip()
        if not text or len(text) < 3:
            continue

        word_count = textstat.lexicon_count(text, removepunct=True)
        if word_count < 1:
            continue

        syllable_count = textstat.syllable_count(text)
        syllables_per_word = syllable_count / word_count if word_count > 0 else 0

        try:
            flesch_ease = textstat.flesch_reading_ease(text)
        except Exception:
            flesch_ease = np.nan

        try:
            flesch_grade = textstat.flesch_kincaid_grade(text)
        except Exception:
            flesch_grade = np.nan

        try:
            gunning = textstat.gunning_fog(text)
        except Exception:
            gunning = np.nan

        try:
            coleman = textstat.coleman_liau_index(text)
        except Exception:
            coleman = np.nan

        try:
            ari = textstat.automated_readability_index(text)
        except Exception:
            ari = np.nan

        try:
            dale_chall = textstat.dale_chall_readability_score(text)
        except Exception:
            dale_chall = np.nan

        results.append({
            "original_index": idx,
            "text": text,
            "word_count": word_count,
            "syllable_count": syllable_count,
            "syllables_per_word": round(syllables_per_word, 3),
            "flesch_reading_ease": round(flesch_ease, 2) if not np.isnan(flesch_ease) else np.nan,
            "flesch_kincaid_grade": round(flesch_grade, 2) if not np.isnan(flesch_grade) else np.nan,
            "gunning_fog": round(gunning, 2) if not np.isnan(gunning) else np.nan,
            "coleman_liau": round(coleman, 2) if not np.isnan(coleman) else np.nan,
            "ari": round(ari, 2) if not np.isnan(ari) else np.nan,
            "dale_chall": round(dale_chall, 2) if not np.isnan(dale_chall) else np.nan,
        })

    print(f"  Computed readability for {len(results):,} sentences")
    return pd.DataFrame(results)


# ─────────────────────────── Flesch Ease Buckets ───────────────────────────

def flesch_bucket(score):
    """Categorise Flesch Reading Ease score."""
    if pd.isna(score):
        return "Unknown"
    if score >= 90:
        return "Very Easy (90-100)"
    elif score >= 80:
        return "Easy (80-89)"
    elif score >= 70:
        return "Fairly Easy (70-79)"
    elif score >= 60:
        return "Standard (60-69)"
    elif score >= 50:
        return "Fairly Difficult (50-59)"
    elif score >= 30:
        return "Difficult (30-49)"
    else:
        return "Very Confusing (<30)"


def grade_bucket(grade):
    """Categorise grade level."""
    if pd.isna(grade):
        return "Unknown"
    if grade <= 4:
        return "Elementary (≤4)"
    elif grade <= 6:
        return "Middle School (5-6)"
    elif grade <= 8:
        return "Junior High (7-8)"
    elif grade <= 10:
        return "High School (9-10)"
    elif grade <= 12:
        return "Senior High (11-12)"
    else:
        return "College+ (13+)"


# ─────────────────────────── Statistics ────────────────────────────────────

def compute_stats(rdf: pd.DataFrame) -> dict:
    """Compute aggregate readability statistics."""
    metrics = ["flesch_reading_ease", "flesch_kincaid_grade", "gunning_fog",
               "coleman_liau", "ari", "dale_chall", "syllables_per_word"]

    stats_dict = {
        "n_sentences": len(rdf),
        "metrics": {},
    }

    for m in metrics:
        vals = rdf[m].dropna()
        if len(vals) == 0:
            continue
        stats_dict["metrics"][m] = {
            "n": int(len(vals)),
            "mean": round(float(vals.mean()), 2),
            "median": round(float(vals.median()), 2),
            "std": round(float(vals.std()), 2),
            "min": round(float(vals.min()), 2),
            "max": round(float(vals.max()), 2),
            "p25": round(float(vals.quantile(0.25)), 2),
            "p75": round(float(vals.quantile(0.75)), 2),
        }

    # Flesch ease distribution
    rdf["flesch_bucket"] = rdf["flesch_reading_ease"].apply(flesch_bucket)
    bucket_counts = rdf["flesch_bucket"].value_counts().to_dict()
    stats_dict["flesch_ease_distribution"] = bucket_counts

    # Grade level distribution
    rdf["grade_bucket"] = rdf["flesch_kincaid_grade"].apply(grade_bucket)
    grade_counts = rdf["grade_bucket"].value_counts().to_dict()
    stats_dict["grade_level_distribution"] = grade_counts

    return stats_dict


# ─────────────────────────── Charts ────────────────────────────────────────

def chart_flesch_distribution(rdf: pd.DataFrame):
    """Histogram of Flesch Reading Ease scores."""
    vals = rdf["flesch_reading_ease"].dropna()
    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    ax.hist(vals.clip(-50, 121), bins=40, color=GOOGLE_BLUE, edgecolor="white", linewidth=0.5)
    ax.axvline(vals.median(), color=GOOGLE_RED, linestyle="--", linewidth=2,
               label=f"Median: {vals.median():.1f}")
    ax.axvline(vals.mean(), color=GOOGLE_YELLOW, linestyle="--", linewidth=2,
               label=f"Mean: {vals.mean():.1f}")

    # Shade difficulty zones
    ax.axvspan(-50, 30, alpha=0.05, color="red", label="Very Confusing")
    ax.axvspan(70, 121, alpha=0.05, color="green", label="Easy+")

    ax.set_xlabel("Flesch Reading Ease Score", fontweight="bold")
    ax.set_ylabel("Number of Cited Sentences", fontweight="bold")
    ax.set_title("Readability of Google AI Mode Cited Sentences\n(Flesch Reading Ease — higher = easier to read)",
                 fontsize=13)
    ax.legend(framealpha=0.9, fontsize=10)
    fig.tight_layout()
    save_fig(fig, "readability_distribution.png")


def chart_readability_vs_position(rdf: pd.DataFrame, pages: pd.DataFrame):
    """Scatter: readability vs document position."""
    if pages is None or len(pages) == 0:
        print("  (skip) No positional data for readability vs position chart")
        return

    # Merge on original index or text match
    merged = pages[["relative_position", "cited_sentence"]].copy()
    merged = merged[merged["relative_position"].notna()]
    merged = merged.merge(
        rdf[["text", "flesch_reading_ease", "flesch_kincaid_grade"]],
        left_on="cited_sentence",
        right_on="text",
        how="inner"
    )

    if len(merged) < 10:
        print(f"  (skip) Only {len(merged)} matched rows for position chart")
        return

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    scatter = ax.scatter(
        merged["relative_position"] * 100,
        merged["flesch_reading_ease"],
        alpha=0.3, s=15, color=GOOGLE_BLUE, edgecolors="none"
    )

    # Add trend line
    z = np.polyfit(merged["relative_position"] * 100, merged["flesch_reading_ease"], 1)
    p = np.poly1d(z)
    x_line = np.linspace(0, 100, 100)
    ax.plot(x_line, p(x_line), color=GOOGLE_RED, linewidth=2, linestyle="--",
            label=f"Trend (slope: {z[0]:.2f})")

    ax.set_xlabel("Position in Document (%)", fontweight="bold")
    ax.set_ylabel("Flesch Reading Ease", fontweight="bold")
    ax.set_title("Readability vs Position in Source Document\n(Do easier sentences get cited from the top?)",
                 fontsize=13)
    ax.legend(framealpha=0.9)
    fig.tight_layout()
    save_fig(fig, "readability_vs_position.png")


def chart_readability_vs_wordcount(rdf: pd.DataFrame):
    """Box plot: readability by word count bucket."""
    rdf = rdf.copy()
    rdf["wc_bucket"] = pd.cut(
        rdf["word_count"],
        bins=[0, 5, 8, 10, 12, 15, 20],
        labels=["1-5", "6-8", "9-10", "11-12", "13-15", "16-20"]
    )

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    valid = rdf[rdf["wc_bucket"].notna() & rdf["flesch_reading_ease"].notna()]
    sns.boxplot(data=valid, x="wc_bucket", y="flesch_reading_ease",
                hue="wc_bucket", palette="Blues_d", ax=ax, showfliers=False,
                legend=False)

    ax.set_xlabel("Sentence Word Count", fontweight="bold")
    ax.set_ylabel("Flesch Reading Ease", fontweight="bold")
    ax.set_title("How Readability Changes With Sentence Length\n(Cited sentences only)",
                 fontsize=13)
    fig.tight_layout()
    save_fig(fig, "readability_vs_wordcount.png")


def chart_grade_breakdown(rdf: pd.DataFrame):
    """Bar chart of grade level distribution."""
    rdf = rdf.copy()
    rdf["grade_bucket"] = rdf["flesch_kincaid_grade"].apply(grade_bucket)
    order = ["Elementary (≤4)", "Middle School (5-6)", "Junior High (7-8)",
             "High School (9-10)", "Senior High (11-12)", "College+ (13+)"]
    counts = rdf["grade_bucket"].value_counts()
    counts = counts.reindex([o for o in order if o in counts.index])

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    colors = [GOOGLE_GREEN, GOOGLE_BLUE, GOOGLE_BLUE, GOOGLE_YELLOW, GOOGLE_RED, GOOGLE_RED]
    bars = ax.bar(counts.index, counts.values, color=colors[:len(counts)], edgecolor="white")
    ax.bar_label(bars, fmt="%d", padding=4, fontsize=10)

    ax.set_xlabel("Reading Grade Level (Flesch-Kincaid)", fontweight="bold")
    ax.set_ylabel("Number of Cited Sentences", fontweight="bold")
    ax.set_title("Grade Level Distribution of Google AI Mode Cited Sentences",
                 fontsize=13)
    plt.xticks(rotation=25, ha="right")
    ax.set_ylim(0, counts.max() * 1.15)
    fig.tight_layout()
    save_fig(fig, "readability_grade_breakdown.png")


# ─────────────────────────── Main ──────────────────────────────────────────

def main():
    print("=" * 60)
    print("READABILITY ANALYSIS OF CITED SENTENCES")
    print("=" * 60)

    # Load data
    frag_df, pages_df = load_data()

    # Compute readability scores
    print("\nComputing readability metrics…")
    rdf = compute_readability(frag_df["cited_sentence"])

    # Save per-sentence CSV
    out_csv = ANALYSIS_DIR / "readability_per_sentence.csv"
    rdf.to_csv(out_csv, index=False)
    print(f"\n  ✓ Saved {out_csv}")

    # Compute aggregate stats
    print("\nComputing aggregate statistics…")
    stats_dict = compute_stats(rdf)

    out_json = ANALYSIS_DIR / "readability_stats.json"
    with open(out_json, "w") as f:
        json.dump(stats_dict, f, indent=2)
    print(f"  ✓ Saved {out_json}")

    # Print summary
    print("\n" + "─" * 60)
    print("READABILITY SUMMARY")
    print("─" * 60)
    for metric, vals in stats_dict["metrics"].items():
        print(f"\n  {metric}:")
        print(f"    Mean: {vals['mean']}  |  Median: {vals['median']}  |  Std: {vals['std']}")
        print(f"    Range: [{vals['min']}, {vals['max']}]  |  IQR: [{vals['p25']}, {vals['p75']}]")

    print("\n  Flesch Ease Distribution:")
    for bucket, count in sorted(stats_dict["flesch_ease_distribution"].items()):
        pct = count / stats_dict["n_sentences"] * 100
        print(f"    {bucket}: {count:,} ({pct:.1f}%)")

    print("\n  Grade Level Distribution:")
    for bucket, count in sorted(stats_dict["grade_level_distribution"].items()):
        pct = count / stats_dict["n_sentences"] * 100
        print(f"    {bucket}: {count:,} ({pct:.1f}%)")

    # Generate charts
    print("\nGenerating charts…")
    chart_flesch_distribution(rdf)
    chart_readability_vs_position(rdf, pages_df)
    chart_readability_vs_wordcount(rdf)
    chart_grade_breakdown(rdf)

    print(f"\n✅ Readability analysis complete. {len(rdf):,} sentences analysed.")


if __name__ == "__main__":
    main()
