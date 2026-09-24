# Nobel Prize Record

Independent archive of Nobel Prize records. It is not affiliated with, endorsed by, or sponsored by Nobel Prize Outreach or the Nobel Foundation.

The site lists prizes by subject, the official motivation for each award, laureate details published by the Nobel Prize API, and — where the nomination archive is open — the other people and organizations named on the official nomination list. Every row has a link back to nobelprize.org so it can be checked by hand.

GitHub Pages is served from the repository root: [https://buffedlizard55-lab.github.io/NOBEL-PRIZE/](https://buffedlizard55-lab.github.io/NOBEL-PRIZE/).

## What is verified, and what is not invented

- Prize rows, names, portions, amounts, dates, and motivations come from `https://api.nobelprize.org`. API v2 is preferred for the public name and motivation. API v1 is kept as a cross-check. Disagreements are flagged, not silently rewritten.
- “Why this project was chosen over others” is not published as a ranking. The stated reason is the official motivation. The nomination archive manual says nomination counts are not votes and are not a basis for selection.
- Other candidates are stored only after a nomination-archive list page is downloaded. If that page is missing, the prize links to the official list and says the names were not ingested. No nominee is guessed.
- Economic sciences is included and labeled as the Sveriges Riksbank Prize in Economic Sciences in Memory of Alfred Nobel. It is not one of the five prizes in Alfred Nobel’s 1895 will.
- 2026 prizes are omitted. On 24 September 2026 the official physics list said the 2026 physics prize had not been awarded and would be announced on 6 October 2026 at the earliest.

## Sources

- [API developer zone](https://www.nobelprize.org/about/developer-zone-2/)
- [API terms](https://www.nobelprize.org/about/terms-of-use-for-api-nobelprize-org-and-data-nobelprize-org/) — CC0, with the terms prevailing. Do not imply endorsement. Do not alter or censor the data.
- [Nobel Prize facts](https://www.nobelprize.org/prizes/facts/nobel-prize-facts/), retrieved 2026-09-24, used only as a cross-check (633 awarded prizes, 49 not-awarded occasions, 1,026 laureate slots).
- [Nomination archive](https://www.nobelprize.org/nomination/archive/) and its [manual](https://www.nobelprize.org/nomination/archive/manual.php).
- [Alfred Nobel’s will](https://www.nobelprize.org/alfred-nobel/full-text-of-alfred-nobels-will-2/). The 2018 English translation is linked, not copied in full.

## Review files

| File | What it is |
| --- | --- |
| `data/prizes.csv` | One prize per line, with official links |
| `data/laureates.csv` | One laureate record per line |
| `data/nominations.csv` | One stored nomination per line, when lists have been downloaded |
| `data/FLAGS.md` | Irregularities and scope notes for review |
| `data/catalog.json` | File the site loads |
| `data/verification-report.json` | Result of `scripts/verify_catalog.py` |

## Refresh the data

The sandbox that built this repository could not open TLS to `api.nobelprize.org`. Refresh from a network that can, or run the GitHub Actions workflow **Refresh official Nobel data**.

```bash
python scripts/fetch_official.py
python scripts/build_catalog.py
python scripts/verify_catalog.py
python -m unittest scripts/test_parser.py
```

`fetch_official.py` uses only the Python standard library. It pauses between nomination pages. Failed pages are recorded in `data/raw/fetch_manifest.json` and are not filled in.

## Known limits — next session

These are the gaps that still block a complete “who else was considered” answer. They should be worked in the next session, not papered over.

1. **Nomination detail pages are not bulk-copied.** The archive has on the order of 23,000 published nominations. This project stores list pages (nominee, nominator, official “Show” link) when the fetcher has run. It does not download each `show.php` motivation. Doing that would be a large, slow crawl and conflicts with the API terms’ request to avoid burdening the service. Next step: fetch detail pages in small, delayed batches, or ask the awarding institutions for a bulk export.
2. **Official nomination totals disagree.** On 2026-09-24 the archive homepage table said 23,141 nominations and the advanced search page said 23,983. Both numbers are kept and flagged. They need a human check with Nobel Prize Outreach. Do not average them.
3. **Medicine nominations stop at 1953** on the archive homepage, not at the 50-year line. Years 1954–1975 must not be filled from memory. After a fetch, compare those pages with the homepage statement.
4. **Economic sciences nominations are not in the public archive.** `list.php?prize=6&year=1969` returned 0 nominations, and the search form has no economics category. That zero is not evidence that nobody was nominated.
5. **The 50-year seal still covers 1976 onward**, as of the archive tables retrieved in September 2026. New years open on the archive’s own schedule, which can lag the seal.
6. **Physics and chemistry hide a nomination if a nominee is alive.** A laureate name missing from a list is flagged for review. It is not a finding that the person was not nominated.
7. **API prize status and the facts page do not always use the same word.** Boris Pasternak’s API `prizeStatus` is `restricted`. The facts page says he was coerced to decline. Jean-Paul Sartre’s API status is `declined`. Le Duc Tho’s facts pages use more than one wording for the same refusal. The archive shows both and does not collapse them.
8. **API v1 name order can differ from API v2.** Example checked on 24 September 2026: v1 lists the 2024 literature laureate as first name Kang, surname Han; the official list and API v2 use Han Kang. v2 is displayed. The difference is flagged when both files are present.
9. **2026 prizes** should be added only after the October 2026 announcements, by re-running the fetcher. Do not add them early.
10. **Adjusted prize amounts** are copied from `prizeAmountAdjusted` when API v2 is present. This project does not calculate its own inflation series.

## Local preview

```bash
python -m http.server 8000 --bind 0.0.0.0
```

Open the site root. Paths are relative so GitHub Pages project sites work without a custom base URL.
