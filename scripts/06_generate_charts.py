"""
06_generate_charts.py
======================
Generate publication-quality charts for the article and report.

Charts produced:
  1. positional_distribution.png  – bar chart of citation position deciles
  2. sentence_length_dist.png     – histogram of cited sentence word counts
  3. domain_frequency.png         – horizontal bar chart of top 20 domains
  4. platform_overlap_venn.png    – Venn-style summary (simple 2-circle)
  5. category_fragment_coverage.png – stacked bar by query category
  6. citations_per_query_dist.png – distribution of citations per query

Usage:
    python scripts/06_generate_charts.py
"""

import os
import sys as _sys
try:
    _sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    _sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import seaborn as sns
from dotenv import load_dotenv

load_dotenv()

ANALYSIS_DIR = Path(os.environ.get("ANALYSIS_DATA_DIR", "data/analysis"))
PARSED_DIR = Path(os.environ.get("PARSED_DATA_DIR", "data/parsed"))
CHARTS_DIR = Path("reports")
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Style ───────────────────────────────────────────────────────────────────
sns.set_theme(style="whitegrid", palette="muted", font_scale=1.2)
GOOGLE_BLUE = "#4285F4"
GOOGLE_RED  = "#EA4335"
GOOGLE_YELLOW = "#FBBC05"
GOOGLE_GREEN  = "#34A853"
PALETTE = [GOOGLE_BLUE, GOOGLE_RED, GOOGLE_GREEN, GOOGLE_YELLOW]

DPI = 150
FIG_W, FIG_H = 10, 6


def save_fig(fig, name: str):
    path = CHARTS_DIR / name
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ {path}")


# ── 1. Positional Distribution ──────────────────────────────────────────────

def chart_positional_distribution():
    fp = ANALYSIS_DIR / "positional_distribution.csv"
    if not fp.exists():
        print("  (skip) positional_distribution.csv not found")
        return

    df = pd.read_csv(fp)
    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    bars = ax.bar(df["position_decile"], df["pct"], color=GOOGLE_BLUE, edgecolor="white", linewidth=0.5)
    ax.set_xlabel("Position in Document (decile)", fontweight="bold")
    ax.set_ylabel("% of Citations", fontweight="bold")
    ax.set_title("Where in a Page Are Cited Sentences Found?\n(0-10% = top of page, 90-100% = bottom)", fontsize=13)
    ax.bar_label(bars, fmt="%.1f%%", padding=3, fontsize=9)
    plt.xticks(rotation=35, ha="right")
    ax.set_ylim(0, df["pct"].max() * 1.2)
    fig.tight_layout()
    save_fig(fig, "positional_distribution.png")


# ── 2. Sentence Length Distribution ─────────────────────────────────────────

def chart_sentence_length():
    fp = PARSED_DIR / "citations.csv"
    if not fp.exists():
        print("  (skip) citations.csv not found")
        return

    df = pd.read_csv(fp)
    lengths = df[df["cited_sentence_word_count"] > 0]["cited_sentence_word_count"]
    if len(lengths) < 5:
        print("  (skip) insufficient sentence length data")
        return

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    ax.hist(lengths.clip(upper=50), bins=30, color=GOOGLE_BLUE, edgecolor="white", linewidth=0.5)
    ax.axvline(lengths.median(), color=GOOGLE_RED, linestyle="--", linewidth=2, label=f"Median: {lengths.median():.0f} words")
    ax.axvline(lengths.mean(), color=GOOGLE_YELLOW, linestyle="--", linewidth=2, label=f"Mean: {lengths.mean():.1f} words")
    ax.set_xlabel("Cited Sentence Length (words)", fontweight="bold")
    ax.set_ylabel("Number of Citations", fontweight="bold")
    ax.set_title("Google AI Mode: Distribution of Cited Sentence Length\n(from #:~:text= URL fragments)", fontsize=13)
    ax.legend(framealpha=0.9)
    fig.tight_layout()
    save_fig(fig, "sentence_length_dist.png")


# ── 3. Domain Frequency ──────────────────────────────────────────────────────

