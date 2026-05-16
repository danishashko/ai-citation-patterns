# AI Citation Patterns — May 2026

**153,425 citations. 5,000 queries. 6 AI platforms.**

This repo contains the dataset, analysis scripts, and findings from a large-scale study of how AI search platforms select and cite web content.

**Read the full article:** [How AI Search Platforms Cite the Web — May 2026 Edition](https://hackmd.io/@A09fyOMpSD2VYIJodmXHqQ/SyKkHeLJfl)

---

## What This Study Covers

We ran 5,000 queries across six AI platforms and recorded every cited URL, decoding the exact cited sentence whenever the platform exposed a `#:~:text=` text fragment. Key findings:

- **Google AI Mode** dropped text fragment exposure entirely (was 70.9% in March 2026, now 0%).
- **Gemini** expanded fragment coverage to 84.1% — the only remaining window into Google's sentence-level chunking logic.
- **ChatGPT cited URLs overlap Google top-10 at just 4.2%.** Classical SEO does not transfer to ChatGPT.
- **Median cited sentence: 10 words.** Nothing longer than 18 words was cited in the Gemini fragment sample.
- **Cited sentences cluster in the top 37% of the page.** Front-loaded claims win.
- **Freshness collapsed**: median cited content age dropped from 2.2 years (March 2026) to 298 days.

---

## Platforms

| Platform | Citations | Fragment coverage | SERP URL overlap |
|---|---|---|---|
| Google AI Mode | 88,392 | 0% | 22.5% |
| Grok | 30,676 | 0% | 14.1% |
| Gemini | 13,487 | 84.1% | 41.1% |
| Microsoft Copilot | 8,779 | 0% | 23.7% |
| Perplexity | 8,562 | 0% | 39.4% |
| ChatGPT | 3,529 | 0% | 4.2% |
| **Total** | **153,425** | | |

---

## Repo Structure

```
data/
  parsed/
    citations.csv          # 153,425 citation rows: URL, platform, query, fragment, cited_text
    answers.csv            # Raw AI answers per query per platform
    serp.csv               # Organic SERP top-10 for each query
    source_pages.csv       # Scraped source pages for positional analysis
  analysis/
    summary_stats.json
    domain_frequency.csv
    citation_vs_serp_rank.csv
    positional_distribution.csv
    readability_per_sentence.csv
    readability_stats.json
    sentence_length_stats.csv
    freshness_dates.csv
    freshness_stats.json
    platform_overlap.csv
    category_breakdown.csv
queries/
  queries.csv              # 5,000 queries used in this study
scripts/
  01_collect_ai_mode.py    # Collect AI Mode citations via Bright Data scraper
  02_collect_gemini.py     # Collect Gemini citations + text fragments
  02b_collect_serp.py      # Collect organic SERP top-10 for each query
  03_parse_text_fragments.py  # Decode #:~:text= fragments to cited sentences
  04_scrape_source_pages.py   # Scrape source pages for positional analysis
  05_analyze_patterns.py      # Core statistical analysis
  06_generate_charts.py       # Initial chart generation
  07_readability_analysis.py  # Flesch-Kincaid readability per sentence
  08_freshness_analysis.py    # Content age analysis
  09_generate_v2_charts.py    # Final publication charts (reports/v2/)
notebooks/
  01_methodology.ipynb     # Study design and methodology walkthrough
  02_findings.ipynb        # Interactive findings exploration
reports/
  v2/                      # Publication-ready charts (PNG, 2x scale)
article/
  article.md               # Full research article
  article_linkedin.md      # LinkedIn-formatted version
```

---

## Quickstart (data already included)

```bash
git clone https://github.com/danishashko/ai-citation-patterns
cd ai-citation-patterns
pip install -r requirements.txt

# Run analysis on the included dataset
python scripts/05_analyze_patterns.py

# Regenerate charts
python scripts/09_generate_v2_charts.py
```

**To collect fresh data** you need a [Bright Data](https://brightdata.com) account with access to the Google AI Mode and SERP scrapers:

```bash
cp .env.example .env
# Edit .env and add your BRIGHTDATA_API_KEY
python scripts/01_collect_ai_mode.py --limit 50
```

---

## Data Schema

### `citations.csv`

| Column | Description |
|---|---|
| `query` | Search query |
| `platform` | ai_mode / gemini / chatgpt / perplexity / copilot / grok |
| `url` | Cited URL |
| `domain` | Extracted domain |
| `fragment` | Raw `#:~:text=` fragment (Gemini only, May 2026) |
| `cited_text` | Decoded cited sentence (where fragment available) |
| `answer_id` | Foreign key to answers.csv |

### `serp.csv`

| Column | Description |
|---|---|
| `query` | Search query |
| `url` | Organic result URL |
| `rank` | Position 1-10 |
| `domain` | Extracted domain |

---

## Prior Study

March 2026 (42,971 citations, 520 queries, Google AI Mode only): [grounding-citation-analysis](https://github.com/danishashko/grounding-citation-analysis)

---

## Citation

```
Shashko, D. (May 2026). AI Citation Patterns: 153,425 citations across 6 AI platforms.
https://github.com/danishashko/ai-citation-patterns
```

---

## License

MIT
