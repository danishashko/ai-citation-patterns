# Mermaid Diagrams — May 2026 Edition

These diagrams accompany the May 2026 study and are embedded in the long-form article and README. GitHub renders Mermaid blocks natively.

---

## Diagram 1 — Full Pipeline Architecture (5,000 queries × 6 platforms)

```mermaid
flowchart TD
    A["queries_5k.csv<br/>5,000 queries × 25 verticals"] --> B1["01_collect_ai_mode.py<br/>Bright Data AI Mode"]
    A --> B2["02_collect_gemini.py<br/>Bright Data Gemini"]
    A --> B3["02_collect_chatgpt.py<br/>Bright Data ChatGPT"]
    A --> B4["02_collect_perplexity.py<br/>Bright Data Perplexity"]
    A --> B5["02_collect_copilot.py<br/>Bright Data Copilot"]
    A --> B6["02_collect_grok.py<br/>Bright Data Grok"]
    A --> S["02b_collect_serp.py<br/>Bright Data SERP API"]
    B1 --> P["03_parse_text_fragments.py"]
    B2 --> P
    B3 --> P
    B4 --> P
    B5 --> P
    B6 --> P
    P --> C["citations.csv<br/>153,425 rows"]
    P --> AN["answers.csv<br/>13,710 rows"]
    S --> SR["serp.csv<br/>44,348 rows / 4,998 queries"]
    C --> SC["04_scrape_source_pages.py<br/>fragment-bearing URLs only"]
    SC --> SP["source_pages.csv<br/>11,344 rows · 87.9% match"]
    C --> AZ["05_analyze_patterns.py"]
    SR --> AZ
    SP --> AZ
    AZ --> ST["data/analysis/*.json + *.csv"]
    AZ --> RD["07_readability_analysis.py"]
    AZ --> FR["08_freshness_analysis.py"]
    ST --> CH["06_generate_charts.py"]
    CH --> R["reports/*.png"]
```

---

## Diagram 2 — How Text Fragments Used to Work (and Where They Still Do)

```mermaid
graph LR
    A["https://example.com/page#:~:text=cited%20sentence%20here"]
    A --> B["Base URL<br/>https://example.com/page"]
    A --> C["Fragment directive<br/>#:~:text="]
    A --> D["URL-encoded cited sentence"]
    style C fill:#4285F4,color:#fff
    style D fill:#34A853,color:#fff
```

**May 2026 reality:**

```mermaid
flowchart LR
    Q["Same 5,000 queries"] --> AM["AI Mode → 0% URLs carry<br/>#:~:text= (was 70.9% in 2025)"]
    Q --> G["Gemini → 84.1% URLs carry<br/>#:~:text= (was 51.8% in 2025)"]
    style AM fill:#EA4335,color:#fff
    style G fill:#34A853,color:#fff
```

---

## Diagram 3 — Where Cited Sentences Live in the Source Page

Mean position **0.3704** across 9,968 fragment-resolved citations (t = −63.45 vs 0.50, p < 0.001).

```mermaid
graph TD
    subgraph "Source Page (top → bottom)"
        P1["0–10% (679 cites)"]
        P2["10–20% (1,577)"]
        P3["20–30% (1,920) ← peak"]
        P4["30–40% (1,802)"]
        P5["40–50% (1,487)"]
        P6["50–60% (1,057)"]
        P7["60–70% (711)"]
        P8["70–80% (411)"]
        P9["80–90% (233)"]
        P10["90–100% (91)"]
    end
    style P3 fill:#34A853,color:#fff
    style P4 fill:#34A853,color:#fff
    style P2 fill:#34A853,color:#fff,opacity:0.8
    style P5 fill:#34A853,color:#fff,opacity:0.7
    style P6 fill:#FBBC05
    style P7 fill:#FBBC05,opacity:0.6
    style P8 fill:#EA4335,color:#fff,opacity:0.5
    style P9 fill:#EA4335,color:#fff,opacity:0.4
    style P10 fill:#EA4335,color:#fff,opacity:0.3
```

---

## Diagram 4 — AI Mode vs Gemini Domain Overlap

Jaccard similarity = **0.0466**.

