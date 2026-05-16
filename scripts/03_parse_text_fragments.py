"""
03_parse_text_fragments.py
===========================
Parse raw Bright Data JSON snapshots and extract:
  - The cited sentence from every #:~:text= URL fragment
  - Citation metadata: position, domain, title, description
  - Answer metadata: word count, sentence count, paragraph count
  - Source type: platform (ai_mode / gemini)

Output: data/parsed/citations.csv + data/parsed/answers.csv

Usage:
    python scripts/03_parse_text_fragments.py
    python scripts/03_parse_text_fragments.py --raw-dir data/raw --out-dir data/parsed
"""

import argparse
import sys as _sys
try:
    _sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    _sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
import json
import re
import os
from pathlib import Path
from urllib.parse import unquote, urlparse, parse_qs

import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

RAW_DIR = Path(os.environ.get("RAW_DATA_DIR", "data/raw"))
PARSED_DIR = Path(os.environ.get("PARSED_DATA_DIR", "data/parsed"))
PARSED_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────── Text Fragment Parser ──────────────────────────

def parse_text_fragment(url: str) -> dict:
    """
    Extract the #:~:text= fragment from a URL.

    The Text Fragments spec supports:
        #:~:text=[prefix-,]textStart[,textEnd][,-suffix]
    We return the decoded textStart (the primary cited snippet).

    Returns dict with keys: fragment_raw, text_start, text_end, prefix, suffix
    """
    result = {
        "fragment_raw": None,
        "text_start": None,
        "text_end": None,
        "prefix": None,
        "suffix": None,
    }

    if "#:~:text=" not in url:
        return result

    fragment = url.split("#:~:text=", 1)[1]
    # Remove any secondary fragment directives
    fragment = fragment.split("&")[0]
    result["fragment_raw"] = unquote(fragment)

    # Parse prefix-, textStart, textEnd, -suffix
    # Format: [prefix-,]textStart[,textEnd][,-suffix]
    decoded = unquote(fragment.replace("+", " "))

    parts = decoded.split(",")

    # Detect prefix: ends with "-"
    prefix = None
    suffix = None
    text_parts = []

    i = 0
    if parts and parts[0].endswith("-"):
        prefix = parts[0][:-1]
        i = 1
    for j in range(i, len(parts)):
        if parts[j].startswith("-"):
            suffix = parts[j][1:]
        else:
            text_parts.append(parts[j])

    result["prefix"] = prefix
    result["suffix"] = suffix

    if text_parts:
        result["text_start"] = text_parts[0].strip()
    if len(text_parts) > 1:
        result["text_end"] = text_parts[1].strip()

    return result


# Tracking-only query params to strip for canonical URL comparison
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "ref", "referrer", "source", "fbclid", "gclid", "yclid",
}


def clean_base_url(url: str) -> str:
    """Strip text fragment and tracking query params to get a canonical page URL."""
    from urllib.parse import urlparse, urlencode, parse_qsl
    if "#:~:text=" in url:
        url = url.split("#:~:text=")[0]
    elif "#" in url:
        url = url.split("#")[0]
    # Strip tracking params (e.g. ?utm_source=chatgpt.com)
    if "?" in url:
        parsed = urlparse(url)
        clean_qs = [(k, v) for k, v in parse_qsl(parsed.query)
                    if k.lower() not in _TRACKING_PARAMS]
        url = parsed._replace(query=urlencode(clean_qs)).geturl().rstrip("?")
    return url


def _domain_from_url(url: str) -> str:
    """Extract bare domain from a URL (strips www.)."""
    try:
        from urllib.parse import urlparse
        netloc = urlparse(url).netloc.lower()
        return netloc.removeprefix("www.")
    except Exception:
        return ""


def word_count(text: str) -> int:
    if not text:
        return 0
    return len(str(text).split())


def sentence_count(text: str) -> int:
    if not text:
        return 0
    return len(re.findall(r"[.!?]+", str(text))) + 1


def has_list(markdown: str) -> bool:
    """Detect lists from answer_text_markdown (- item or 1. item)."""
    if not markdown:
        return False
    return bool(re.search(r"^[\s]*[-*+]\s|^[\s]*\d+\.\s", str(markdown), re.MULTILINE))


def has_table(markdown: str) -> bool:
    """Detect tables from answer_text_markdown (| col | col |)."""
    if not markdown:
        return False
    return bool(re.search(r"\|.+\|", str(markdown)))


# ─────────────────────────── Core Parser ───────────────────────────────────

