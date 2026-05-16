"""
01_collect_ai_mode.py
=====================
Collect Google AI Mode responses via Bright Data's AI Mode Scraper.

Dataset ID : gd_mcswdt6z2elth3zqr2
Endpoint   : POST https://api.brightdata.com/datasets/v3/trigger
             GET  https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}

Usage:
    python scripts/01_collect_ai_mode.py
    python scripts/01_collect_ai_mode.py --queries queries/queries.csv --limit 50
    python scripts/01_collect_ai_mode.py --resume snapshots/pending.txt
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests

# Force UTF-8 stdout/stderr (Windows defaults to cp1252 when piped to Tee-Object,
# which crashes on '\u2192' arrows etc.)
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
from dotenv import load_dotenv
from tqdm import tqdm

# ─────────────────────────── Config ────────────────────────────────────────

load_dotenv()

API_KEY = os.environ.get("BRIGHTDATA_API_KEY", "")
DATASET_ID = os.environ.get("BRIGHTDATA_AI_MODE_DATASET_ID", "gd_mcswdt6z2elth3zqr2")
COUNTRY = os.environ.get("COUNTRY", "US")
TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", 120))
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", 10))
MAX_POLLS = int(os.environ.get("MAX_POLL_ATTEMPTS", 60))

RAW_DIR        = Path(os.environ.get("RAW_DATA_DIR", "data/raw"))
CHECKPOINT_DIR = RAW_DIR / "checkpoints"
RAW_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

TRIGGER_URL = "https://api.brightdata.com/datasets/v3/trigger"
SNAPSHOT_URL = "https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}"

BATCH_SIZE = 10          # queries per API call
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}


# ─────────────────────────── Helpers ───────────────────────────────────────

def check_api_key():
    if not API_KEY or API_KEY == "your_brightdata_api_key_here":
        print("ERROR: Set BRIGHTDATA_API_KEY in your .env file.")
        sys.exit(1)


def load_queries(csv_path: str, limit: int | None = None) -> list[dict]:
    df = pd.read_csv(csv_path)
    if limit:
        df = df.head(limit)
    queries = []
    for _, row in df.iterrows():
        queries.append({
            "url": "https://www.google.com/search?udm=50",
            "prompt": row["query"],
            "country": COUNTRY,
        })
    return queries


def trigger_snapshot(payload: list[dict]) -> str:
    """Trigger a Bright Data snapshot and return snapshot_id."""
    resp = requests.post(
        TRIGGER_URL,
        params={"dataset_id": DATASET_ID, "include_errors": "true"},
        headers=HEADERS,
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
    """Poll until snapshot is ready, then return records."""
    url = SNAPSHOT_URL.format(snapshot_id=snapshot_id)
    for attempt in range(1, MAX_POLLS + 1):
        time.sleep(POLL_INTERVAL)
        resp = requests.get(
            url,
            headers=HEADERS,
            params={"format": "json"},
            timeout=TIMEOUT,
        )
        if resp.status_code == 200:
            try:
                data = resp.json()
            except Exception:
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

CHECKPOINT_FILE = CHECKPOINT_DIR / "ai_mode_checkpoint.json"


def load_checkpoint() -> dict[int, dict]:
    """Returns {batch_idx: {snapshot_id, saved, output_file}}"""
    if CHECKPOINT_FILE.exists():
        data = json.loads(CHECKPOINT_FILE.read_text(encoding="utf-8"))
        return {b["batch_idx"]: b for b in data}
    return {}


def save_checkpoint(checkpoint: dict[int, dict]):
    CHECKPOINT_FILE.write_text(
        json.dumps(list(checkpoint.values()), indent=2), encoding="utf-8"
    )


def mark_saved(checkpoint: dict[int, dict], batch_idx: int, output_file: Path):
    checkpoint[batch_idx]["saved"] = True
    checkpoint[batch_idx]["output_file"] = str(output_file)
    save_checkpoint(checkpoint)


def save_raw(records: list[dict], snapshot_id: str):
    out_path = RAW_DIR / f"ai_mode_{snapshot_id}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"  ✓ Saved {len(records)} records → {out_path}")
    return out_path


def collect_all(queries: list[dict]) -> list[Path]:
    """Trigger all batches simultaneously, poll concurrently, resume on restart."""
    all_batches = [queries[i : i + BATCH_SIZE] for i in range(0, len(queries), BATCH_SIZE)]

    # ── Fast-path: all batches already on disk from a prior run ────────────
    existing_files = sorted(RAW_DIR.glob("ai_mode_*.json"))
    if len(existing_files) >= len(all_batches):
        print(f"  All {len(all_batches)} batches already on disk. Nothing to do.")
        return existing_files

    checkpoint  = load_checkpoint()

    already_saved = [
        Path(b["output_file"]) for b in checkpoint.values()
        if b.get("saved") and b.get("output_file") and Path(b["output_file"]).exists()
    ]
    if already_saved:
        print(f"  Resuming: {len(already_saved)}/{len(all_batches)} batches already saved.")

    # ── Step 1: trigger new batches or queue existing snapshot IDs ──────────
    snapshot_jobs: list[tuple[int, str]] = []
    for idx, batch in enumerate(all_batches):
        existing = checkpoint.get(idx, {})
        if existing.get("saved") and existing.get("output_file") and Path(existing["output_file"]).exists():
            continue
        if existing.get("snapshot_id"):
            print(f"  Retrying snapshot {existing['snapshot_id']} (batch {idx+1})")
            snapshot_jobs.append((idx, existing["snapshot_id"]))
        else:
            try:
                snapshot_id = trigger_snapshot(batch)
                checkpoint[idx] = {"batch_idx": idx, "snapshot_id": snapshot_id, "saved": False, "output_file": None}
                save_checkpoint(checkpoint)
                snapshot_jobs.append((idx, snapshot_id))
            except Exception as e:
                print(f"  x Batch {idx+1} trigger failed: {e}")

    if not snapshot_jobs:
        print("  All batches already saved.")
        return already_saved

    print(f"  {len(snapshot_jobs)} snapshots in flight. Polling concurrently...")
    saved_files = list(already_saved)

    # ── Step 2: poll all concurrently ───────────────────────────────────────
    def fetch_and_save(batch_idx: int, snapshot_id: str) -> Path | None:
        label = f"ai_mode[{batch_idx+1}/{len(all_batches)}]"
        try:
            records = poll_snapshot(snapshot_id, label=label)
            out = save_raw(records, snapshot_id)
            mark_saved(checkpoint, batch_idx, out)
            return out
        except Exception as e:
            print(f"  x Batch {batch_idx+1} ({snapshot_id}) failed: {e}")
            return None

    with ThreadPoolExecutor(max_workers=max(len(snapshot_jobs), 1)) as executor:
        futures = {
            executor.submit(fetch_and_save, idx, sid): (idx, sid)
            for idx, sid in snapshot_jobs
        }
        for future in tqdm(as_completed(futures), total=len(futures), desc="ai_mode"):
            result = future.result()
            if result:
                saved_files.append(result)

    return saved_files


# ─────────────────────────── CLI ───────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Collect Google AI Mode data via Bright Data.")
    parser.add_argument("--queries", default="queries/queries.csv", help="Path to queries CSV")
    parser.add_argument("--limit", type=int, default=None, help="Max queries to collect")
    args = parser.parse_args()

    check_api_key()

    print(f"Loading queries from {args.queries}...")
    queries = load_queries(args.queries, args.limit)
    print(f"Loaded {len(queries)} queries. Starting collection...\n")

    files = collect_all(queries)
    print(f"\nCollection complete. {len(files)} snapshot files written to {RAW_DIR}/")


if __name__ == "__main__":
    main()
