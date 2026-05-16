"""
02_collect_gemini.py  (multi-platform collector)
=================================================
Collect AI citation data from all non-Google-AI-Mode platforms via Bright Data:
  gemini, chatgpt, perplexity, copilot, grok

Supported platforms and their Bright Data dataset IDs (set in .env):
  Platform     Env var                          Dataset ID
  ─────────── ─────────────────────────────── ─────────────────────
  gemini      BRIGHTDATA_GEMINI_DATASET_ID     gd_mbz66arm2mf9cu856y
  chatgpt     BRIGHTDATA_CHATGPT_DATASET_ID    gd_m7aof0k82r803d5bjm
  perplexity  BRIGHTDATA_PERPLEXITY_DATASET_ID gd_m7dhdot1vw9a7gc1n
  copilot     BRIGHTDATA_COPILOT_DATASET_ID    gd_m7di5jy6s9geokz8w
  grok        BRIGHTDATA_GROK_DATASET_ID       gd_m8ve0u141icu75ae74

Note on text fragment coverage:
  Google AI Mode and Gemini embed #:~:text= fragments in citation URLs,
  enabling sentence-level extraction.  ChatGPT, Perplexity, Copilot, and
  Grok return plain citation URLs — these are valuable for domain/URL
  overlap analysis but won't yield sentence-level data in step 03.

Usage:
    # Single platform
    python scripts/02_collect_gemini.py --platform gemini
    python scripts/02_collect_gemini.py --platform chatgpt --limit 10

    # All five platforms sequentially
    python scripts/02_collect_gemini.py --all

    # Test all platforms with 5 queries each
    python scripts/02_collect_gemini.py --all --limit 5
"""

import argparse
import sys as _sys
try:
    _sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    _sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

# ─────────────────────────── Platform Config ───────────────────────────────

API_KEY = os.environ.get("BRIGHTDATA_API_KEY", "")
COUNTRY = os.environ.get("COUNTRY", "US")
TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", 120))
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", 10))
MAX_POLLS = int(os.environ.get("MAX_POLL_ATTEMPTS", 60))
BATCH_SIZE = 10
MAX_CONCURRENT_POLLS = 15  # cap simultaneous Bright Data poll connections

RAW_DIR        = Path(os.environ.get("RAW_DATA_DIR", "data/raw"))
CHECKPOINT_DIR = RAW_DIR / "checkpoints"
RAW_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

TRIGGER_URL  = "https://api.brightdata.com/datasets/v3/trigger"
SNAPSHOT_URL = "https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}"

# Per-platform: dataset ID env var and the target URL to submit with each query
PLATFORMS = {
    "gemini": {
        "env_var": "BRIGHTDATA_GEMINI_DATASET_ID",
        "url": "https://gemini.google.com",
    },
    "chatgpt": {
        "env_var": "BRIGHTDATA_CHATGPT_DATASET_ID",
        "url": "https://chatgpt.com",
    },
    "perplexity": {
        "env_var": "BRIGHTDATA_PERPLEXITY_DATASET_ID",
        "url": "https://www.perplexity.ai",
    },
    "copilot": {
        "env_var": "BRIGHTDATA_COPILOT_DATASET_ID",
        "url": "https://copilot.microsoft.com",
    },
    "grok": {
        "env_var": "BRIGHTDATA_GROK_DATASET_ID",
        "url": "https://grok.com",
    },
}


# ─────────────────────────── Helpers ───────────────────────────────────────

def get_headers():
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }


def check_config(platform: str) -> str:
    if not API_KEY or "your_" in API_KEY:
        print("ERROR: Set BRIGHTDATA_API_KEY in .env")
        sys.exit(1)
    env_var = PLATFORMS[platform]["env_var"]
    dataset_id = os.environ.get(env_var, "")
    if not dataset_id:
        print(f"ERROR: Set {env_var} in .env for platform '{platform}'")
        sys.exit(1)
    return dataset_id


