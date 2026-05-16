"""
Generate publication-quality charts for the May 2026 article (v2).

Library choice: Plotly + Kaleido. Reasoning: matplotlib looks like 2014 academia.
Plotly with hand-tuned editorial styling (FT/Economist palette, Inter font, white
background, single accent color per chart) renders genuinely publication-grade
PNGs at 2x scale via Kaleido. Output goes to reports/v2/.
"""

from pathlib import Path
import json
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

OUT = Path("reports/v2")
OUT.mkdir(parents=True, exist_ok=True)

# ------- Editorial theme -------
INK = "#1a1a1a"
SUB = "#5a5a5a"
GRID = "#e6e6e6"
ACCENT = "#d6443c"          # editorial red
ACCENT_2 = "#1f6feb"        # editorial blue
ACCENT_3 = "#2a8c3f"        # editorial green
NEUTRAL = "#9aa0a6"
BG = "#ffffff"

FONT = dict(family="Inter, Helvetica Neue, Arial, sans-serif", color=INK, size=14)

def base_layout(title, subtitle=None, height=520, width=1100, source="Source: grounding-citation-analysis, n=153,425 citations across 5,000 queries"):
    full_title = f"<b>{title}</b>"
    if subtitle:
        full_title += f"<br><span style='font-size:14px;color:{SUB};font-weight:400'>{subtitle}</span>"
    return dict(
        title=dict(text=full_title, x=0.02, xanchor="left", y=0.94, yanchor="top",
                   font=dict(family=FONT["family"], size=22, color=INK)),
        paper_bgcolor=BG, plot_bgcolor=BG,
        font=FONT,
        margin=dict(l=70, r=40, t=120, b=80),
        height=height, width=width,
        annotations=[dict(text=source, xref="paper", yref="paper",
                          x=0, y=-0.15, xanchor="left", showarrow=False,
                          font=dict(size=11, color=SUB))],
    )

def style_axes(fig, xtitle="", ytitle="", x_tickformat=None, y_tickformat=None, show_x_grid=False):
    fig.update_xaxes(title=dict(text=xtitle, font=dict(size=13, color=SUB)),
                     showgrid=show_x_grid, gridcolor=GRID, zeroline=False,
                     showline=True, linecolor=GRID, ticks="outside", tickcolor=GRID,
                     tickfont=dict(size=12, color=INK), tickformat=x_tickformat)
    fig.update_yaxes(title=dict(text=ytitle, font=dict(size=13, color=SUB)),
                     showgrid=True, gridcolor=GRID, zeroline=False,
                     showline=False, ticks="", tickfont=dict(size=12, color=INK),
                     tickformat=y_tickformat)
    return fig

def save(fig, name):
    path = OUT / f"{name}.png"
    fig.write_image(str(path), scale=2)
    print(f"  -> {path}")

# ------- Load data -------
ss = json.load(open("data/analysis/summary_stats.json"))
rs = json.load(open("data/analysis/readability_stats.json"))
fs = json.load(open("data/analysis/freshness_stats.json"))
pos = pd.read_csv("data/analysis/positional_distribution.csv")
dom = pd.read_csv("data/analysis/domain_frequency.csv")
slen = pd.read_csv("data/analysis/sentence_length_stats.csv")

# ============================================================
# Chart 1: The death of text fragments in AI Mode (slope chart)
# ============================================================
fig = go.Figure()
labels = ["AI Mode", "Gemini"]
v_prior = [70.9, 51.8]
v_2026 = [0.0, 84.13]
colors = [ACCENT, ACCENT_3]

for i, lab in enumerate(labels):
    fig.add_trace(go.Scatter(
        x=["March 2026", "May 2026"], y=[v_prior[i], v_2026[i]],
        mode="lines+markers+text",
        line=dict(color=colors[i], width=4),
        marker=dict(size=14, color=colors[i], line=dict(width=2, color="white")),
        text=[f"{v_prior[i]:.1f}%", f"{v_2026[i]:.1f}%"],
        textposition=["middle left", "middle right"],
        textfont=dict(size=14, color=colors[i], family=FONT["family"]),
        name=lab, showlegend=False,
        cliponaxis=False,
    ))
    fig.add_annotation(x="May 2026", y=v_2026[i], text=f"<b>{lab}</b>",
                       xanchor="left", xshift=70, showarrow=False,
                       font=dict(size=14, color=colors[i]))