```mermaid
flowchart LR
    AM["AI Mode<br/>29,795 unique domains"] -.shared.- G["Gemini<br/>5,143 unique domains"]
    AM --- O["Overlap: 1,556 domains<br/>(4.66% Jaccard)"]
    G --- O
    style AM fill:#4285F4,color:#fff
    style G fill:#0F9D58,color:#fff
    style O fill:#FBBC05
```

---

## Diagram 5 — Citation vs Organic SERP Alignment

For 153,425 citations, joined to fresh organic top-10 SERPs from the same queries:

```mermaid
graph LR
    All["153,425 cited URLs"] --> Top["35,360 in organic top-10<br/>(23.05%)"]
    All --> Out["118,065 NOT in top-10<br/>(76.95%)"]
    Top --> R["Mean rank when matched: 4.27"]
    style Top fill:#34A853,color:#fff
    style Out fill:#EA4335,color:#fff
    style R fill:#FBBC05
```

By platform (URL in organic top-10):

```mermaid
graph TD
    G["Gemini 41.14%"]
    P["Perplexity 39.40%"]
    C["Copilot 23.68%"]
    A["AI Mode 22.49%"]
    K["Grok 14.13%"]
    T["ChatGPT 4.19%"]
    style G fill:#34A853,color:#fff
    style P fill:#34A853,color:#fff
    style C fill:#FBBC05
    style A fill:#FBBC05
    style K fill:#EA4335,color:#fff
    style T fill:#EA4335,color:#fff
```

---

## Diagram 6 — Cited Sentence Length: Hard 18-Word Ceiling

Across 11,346 sentence-level extractions:

```mermaid
graph LR
    A["1–5 words<br/>682 (6.0%)"]
    B["6–10 words<br/>5,133 (45.2%)"]
    C["11–20 words<br/>5,531 (48.8%) ← sweet spot"]
    D["21+ words<br/>0 cites in entire dataset"]
    style A fill:#FBBC05
    style B fill:#34A853,color:#fff
    style C fill:#34A853,color:#fff
    style D fill:#EA4335,color:#fff
```

Mean = 9.27 words · Median = 10 · IQR 7–11 · Max = 18.

---

## Diagram 7 — Readability Is Bimodal

```mermaid
graph LR
    A["Very Easy (Flesch 90+)<br/>2,569 (22.9%)"]
    B["Easy (80–89)<br/>1,351 (12.0%)"]
    C["Standard (60–69)<br/>1,464 (13.1%)"]
    D["Difficult (30–49)<br/>2,747 (24.5%)"]
    E["Very Confusing (<30)<br/>2,302 (20.5%)"]
    style A fill:#34A853,color:#fff
    style B fill:#34A853,color:#fff,opacity:0.8
    style C fill:#FBBC05
    style D fill:#EA4335,color:#fff
    style E fill:#EA4335,color:#fff
```

Cited content is bimodal — elementary or technical. Mid-register prose is rare.

---

## Diagram 8 — Freshness: Median Page Is ~10 Months Old

```mermaid
graph TD
    A["< 1 month: 436"]
    B["1–3 months: 579"]
    C["3–6 months: 661"]
    D["6–12 months: 554"]
    E["1–2 years: 633"]
    F["2–5 years: 694 ← largest single bucket"]
    G["5+ years: 545"]
    style A fill:#34A853,color:#fff
    style B fill:#34A853,color:#fff,opacity:0.9
    style C fill:#34A853,color:#fff,opacity:0.8
    style D fill:#FBBC05
    style E fill:#FBBC05
    style F fill:#4285F4,color:#fff
    style G fill:#FBBC05
```

Median age = 298 days · 61.9% of dated cited URLs published in 2025–2026 · Long tail back to 1998.

---

## Diagram 9 — Per-Platform Personality

```mermaid
quadrantChart
    title Volume vs Organic Alignment
    x-axis "Low organic alignment" --> "High organic alignment"
    y-axis "Few cites/query" --> "Many cites/query"
    quadrant-1 "High volume + aligned"
    quadrant-2 "High volume + divergent"
    quadrant-3 "Low volume + divergent"
    quadrant-4 "Low volume + aligned"
    "AI Mode": [0.225, 0.50]
    "Gemini": [0.41, 0.20]
    "Grok": [0.14, 0.95]
    "Copilot": [0.237, 0.28]
    "Perplexity": [0.394, 0.25]
    "ChatGPT": [0.042, 0.55]
```
