# Mermaid Diagrams — Source Files

These diagrams are embedded in the article and README using GitHub's native Mermaid rendering.
Copy any diagram block into a `.md` file and GitHub will render it automatically.

---

## Diagram 1: Full Pipeline Architecture

```mermaid
flowchart TD
    A[100 Queries\nqueries.csv] --> B[Bright Data\nAI Mode Scraper\ngd_mcswdt6z2elth3zqr2]
    A --> C[Bright Data\nGemini Scraper]
    B --> D[Raw JSON Snapshots\nai_mode_*.json]
    C --> E[Raw JSON Snapshots\ngemini_*.json]
    D --> F[03_parse_text_fragments.py\nDecodes #:~:text= URLs]
    E --> F
    F --> G[citations.csv\n1 row per citation\nwith cited_sentence]
    G --> H[04_scrape_source_pages.py\nFetch + position cited sentence]
    H --> I[source_pages.csv\nrelative_position 0.0-1.0]
    G --> J[05_analyze_patterns.py\nStatistical tests]
    I --> J
    J --> K[summary_stats.json\nCSV outputs]
    K --> L[06_generate_charts.py]
    L --> M[PNG Charts\nreports/]
```

---

## Diagram 2: Text Fragment URL Anatomy

```mermaid
graph LR
    A["https://healthline.com/nutrition/IF#:~:text=Intermittent%20fasting%20is%20an%20eating%20pattern"]
    A --> B["Base URL\nhttps://healthline.com/nutrition/IF"]
    A --> C["Fragment directive\n#:~:text="]
    A --> D["Encoded cited sentence\nIntermittent fasting is\nan eating pattern"]
    style C fill:#4285F4,color:#fff
    style D fill:#34A853,color:#fff
```

---

## Diagram 3: Citation Position Hypothesis

```mermaid
graph TD
    subgraph Source Document
        P1["Paragraph 1\n← Cited sentences cluster here"]
        P2["Paragraph 2\n← Also frequently cited"]
        P3["Paragraph 3"]
        HR1["---"]
        P4["Middle content\n(rarer citations)"]
        HR2["---"]
        P5["Bottom content\n(rarely cited)"]
    end
    style P1 fill:#34A853,color:#fff
    style P2 fill:#34A853,color:#fff
    style P3 fill:#FBBC05
    style P4 fill:#EA4335,color:#fff,opacity:0.6
    style P5 fill:#EA4335,color:#fff,opacity:0.3
```

---

## Diagram 4: AI Mode vs Gemini Coverage

```mermaid
venn
    title Citation Domain Overlap: AI Mode vs Gemini
    "AI Mode Only" : 40
    "Shared" : 60
    "Gemini Only" : 35
```

---

## Diagram 5: DEJAN Pipeline vs Our Evidence

```mermaid
flowchart LR
    subgraph "DEJAN AI Proposed Pipeline"
        A[BM25 Retrieval] --> B[BERT Re-ranking]
        B --> C[Sliding Window Extraction]
        C --> D[Answer Synthesis]
    end
    subgraph "Our Empirical Evidence"
        E["Top-of-page bias\n(consistent with BM25 weighting)"]
        F["Declarative sentences preferred\n(consistent with semantic re-ranking)"]
        G["Sentence-bounded citations\n(consistent with window extraction)"]
    end
    A -.->|Supports| E
    B -.->|Supports| F
    C -.->|Supports| G
    style E fill:#34A853,color:#fff
    style F fill:#34A853,color:#fff
    style G fill:#34A853,color:#fff
```

---

## Diagram 6: Sentence Length Optimal Zone

```mermaid
graph LR
    A["1-5 words\n❌ Too short\n(ambiguous)"]
    B["6-10 words\n⚠ Borderline"]
    C["10-20 words\n✅ SWEET SPOT\n(most often cited)"]
    D["21-30 words\n⚠ Declining"]
    E["31+ words\n❌ Rarely cited\n(too complex)"]
    style C fill:#34A853,color:#fff
    style A fill:#EA4335,color:#fff
    style E fill:#EA4335,color:#fff
    style B fill:#FBBC05
    style D fill:#FBBC05
```
