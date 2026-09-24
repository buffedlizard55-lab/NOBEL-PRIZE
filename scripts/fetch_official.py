#!/usr/bin/env python3
"""Download official Nobel Prize API responses and nomination-archive lists.

Run this on a network that can reach nobelprize.org. The sandbox used to build
this repository could not open TLS to api.nobelprize.org; GitHub Actions can.
The script does not fill gaps. Failed requests are recorded and skipped.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from nobel_lib import (  # noqa: E402
    API_V1_COUNTRIES,
    API_V1_LAUREATES,
    API_V1_PRIZES,
    API_V2_LAUREATES,
    API_V2_PRIZES,
    CATEGORIES,
    nomination_list_url,
    parse_nomination_list,
)

USER_AGENT = (
    "NOBEL-PRIZE-record/1.0 "
    "(independent archive; cites nobelprize.org; "
    "+https://github.com/buffedlizard55-lab/NOBEL-PRIZE)"
)
ROOT = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def http_get(url, timeout=90, attempts=4):
    last_error = None
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read()
                charset = response.headers.get_content_charset() or "utf-8"
                status = getattr(response, "status", 200)
                return payload, charset, status, None
        except urllib.error.HTTPError as exc:
            body = exc.read()
            last_error = f"HTTP {exc.code} for {url}"
            if exc.code in (429, 500, 502, 503, 504) and attempt < attempts:
                time.sleep(min(20, 2 ** attempt))
                continue
            return body, "utf-8", exc.code, last_error
        except Exception as exc:  # network errors should be recorded, not invented around
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < attempts:
                time.sleep(min(20, 2 ** attempt))
                continue
    return b"", "utf-8", None, last_error


def decode(payload, charset):
    for encoding in (charset, "utf-8", "iso-8859-1"):
        if not encoding:
            continue
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="replace")


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_json_url(url):
    payload, charset, status, error = http_get(url)
    text = decode(payload, charset) if payload else ""
    body = None
    if not error:
        try:
            body = json.loads(text)
        except json.JSONDecodeError as exc:
            error = f"JSON decode failed for {url}: {exc}"
    return {
        "url": url,
        "retrievedAt": now(),
        "status": status,
        "error": error,
        "body": body,
    }


def fetch_paged(base_url, list_key, limit=500):
    offset = 0
    pages = []
    items = []
    total = None
    while True:
        joiner = "&" if "?" in base_url else "?"
        url = f"{base_url}{joiner}limit={limit}&offset={offset}"
        page = fetch_json_url(url)
        pages.append({key: page[key] for key in ("url", "retrievedAt", "status", "error")})
        if page["error"] or not isinstance(page["body"], dict):
            return {"pages": pages, "items": items, "total": total, "error": page["error"] or "empty body"}
        batch = page["body"].get(list_key) or []
        meta = page["body"].get("meta") or {}
        total = meta.get("count", total)
        items.extend(batch)
        print(f"  {list_key} offset {offset}: {len(batch)} rows, meta.count={total}", flush=True)
        if not batch:
            break
        offset += limit
        if total is not None and offset >= int(total):
            break
        if offset > 5000:
            return {"pages": pages, "items": items, "total": total, "error": "pagination guard tripped"}
        time.sleep(0.2)
    error = None
    if total is not None and len(items) != int(total):
        error = f"downloaded {len(items)} {list_key} but meta.count is {total}"
    return {"pages": pages, "items": items, "total": total, "error": error, "retrievedAt": now()}


def fetch_nomination_pages(out_dir: Path, delay: float):
    results = []
    targets = []
    for category, meta in CATEGORIES.items():
        if category == "economics":
            # Document the empty public page. Do not treat zero as a real nominee list.
            targets.append((category, 1969, True))
            continue
        # Fetch through 1975 even for medicine, so the homepage's 1953 cutoff can be checked.
        for year in range(1901, 1976):
            targets.append((category, year, False))

    for index, (category, year, economics_probe) in enumerate(targets, start=1):
        url = nomination_list_url(category, year)
        print(f"[{index}/{len(targets)}] {category} {year}", flush=True)
        payload, charset, status, error = http_get(url, timeout=60)
        html = decode(payload, charset) if payload else ""
        parsed = None
        if not error and html:
            parsed = parse_nomination_list(html, url)
            parsed["retrievedAt"] = now()
            parsed["httpStatus"] = status
            parsed["category"] = category
            parsed["year"] = year
            parsed["economicsProbe"] = economics_probe
        record = {
            "category": category,
            "year": year,
            "url": url,
            "retrievedAt": now(),
            "httpStatus": status,
            "error": error,
            "statedCount": None if not parsed else parsed.get("statedCount"),
            "parsedCount": None if not parsed else parsed.get("parsedCount"),
            "countMatchesStated": None if not parsed else parsed.get("countMatchesStated"),
        }
        html_path = out_dir / "nomination_html" / f"{category}-{year}.html"
        json_path = out_dir / "nominations" / category / f"{year}.json"
        keep_html = error is not None or parsed is None or not parsed.get("countMatchesStated")
        if year in (1901, 1975) or economics_probe:
            keep_html = True
        if keep_html and html:
            html_path.parent.mkdir(parents=True, exist_ok=True)
            html_path.write_text(html, encoding="utf-8")
            record["htmlFile"] = str(html_path)
        if parsed is not None:
            write_json(json_path, parsed)
            record["file"] = str(json_path)
        results.append(record)
        time.sleep(delay)
    return results


def main():
    parser = argparse.ArgumentParser(description="Download official Nobel Prize sources")
    parser.add_argument("--out", default=str(ROOT / "data" / "raw"))
    parser.add_argument("--delay", type=float, default=0.35, help="Seconds between nomination pages")
    parser.add_argument("--skip-nominations", action="store_true")
    parser.add_argument("--nominations-only", action="store_true")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    errors = []

    if not args.nominations_only:
        singles = {
            "v1_prize.json": API_V1_PRIZES,
            "v1_laureate.json": API_V1_LAUREATES,
            "v1_country.json": API_V1_COUNTRIES,
        }
        for name, url in singles.items():
            print(f"Fetching {url}", flush=True)
            record = fetch_json_url(url)
            write_json(out / name, record)
            if record["error"]:
                errors.append(record["error"])
                print(f"  ERROR {record['error']}", flush=True)
            else:
                key = "prizes" if "prize" in name else "laureates" if "laureate" in name else "countries"
                body = record["body"] or {}
                print(f"  saved {name}: {len(body.get(key, []))} rows", flush=True)

        print(f"Fetching {API_V2_PRIZES}", flush=True)
        prizes = fetch_paged(API_V2_PRIZES, "nobelPrizes", limit=200)
        write_json(out / "v2_prizes.json", prizes)
        if prizes.get("error"):
            errors.append(prizes["error"])
            print(f"  ERROR {prizes['error']}", flush=True)

        print(f"Fetching {API_V2_LAUREATES}", flush=True)
        laureates = fetch_paged(API_V2_LAUREATES, "laureates", limit=200)
        write_json(out / "v2_laureates.json", laureates)
        if laureates.get("error"):
            errors.append(laureates["error"])
            print(f"  ERROR {laureates['error']}", flush=True)

    nomination_log = []
    if not args.skip_nominations:
        nomination_log = fetch_nomination_pages(out, args.delay)
        for row in nomination_log:
            if row.get("error") or row.get("countMatchesStated") is False:
                errors.append(
                    f"{row['category']} {row['year']}: error={row.get('error')} "
                    f"stated={row.get('statedCount')} parsed={row.get('parsedCount')}"
                )

    manifest = {
        "retrievedAt": now(),
        "errors": errors,
        "nominationPages": [
            {key: row.get(key) for key in ("category", "year", "url", "httpStatus", "error", "statedCount", "parsedCount", "countMatchesStated")}
            for row in nomination_log
        ],
        "categories": {key: {"nom_prize": value["nom_prize"]} for key, value in CATEGORIES.items()},
    }
    write_json(out / "fetch_manifest.json", manifest)
    print(f"Finished with {len(errors)} recorded problems.", flush=True)
    if errors:
        print("Problems are recorded in data/raw/fetch_manifest.json. Missing rows were not invented.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
