"""One-time TMDB enrichment: fetch poster_path for every movie with a tmdb_id.

Writes data/tmdb_posters.csv (tmdb_id, poster_path) -- gitignored external input,
same status as the MovieLens CSVs: a fresh clone re-fetches it (needs a TMDB key).
Resumable: ids already in the CSV are skipped, so an interrupted run continues
where it left off and a completed run is a no-op.

Distinguishes three outcomes:
- poster found      -> path written ("/abc.jpg")
- definitively none -> empty string written (TMDB 404 / no poster), cached
- transient failure -> NOT written, so the next run retries it

Usage:
    python fetch_posters.py          # reads TMDB_API_TOKEN from pipeline/.env or env
"""

import csv
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
LINKS_CSV = HERE.parent / "data" / "links.csv"
OUT_CSV = HERE.parent / "data" / "tmdb_posters.csv"
WORKERS = 8
THROTTLE_S = 0.25  # per-worker pause -> ~25 req/s total, polite


def load_token() -> str:
    if os.environ.get("TMDB_API_TOKEN"):
        return os.environ["TMDB_API_TOKEN"]
    env_file = HERE / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("TMDB_API_TOKEN="):
                return line.split("=", 1)[1].strip()
    sys.exit("TMDB_API_TOKEN not found (env var or pipeline/.env)")


def fetch_poster(tmdb_id: str, token: str) -> str | None:
    """Returns poster path, '' for definitively-no-poster, None for give-up (retry next run)."""
    req = Request(
        f"https://api.themoviedb.org/3/movie/{tmdb_id}",
        headers={"Authorization": f"Bearer {token}", "User-Agent": "givemore-pipeline"},
    )
    for attempt in range(4):
        try:
            with urlopen(req, timeout=20) as response:
                poster = json.load(response).get("poster_path")
                time.sleep(THROTTLE_S)
                return poster or ""
        except HTTPError as error:
            if error.code == 404:
                return ""  # stale tmdb id -> definitively no poster
            if error.code == 429:
                time.sleep(2 ** attempt)
                continue
            time.sleep(1 + attempt)
        except Exception:
            time.sleep(1 + attempt)
    return None


def main() -> None:
    token = load_token()

    with open(LINKS_CSV) as f:
        tmdb_ids = sorted({row["tmdbId"].strip() for row in csv.DictReader(f) if row["tmdbId"].strip()})

    done: set[str] = set()
    if OUT_CSV.exists():
        with open(OUT_CSV) as f:
            done = {row["tmdb_id"] for row in csv.DictReader(f)}

    todo = [t for t in tmdb_ids if t not in done]
    print(f"{len(tmdb_ids)} tmdb ids | {len(done)} cached | {len(todo)} to fetch")
    if not todo:
        print("nothing to do")
        return

    new_file = not OUT_CSV.exists()
    fetched = failed = 0
    with open(OUT_CSV, "a", newline="") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["tmdb_id", "poster_path"])
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = {pool.submit(fetch_poster, t, token): t for t in todo}
            for future in as_completed(futures):
                tmdb_id = futures[future]
                poster = future.result()
                if poster is None:
                    failed += 1
                    continue
                writer.writerow([tmdb_id, poster])
                fetched += 1
                if fetched % 500 == 0:
                    f.flush()
                    print(f"  {fetched}/{len(todo)} fetched...")

    print(f"done: {fetched} fetched, {failed} transient failures (re-run to retry)")
    with open(OUT_CSV) as f:
        rows = list(csv.DictReader(f))
    have = sum(1 for r in rows if r["poster_path"])
    print(f"coverage: {have}/{len(rows)} cached ids have a poster")


if __name__ == "__main__":
    main()
