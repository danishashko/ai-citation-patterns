# Google killed text fragments in AI Mode. Here is what 153,425 citations say to do about it.

I rebuilt my AI citation study from scratch on the May 2026 versions of Google AI Mode, Gemini, ChatGPT, Perplexity, Copilot, and Grok.

5,000 queries. 153,425 citations. The single biggest finding rewrites the SEO playbook for AI search.

---

**The headline:**

In March 2026, AI Mode citation URLs carried `#:~:text=` fragments that pinned the exact sentence Google pulled. Coverage was 70.9%. You could decode the URL and see the cited sentence.

Two months later (May 2026), AI Mode fragment coverage is 0.0%. Out of 88,392 AI Mode citations, zero have fragments.

Gemini went the opposite way. Coverage jumped from 51.8% to 84.1%. If you want to see what sentence Google pulls, Gemini is now your only window.

---

**Three tips you can act on this week:**

1. **Stop scraping AI Mode for the cited sentence.** Pivot fragment monitoring to Gemini.
2. **Front-load your factual claims.** Mean cited position is at 37% of the page. Top three paragraphs are your citation zone.
3. **Cap key claims at 18 words.** Mean cited sentence is 9.27 words. Median 10. Max in the entire dataset is 18. Long sentences get zero citations.

---

**Per-platform behavior diverges hard:**

| Platform | Citations | URL in top-10 | Domain in top-10 | Mean rank |
|---|---|---|---|---|
| Gemini | 13,487 | 41.1% | 21.4% | 4.06 |
| Perplexity | 8,562 | 39.4% | 50.3% | 4.18 |
| Copilot | 8,779 | 23.7% | 34.9% | 3.07 |
| AI Mode | 88,392 | 22.5% | 39.5% | 4.43 |
| Grok | 30,676 | 14.1% | 30.4% | 4.41 |
| ChatGPT | 3,529 | 4.2% | 21.1% | 4.14 |

ChatGPT has 4.2% URL overlap with the organic top-10. 95.8% of its citations come from outside the SERP. You cannot win on ChatGPT through Google rankings alone. Brand mentions on Wikipedia and high-DR publishers do the heavy lifting there.

AI Mode and Gemini are both Google products running on Gemini models. They share only 4.66% of cited domains (Jaccard 0.0466). Optimize for them as if they were unrelated platforms.

---

**Other findings worth your time:**

- YouTube (9,868 citations) and Reddit (6,595) are the two single largest citation sources across all platforms. If you skip video and community content, you skip the two biggest pools.
- Readability is bimodal. 22.9% Very Easy (Flesch 90+), 24.5% Difficult (Flesch 30-49). The middle (Fairly Difficult, 50-59) is only 2.6% of citations. Match readability to query intent. Avoid the muddled middle.
- Median cited page is 298 days old. 61.9% of dated citations are from 2025-2026. Freshness preference tightened since my March 2026 run but evergreen content from 2018-2022 still gets cited.
- Across all platforms, moving from organic rank #10 to rank #1 is roughly a 9.3x improvement in citation probability.

---

**Full article + open data + code:**

GitHub: https://github.com/danishashko/grounding-citation-analysis

Bright Data made the multi-platform scraping possible at this scale.

If you are running AI search visibility for a brand, fix your monitoring scripts first. Anything pulling fragments off AI Mode URLs has been returning empty strings since the change.

#SEO #AISEO #GenerativeSearch #LLMSEO #DigitalMarketing
