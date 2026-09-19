#!/usr/bin/env python3
"""
Dead-link pruning pass (plans/improvements_audit.md, §4 "Dead-link pruning").

Checks each video's source URL and flags ones that look removed/dead, so
they can be reviewed and blacklisted. Does NOT touch blacklist.txt by
default — it only writes a report. Pass --apply to append confirmed-dead
viewkeys to blacklist.txt directly (still asks for confirmation first,
unless --yes is also given).

This makes real HTTP requests to the source sites (Pornhub / xHamster) for
every video in videos.json (8,000+ as of 2026-08-03) — expect it to take a
while even with concurrency, and don't run it constantly; the sites can
rate-limit or temporarily block an IP that hammers them.

Usage:
    python scratch/find_dead_links.py                  # dry run, writes a report
    python scratch/find_dead_links.py --sample 20       # only check the first 20 (for testing)
    python scratch/find_dead_links.py --apply           # also blacklist confirmed-dead viewkeys (asks first)
    python scratch/find_dead_links.py --apply --yes     # ...without asking
    python scratch/find_dead_links.py --workers 5        # lower concurrency if you're getting blocked
"""
import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from curl_cffi import requests

VIDEOS_FILE = "videos.json"
BLACKLIST_FILE = "blacklist.txt"
REPORT_FILE = os.path.join("scratch", "dead_links_report.json")

# Status codes that unambiguously mean "gone" regardless of body content.
DEAD_STATUS_CODES = {404, 410}

# Both Pornhub and xHamster return HTTP 200 for a "this video was removed"
# page rather than a real 404 — the page has to be sniffed for a marker
# phrase. Keep this list conservative (exact, lowercase phrases) to avoid
# false positives on videos that just mention "removed" in a title/comment.
REMOVAL_MARKERS = [
    "this video has been removed",
    "video has been deleted",
    "this video is currently unavailable",
    "the page you are looking for could not be found",
    "video not found",
    "this video was deleted",
]

REQUEST_TIMEOUT = 15


def check_url(url):
    """Returns (status, detail) where status is one of: 'ok', 'dead', 'suspicious', 'error'."""
    try:
        res = requests.get(url, impersonate="chrome", timeout=REQUEST_TIMEOUT, allow_redirects=True)
    except Exception as e:
        return "error", str(e)

    if res.status_code in DEAD_STATUS_CODES:
        return "dead", f"HTTP {res.status_code}"

    if res.status_code >= 400:
        return "suspicious", f"HTTP {res.status_code}"

    body_lower = res.text.lower() if res.text else ""
    for marker in REMOVAL_MARKERS:
        if marker in body_lower:
            return "dead", f"removal marker: \"{marker}\""

    return "ok", f"HTTP {res.status_code}"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sample", type=int, default=None, help="Only check the first N videos (for testing)")
    parser.add_argument("--workers", type=int, default=8, help="Concurrent requests (default 8 — keep modest)")
    parser.add_argument("--apply", action="store_true", help="Append confirmed-dead viewkeys to blacklist.txt")
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt for --apply")
    args = parser.parse_args()

    if not os.path.exists(VIDEOS_FILE):
        print(f"ERROR: {VIDEOS_FILE} not found. Run this from the project root.")
        sys.exit(1)

    with open(VIDEOS_FILE, "r", encoding="utf-8") as f:
        videos = json.load(f)

    existing_blacklist = set()
    if os.path.exists(BLACKLIST_FILE):
        with open(BLACKLIST_FILE, "r", encoding="utf-8") as f:
            existing_blacklist = {line.strip() for line in f if line.strip()}

    candidates = [v for v in videos if v["viewkey"] not in existing_blacklist]
    if args.sample:
        candidates = candidates[: args.sample]

    print(f"Checking {len(candidates)} videos ({args.workers} concurrent workers)...")
    print("This makes real requests to the source sites — expect it to take a while.\n")

    results = {"dead": [], "suspicious": [], "error": [], "ok_count": 0}
    t0 = time.time()
    checked = 0

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(check_url, v["url"]): v for v in candidates}
        for future in as_completed(futures):
            vid = futures[future]
            status, detail = future.result()
            checked += 1
            if status == "ok":
                results["ok_count"] += 1
            else:
                results[status].append({"viewkey": vid["viewkey"], "title": vid["title"], "url": vid["url"], "detail": detail})
            if checked % 100 == 0 or checked == len(candidates):
                elapsed = time.time() - t0
                print(f"  {checked}/{len(candidates)} checked ({elapsed:.0f}s elapsed)")

    os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"OK:          {results['ok_count']}")
    print(f"Dead:        {len(results['dead'])}  (confirmed removed/404 — safe to blacklist)")
    print(f"Suspicious:  {len(results['suspicious'])}  (non-200, not confirmed dead — review manually)")
    print(f"Errors:      {len(results['error'])}  (network/timeout issues — inconclusive, not necessarily dead)")
    print(f"Report written to {REPORT_FILE}")
    print(f"{'='*60}")

    if args.apply and results["dead"]:
        dead_viewkeys = [d["viewkey"] for d in results["dead"]]
        if not args.yes:
            resp = input(f"\nAppend {len(dead_viewkeys)} confirmed-dead viewkeys to {BLACKLIST_FILE}? [y/N] ")
            if resp.strip().lower() != "y":
                print("Skipped — nothing written to blacklist.txt.")
                return
        merged = sorted(existing_blacklist | set(dead_viewkeys))
        with open(BLACKLIST_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(merged) + "\n")
        print(f"Appended {len(dead_viewkeys)} viewkeys to {BLACKLIST_FILE}.")


if __name__ == "__main__":
    main()