def load_queries(csv_path: str, platform: str, limit: int | None = None) -> list[dict]:
    df = pd.read_csv(csv_path)
    if limit:
        df = df.head(limit)
    target_url = PLATFORMS[platform]["url"]
    return [
        {"url": target_url, "prompt": row["query"], "country": COUNTRY}
        for _, row in df.iterrows()
    ]


def trigger_snapshot(payload: list[dict], dataset_id: str) -> str:
    resp = requests.post(
        TRIGGER_URL,
        params={"dataset_id": dataset_id, "include_errors": "true"},
        headers=get_headers(),
        json=payload,
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    snapshot_id = data.get("snapshot_id") or data.get("id")
    if not snapshot_id:
        raise ValueError(f"No snapshot_id in response: {data}")
    print(f"  → Snapshot triggered: {snapshot_id}")
    return snapshot_id


def poll_snapshot(snapshot_id: str, label: str = "") -> list[dict]:
    url = SNAPSHOT_URL.format(snapshot_id=snapshot_id)
    for attempt in range(1, MAX_POLLS + 1):
        time.sleep(POLL_INTERVAL)
        resp = requests.get(
            url, headers=get_headers(), params={"format": "json"}, timeout=TIMEOUT
        )
        if resp.status_code == 200:
            try:
                data = resp.json()
            except Exception:
                # Bright Data sometimes returns NDJSON (newline-delimited JSON)
                lines = [l.strip() for l in resp.text.splitlines() if l.strip()]
                try:
                    data = [json.loads(l) for l in lines]
                except Exception:
                    data = {}
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "data" in data:
                return data["data"]
            status = data.get("status", "unknown") if isinstance(data, dict) else "unknown"
            if attempt % 5 == 0:
                print(f"    [{label}] Poll {attempt}/{MAX_POLLS}: {status}")
        elif resp.status_code == 202:
            if attempt % 5 == 0:
                print(f"    [{label}] Poll {attempt}/{MAX_POLLS}: processing...")
        else:
            print(f"    [{label}] Poll {attempt}/{MAX_POLLS}: HTTP {resp.status_code}")
    raise TimeoutError(f"Snapshot {snapshot_id} did not complete after {MAX_POLLS} polls.")


# ─────────────────────────── Checkpoint helpers ────────────────────────────

def checkpoint_path(platform: str) -> Path:
    return CHECKPOINT_DIR / f"{platform}_checkpoint.json"


def load_checkpoint(platform: str) -> list[dict]:
    """Load saved batch states: [{batch_idx, snapshot_id, saved, output_file}]"""
    p = checkpoint_path(platform)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return []


def save_checkpoint(platform: str, batches: list[dict]):
    checkpoint_path(platform).write_text(
        json.dumps(batches, indent=2), encoding="utf-8"
    )


def mark_saved(platform: str, batch_idx: int, output_file: Path):
    batches = load_checkpoint(platform)
    for b in batches:
        if b["batch_idx"] == batch_idx:
            b["saved"] = True
            b["output_file"] = str(output_file)
            break
    save_checkpoint(platform, batches)


def save_raw(records: list[dict], platform: str, snapshot_id: str) -> Path:
    out_path = RAW_DIR / f"{platform}_{snapshot_id}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"  ✓ Saved {len(records)} records → {out_path}")
    return out_path


def collect_platform(platform: str, queries_csv: str, limit: int | None, batch_size: int) -> list[Path]:
    print(f"\n{'='*60}")
    print(f"  Platform: {platform.upper()}")
    print(f"{'='*60}")

    dataset_id = check_config(platform)
    queries = load_queries(queries_csv, platform, limit)
    all_batches = [queries[i: i + batch_size] for i in range(0, len(queries), batch_size)]

    # ── Fast-path: if all batches already exist on disk (e.g. prior non-checkpoint run) ──
    existing_files = sorted(RAW_DIR.glob(f"{platform}_*.json"))
    if len(existing_files) >= len(all_batches):
        print(f"  All {len(all_batches)} batches already on disk. Skipping {platform}.")
        return existing_files

    # ── Load checkpoint: skip already-saved, retry timed-out ───────────────
    checkpoint = {b["batch_idx"]: b for b in load_checkpoint(platform)}
    already_saved = [
        Path(b["output_file"]) for b in checkpoint.values()
        if b.get("saved") and b.get("output_file") and Path(b["output_file"]).exists()
    ]
    if already_saved:
        print(f"  Resuming: {len(already_saved)} batches already saved, skipping.")

    # ── Step 1: trigger missing batches, reuse existing snapshot IDs ───────
    snapshot_jobs: list[tuple[int, str]] = []  # (batch_idx, snapshot_id)

    for idx, batch in enumerate(all_batches):
        existing = checkpoint.get(idx, {})
        if existing.get("saved") and existing.get("output_file") and Path(existing["output_file"]).exists():
            continue  # already done
        if existing.get("snapshot_id"):
            # Was triggered before but timed out — retry polling
            print(f"  Retrying snapshot {existing['snapshot_id']} (batch {idx+1})")
            snapshot_jobs.append((idx, existing["snapshot_id"]))
        else:
            # Fresh trigger
            try:
                snapshot_id = trigger_snapshot(batch, dataset_id)
                # Save to checkpoint immediately so we can resume if we crash
                checkpoint[idx] = {"batch_idx": idx, "snapshot_id": snapshot_id, "saved": False, "output_file": None}
                save_checkpoint(platform, list(checkpoint.values()))
                snapshot_jobs.append((idx, snapshot_id))
            except Exception as e:
                print(f"  x {platform} batch {idx+1} trigger failed: {e}")

    if not snapshot_jobs:
        print(f"  All batches already saved. Nothing to do.")
        return already_saved

    print(f"  {len(snapshot_jobs)} snapshots in flight. Polling concurrently...")

    # ── Step 2: poll all concurrently ─────────────────────────────────────
    saved_files = list(already_saved)

    def fetch_and_save(batch_idx: int, snapshot_id: str) -> Path | None:
        label = f"{platform}[{batch_idx+1}/{len(all_batches)}]"
        try:
            records = poll_snapshot(snapshot_id, label=label)
            out = save_raw(records, platform, snapshot_id)
            mark_saved(platform, batch_idx, out)
            return out
        except Exception as e:
            print(f"  x {label} failed: {e}")
            return None

    with ThreadPoolExecutor(max_workers=min(MAX_CONCURRENT_POLLS, max(len(snapshot_jobs), 1))) as executor:
        futures = {
            executor.submit(fetch_and_save, idx, sid): (idx, sid)
            for idx, sid in snapshot_jobs
        }
        for future in tqdm(as_completed(futures), total=len(futures), desc=platform):
            result = future.result()
            if result:
                saved_files.append(result)

    total = len(all_batches)
    print(f"  {platform}: {len(saved_files)}/{total} batches saved.")
    return saved_files


# ─────────────────────────── CLI ───────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Collect AI citation data from multiple platforms via Bright Data."
    )
    parser.add_argument(
        "--platform",
        choices=list(PLATFORMS.keys()),
        help="Single platform to collect",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Collect all 5 platforms sequentially",
    )
    parser.add_argument("--queries", default="queries/queries.csv")
    parser.add_argument("--limit", type=int, default=None, help="Max queries per platform")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args = parser.parse_args()

    if not API_KEY or "your_" in API_KEY:
        print("ERROR: Set BRIGHTDATA_API_KEY in .env")
        sys.exit(1)

    if not args.platform and not args.all:
        parser.print_help()
        print("\nERROR: specify --platform <name> or --all")
        sys.exit(1)

    platforms_to_run = list(PLATFORMS.keys()) if args.all else [args.platform]
    all_files = []

    for platform in platforms_to_run:
        files = collect_platform(platform, args.queries, args.limit, args.batch_size)
        all_files.extend(files)

    print(f"\n{'='*60}")
    print(f"  Total snapshot files saved: {len(all_files)}")
    print(f"  Output directory: {RAW_DIR}/")
    print(f"  Next: python scripts/03_parse_text_fragments.py")


if __name__ == "__main__":
    main()
