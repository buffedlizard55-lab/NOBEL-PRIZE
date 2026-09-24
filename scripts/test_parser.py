#!/usr/bin/env python3
"""Parser tests. These do not require the Nobel Prize website."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_catalog import build  # noqa: E402
from nobel_lib import name_match_level, parse_nomination_list, portion_from_share  # noqa: E402


FIXTURE = """<!DOCTYPE html>
<html><body>
<p>2 nominations</p>
<table>
<tr><th>Nominee(s)</th><th>Nominator(s)</th><th></th></tr>
<tr>
  <td><a href="show_people.php?id=511">Svante Arrhenius</a><br>
      <a href="show_people.php?id=9563">Jacobus Henricus Van´t Hoff</a></td>
  <td><a href="show_people.php?id=1845">Per Cleve</a></td>
  <td><a href="show.php?id=502&amp;mode=">Show »</a></td>
</tr>
<tr><td></td><td></td><td></td></tr>
<tr>
  <td><a href="/nomination/archive/show_people.php?id=2021">William Randal Cremer</a></td>
  <td>37 members of the Swedish parliament (Wavrinsky)</td>
  <td><a href="show.php?id=1570">Show »</a></td>
</tr>
</table>
</body></html>
"""


class ParserTests(unittest.TestCase):
    def test_list_page(self):
        parsed = parse_nomination_list(FIXTURE, "https://www.nobelprize.org/nomination/archive/list.php?prize=2&year=1901")
        self.assertEqual(parsed["statedCount"], 2)
        self.assertEqual(parsed["parsedCount"], 2)
        self.assertTrue(parsed["countMatchesStated"])
        first = parsed["nominations"][0]
        self.assertEqual(first["nominationId"], "502")
        self.assertEqual([person["name"] for person in first["nominees"]], ["Svante Arrhenius", "Jacobus Henricus Van´t Hoff"])
        self.assertEqual(first["nominees"][1]["personId"], "9563")
        self.assertIn("show.php?id=502", first["showUrl"])
        second = parsed["nominations"][1]
        self.assertEqual(second["nominators"][0]["name"], "37 members of the Swedish parliament (Wavrinsky)")
        self.assertIsNone(second["nominators"][0]["personId"])
        self.assertTrue(second["nominees"][0]["url"].startswith("https://www.nobelprize.org/nomination/archive/show_people.php?id=2021"))

    def test_name_match_does_not_overclaim(self):
        self.assertEqual(name_match_level("Sully Prudhomme", "Sully (René) Prudhomme"), "exact_without_parenthetical")
        self.assertEqual(name_match_level("Wilhelm Conrad Röntgen", "Wilhelm Röntgen"), "possible")
        self.assertIsNone(name_match_level("Marie Curie", "Pierre Curie"))
        self.assertEqual(name_match_level("Miguel Angel Asturias", "Miguel Ángel Asturias"), "diacritic")
        self.assertEqual(name_match_level("Eugene O'Neill", "Eugene O´Neill"), "exact")
        self.assertEqual(name_match_level("Eisaku Satō", "Eisako Sato"), "near")
        self.assertIsNone(name_match_level("Gustaf Dalén", "Nils Dalén"))
        self.assertEqual(portion_from_share("4"), "1/4")
        self.assertEqual(portion_from_share("1"), "1")

    def test_build_does_not_invent_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw"
            out = Path(tmp) / "out"
            raw.mkdir()
            (raw / "v2_prizes.json").write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "awardYear": "1901",
                                "category": {"en": "Physics"},
                                "categoryFullName": {"en": "The Nobel Prize in Physics"},
                                "dateAwarded": "1901-11-12",
                                "prizeAmount": 150782,
                                "prizeAmountAdjusted": 10833458,
                                "laureates": [
                                    {
                                        "id": "1",
                                        "knownName": {"en": "Wilhelm Conrad Röntgen"},
                                        "fullName": {"en": "Wilhelm Conrad Röntgen"},
                                        "portion": "1",
                                        "sortOrder": "1",
                                        "motivation": {"en": "in recognition of the extraordinary services he has rendered by the discovery of the remarkable rays subsequently named after him", "se": "svensk text"},
                                    }
                                ],
                            },
                            {
                                "awardYear": "1940",
                                "category": {"en": "Physics"},
                                "categoryFullName": {"en": "The Nobel Prize in Physics"},
                                "topMotivation": {"en": "No Nobel Prize was awarded this year. 1/3 of the prize money was allocated to the main fund and 2/3 was allocated to the special fund of this prize section."},
                                "prizeAmount": 138570,
                                "prizeAmountAdjusted": 4439858,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (raw / "v2_laureates.json").write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "id": "1",
                                "knownName": {"en": "Wilhelm Conrad Röntgen"},
                                "fullName": {"en": "Wilhelm Conrad Röntgen"},
                                "gender": "male",
                                "birth": {"date": "1845-03-27", "place": {"locationString": {"en": "Lennep, Prussia (now Remscheid, Germany)"}}},
                                "death": {"date": "1923-02-10", "place": {"locationString": {"en": "Munich, Germany"}}},
                                "nobelPrizes": [
                                    {
                                        "awardYear": "1901",
                                        "category": {"en": "Physics"},
                                        "prizeStatus": "received",
                                        "portion": "1",
                                        "motivation": {"en": "in recognition of the extraordinary services he has rendered by the discovery of the remarkable rays subsequently named after him"},
                                        "affiliations": [{"name": {"en": "Munich University"}, "city": {"en": "Munich"}, "country": {"en": "Germany"}}],
                                        "links": [
                                            {"rel": "external", "href": "https://www.nobelprize.org/prizes/physics/1901/rontgen/facts/", "class": ["laureate facts"]}
                                        ],
                                    }
                                ],
                                "links": [{"rel": "external", "href": "https://www.nobelprize.org/laureate/1", "class": ["laureate facts"]}],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            catalog = build(raw, out)
            self.assertEqual(len(catalog["prizes"]), 2)
            physics = next(prize for prize in catalog["prizes"] if prize["key"] == "physics-1901")
            self.assertEqual(physics["laureates"][0]["displayName"], "Wilhelm Conrad Röntgen")
            self.assertEqual(physics["laureates"][0]["prizeStatus"], "received")
            self.assertTrue(physics["laureates"][0]["motivation"].startswith("in recognition"))
            self.assertIn("svensk text", json.dumps(physics))
            withheld = next(prize for prize in catalog["prizes"] if prize["key"] == "physics-1940")
            self.assertFalse(withheld["awarded"])
            self.assertEqual(withheld["laureates"], [])
            self.assertIn("No Nobel Prize was awarded", withheld["overallMotivation"])
            # A partial fixture must not grow extra prize years.
            self.assertNotIn("chemistry-1901", {prize["key"] for prize in catalog["prizes"]})


if __name__ == "__main__":
    unittest.main()