fig.update_layout(**base_layout(
    "Google quietly killed text fragments in AI Mode",
    "Share of AI Mode and Gemini citation URLs that contain a #:~:text= fragment (March 2026 vs May 2026)",
    height=540, width=1100,
    source="Source: grounding-citation-analysis. March 2026 study n=42,971 citations (520 queries); May 2026 study n=153,425 (5,000 queries)."
))
fig = style_axes(fig, ytitle="% of citations with text fragment", y_tickformat=".0f")
fig.update_yaxes(range=[-5, 100], ticksuffix="%")
fig.update_xaxes(range=[-0.4, 1.6])
save(fig, "01_fragment_death")

# ============================================================
# Chart 2: Where citations land in source pages
# ============================================================
colors2 = [ACCENT_2 if "10-20" in d or "20-30" in d or "30-40" in d else NEUTRAL for d in pos["position_decile"]]
fig = go.Figure(go.Bar(
    x=pos["position_decile"], y=pos["pct"],
    marker=dict(color=colors2, line=dict(width=0)),
    text=[f"{v:.1f}%" for v in pos["pct"]],
    textposition="outside",
    textfont=dict(size=12, color=INK),
    hovertemplate="%{x}: %{y:.1f}%<extra></extra>",
))
fig.update_layout(**base_layout(
    "Three quarters of citations sit in the top half of the page",
    f"Position of cited sentence within source page, n={int(pos['count'].sum()):,} matched citations"
))
fig = style_axes(fig, xtitle="Position in document (decile, top -> bottom)",
                 ytitle="Share of citations")
fig.update_yaxes(ticksuffix="%", range=[0, 22])
fig.add_annotation(x="20-30%", y=21, text="<b>Peak: 19.3%</b>", showarrow=False,
                   font=dict(size=13, color=ACCENT_2))
save(fig, "02_position_bias")

# ============================================================
# Chart 3: The 18-word ceiling on cited sentences
# ============================================================
slen_buckets = ["1-5", "6-10", "11-20", "21-30", "31+"]
slen_vals = [682, 5133, 5531, 0, 0]
colors3 = [NEUTRAL, ACCENT_2, ACCENT_2, "#f0f0f0", "#f0f0f0"]
fig = go.Figure(go.Bar(
    x=slen_buckets, y=slen_vals,
    marker=dict(color=colors3),
    text=[f"{v:,}" for v in slen_vals],
    textposition="outside", textfont=dict(size=13, color=INK),
    hovertemplate="%{x} words: %{y:,}<extra></extra>",
))
fig.update_layout(**base_layout(
    "Nothing over 18 words gets cited",
    f"Word count of {int(sum(slen_vals)):,} cited sentences (mean {ss['summary']['avg_cited_sentence_words']}, median 10, max 18)"
))
fig = style_axes(fig, xtitle="Sentence length (words)", ytitle="Cited sentences")
fig.add_annotation(x="21-30", y=2500, text="<b>Hard ceiling at 18 words</b><br>0 citations beyond this point",
                   showarrow=True, arrowhead=2, ax=-70, ay=-30, arrowcolor=ACCENT,
                   font=dict(size=13, color=ACCENT), bgcolor="white")
save(fig, "03_sentence_length")

# ============================================================
# Chart 4: Top 15 domains
# ============================================================
top15 = dom.head(15).iloc[::-1]
colors4 = []
for d in top15["domain"]:
    if d in ("youtube.com", "reddit.com"): colors4.append(ACCENT)
    elif "wikipedia" in d or "ncbi" in d or "mayoclinic" in d or "clevelandclinic" in d: colors4.append(ACCENT_3)
    else: colors4.append(ACCENT_2)