def parse_snapshot_file(filepath: Path) -> tuple[list[dict], list[dict]]:
    """
    Parse one raw snapshot JSON file and return (citation_rows, answer_rows).
    """
    # Detect platform from filename (ai_mode_*.json, gemini_*.json, chatgpt_*.json, etc.)
    name = filepath.name.lower()
    if "ai_mode" in name:
        platform = "ai_mode"
    elif "gemini" in name:
        platform = "gemini"
    elif "chatgpt" in name:
        platform = "chatgpt"
    elif "perplexity" in name:
        platform = "perplexity"
    elif "copilot" in name:
        platform = "copilot"
    elif "grok" in name:
        platform = "grok"
    else:
        platform = "unknown"

    with open(filepath, encoding="utf-8") as f:
        records = json.load(f)

    citation_rows = []
    answer_rows = []

    for record in records:
        # Prefer input.prompt (always clean) over the top-level prompt field,
        # which for Gemini/ChatGPT echoes back the query with Spanish
        # conversation prefixes like "Has dicho " / "Tú dijiste ".
        query = (
            (record.get("input") or {}).get("prompt", "")
            or record.get("prompt", "")
        )
        # Prefer markdown — it's structured and clean (answer_html can be 1MB+)
        answer_md = record.get("answer_text_markdown", "") or record.get("answer_text", "")
        answer_text = record.get("answer_text", "") or answer_md
        # Never load answer_html — it contains full page HTML, not just the answer
        timestamp = record.get("timestamp", "")
        country = record.get("country", "")
        snapshot_id = filepath.stem

        # ── Answer-level metadata ──────────────────────────────────────────
        answer_row = {
            "snapshot_id": snapshot_id,
            "platform": platform,
            "query": query,
            "country": country,
            "timestamp": timestamp,
            "answer_word_count": word_count(answer_md),
            "answer_sentence_count": sentence_count(answer_md),
            "answer_has_list": has_list(answer_md),
            "answer_has_table": has_table(answer_md),
            "citation_count": 0,  # will update below
            "links_count": len(record.get("links_attached", []) or []),
        }

        # ── Citation-level extraction ──────────────────────────────────────
        # Copilot uses "sources" instead of "citations"
        citations = record.get("citations") or record.get("sources") or []
        answer_row["citation_count"] = len(citations)

        for cite_idx, cite in enumerate(citations):
            raw_url = cite.get("url") or ""  # guard against None
            raw_url = str(raw_url)              # ensure always a string
            # Some platforms (Copilot) omit the domain field — derive from URL.
            # Some platforms (AI Mode, Gemini) return full URL as domain — clean it.
            raw_domain = cite.get("domain", "") or ""
            if raw_domain.startswith("http"):
                # Full URL stored in domain field (AI Mode / Grok)
                domain = _domain_from_url(raw_domain)
            elif raw_domain and "." in raw_domain:
                # Looks like a real bare domain already
                domain = raw_domain
            else:
                # Display name (e.g. "Mayo Clinic", "NIDDK") or empty — derive from URL
                domain = _domain_from_url(raw_url)
            title = cite.get("title", "")
            description = cite.get("description", "")
            cited_flag = cite.get("cited", False)

            # Parse text fragment
            frag = parse_text_fragment(raw_url)
            base_url = clean_base_url(raw_url)

            # cited_sentence = text_start (page anchor for positional matching)
            # cited_passage  = text_start ... text_end (full highlighted range)
            # When Google uses a range fragment (textStart,textEnd), text_start
            # is the opening anchor and text_end is the closing anchor.
            cited_sentence = frag["text_start"] or ""
            cited_passage = cited_sentence
            if frag["text_end"]:
                cited_passage = f"{cited_sentence} … {frag['text_end']}"

            # Word count of the full passage (both anchors) as a span proxy
            cited_sentence_len = len(cited_passage.split()) if cited_passage else 0
            has_fragment = "#:~:text=" in raw_url

            citation_rows.append({
                "snapshot_id": snapshot_id,
                "platform": platform,
                "query": query,
                "country": country,
                "timestamp": timestamp,
                # Citation basics
                "citation_index": cite_idx,
                "citation_url_raw": raw_url,
                "citation_url_clean": base_url,
                "domain": domain,
                "title": title,
                "description": description,
                "cited_flag": cited_flag,
                # Text fragment
                "has_text_fragment": has_fragment,
                "fragment_raw": frag["fragment_raw"],
                "cited_sentence": cited_sentence,        # text_start — page anchor for positional matching
                "cited_passage": cited_passage,           # text_start … text_end — full highlighted range
                "cited_sentence_word_count": cited_sentence_len,  # span proxy (both anchors)
                "text_end": frag["text_end"],
                "prefix": frag["prefix"],
                "suffix": frag["suffix"],
                # Answer context
                "answer_word_count": answer_row["answer_word_count"],
            })

        answer_rows.append(answer_row)

    return citation_rows, answer_rows


def parse_all(raw_dir: Path, out_dir: Path):
    # Skip non-snapshot files (e.g. serp_results.json, .gitkeep)
    known_prefixes = ("ai_mode_", "gemini_", "chatgpt_", "perplexity_", "copilot_", "grok_")
    json_files = sorted(
        fp for fp in raw_dir.glob("*.json")
        if any(fp.name.startswith(p) for p in known_prefixes)
    )
    if not json_files:
        print(f"No snapshot JSON files found in {raw_dir}. Run collection scripts first.")
        return

    all_citations = []
    all_answers = []

    for fp in tqdm(json_files, desc="Parsing snapshots"):
        try:
            citations, answers = parse_snapshot_file(fp)
            all_citations.extend(citations)
            all_answers.extend(answers)
        except Exception as e:
            print(f"  ✗ Failed to parse {fp.name}: {e}")

    if all_citations:
        cite_df = pd.DataFrame(all_citations)
        cite_path = out_dir / "citations.csv"
        cite_df.to_csv(cite_path, index=False)
        print(f"\n✓ {len(cite_df)} citation rows → {cite_path}")
        print(f"  Fragment coverage: {cite_df['has_text_fragment'].mean():.1%} of citations have #:~:text=")

    if all_answers:
        ans_df = pd.DataFrame(all_answers)
        ans_path = out_dir / "answers.csv"
        ans_df.to_csv(ans_path, index=False)
        print(f"✓ {len(ans_df)} answer rows → {ans_path}")


# ─────────────────────────── CLI ───────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Parse raw snapshots and extract text fragments.")
    parser.add_argument("--raw-dir", default=str(RAW_DIR))
    parser.add_argument("--out-dir", default=str(PARSED_DIR))
    args = parser.parse_args()

    parse_all(Path(args.raw_dir), Path(args.out_dir))
    print("\nDone.")


if __name__ == "__main__":
    main()
