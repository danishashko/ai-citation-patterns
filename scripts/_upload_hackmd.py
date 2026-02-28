"""
Upload article.md to HackMD with all images.

Workflow:
  1. Create a placeholder note via POST /v1/notes
  2. Upload each image via POST /v1/notes/{noteId}/images
  3. Rewrite image paths in the markdown to HackMD-hosted URLs
  4. Update the note content via PATCH /v1/notes/{noteId}
"""

import os
import re
import sys
import time
import requests

API_BASE = "https://api.hackmd.io/v1"
API_TOKEN = os.environ.get("HACKMD_API_TOKEN", "")

ARTICLE_PATH = "article/article.md"
REPORTS_DIR = "reports"

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
}


def create_note(title: str, content: str = "Uploading...") -> dict:
    """Create a new note, return the full response JSON."""
    resp = requests.post(
        f"{API_BASE}/notes",
        headers={**HEADERS, "Content-Type": "application/json"},
        json={
            "title": title,
            "content": content,
            "readPermission": "guest",
            "writePermission": "owner",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def upload_image(note_id: str, image_path: str) -> str:
    """Upload an image to a note, return the hosted URL."""
    with open(image_path, "rb") as f:
        resp = requests.post(
            f"{API_BASE}/notes/{note_id}/images",
            headers={"Authorization": f"Bearer {API_TOKEN}"},
            files={"image": (os.path.basename(image_path), f, "image/png")},
            timeout=60,
        )
    resp.raise_for_status()
    data = resp.json()
    return data["data"]["link"]


def update_note(note_id: str, content: str):
    """Update note content."""
    resp = requests.patch(
        f"{API_BASE}/notes/{note_id}",
        headers={**HEADERS, "Content-Type": "application/json"},
        json={"content": content},
        timeout=60,
    )
    resp.raise_for_status()
    # PATCH may return empty body (202) — that's fine
    if resp.text.strip():
        return resp.json()
    return {"status": resp.status_code}


def main():
    if not API_TOKEN:
        print("ERROR: Set HACKMD_API_TOKEN environment variable")
        sys.exit(1)

    # Verify API access
    print("Verifying API access...")
    me = requests.get(f"{API_BASE}/me", headers=HEADERS, timeout=15)
    me.raise_for_status()
    user = me.json()
    print(f"  Authenticated as: {user.get('name', 'unknown')} (@{user.get('userPath', '?')})")

    # Read article
    print("\nReading article...")
    with open(ARTICLE_PATH, "r", encoding="utf-8") as f:
        markdown = f.read()

    # Find all image references
    image_refs = re.findall(r'!\[([^\]]*)\]\((\.\./reports/[^)]+)\)', markdown)
    print(f"  Found {len(image_refs)} image references")

    # Step 1: Create note with placeholder
    print("\nCreating HackMD note...")
    note = create_note(
        title="How Google Actually Chooses Which Sentences to Cite in AI Mode",
        content="# Uploading article with images...\n\nPlease wait.",
    )
    note_id = note["id"]
    publish_link = note.get("publishLink", "")
    print(f"  Note ID: {note_id}")
    print(f"  Publish link: https://hackmd.io/{publish_link}")

    # Step 2: Upload each image
    print(f"\nUploading {len(image_refs)} images...")
    url_map = {}  # local_path -> hackmd_url
    for i, (alt_text, local_path) in enumerate(image_refs, 1):
        # Convert relative path from article/ to project root
        filename = local_path.replace("../reports/", "")
        abs_path = os.path.join(REPORTS_DIR, filename)

        if not os.path.exists(abs_path):
            print(f"  [{i}/{len(image_refs)}] MISSING: {abs_path}")
            continue

        print(f"  [{i}/{len(image_refs)}] Uploading {filename}...", end=" ", flush=True)
        try:
            hackmd_url = upload_image(note_id, abs_path)
            url_map[local_path] = hackmd_url
            print(f"OK -> {hackmd_url}")
        except Exception as e:
            print(f"FAILED: {e}")

        # Small delay to avoid rate limiting
        if i < len(image_refs):
            time.sleep(1)

    print(f"\n  Successfully uploaded {len(url_map)}/{len(image_refs)} images")

    # Step 3: Rewrite image paths
    print("\nRewriting image paths in markdown...")
    updated_markdown = markdown
    for local_path, hackmd_url in url_map.items():
        updated_markdown = updated_markdown.replace(local_path, hackmd_url)

    # Also fix mermaid diagrams — HackMD supports them natively
    # No changes needed for mermaid blocks

    # Step 4: Update note with final content
    print("Updating note with final content...")
    update_note(note_id, updated_markdown)
    print("  Done!")

    # Final output
    print("\n" + "=" * 60)
    print("HACKMD UPLOAD COMPLETE")
    print("=" * 60)
    print(f"  Note ID:      {note_id}")
    print(f"  Edit URL:     https://hackmd.io/{note_id}")
    print(f"  Publish URL:  https://hackmd.io/{publish_link}")
    print(f"  Images:       {len(url_map)}/{len(image_refs)} uploaded")
    print("=" * 60)


if __name__ == "__main__":
    main()
