"""QA verification - re-derive every key article stat from raw CSVs/JSONs."""
import json
import pandas as pd
from pathlib import Path

ROOT = Path(r"D:\grounding-citation-analysis")
A = ROOT / "data" / "analysis"
P = ROOT / "data" / "parsed"

print("=" * 70)
print("QA: Re-deriving every stat used in article from source files")
print("=" * 70)

# 1. Citations totals
cites = pd.read_csv(P / "citations.csv", low_memory=False)
print(f"\n[1] citations.csv rows: {len(cites):,}  (article claims 153,425)")
assert len(cites) == 153425

# 2. Per-platform totals
print("\n[2] Per-platform citation totals:")
print(cites.groupby("platform").size().sort_values(ascending=False))

# 3. Per-platform queries with citations
print("\n[3] Per-platform queries with >=1 citation:")
print(cites.groupby("platform")["query"].nunique().sort_values(ascending=False))

# 4. Fragment coverage per platform
print("\n[4] Per-platform text-fragment coverage (%):")
fc = cites.groupby("platform")["has_text_fragment"].mean() * 100
print(fc.round(2))

# 5. Total unique queries with citations
print(f"\n[5] Total unique queries appearing in citations: {cites['query'].nunique()}")

# 6. Top domains
print("\n[6] Top 15 domains by citation count:")
print(cites["domain"].value_counts().head(15))

# 7. Summary stats
ss = json.loads((A / "summary_stats.json").read_text())
print("\n[7] summary_stats.json keys:")
print(list(ss.keys()))
print(f"\nposition mean: {ss.get('position_mean')}")
print(f"position t-stat: {ss.get('position_t_stat')}")
print(f"position p-value: {ss.get('position_p_value')}")
print(f"position n: {ss.get('position_n')}")
print(f"sentence words mean: {ss.get('sentence_words_mean')}")
print(f"sentence words median: {ss.get('sentence_words_median')}")
print(f"sentence words max: {ss.get('sentence_words_max')}")
print(f"sentence words n: {ss.get('sentence_words_n')}")

# 8. SERP join
print("\n[8] Citation vs SERP rank file:")
csr = pd.read_csv(A / "citation_vs_serp_rank.csv")
print(csr.head(20))

# 9. Per-platform SERP alignment
print("\n[9] Per-platform: % cited URL in organic top-10")
serp = pd.read_csv(P / "serp.csv", low_memory=False)
top10 = serp[serp["rank_absolute"] <= 10]
url_set = set(top10["url"].dropna())
domain_set = set(top10["domain"].dropna())
# build query-scoped url and domain sets
top10_by_q = top10.groupby("query")["url"].apply(lambda s: set(s.dropna())).to_dict()
top10_dom_by_q = top10.groupby("query")["domain"].apply(lambda s: set(s.dropna())).to_dict()

def url_in_top10(row):
    s = top10_by_q.get(row["query"])
    return bool(s and row["citation_url_clean"] in s)

def dom_in_top10(row):
    s = top10_dom_by_q.get(row["query"])
    return bool(s and row["domain"] in s)

cites["url_in_top10"] = cites.apply(url_in_top10, axis=1)
cites["dom_in_top10"] = cites.apply(dom_in_top10, axis=1)
print("URL in top10 by platform:")
print((cites.groupby("platform")["url_in_top10"].mean() * 100).round(2))
print("Domain in top10 by platform:")
print((cites.groupby("platform")["dom_in_top10"].mean() * 100).round(2))
print(f"Overall URL in top10: {cites['url_in_top10'].mean()*100:.2f}%")
print(f"Overall Domain in top10: {cites['dom_in_top10'].mean()*100:.2f}%")

# 10. Avg answer words per platform
print("\n[10] Avg answer word count per platform:")
ans = pd.read_csv(P / "answers.csv")
print(ans.groupby("platform")["answer_word_count"].mean().round(2).sort_values(ascending=False))

# 11. Readability check
print("\n[11] readability_stats.json:")
rs = json.loads((A / "readability_stats.json").read_text())
print(json.dumps(rs, indent=2)[:1500])

# 12. Freshness check
print("\n[12] freshness_stats.json:")
fs = json.loads((A / "freshness_stats.json").read_text())
print(json.dumps(fs, indent=2)[:1500])

# 13. Platform overlap
print("\n[13] platform_overlap.csv:")
po = pd.read_csv(A / "platform_overlap.csv")
print(po)

print("\n" + "=" * 70)
print("QA COMPLETE")
print("=" * 70)