fig = go.Figure(go.Bar(
    y=top15["domain"], x=top15["citation_count"],
    orientation="h",
    marker=dict(color=colors4),
    text=[f"{v:,}" for v in top15["citation_count"]],
    textposition="outside", textfont=dict(size=12, color=INK),
    hovertemplate="%{y}: %{x:,} citations<extra></extra>",
))
fig.update_layout(**base_layout(
    "YouTube and Reddit dominate AI citations",
    "Top 15 cited domains across 6 platforms. Red = social/UGC, green = medical/wiki, blue = editorial.",
    height=620,
))
fig = style_axes(fig, xtitle="Citations", ytitle="")
fig.update_xaxes(range=[0, 11500])
save(fig, "04_top_domains")

# ============================================================
# Chart 5: AI Mode vs Gemini overlap (manual venn-style)
# ============================================================
fig = go.Figure()
# circles via shapes
fig.add_shape(type="circle", x0=-0.85, y0=-0.55, x1=0.45, y1=0.75,
              fillcolor="rgba(214,68,60,0.45)", line=dict(color=ACCENT, width=2))
fig.add_shape(type="circle", x0=-0.05, y0=-0.55, x1=1.25, y1=0.75,
              fillcolor="rgba(31,111,235,0.45)", line=dict(color=ACCENT_2, width=2))
fig.add_annotation(x=-0.55, y=0.1, text="<b>AI Mode</b><br>29,795 unique<br>domains",
                   showarrow=False, font=dict(size=14, color="white"))
fig.add_annotation(x=0.95, y=0.1, text="<b>Gemini</b><br>5,143 unique<br>domains",
                   showarrow=False, font=dict(size=14, color="white"))
fig.add_annotation(x=0.20, y=0.1, text="<b>1,556</b><br>shared",
                   showarrow=False, font=dict(size=14, color=INK))
fig.add_annotation(x=0.20, y=-0.85, text="<b>Jaccard similarity = 0.0466</b> (4.66% overlap)",
                   showarrow=False, font=dict(size=14, color=INK))
fig.update_xaxes(range=[-1.4, 1.8], visible=False)
fig.update_yaxes(range=[-1.1, 1.0], visible=False, scaleanchor="x", scaleratio=1)
fig.update_layout(**base_layout(
    "Two Google AI products cite almost entirely different sources",
    "Overlap of unique domains cited by AI Mode and Gemini",
    height=560,
))
save(fig, "05_platform_overlap")

# ============================================================
# Chart 6: SERP alignment per platform (grouped bar)
# ============================================================
plats = ss["h7_citation_vs_organic_rank"]["by_platform"]
plats_sorted = sorted(plats, key=lambda p: -p["url_in_top10_pct"])
names = [p["platform"] for p in plats_sorted]
url_pct = [p["url_in_top10_pct"] for p in plats_sorted]
dom_pct = [p["domain_in_top10_pct"] for p in plats_sorted]

fig = go.Figure()
fig.add_trace(go.Bar(name="Cited URL in organic top-10", x=names, y=url_pct,
                    marker=dict(color=ACCENT_2),
                    text=[f"{v:.1f}%" for v in url_pct], textposition="outside",
                    textfont=dict(size=12, color=INK)))
fig.add_trace(go.Bar(name="Cited domain in organic top-10", x=names, y=dom_pct,
                    marker=dict(color=NEUTRAL),
                    text=[f"{v:.1f}%" for v in dom_pct], textposition="outside",
                    textfont=dict(size=12, color=INK)))
fig.update_layout(**base_layout(
    "AI citations reach far beyond Google's top 10",
    "Share of cited URLs/domains that also rank in the organic top-10 for the same query",
    height=560,
))
fig = style_axes(fig, xtitle="", ytitle="Share of citations")
fig.update_yaxes(ticksuffix="%", range=[0, 60])
fig.update_layout(barmode="group", legend=dict(orientation="h", x=0, y=1.05,
                                                font=dict(size=12, color=INK),
                                                bgcolor="rgba(0,0,0,0)"))
save(fig, "06_serp_alignment")

# ============================================================
# Chart 7: Readability bimodal split
# ============================================================
flesch = rs["flesch_ease_distribution"]
order = ["Very Confusing (<30)", "Difficult (30-49)", "Fairly Difficult (50-59)",
         "Standard (60-69)", "Fairly Easy (70-79)", "Easy (80-89)", "Very Easy (90-100)"]
