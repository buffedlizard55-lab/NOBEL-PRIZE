#!/usr/bin/env python3
"""Check the catalog against structural rules and official cross-check figures.

A failing check means the downloaded files disagree with a rule or with an
official page retrieved on 2026-09-24. It does not authorize a silent fix.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from nobel_lib import (  # noqa: E402
    CATEGORIES,
    OFFICIAL_FACTS,
    UNAWARDED_YEARS,
    portion_value,
)

ROOT = Path(__file__).resolve().parents[1]


def add(problems, severity, code, message):
    problems.append({"severity": severity, "code": code, "message": message})


def verify(catalog):
    problems = []
    prizes = catalog.get("prizes") or []
    laureates = catalog.get("laureates") or []
    if not prizes:
        add(problems, "integrity", "empty_catalog", "Catalog has no prize records.")
        return problems

    keys = [prize["key"] for prize in prizes]
    if len(keys) != len(set(keys)):
        add(problems, "integrity", "duplicate_prize_key", "Prize keys are not unique.")
    ids = [person["id"] for person in laureates]
    if len(ids) != len(set(ids)):
        add(problems, "integrity", "duplicate_laureate_id", "Laureate ids are not unique.")

    years = {prize["year"] for prize in prizes}
    if any(year < 1901 or year > 2025 for year in years):
        add(problems, "integrity", "year_out_of_range", f"Years outside 1901–2025: {sorted(year for year in years if year < 1901 or year > 2025)}")
    if 2026 in years:
        add(problems, "integrity", "year_2026_present", "2026 prize records are present, but the official physics list page said that prize had not been awarded.")

    awarded_by_category = {key: 0 for key in CATEGORIES}
    slots_by_category = {key: 0 for key in CATEGORIES}
    unawarded = {key: [] for key in CATEGORIES}
    female_slots = 0
    org_ids = set()

    for prize in prizes:
        category = prize["category"]
        if category not in CATEGORIES:
            add(problems, "integrity", "unknown_category", f"Unknown category on {prize.get('key')}")
            continue
        if category == "economics" and prize["year"] < 1969:
            add(problems, "integrity", "economics_before_1969", f"Economic sciences record before 1969: {prize['key']}")
        if not prize.get("links", {}).get("summary") or not prize.get("links", {}).get("apiPrize"):
            add(problems, "integrity", "missing_official_link", f"{prize['key']} is missing an official link.")
        if prize["awarded"]:
            awarded_by_category[category] += 1
            slots_by_category[category] += len(prize["laureates"])
            if not prize["laureates"]:
                add(problems, "integrity", "awarded_without_laureates", prize["key"])
            if len(prize["laureates"]) > 3:
                add(problems, "integrity", "more_than_three", prize["key"])
            values = [portion_value(row.get("portion")) for row in prize["laureates"]]
            if any(value is None for value in values) or abs(sum(values) - 1) > 0.001:
                add(problems, "integrity", "bad_portions", f"{prize['key']} portions { [row.get('portion') for row in prize['laureates']] }")
            for row in prize["laureates"]:
                if not row.get("motivation"):
                    add(problems, "integrity", "missing_motivation", f"{prize['key']} laureate {row.get('id')}")
                if not row.get("displayName"):
                    add(problems, "integrity", "missing_name", f"{prize['key']} laureate {row.get('id')}")
                if not row.get("factsUrl"):
                    add(problems, "integrity", "missing_facts_url", f"{prize['key']} laureate {row.get('id')}")
        else:
            unawarded[category].append(prize["year"])
            if prize["laureates"]:
                add(problems, "integrity", "unawarded_has_laureates", prize["key"])

    people = {person["id"]: person for person in laureates}
    for person in laureates:
        if person.get("gender") == "female":
            female_slots += len(person.get("prizes") or [])
        if person.get("isOrganization"):
            org_ids.add(person["id"])

    for category, expected_years in UNAWARDED_YEARS.items():
        got = sorted(unawarded.get(category) or [])
        if got != sorted(expected_years):
            add(
                problems,
                "integrity",
                "unawarded_year_mismatch",
                f"{category} unawarded years in catalog {got} differ from the facts page list {sorted(expected_years)}.",
            )
        expected_awarded = OFFICIAL_FACTS["by_category"][category]["prizes"]
        if awarded_by_category[category] != expected_awarded:
            add(
                problems,
                "integrity",
                "awarded_count_mismatch",
                f"{category} awarded prizes: catalog {awarded_by_category[category]}, facts page {expected_awarded}.",
            )
        expected_slots = OFFICIAL_FACTS["by_category"][category]["slots"]
        if slots_by_category[category] != expected_slots:
            add(
                problems,
                "integrity",
                "slot_count_mismatch",
                f"{category} laureate slots: catalog {slots_by_category[category]}, facts page {expected_slots}.",
            )

    awarded_total = sum(awarded_by_category.values())
    if awarded_total != OFFICIAL_FACTS["awarded_prizes"]:
        add(problems, "integrity", "awarded_total_mismatch", f"Awarded prizes {awarded_total} != facts page {OFFICIAL_FACTS['awarded_prizes']}.")
    slot_total = sum(slots_by_category.values())
    if slot_total != OFFICIAL_FACTS["laureate_slots"]:
        add(problems, "integrity", "slot_total_mismatch", f"Laureate slots {slot_total} != facts page {OFFICIAL_FACTS['laureate_slots']}.")

    if female_slots != OFFICIAL_FACTS["prizes_to_women"]:
        add(
            problems,
            "review",
            "women_award_count_differs",
            f"Catalog has {female_slots} prize awards with gender female. The facts page says the prizes were awarded 68 times to women. This may be a definition difference. It is flagged, not corrected.",
        )
    if len(org_ids) != OFFICIAL_FACTS["organisations"]:
        add(
            problems,
            "review",
            "organisation_count_differs",
            f"Catalog classifies {len(org_ids)} laureate ids as organisations. The facts page says 28 organisations. Review the classification before treating either number as final.",
        )

    # Every facts-page repeat case we can check by year should exist.
    required = [
        ("physics", 1956, "Bardeen"),
        ("physics", 1972, "Bardeen"),
        ("chemistry", 1911, "Curie"),
        ("physics", 1903, "Curie"),
        ("chemistry", 1954, "Pauling"),
        ("peace", 1962, "Pauling"),
        ("chemistry", 1958, "Sanger"),
        ("chemistry", 1980, "Sanger"),
        ("chemistry", 2001, "Sharpless"),
        ("chemistry", 2022, "Sharpless"),
    ]
    for category, year, snippet in required:
        prize = next((item for item in prizes if item["category"] == category and item["year"] == year), None)
        names = " ".join(row.get("displayName") or "" for row in (prize or {}).get("laureates") or [])
        if prize is None or snippet.casefold() not in names.casefold():
            add(problems, "integrity", "facts_page_laureate_missing", f"Facts page names {snippet} for {category} {year}, but the catalog row does not.")

    return problems


def main():
    parser = argparse.ArgumentParser(description="Verify the Nobel Prize catalog")
    parser.add_argument("--catalog", default=str(ROOT / "data" / "catalog.json"))
    parser.add_argument("--report", default=str(ROOT / "data" / "verification-report.json"))
    args = parser.parse_args()
    catalog_path = Path(args.catalog)
    if not catalog_path.exists():
        report = {"ok": False, "problems": [{"severity": "integrity", "code": "missing_catalog", "message": f"{catalog_path} does not exist"}]}
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(report["problems"][0]["message"])
        return 1
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    problems = verify(catalog)
    integrity = [item for item in problems if item["severity"] == "integrity"]
    report = {
        "ok": not integrity,
        "integrityCount": len(integrity),
        "reviewCount": sum(1 for item in problems if item["severity"] == "review"),
        "problems": problems,
        "catalogCounts": catalog.get("meta", {}).get("counts"),
    }
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"integrity={report['integrityCount']} review={report['reviewCount']} ok={report['ok']}")
    for item in problems:
        print(f"- {item['severity']} {item['code']}: {item['message']}")
    return 1 if integrity else 0


if __name__ == "__main__":
    raise SystemExit(main())
