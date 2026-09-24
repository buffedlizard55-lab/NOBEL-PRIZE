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

## What this build checked

Retrieved 2026-09-24 from the official API and nomination archive:

- 682 prize records: 633 awarded and 49 not awarded. That matches the facts page.
- 1,018 laureate records and 1,026 award slots. That matches the facts page.
- 68 prize awards recorded as female, and 28 organisation records. That matches the facts page.
- Repeated laureates in the download: Marie Curie, John Bardeen, Linus Pauling, Frederick Sanger, K. Barry Sharpless, the International Committee of the Red Cross, and the Office of the United Nations High Commissioner for Refugees.
- API prize status is `declined` for Jean-Paul Sartre and Le Duc Tho, and `restricted` for Boris Pasternak. Those words are shown as published.
- 2025 is included. 2026 is not.

## Known limits — next session

1. **Nomination detail pages are not bulk-copied.** List pages are stored: nominee, nominator, and the official Show link. Each `show.php` motivation is linked, not copied. A full crawl would be large and would burden the service. Next step: small delayed batches, or a bulk export from the awarding institutions.
2. **Official nomination totals disagree.** On 2026-09-24 the archive homepage table said 23,141 nominations and the advanced search page said 23,983. Both numbers are kept. Do not average them.
3. **Medicine list pages disagree with their own counts.** For 45 medicine years, mostly 1901–1946, the page says more nominations than it contains Show links. Every linked row is stored. The missing rows are not in the HTML and were not invented. Saved copies of those pages are in `data/raw/nomination_html/`.
4. **Medicine nominations stop at 1953** on the archive homepage. The 1954–1975 list pages returned 0. That zero is flagged. It is not a complete candidate list.
5. **Economic sciences nominations are not in the public archive.** `list.php?prize=6&year=1969` returned 0, and the search form has no economics category. That zero is not evidence that nobody was nominated.
6. **The 50-year seal still covers 1976 onward**, as of the archive tables retrieved in September 2026.
7. **Some laureate names are not on that year’s stored list.** Examples kept as flags, not corrections: Richard Kuhn is absent from the 1938 chemistry list and present in other chemistry years; Albert Lutuli is absent from 1960 peace and present in 1961 as Albert Luthuli. Those rows were not moved. Physics and chemistry can also omit a nomination while a nominee is alive.
8. **Spellings differ.** The list may use a longer name, a diacritic, or a near spelling (`Eisako Sato` for Eisaku Satō, `Aleksandr Solzjenitsyn` for Aleksandr Solzhenitsyn). The API name is displayed. The list spelling is shown beside it and was not rewritten.
9. **API prize status and the facts page do not always use the same word.** Pasternak’s API status is `restricted`. The facts page says he was coerced to decline. Kuhn, Butenandt, and Domagk are `received` in the API; the facts page says they were forced to decline and could later receive the diploma and medal, but not the prize amount. Both are kept.
10. **API v1 name order can differ from API v2.** Example: v1 lists the 2024 literature laureate as Kang Han; v2 and the official list use Han Kang. v2 is displayed. The difference is flagged.
11. **2026 prizes** should be added only after the October 2026 announcements, by re-running the fetcher.
12. **Adjusted prize amounts** are copied from `prizeAmountAdjusted`. This project does not calculate its own inflation series.

## Local preview

```bash
python -m http.server 8000 --bind 0.0.0.0
```

Open the site root. Paths are relative so GitHub Pages project sites work without a custom base URL.
