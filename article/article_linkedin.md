# I Reverse-Engineered 42,971 AI Citations to Find Out What Google Actually Quotes — Here's What I Found

*By Daniel Shashko | [Full study + code](https://github.com/danishashko/grounding-citation-analysis)*

---

Everyone in SEO is asking the same thing: **how do I get cited by AI assistants?**

We've seen several major studies counting which *pages* get cited. Ahrefs did it at scale (17M citations across 7 platforms). Surfer SEO tracked 36M AI Overviews with 46M citations. Seer Interactive dissected how Gemini decomposes queries internally. But none of them answered a more fundamental question:

**Which *sentences* does Google actually pull from your page? And what do those sentences have in common?**

It turns out the answer has been hiding in plain sight — encoded in the citation URLs themselves.

---

## The Discovery: Google Tells You Exactly What It Cited

Every Google AI Mode and Gemini citation URL contains a `#:~:text=` fragment — a [Web Text Fragment](https://web.dev/articles/text-fragments) that encodes the **exact sentence** Google extracted from the source page.

Here's a real example:

```
https://www.healthline.com/nutrition/intermittent-fasting-guide#:~:text=Intermittent%20fasting%20is%20an%20eating%20pattern%20that%20cycles%20between%20periods%20of%20fasting%20and%20eating
```

Decode it:

> *"Intermittent fasting is an eating pattern that cycles between periods of fasting and eating"*

That's the exact sentence Google grounded its answer on. Not a guess — Google's own URL tells you.

ChatGPT, Perplexity, Copilot, and Grok don't do this. They just link to the page. Only AI Mode and Gemini reveal the cited sentence.

**So we decoded all of them.**

---

## The Dataset

520 queries across 19 categories (health, finance, tech, career, etc.) sent to 6 platforms via Bright Data's scraper APIs:

| Platform | Citations |
|---|---|
| Grok | 17,248 |
| AI Mode | 13,622 |
| Perplexity | 5,008 |
| Gemini | 3,885 |
| Copilot | 2,411 |
| ChatGPT | 797 |
| **Total** | **42,971** |

From AI Mode + Gemini's fragment URLs, we extracted **11,672 sentence-level citations**. Then we scraped 1,931 source pages and located every cited sentence to measure its exact position in the document, its word count, readability level, and surrounding structure.

This is the first study to analyse AI citations at the sentence level at this scale. The full codebase, data, and methodology are published — everything is reproducible.

---

## Finding 1: Nothing Over 17 Words Was Ever Cited

This was the biggest surprise.

Across 11,672 cited sentences:
- **Mean length: 9.8 words** (median: 10)
- **43% fell in the 6–10 word range**
- **49.4% in the 11–20 word range**
- **Zero sentences over 17 words** — not a single one

The distribution is remarkably tight. The 6–20 word range covers 92.4% of everything Google cited. Here's the difference between cited and not cited:

✅ *"Intermittent fasting cycles between periods of eating and fasting."* (8 words)

❌ *"Studies have suggested that intermittent fasting may, depending on the individual's metabolic profile, produce varying results in terms of weight management outcomes when compared with continuous caloric restriction approaches."* (31 words)

The first is what RAG researchers call an **atomic fact** — a self-contained, single-claim statement that makes sense on its own. The second is compound, hedged, and verbose. Google's pipeline picks the first and skips the second every time.

This also rules out several common chunking strategies (fixed-size windows, paragraph-level chunking, recursive splitting) and points toward **sentence-boundary chunking** — where the algorithm splits text at sentence boundaries and scores each one independently.

**What this means for your content:** If your important claims are buried in long sentences with multiple clauses, Google will never cite them. Rewrite key facts as short declarative statements — one claim per sentence, 15 words or fewer.

---

## Finding 2: Cited Sentences Cluster Near the Top of the Page

We located 1,719 cited sentences on their source pages and measured their position as a percentage down the document.

- **Mean position: 34.9%** (median 31.2%)
- 75% of cited sentences appear in the **first half of the page**
- 25th percentile: just 18% down the page
- The statistical test: t = -29.54, p < 10⁻¹⁵⁰ — this isn't subtle

Your most citable facts belong in your opening paragraphs. If you "build up" to your key claim in section 5, it's sitting in the lowest-probability citation zone.

This makes sense through a retrieval lens: sentences near the top of the page tend to contain the core answer in close proximity to the query terms. Page intros are written to answer the question directly, and Google's scoring rewards that.

**The practical takeaway is simple:** open with your best content. Lead with the answer, then explain.

---

## Finding 3: 74.7% of AI-Cited URLs Aren't in the Organic Top 10

This is the most important finding for anyone still running a traditional SEO playbook.

We cross-referenced all 42,971 citations against Google's own organic SERP rankings for the same 520 queries (collected via Bright Data's SERP API).

**Only 25.3% of cited URLs appear in the organic top-10.**

The breakdown by platform:

| Platform | URLs in organic top-10 |
|---|---|
| Perplexity | 43.5% |
| Copilot | 32.5% |
| AI Mode | 25.1% |
| Grok | 22.2% |
| Gemini | 15.3% |
| ChatGPT | 6.5% |

Perplexity behaves most like traditional search. ChatGPT is the most independent — 93.5% of its cited URLs don't rank in the top 10 at all.

But here's the twist: when a URL *does* rank organically, it tends to rank high. Mean position: **3.95**. Moving from rank #10 to rank #1 is roughly a **25x improvement** in citation probability.

**What this means for your content strategy:** Organic ranking still helps (a lot, for the top 3 spots), but it's nowhere near sufficient. AI platforms are discovering content far beyond the traditional top-10 results page. Brand presence, topical authority, and domain trust across the broader web matter more than chasing individual keyword rankings.

Ahrefs' brand visibility study backs this up: branded web mentions (Spearman r = 0.664) correlate more strongly with AI Overview visibility than backlinks, domain rating, or organic traffic. Getting mentioned across the web — linked or unlinked — compounds your AI visibility.

---

## 3 More Quick Findings

**Structured content dominates.** Pages with headings, lists, and tables had a **91.3% sentence-match rate** vs 39.3% for unstructured pages. Structure isn't just an SEO checkbox — it pre-chunks your content for Google's retrieval pipeline. Pages with lists and headings are already segmented into atomic claims by the author, which is exactly what the algorithm needs.

**AI Mode and Gemini cite almost nothing in common.** Despite both being Google products running on the same LLM family, they share only **3.5%** of their cited domains (Jaccard = 0.035). They clearly use different retrieval corpora and pipelines. Being visible in AI Mode doesn't mean you're visible in Gemini — and vice versa.

**Readability is bimodal, not bell-curved.** Google cites both simple sentences (Flesch 90–100: 23.5%) and dense technical ones (Flesch <30: 21.3%). The *least* cited tier? Middle-of-the-road prose (Flesch 50–59: just 5%). Corporate jargon and hedged language barely get cited. Match readability to query intent — write simply for consumer queries, technically for specialist queries. Don't aim for the mushy middle.

**Content freshness is less important than you think (for AI Mode).** The median cited page is **2.2 years old**. Over half (52.7%) is 2+ years old. Compare that to ChatGPT and Perplexity, which Ahrefs found cite content ~458 days and ~250 days fresher than organic Google results, respectively. For AI Mode specifically, evergreen authority beats recency.

---

## The Cheatsheet: Getting Cited in Google AI Mode

Here's everything boiled down to a single reference card. Save this or screenshot it.

**Sentence structure:**
- 6–15 words per key claim (sweet spot: 91.4% of citations)
- One fact per sentence — no compound clauses
- Declarative tone, not passive or hedged
- Match readability to query intent

**Page structure:**
- Most important claims in the first 3 paragraphs
- Use `<h2>`/`<h3>` to signal topic sections
- Use lists or tables for enumerations
- Lead with the answer, then provide context

**Platform-specific:**
- **AI Mode** — sentence structure matters most; write atomic facts
- **Perplexity + Copilot** — organic ranking is the primary lever
- **ChatGPT** — brand presence across the broader web; organic ranking barely matters
- **Grok** — domain-level authority > individual page ranking
- **Gemini** — dual strategy with AI Mode, but expect entirely different pages to be cited

**Freshness:**
- AI Mode's median cited page is 2.2 years old — evergreen content works
- ChatGPT and Perplexity strongly prefer fresh content
- Keep pages updated regardless — it can't hurt

**Decode your own citations:**
```
python -c "from urllib.parse import unquote; print(unquote('Your%20Fragment%20Here'))"
```

---

## The Full Study

The complete article covers all 9 findings in detail, with charts, statistical tests, and a platform-by-platform optimisation playbook for all 6 platforms.

Everything is open source and reproducible:
- **Full article:** [HackMD](https://hackmd.io/@A09fyOMpSD2VYIJodmXHqQ/r1eJyqthdbe)
- **Code + data:** [github.com/danishashko/grounding-citation-analysis](https://github.com/danishashko/grounding-citation-analysis)
- **Data collected via:** [Bright Data AI Mode Scraper](https://brightdata.com)

Questions? Hit me up in the comments or on [LinkedIn](https://www.linkedin.com/in/daniel-shashko/).

---

*42,971 citations. 520 queries. 6 platforms. The first sentence-level analysis of AI citation behaviour. All code published.*