labels7 = ["Very<br>Confusing<br>(<30)", "Difficult<br>(30-49)", "Fairly<br>Difficult<br>(50-59)",
           "Standard<br>(60-69)", "Fairly<br>Easy<br>(70-79)", "Easy<br>(80-89)", "Very Easy<br>(90-100)"]
vals = [flesch[k] for k in order]
total = sum(vals)
pct7 = [v / total * 100 for v in vals]

# Color: peaks accent, valley gray
peak_idx = [vals.index(max(vals[:3])), vals.index(max(vals[4:]), 4)]
colors7 = [ACCENT if i in peak_idx else (NEUTRAL if v / total < 0.07 else ACCENT_2) for i, v in enumerate(vals)]

fig = go.Figure(go.Bar(
    x=labels7, y=pct7, marker=dict(color=colors7),
    text=[f"{v:.1f}%" for v in pct7], textposition="outside",
    textfont=dict(size=12, color=INK),
    hovertemplate="%{x}: %{y:.1f}% (%{customdata:,} sentences)<extra></extra>",
    customdata=vals,
))
fig.update_layout(**base_layout(
    "Readability is bimodal: Google cites the simple and the dense, not the middle",
    f"Flesch Reading Ease distribution across {total:,} cited sentences",
    height=560,
))
fig = style_axes(fig, xtitle="Flesch Reading Ease", ytitle="Share of cited sentences")
fig.update_yaxes(ticksuffix="%", range=[0, 30])
fig.add_annotation(x="Fairly<br>Difficult<br>(50-59)", y=8, text="<b>Dead zone:</b><br>only 2.6%",
                   showarrow=True, arrowhead=2, ax=0, ay=-40, arrowcolor=NEUTRAL,
                   font=dict(size=12, color=NEUTRAL))
save(fig, "07_readability_bimodal")

# ============================================================
# Chart 8: Freshness by year
# ============================================================
yd = fs["year_distribution"]
years = sorted([int(y) for y in yd.keys()])
counts = [yd[str(y)] for y in years]
colors8 = [ACCENT if y >= 2025 else (ACCENT_2 if y >= 2020 else NEUTRAL) for y in years]
fig = go.Figure(go.Bar(
    x=years, y=counts, marker=dict(color=colors8),
    hovertemplate="%{x}: %{y:,} pages<extra></extra>",
))
fig.update_layout(**base_layout(
    "61.9% of dated cited pages were published in 2025 or 2026",
    f"Publication year of cited source pages, n={sum(counts):,} pages with extractable dates",
))
fig = style_axes(fig, xtitle="Publication year", ytitle="Cited pages")
fig.add_annotation(x=2025.5, y=max(counts) + 100, text="<b>2025-2026: 2,538 pages</b>",
                   showarrow=False, font=dict(size=13, color=ACCENT))
save(fig, "08_freshness_year")

# ============================================================
# Chart 9: Per-platform personality (scatter)
# ============================================================
# size proportional to citations
import math
sizes = [max(20, math.sqrt(p["n_citations"]) * 1.4) for p in plats_sorted]
fig = go.Figure(go.Scatter(
    x=url_pct, y=dom_pct, mode="markers+text",
    marker=dict(size=sizes, color=[ACCENT_2, ACCENT_3, NEUTRAL, ACCENT, ACCENT, NEUTRAL][:len(plats_sorted)],
                line=dict(width=2, color="white"), opacity=0.85),
    text=[p["platform"] for p in plats_sorted],
    textposition="top center",
    textfont=dict(size=14, color=INK, family=FONT["family"]),
    hovertemplate="<b>%{text}</b><br>URL top10: %{x:.1f}%<br>Domain top10: %{y:.1f}%<extra></extra>",
))
fig.update_layout(**base_layout(
    "Each platform has its own SERP-alignment personality",
    "Bubble size = total citations. X = URL match rate, Y = domain match rate vs Google's organic top-10.",
    height=600,
))
fig = style_axes(fig, xtitle="% of cited URLs in organic top-10",
                 ytitle="% of cited domains in organic top-10")
fig.update_xaxes(range=[0, 50], ticksuffix="%")
fig.update_yaxes(range=[15, 60], ticksuffix="%")
save(fig, "09_platform_personality")

print("\nAll 9 charts written to reports/v2/")