def chart_domain_frequency():
    fp = ANALYSIS_DIR / "domain_frequency.csv"
    if not fp.exists():
        print("  (skip) domain_frequency.csv not found")
        return

    df = pd.read_csv(fp).head(20)
    fig, ax = plt.subplots(figsize=(FIG_W, max(FIG_H, len(df) * 0.4)))
    colors = [GOOGLE_BLUE if p == 2 else GOOGLE_GREEN if p == 1 else "#BDBDBD"
              for p in df.get("platform_count", [0]*len(df))]
    bars = ax.barh(df["domain"], df["citation_count"], color=colors, edgecolor="white")
    ax.set_xlabel("Total Citations", fontweight="bold")
    ax.set_title("Top 20 Most-Cited Domains\n(colour = platforms citing them)", fontsize=13)
    ax.invert_yaxis()
    ax.bar_label(bars, padding=4, fontsize=9)

    legend_elements = [
        mpatches.Patch(facecolor=GOOGLE_BLUE, label="Both platforms"),
        mpatches.Patch(facecolor=GOOGLE_GREEN, label="One platform"),
        mpatches.Patch(facecolor="#BDBDBD", label="Data unavailable"),
    ]
    ax.legend(handles=legend_elements, loc="lower right", framealpha=0.9)
    fig.tight_layout()
    save_fig(fig, "domain_frequency.png")


# ── 4. Platform Overlap Summary ──────────────────────────────────────────────

def chart_platform_overlap():
    fp = ANALYSIS_DIR / "platform_overlap.csv"
    if not fp.exists():
        print("  (skip) platform_overlap.csv not found")
        return

    df = pd.read_csv(fp).iloc[0]
    ai_only = df["ai_mode_unique_domains"] - df["overlap_domains"]
    gem_only = df["gemini_unique_domains"] - df["overlap_domains"]
    shared = df["overlap_domains"]

    fig, ax = plt.subplots(figsize=(8, 5))
    categories = ["AI Mode Only", "Shared Domains", "Gemini Only"]
    values = [ai_only, shared, gem_only]
    bar_colors = [GOOGLE_BLUE, GOOGLE_GREEN, GOOGLE_RED]
    bars = ax.bar(categories, values, color=bar_colors, edgecolor="white", linewidth=0.5, width=0.5)
    ax.bar_label(bars, padding=4)
    ax.set_ylabel("Unique Domains", fontweight="bold")
    ax.set_title(
        f"Domain Overlap: Google AI Mode vs Gemini\n"
        f"Jaccard Similarity = {df['jaccard_similarity']:.2%}",
        fontsize=13
    )
    fig.tight_layout()
    save_fig(fig, "platform_overlap_venn.png")


# ── 5. Category Fragment Coverage ────────────────────────────────────────────

def chart_category_coverage():
    fp = ANALYSIS_DIR / "category_breakdown.csv"
    if not fp.exists():
        print("  (skip) category_breakdown.csv not found")
        return

    df = pd.read_csv(fp).sort_values("fragment_coverage", ascending=True)
    fig, ax = plt.subplots(figsize=(FIG_W, max(FIG_H, len(df) * 0.45)))
    bars = ax.barh(df["category"], df["fragment_coverage"],
                   color=GOOGLE_BLUE, edgecolor="white")
    ax.set_xlabel("#:~:text= Fragment Coverage (%)", fontweight="bold")
    ax.set_title("Text Fragment URL Coverage by Query Category", fontsize=13)
    ax.axvline(df["fragment_coverage"].mean(), color=GOOGLE_RED, linestyle="--",
               linewidth=1.5, label=f"Mean: {df['fragment_coverage'].mean():.1f}%")
    ax.bar_label(bars, fmt="%.1f%%", padding=3, fontsize=9)
    ax.legend(framealpha=0.9)
    ax.set_xlim(0, 110)
    fig.tight_layout()
    save_fig(fig, "category_fragment_coverage.png")


# ── 6. Citations Per Query Distribution ──────────────────────────────────────

def chart_citations_per_query():
    fp = PARSED_DIR / "citations.csv"
    if not fp.exists():
        print("  (skip) citations.csv not found")
        return

    df = pd.read_csv(fp)
    per_query = df.groupby(["query", "platform"]).size().reset_index(name="n_citations")

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    for i, (platform, grp) in enumerate(per_query.groupby("platform")):
        ax.hist(grp["n_citations"], bins=15, alpha=0.7, color=PALETTE[i % len(PALETTE)], label=platform)
    ax.set_xlabel("Citations Per Query", fontweight="bold")
    ax.set_ylabel("Number of Queries", fontweight="bold")
    ax.set_title("Distribution of Citation Count Per Query\n(by platform)", fontsize=13)
    ax.legend(framealpha=0.9)
    fig.tight_layout()
    save_fig(fig, "citations_per_query_dist.png")


# ─────────────────────────── Main ──────────────────────────────────────────

def main():
    print("Generating charts…\n")
    chart_positional_distribution()
    chart_sentence_length()
    chart_domain_frequency()
    chart_platform_overlap()
    chart_category_coverage()
    chart_citations_per_query()
    print(f"\n✅ All charts saved to {CHARTS_DIR}/")


if __name__ == "__main__":
    main()
