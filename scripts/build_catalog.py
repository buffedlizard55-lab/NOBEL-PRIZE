#!/usr/bin/env python3
"""Build the review catalog from downloaded official responses.

No prize, laureate, motivation, or nominee is added unless it is present in
those files. Missing files produce an explicit gap, not a guessed row.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from nobel_lib import (  # noqa: E402
    ARCHIVE_HOME,
    ARCHIVE_MANUAL,
    ARCHIVE_SEARCH,
    ARCHIVE_STATED_TOTALS,
    CATEGORIES,
    DEVELOPER_URL,
    FACTS_URL,
    PHYSICS_LIST_URL,
    SOURCED_NOTES,
    STATUTES_URL,
    TERMS_URL,
    V2_CATEGORY_EN,
    WILL_URL,
    archive_status_for,
    clean_motivation,
    clean_ws,
    en,
    fold,
    laureate_api_url,
    laureate_facts_url,
    name_match_level,
    nomination_list_url,
    portion_from_share,
    portion_value,
    prize_api_url,
    summary_url,
    texts_equivalent,
)

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj, pretty=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    if pretty:
        text = json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
    else:
        text = json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n"
    path.write_text(text, encoding="utf-8")


def v1_laureate_name(row):
    parts = [clean_ws(row.get("firstname")), clean_ws(row.get("surname"))]
    parts = [part for part in parts if part]
    return " ".join(parts) if parts else None


def affiliation_label(item):
    if not isinstance(item, dict):
        return None
    if "name" in item and not isinstance(item.get("name"), dict):
        parts = [clean_ws(item.get("name")), clean_ws(item.get("city")), clean_ws(item.get("country"))]
    else:
        parts = [en(item.get("name")), en(item.get("city")), en(item.get("country"))]
    parts = [part for part in parts if part]
    return ", ".join(parts) if parts else None


def place_label(place):
    if not isinstance(place, dict):
        return None
    label = en((place.get("locationString") if isinstance(place.get("locationString"), dict) else None))
    if label:
        return label
    city = en(place.get("city"))
    country = en(place.get("country"))
    parts = [part for part in (city, country) if part]
    return ", ".join(parts) if parts else None


def external_href(links, class_name):
    for link in links or []:
        if link.get("rel") != "external":
            continue
        classes = link.get("class") or []
        if class_name in classes and link.get("href"):
            return link["href"]
    return None


def index_v1_laureates(raw):
    body = (raw or {}).get("body") or {}
    rows = body.get("laureates") or []
    return {str(row.get("id")): row for row in rows if row.get("id") is not None}


def index_v2_laureates(raw):
    items = (raw or {}).get("items") or []
    return {str(row.get("id")): row for row in items if row.get("id") is not None}


def v2_prize_index(raw):
    prizes = {}
    for prize in (raw or {}).get("items") or []:
        year = prize.get("awardYear")
        category = V2_CATEGORY_EN.get(en(prize.get("category")))
        if not year or not category:
            continue
        prizes[(int(year), category)] = prize
    return prizes


def v1_prize_index(raw):
    prizes = {}
    for prize in ((raw or {}).get("body") or {}).get("prizes") or []:
        year = prize.get("year")
        category = prize.get("category")
        if year and category in CATEGORIES:
            prizes[(int(year), category)] = prize
    return prizes


def load_nomination(raw_dir: Path, category, year):
    path = raw_dir / "nominations" / category / f"{year}.json"
    if not path.exists():
        return None
    return load_json(path)


def unique_nominees(parsed):
    seen = {}
    for nomination in (parsed or {}).get("nominations") or []:
        for person in nomination.get("nominees") or []:
            key = person.get("personId") or fold(person.get("name"))
            if not key:
                continue
            slot = seen.setdefault(
                key,
                {
                    "name": person.get("name"),
                    "personId": person.get("personId"),
                    "url": person.get("url"),
                    "nominations": 0,
                },
            )
            slot["nominations"] += 1
    return sorted(seen.values(), key=lambda item: (item["name"] or "").casefold())


def flag(flags, code, severity, message, **extra):
    item = {"code": code, "severity": severity, "message": message}
    item.update({key: value for key, value in extra.items() if value is not None})
    flags.append(item)
    return item


def build(raw_dir: Path, out_dir: Path):
    v1_prizes = v1_prize_index(load_json(raw_dir / "v1_prize.json"))
    v2_prizes = v2_prize_index(load_json(raw_dir / "v2_prizes.json"))
    v1_people = index_v1_laureates(load_json(raw_dir / "v1_laureate.json"))
    v2_people = index_v2_laureates(load_json(raw_dir / "v2_laureates.json"))
    fetch_manifest = load_json(raw_dir / "fetch_manifest.json") or {}

    keys = set(v1_prizes) | set(v2_prizes)
    prizes = []
    laureates = {}
    flags = []
    nomination_rows = []

    if not v2_prizes:
        flag(
            flags,
            "v2_prizes_missing",
            "integrity",
            "data/raw/v2_prizes.json is missing or empty. Unawarded years and prize amounts cannot be verified from the v2 prize endpoint until it is downloaded.",
        )
    if not v2_people:
        flag(
            flags,
            "v2_laureates_missing",
            "integrity",
            "data/raw/v2_laureates.json is missing or empty. Prize status, official known names, and affiliations from the laureate endpoint are not in this build.",
        )

    for year, category in sorted(keys, key=lambda item: (item[0], item[1]), reverse=True):
        v2 = v2_prizes.get((year, category))
        v1 = v1_prizes.get((year, category))
        meta = CATEGORIES[category]
        key = f"{category}-{year}"
        prize_flags = []
        v2_laureates = (v2 or {}).get("laureates") or []
        v1_laureates = (v1 or {}).get("laureates") or []
        awarded = bool(v2_laureates or v1_laureates)
        if v2 and "laureates" not in v2 and not v1_laureates:
            awarded = False
        overall = clean_motivation(en((v2 or {}).get("topMotivation"))) or clean_motivation((v1 or {}).get("overallMotivation"))
        date_awarded = (v2 or {}).get("dateAwarded")
        amount = (v2 or {}).get("prizeAmount")
        amount_adjusted = (v2 or {}).get("prizeAmountAdjusted")
        if not meta["in_will"]:
            flag(
                prize_flags,
                "not_in_alfred_nobels_will",
                "info",
                "This is The Sveriges Riksbank Prize in Economic Sciences in Memory of Alfred Nobel. It was established by Sveriges Riksbank in 1968. It is not one of the five prizes in Alfred Nobel's 1895 will.",
                prizeKey=key,
                sources=[FACTS_URL, WILL_URL],
            )
        if not awarded:
            flag(
                prize_flags,
                "prize_not_awarded",
                "info",
                overall or "The official prize record has no laureates for this year and category.",
                prizeKey=key,
                sources=[summary_url(category, year), prize_api_url(category, year)],
            )

        parsed_nom = load_nomination(raw_dir, category, year)
        ingested = parsed_nom is not None and not parsed_nom.get("error")
        nom_status = archive_status_for(category, year, ingested and category != "economics")
        if category == "economics":
            nom_status = "not_in_public_archive"
        if ingested and category != "economics" and parsed_nom.get("countMatchesStated") is False:
            nom_status = "parse_count_mismatch"
            flag(
                prize_flags,
                "nomination_parse_count_mismatch",
                "integrity",
                f"Official list page says {parsed_nom.get('statedCount')} nominations; the parser stored {parsed_nom.get('parsedCount')}. The page is linked for manual review. Missing names were not filled in.",
                prizeKey=key,
                sources=[nomination_list_url(category, year)],
            )
        if category == "medicine" and year > 1953 and parsed_nom and parsed_nom.get("statedCount") == 0:
            nom_status = "not_released_by_awarding_institution"
            flag(
                prize_flags,
                "medicine_page_returned_zero",
                "review",
                "The downloaded medicine list page says 0 nominations. The archive homepage says this category is published only through 1953. Zero is not treated as a complete candidate list.",
                prizeKey=key,
                sources=[nomination_list_url(category, year), ARCHIVE_HOME],
            )
        if ingested and parsed_nom and parsed_nom.get("statedCount") == 0 and nom_status == "ingested":
            flag(
                prize_flags,
                "official_list_says_zero_nominations",
                "review",
                "The official list page says 0 nominations for a year inside the published window. The zero is kept as published and flagged for review. It is not treated as proof that nobody was considered.",
                prizeKey=key,
                sources=[nomination_list_url(category, year)],
            )
        if nom_status == "not_ingested":
            flag(
                prize_flags,
                "nomination_list_not_ingested",
                "review",
                "This year is inside the published nomination-archive window, but the list page was not stored in this build. Use the official list link. Do not infer nominees.",
                prizeKey=key,
                sources=[nomination_list_url(category, year), ARCHIVE_HOME],
            )
        if nom_status == "not_released_by_awarding_institution":
            flag(
                prize_flags,
                "medicine_nominations_not_released",
                "info",
                "The nomination archive homepage says physiology or medicine data is available only through 1953. No nominee names are invented for this year.",
                prizeKey=key,
                sources=[ARCHIVE_HOME],
            )
        if nom_status == "sealed_or_not_published":
            flag(
                prize_flags,
                "nominations_sealed",
                "info",
                "Nominations are not published until 50 years have elapsed, and the archive homepage's current tables stop at 1975 (medicine at 1953). Names of other candidates are not known to this archive.",
                prizeKey=key,
                sources=[ARCHIVE_HOME, ARCHIVE_MANUAL],
            )

        laureate_rows = []
        seen_ids = set()
        ordered_ids = []
        for source_row in v2_laureates:
            laureate_id = str(source_row.get("id"))
            if laureate_id and laureate_id not in seen_ids:
                seen_ids.add(laureate_id)
                ordered_ids.append(("v2", source_row))
        for source_row in v1_laureates:
            laureate_id = str(source_row.get("id"))
            if laureate_id and laureate_id not in seen_ids:
                seen_ids.add(laureate_id)
                ordered_ids.append(("v1-only", source_row))
                flag(
                    prize_flags,
                    "laureate_missing_from_v2_prize",
                    "review",
                    f"Laureate {laureate_id} is in the v1 prize file but not in the v2 prize file for this year.",
                    prizeKey=key,
                    laureateId=laureate_id,
                )

        for source_name, source_row in ordered_ids:
            laureate_id = str(source_row.get("id"))
            v2_person = v2_people.get(laureate_id) or {}
            v1_person = v1_people.get(laureate_id) or {}
            v2_award = None
            for award in v2_person.get("nobelPrizes") or []:
                award_category = V2_CATEGORY_EN.get(en(award.get("category")))
                if award_category == category and str(award.get("awardYear")) == str(year):
                    v2_award = award
                    break
            v1_award = None
            for award in v1_person.get("prizes") or []:
                if award.get("category") == category and str(award.get("year")) == str(year):
                    v1_award = award
                    break
            if source_name == "v2":
                v1_match = next((row for row in v1_laureates if str(row.get("id")) == laureate_id), None)
            else:
                v1_match = source_row

            known = en(v2_person.get("knownName")) or en(source_row.get("knownName")) or en(v2_person.get("orgName")) or en(source_row.get("orgName"))
            full = en(v2_person.get("fullName")) or en(source_row.get("fullName"))
            v1_name = v1_laureate_name(v1_person) or (v1_laureate_name(v1_match) if v1_match else None)
            raw_name = known or full or v1_name
            display = clean_ws(raw_name)
            if raw_name and raw_name != raw_name.strip():
                flag(
                    prize_flags,
                    "api_trailing_whitespace_in_name",
                    "review",
                    f"The official API name for laureate {laureate_id} contains leading or trailing whitespace. Display name is stripped; the raw value is kept.",
                    prizeKey=key,
                    laureateId=laureate_id,
                    raw=raw_name,
                )
            if known and v1_name and fold(known) != fold(v1_name):
                flag(
                    prize_flags,
                    "v1_v2_name_differs",
                    "review",
                    f"API v2 known/org name is “{known}”. API v1 name is “{v1_name}”. The v2 name is displayed. Neither was rewritten.",
                    prizeKey=key,
                    laureateId=laureate_id,
                    sources=[laureate_api_url(laureate_id), "https://api.nobelprize.org/v1/laureate.json"],
                )

            motivation = clean_motivation(en((v2_award or source_row).get("motivation"))) or clean_motivation((v1_match or {}).get("motivation")) or clean_motivation((v1_award or {}).get("motivation"))
            v1_motivation = clean_motivation((v1_match or {}).get("motivation")) or clean_motivation((v1_award or {}).get("motivation"))
            v2_motivation = clean_motivation(en((v2_award or source_row).get("motivation")))
            if v1_motivation and v2_motivation and not texts_equivalent(v1_motivation, v2_motivation):
                flag(
                    prize_flags,
                    "v1_v2_motivation_differs",
                    "review",
                    "The English motivation in API v1 and API v2 do not match after quote and whitespace cleanup. API v2 is displayed.",
                    prizeKey=key,
                    laureateId=laureate_id,
                    v1=v1_motivation,
                    v2=v2_motivation,
                )
            if awarded and not motivation:
                flag(
                    prize_flags,
                    "missing_motivation",
                    "integrity",
                    f"No official motivation text was found for laureate {laureate_id}.",
                    prizeKey=key,
                    laureateId=laureate_id,
                )

            portion = (v2_award or source_row).get("portion") or portion_from_share((v1_match or {}).get("share")) or portion_from_share((v1_award or {}).get("share"))
            status = (v2_award or {}).get("prizeStatus")
            if v2_people and status is None and awarded:
                flag(
                    prize_flags,
                    "prize_status_missing",
                    "review",
                    f"No prizeStatus field was found on the v2 laureate record for {laureate_id} in {year} {category}.",
                    prizeKey=key,
                    laureateId=laureate_id,
                    sources=[laureate_api_url(laureate_id)],
                )
            if status and status != "received":
                flag(
                    prize_flags,
                    "prize_status_not_received",
                    "review",
                    f"Official API prizeStatus is “{status}”. This archive does not translate that word.",
                    prizeKey=key,
                    laureateId=laureate_id,
                    sources=[laureate_api_url(laureate_id)],
                )

            org_name = en(v2_person.get("orgName")) or en(source_row.get("orgName"))
            gender = v2_person.get("gender") or v1_person.get("gender")
            birth = v2_person.get("birth") if isinstance(v2_person.get("birth"), dict) else {}
            death = v2_person.get("death") if isinstance(v2_person.get("death"), dict) else {}
            birth_date = birth.get("date") or v1_person.get("born")
            death_date = death.get("date") or v1_person.get("died")
            if death_date in ("0000-00-00", "0000"):
                death_date = None
            if birth_date in ("0000-00-00", "0000"):
                birth_date = None
            is_org = bool(org_name) or (not gender and not birth_date and not en(v2_person.get("familyName")) and not v1_person.get("surname") and not v1_person.get("born"))
            if is_org and not org_name:
                flag(
                    prize_flags,
                    "organization_classification_heuristic",
                    "review",
                    f"Laureate {laureate_id} has no orgName field but also lacks a family name, gender, and birth date. Classified as an organization for filtering only. Review the official record.",
                    prizeKey=key,
                    laureateId=laureate_id,
                    sources=[laureate_facts_url(laureate_id)],
                )

            affiliations = []
            raw_affiliations = (v2_award or {}).get("affiliations")
            if raw_affiliations is None:
                raw_affiliations = (v1_award or {}).get("affiliations") or []
            if isinstance(raw_affiliations, dict):
                raw_affiliations = [raw_affiliations]
            for item in raw_affiliations or []:
                if item in ([], {}):
                    flag(prize_flags, "empty_affiliation_object", "review", f"Empty affiliation object for laureate {laureate_id}.", prizeKey=key, laureateId=laureate_id)
                    continue
                label = affiliation_label(item)
                if label:
                    affiliations.append(label)

            facts = external_href((v2_award or {}).get("links"), "laureate facts") or external_href(v2_person.get("links"), "laureate facts") or laureate_facts_url(laureate_id)
            person_summary = external_href((v2_award or {}).get("links"), "prize summary") or summary_url(category, year)
            wikipedia = ((v2_person.get("wikipedia") or {}).get("english")) if isinstance(v2_person.get("wikipedia"), dict) else None
            wikidata = ((v2_person.get("wikidata") or {}).get("url")) if isinstance(v2_person.get("wikidata"), dict) else None

            if date_awarded and death_date and str(death_date) < str(date_awarded):
                flag(
                    prize_flags,
                    "death_date_before_award_date",
                    "review",
                    f"Recorded death date {death_date} is earlier than recorded award date {date_awarded}. This is a date comparison, not a judgment that the award violated the statutes. Review the facts page and statutes.",
                    prizeKey=key,
                    laureateId=laureate_id,
                    sources=[FACTS_URL, STATUTES_URL, facts],
                )

            row = {
                "id": laureate_id,
                "displayName": display,
                "rawName": raw_name,
                "fullName": full,
                "v1Name": v1_name,
                "portion": portion,
                "motivation": motivation,
                "prizeStatus": status,
                "sortOrder": str((v2_award or source_row).get("sortOrder") or ""),
                "affiliations": affiliations,
                "factsUrl": facts,
                "apiUrl": laureate_api_url(laureate_id),
                "isOrganization": bool(is_org),
            }
            for candidate in (v2_award, source_row):
                motivation_obj = (candidate or {}).get("motivation")
                if isinstance(motivation_obj, dict) and motivation_obj.get("se"):
                    row["motivationSwedish"] = motivation_obj.get("se")
                    break
            laureate_rows.append(row)

            person = laureates.setdefault(
                laureate_id,
                {
                    "id": laureate_id,
                    "displayName": display,
                    "fullName": full,
                    "givenName": en(v2_person.get("givenName")),
                    "familyName": en(v2_person.get("familyName")),
                    "gender": gender,
                    "isOrganization": bool(is_org),
                    "birthDate": birth_date,
                    "birthPlace": place_label(birth.get("place") or {}) or ", ".join(
                        part for part in (clean_ws(v1_person.get("bornCity")), clean_ws(v1_person.get("bornCountry"))) if part
                    ) or None,
                    "deathDate": death_date,
                    "deathPlace": place_label((death or {}).get("place") or {}) or ", ".join(
                        part for part in (clean_ws(v1_person.get("diedCity")), clean_ws(v1_person.get("diedCountry"))) if part
                    ) or None,
                    "factsUrl": facts,
                    "apiUrl": laureate_api_url(laureate_id),
                    "wikipediaFromOfficialApi": wikipedia,
                    "wikidataFromOfficialApi": wikidata,
                    "prizes": [],
                },
            )
            person["prizes"].append(key)

            for note in SOURCED_NOTES:
                if note["year"] == year and note["category"] == category and display and fold(note["name"]) == fold(display):
                    flag(
                        prize_flags,
                        note["code"],
                        "review",
                        note["message"],
                        prizeKey=key,
                        laureateId=laureate_id,
                        sources=note["sources"],
                    )
                    if "decline" in note["message"].lower() and status and status != "declined":
                        flag(
                            prize_flags,
                            "facts_page_and_api_status_differ",
                            "review",
                            f"A sourced official narrative mentions decline, but API prizeStatus is “{status}”. Both are kept.",
                            prizeKey=key,
                            laureateId=laureate_id,
                            sources=note["sources"] + [laureate_api_url(laureate_id)],
                        )

        portions = [portion_value(row["portion"]) for row in laureate_rows]
        if awarded:
            if len(laureate_rows) > 3:
                flag(prize_flags, "more_than_three_laureates", "integrity", "More than three laureates are attached to this prize. The statutes say a prize may not be divided among more than three persons.", prizeKey=key, sources=[STATUTES_URL])
            if any(value is None for value in portions):
                flag(prize_flags, "portion_unparsed", "integrity", "At least one prize portion could not be parsed.", prizeKey=key)
            elif abs(sum(portions) - 1.0) > 0.001:
                flag(prize_flags, "portions_do_not_sum_to_one", "integrity", f"Prize portions sum to {sum(portions):.4f}, not 1.", prizeKey=key)

        nominee_summary = unique_nominees(parsed_nom) if parsed_nom and category != "economics" else []
        if nominee_summary:
            for row in laureate_rows:
                levels = [name_match_level(row["displayName"], nominee["name"]) for nominee in nominee_summary]
                if "exact" in levels or "exact_without_parenthetical" in levels:
                    continue
                if "possible" in levels:
                    flag(
                        prize_flags,
                        "laureate_only_possible_nominee_name_match",
                        "review",
                        f"{row['displayName']} is not an exact name match to a published nominee on the official list. A possible token match exists and must be reviewed. This is not a statement that the person was or was not nominated.",
                        prizeKey=key,
                        laureateId=row["id"],
                        sources=[nomination_list_url(category, year)],
                    )
                elif nom_status in ("ingested", "parse_count_mismatch"):
                    flag(
                        prize_flags,
                        "laureate_name_not_on_nomination_list",
                        "review",
                        f"No exact or parenthetical-stripped name match for {row['displayName']} on the stored official nomination list. Possible causes include spelling, an omission allowed by the archive rules, or a parser gap. This is not a finding that the laureate was not nominated.",
                        prizeKey=key,
                        laureateId=row["id"],
                        sources=[nomination_list_url(category, year), ARCHIVE_MANUAL],
                    )
            if any(item.get("nominationId") == "19478" for item in (parsed_nom or {}).get("nominations") or []):
                flag(
                    prize_flags,
                    "physics_1901_grenville_clark_id_discontinuity",
                    "review",
                    "The official Physics 1901 nomination list includes Grenville Clark, nominated by Louis Susky, at show.php?id=19478. Neighboring 1901 physics registration numbers on that page are much lower. The row is kept exactly as published and flagged for manual review. It was not reclassified.",
                    prizeKey=key,
                    sources=["https://www.nobelprize.org/nomination/archive/show.php?id=19478", nomination_list_url("physics", 1901)],
                )

        if parsed_nom and category != "economics":
            for nomination in parsed_nom.get("nominations") or []:
                nomination_rows.append(
                    {
                        "year": year,
                        "category": category,
                        "nominationId": nomination.get("nominationId"),
                        "nomineeNames": " | ".join(person.get("name") or "" for person in nomination.get("nominees") or []),
                        "nomineeIds": " | ".join(person.get("personId") or "" for person in nomination.get("nominees") or []),
                        "nominatorNames": " | ".join(person.get("name") or "" for person in nomination.get("nominators") or []),
                        "nominatorIds": " | ".join(person.get("personId") or "" for person in nomination.get("nominators") or []),
                        "showUrl": nomination.get("showUrl"),
                        "listUrl": nomination_list_url(category, year),
                    }
                )

        prize = {
            "key": key,
            "year": year,
            "category": category,
            "categoryLabel": meta["label"],
            "categoryFullName": (en((v2 or {}).get("categoryFullName")) or meta["full"]),
            "awarded": awarded,
            "inAlfredNobelsWill": meta["in_will"],
            "dateAwarded": date_awarded,
            "prizeAmount": amount,
            "prizeAmountAdjusted": amount_adjusted,
            "currency": "SEK" if amount is not None else None,
            "overallMotivation": overall,
            "laureates": laureate_rows,
            "links": {
                "summary": summary_url(category, year),
                "apiPrize": prize_api_url(category, year),
                "apiV1Prizes": "https://api.nobelprize.org/v1/prize.json",
                "nominationList": nomination_list_url(category, year),
                "categoryList": meta["list_url"],
            },
            "nomination": {
                "status": nom_status,
                "statedCount": None if not parsed_nom else parsed_nom.get("statedCount"),
                "parsedCount": None if not parsed_nom else parsed_nom.get("parsedCount"),
                "countMatchesStated": None if not parsed_nom else parsed_nom.get("countMatchesStated"),
                "file": None if not parsed_nom or category == "economics" else f"data/nominations/{category}/{year}.json",
                "nominees": nominee_summary,
                "note": meta["archive_note"],
            },
            "selection": {
                "officialMotivationIsTheStatedReason": True,
                "committeeComparativeRankingPublished": False,
                "statement": (
                    "The awarding institution publishes the motivation above. It does not publish a ranked "
                    "explanation of why this work was chosen over other nominated work. Nomination counts "
                    "are not votes and are not a basis for selection."
                ),
                "sources": [ARCHIVE_MANUAL, summary_url(category, year)],
            },
            "flagCodes": sorted({item["code"] for item in prize_flags}),
        }
        prizes.append(prize)
        flags.extend(prize_flags)

    # People with more than one prize, derived from the catalog, not from memory.
    for person in laureates.values():
        if len(person["prizes"]) > 1:
            flag(
                flags,
                "multiple_prizes",
                "info",
                f"{person['displayName']} is attached to {len(person['prizes'])} prize records in the downloaded data: {', '.join(person['prizes'])}.",
                laureateId=person["id"],
                sources=[person["apiUrl"], FACTS_URL],
            )

    if ARCHIVE_STATED_TOTALS["table_total"] != ARCHIVE_STATED_TOTALS["search_page_total"]:
        flag(
            flags,
            "nomination_archive_totals_disagree",
            "review",
            (
                f"On 2026-09-24 the nomination archive homepage table totalled "
                f"{ARCHIVE_STATED_TOTALS['table_total']} nominations, while the advanced search page said "
                f"{ARCHIVE_STATED_TOTALS['search_page_total']}. Both numbers are official and they disagree. "
                "This archive does not average or choose one."
            ),
            sources=[ARCHIVE_HOME, ARCHIVE_SEARCH],
        )

    for index, item in enumerate(flags, start=1):
        item["id"] = f"f{index:04d}"

    laureate_list = sorted(laureates.values(), key=lambda item: (item.get("displayName") or "").casefold())
    catalog = {
        "meta": {
            "title": "Nobel Prize Record",
            "independentArchive": True,
            "notEndorsedByNobelPrizeOutreach": True,
            "builtAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "fetchRetrievedAt": fetch_manifest.get("retrievedAt"),
            "latestAwardYearInSources": max((prize["year"] for prize in prizes), default=None),
            "notAnnounced": {
                "year": 2026,
                "note": (
                    "As of the official physics list page retrieved 2026-09-24, the Nobel Prize in Physics 2026 "
                    "had not been awarded. It will be announced on Tuesday 6 October 2026, 11:45 CEST at the earliest. "
                    "No 2026 prize records are included."
                ),
                "source": PHYSICS_LIST_URL,
            },
            "termsUrl": TERMS_URL,
            "willUrl": WILL_URL,
            "factsUrl": FACTS_URL,
            "statutesUrl": STATUTES_URL,
            "developerUrl": DEVELOPER_URL,
            "archiveHome": ARCHIVE_HOME,
            "archiveManual": ARCHIVE_MANUAL,
            "nominationCountIsNotAVote": (
                "The nomination archive manual says the number of nominations is not a basis for evaluation "
                "and selection, and that it is not a voting process."
            ),
            "sources": [
                API_SOURCE for API_SOURCE in (
                    "https://api.nobelprize.org/2.1/nobelPrizes",
                    "https://api.nobelprize.org/2.1/laureates",
                    "https://api.nobelprize.org/v1/prize.json",
                    "https://api.nobelprize.org/v1/laureate.json",
                    ARCHIVE_HOME,
                    FACTS_URL,
                )
            ],
            "counts": {
                "prizeRecords": len(prizes),
                "awardedPrizeRecords": sum(1 for prize in prizes if prize["awarded"]),
                "unawardedPrizeRecords": sum(1 for prize in prizes if not prize["awarded"]),
                "laureateEntities": len(laureate_list),
                "laureateSlots": sum(len(prize["laureates"]) for prize in prizes),
                "flags": len(flags),
            },
            "archiveTotals": ARCHIVE_STATED_TOTALS,
            "officialFactsCrossCheck": {
                "source": FACTS_URL,
                "retrieved": "2026-09-24",
            },
        },
        "categories": [
            {
                "id": key,
                "label": value["label"],
                "full": value["full"],
                "inWill": value["in_will"],
                "listUrl": value["list_url"],
                "archiveNote": value["archive_note"],
            }
            for key, value in CATEGORIES.items()
        ],
        "prizes": prizes,
        "laureates": laureate_list,
        "flags": flags,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "catalog.json", catalog, pretty=False)
    write_json(out_dir / "flags.json", flags, pretty=True)
    write_prizes_csv(out_dir / "prizes.csv", prizes)
    write_laureates_csv(out_dir / "laureates.csv", laureate_list, prizes)
    write_nominations_csv(out_dir / "nominations.csv", nomination_rows)
    write_flags_md(out_dir / "FLAGS.md", flags)
    # Copy nomination detail files next to the site data if they live in raw.
    for category in CATEGORIES:
        source = raw_dir / "nominations" / category
        if not source.exists():
            continue
        target = out_dir / "nominations" / category
        target.mkdir(parents=True, exist_ok=True)
        for path in source.glob("*.json"):
            target.joinpath(path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return catalog


def write_prizes_csv(path: Path, prizes):
    fields = [
        "year", "category", "awarded", "laureate_ids", "laureate_names", "portions",
        "prize_statuses", "motivations", "overall_motivation", "date_awarded",
        "prize_amount_sek", "prize_amount_adjusted_sek", "summary_url", "api_url",
        "nomination_list_url", "nomination_status", "nomination_stated_count", "flag_codes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for prize in prizes:
            writer.writerow(
                {
                    "year": prize["year"],
                    "category": prize["category"],
                    "awarded": prize["awarded"],
                    "laureate_ids": " | ".join(row["id"] for row in prize["laureates"]),
                    "laureate_names": " | ".join(row.get("displayName") or "" for row in prize["laureates"]),
                    "portions": " | ".join(row.get("portion") or "" for row in prize["laureates"]),
                    "prize_statuses": " | ".join(row.get("prizeStatus") or "" for row in prize["laureates"]),
                    "motivations": " | ".join(row.get("motivation") or "" for row in prize["laureates"]),
                    "overall_motivation": prize.get("overallMotivation") or "",
                    "date_awarded": prize.get("dateAwarded") or "",
                    "prize_amount_sek": prize.get("prizeAmount") if prize.get("prizeAmount") is not None else "",
                    "prize_amount_adjusted_sek": prize.get("prizeAmountAdjusted") if prize.get("prizeAmountAdjusted") is not None else "",
                    "summary_url": prize["links"]["summary"],
                    "api_url": prize["links"]["apiPrize"],
                    "nomination_list_url": prize["links"]["nominationList"],
                    "nomination_status": prize["nomination"]["status"],
                    "nomination_stated_count": prize["nomination"].get("statedCount") if prize["nomination"].get("statedCount") is not None else "",
                    "flag_codes": " | ".join(prize["flagCodes"]),
                }
            )


def write_laureates_csv(path: Path, laureates, prizes):
    prize_by_key = {prize["key"]: prize for prize in prizes}
    fields = [
        "id", "display_name", "gender", "organization", "birth_date", "birth_place",
        "death_date", "death_place", "prize_keys", "categories", "years", "motivations",
        "facts_url", "api_url", "wikipedia_linked_from_official_api",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for person in laureates:
            motivations = []
            categories = []
            years = []
            for key in person["prizes"]:
                prize = prize_by_key.get(key) or {}
                categories.append(prize.get("category") or "")
                years.append(str(prize.get("year") or ""))
                for row in prize.get("laureates") or []:
                    if row["id"] == person["id"] and row.get("motivation"):
                        motivations.append(row["motivation"])
            writer.writerow(
                {
                    "id": person["id"],
                    "display_name": person.get("displayName") or "",
                    "gender": person.get("gender") or "",
                    "organization": person.get("isOrganization"),
                    "birth_date": person.get("birthDate") or "",
                    "birth_place": person.get("birthPlace") or "",
                    "death_date": person.get("deathDate") or "",
                    "death_place": person.get("deathPlace") or "",
                    "prize_keys": " | ".join(person["prizes"]),
                    "categories": " | ".join(categories),
                    "years": " | ".join(years),
                    "motivations": " | ".join(motivations),
                    "facts_url": person.get("factsUrl") or "",
                    "api_url": person.get("apiUrl") or "",
                    "wikipedia_linked_from_official_api": person.get("wikipediaFromOfficialApi") or "",
                }
            )


def write_nominations_csv(path: Path, rows):
    fields = ["year", "category", "nominationId", "nomineeNames", "nomineeIds", "nominatorNames", "nominatorIds", "showUrl", "listUrl"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_flags_md(path: Path, flags):
    lines = [
        "# Flags for review",
        "",
        "These notes were generated from the downloaded official files and from disagreements between official pages. They are not corrections.",
        "",
        f"Total flags: {len(flags)}",
        "",
    ]
    for item in flags:
        where = item.get("prizeKey") or item.get("laureateId") or "archive"
        lines.append(f"## {item['id']} · {item['severity']} · {item['code']}")
        lines.append("")
        lines.append(f"Where: {where}")
        lines.append("")
        lines.append(item["message"])
        lines.append("")
        for source in item.get("sources") or []:
            lines.append(f"- {source}")
        if item.get("sources"):
            lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Build the Nobel Prize catalog")
    parser.add_argument("--raw", default=str(ROOT / "data" / "raw"))
    parser.add_argument("--out", default=str(ROOT / "data"))
    args = parser.parse_args()
    catalog = build(Path(args.raw), Path(args.out))
    counts = catalog["meta"]["counts"]
    print(
        f"Built {counts['prizeRecords']} prize records, "
        f"{counts['laureateEntities']} laureate entities, "
        f"{counts['flags']} flags."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
