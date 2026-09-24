"""Shared constants and parsers for the Nobel Prize record.

This module does not invent prize facts. Cross-check figures below were copied
from official pages retrieved on 2026-09-24. They are used only to detect
disagreement with the downloaded API records, never to fill a missing row.
"""

from __future__ import annotations

import re
import unicodedata
from html.parser import HTMLParser
from urllib.parse import urljoin

ARCHIVE_LIST = "https://www.nobelprize.org/nomination/archive/list.php"
ARCHIVE_HOME = "https://www.nobelprize.org/nomination/archive/"
ARCHIVE_MANUAL = "https://www.nobelprize.org/nomination/archive/manual.php"
ARCHIVE_SEARCH = "https://www.nobelprize.org/nomination/archive/search.php"
FACTS_URL = "https://www.nobelprize.org/prizes/facts/nobel-prize-facts/"
WILL_URL = "https://www.nobelprize.org/alfred-nobel/full-text-of-alfred-nobels-will-2/"
TERMS_URL = "https://www.nobelprize.org/about/terms-of-use-for-api-nobelprize-org-and-data-nobelprize-org/"
STATUTES_URL = "https://www.nobelprize.org/about/statutes-of-the-nobel-foundation/"
DEVELOPER_URL = "https://www.nobelprize.org/about/developer-zone-2/"
API_V1_PRIZES = "https://api.nobelprize.org/v1/prize.json"
API_V1_LAUREATES = "https://api.nobelprize.org/v1/laureate.json"
API_V1_COUNTRIES = "https://api.nobelprize.org/v1/country.json"
API_V2_PRIZES = "https://api.nobelprize.org/2.1/nobelPrizes"
API_V2_LAUREATES = "https://api.nobelprize.org/2.1/laureates"
PHYSICS_LIST_URL = "https://www.nobelprize.org/prizes/lists/all-nobel-prizes-in-physics/"

# Prize codes verified against list.php titles on 2026-09-24:
# 1 Physics, 2 Chemistry, 3 Physiology or Medicine, 4 Literature, 5 Peace.
# prize=6&year=1969 returned a page titled blank and "0 nominations".
# Economic sciences is not a category on the archive search form.
CATEGORIES = {
    "physics": {
        "label": "Physics",
        "full": "The Nobel Prize in Physics",
        "api": "phy",
        "slug": "physics",
        "nom_prize": 1,
        "in_will": True,
        "list_url": PHYSICS_LIST_URL,
        "archive_from": 1901,
        "archive_through": 1975,
        "archive_note": "Nomination archive homepage: physics nominations are published for 1901–1975.",
    },
    "chemistry": {
        "label": "Chemistry",
        "full": "The Nobel Prize in Chemistry",
        "api": "che",
        "slug": "chemistry",
        "nom_prize": 2,
        "in_will": True,
        "list_url": "https://www.nobelprize.org/prizes/lists/all-nobel-prizes-in-chemistry/",
        "archive_from": 1901,
        "archive_through": 1975,
        "archive_note": "Nomination archive homepage: chemistry nominations are published for 1901–1975.",
    },
    "medicine": {
        "label": "Physiology or Medicine",
        "full": "The Nobel Prize in Physiology or Medicine",
        "api": "med",
        "slug": "medicine",
        "nom_prize": 3,
        "in_will": True,
        "list_url": "https://www.nobelprize.org/prizes/lists/all-nobel-laureates-in-physiology-or-medicine/",
        "archive_from": 1901,
        "archive_through": 1953,
        "archive_note": (
            "Nomination archive homepage: physiology or medicine nominations are "
            "published only through 1953, not through the usual 50-year window."
        ),
    },
    "literature": {
        "label": "Literature",
        "full": "The Nobel Prize in Literature",
        "api": "lit",
        "slug": "literature",
        "nom_prize": 4,
        "in_will": True,
        "list_url": "https://www.nobelprize.org/prizes/lists/all-nobel-prizes-in-literature/",
        "archive_from": 1901,
        "archive_through": 1975,
        "archive_note": "Nomination archive homepage: literature nominations are published for 1901–1975.",
    },
    "peace": {
        "label": "Peace",
        "full": "The Nobel Peace Prize",
        "api": "pea",
        "slug": "peace",
        "nom_prize": 5,
        "in_will": True,
        "list_url": "https://www.nobelprize.org/prizes/lists/all-nobel-peace-prizes/",
        "archive_from": 1901,
        "archive_through": 1975,
        "archive_note": "Nomination archive homepage: peace nominations are published for 1901–1975.",
    },
    "economics": {
        "label": "Economic Sciences",
        "full": "The Sveriges Riksbank Prize in Economic Sciences in Memory of Alfred Nobel",
        "api": "eco",
        "slug": "economic-sciences",
        "nom_prize": 6,
        "in_will": False,
        "list_url": "https://www.nobelprize.org/prizes/lists/all-prizes-in-economic-sciences/",
        "archive_from": None,
        "archive_through": None,
        "archive_note": (
            "Not established by Alfred Nobel's will. The public nomination archive "
            "search form has no economic-sciences category. list.php?prize=6&year=1969 "
            "returned 0 nominations on 2026-09-24. That zero is not evidence that "
            "nobody was nominated."
        ),
    },
}

V2_CATEGORY_EN = {
    "Physics": "physics",
    "Chemistry": "chemistry",
    "Physiology or Medicine": "medicine",
    "Literature": "literature",
    "Peace": "peace",
    "Economic Sciences": "economics",
}

# Years the official facts page lists as not awarded, retrieved 2026-09-24.
# https://www.nobelprize.org/prizes/facts/nobel-prize-facts/
UNAWARDED_YEARS = {
    "physics": [1916, 1931, 1934, 1940, 1941, 1942],
    "chemistry": [1916, 1917, 1919, 1924, 1933, 1940, 1941, 1942],
    "medicine": [1915, 1916, 1917, 1918, 1921, 1925, 1940, 1941, 1942],
    "literature": [1914, 1918, 1935, 1940, 1941, 1942, 1943],
    "peace": [1914, 1915, 1916, 1918, 1923, 1924, 1928, 1932, 1939, 1940, 1941, 1942, 1943, 1948, 1955, 1956, 1966, 1967, 1972],
    "economics": [],
}

# Counts from the same facts page. Peace laureate slots are 112 individuals + 31 organisations.
OFFICIAL_FACTS = {
    "source": FACTS_URL,
    "retrieved": "2026-09-24",
    "span": "1901-2025",
    "awarded_prizes": 633,
    "laureate_slots": 1026,
    "individuals": 990,
    "organisations": 28,
    "not_awarded_occasions": 49,
    "prizes_to_women": 68,
    "by_category": {
        "physics": {"prizes": 119, "slots": 230},
        "chemistry": {"prizes": 117, "slots": 200},
        "medicine": {"prizes": 116, "slots": 232},
        "literature": {"prizes": 118, "slots": 122},
        "peace": {"prizes": 106, "slots": 143},
        "economics": {"prizes": 57, "slots": 99},
    },
}

# Homepage table vs advanced-search total, both retrieved 2026-09-24.
ARCHIVE_STATED_TOTALS = {
    "source": ARCHIVE_HOME,
    "physics": {"from": 1901, "through": 1975, "nominations": 4019},
    "chemistry": {"from": 1901, "through": 1975, "nominations": 4249},
    "medicine": {"from": 1901, "through": 1953, "nominations": 5110},
    "literature": {"from": 1901, "through": 1975, "nominations": 4533},
    "peace": {"from": 1901, "through": 1975, "nominations": 5230},
    "table_total": 23141,
    "search_page_total": 23983,
    "search_page": ARCHIVE_SEARCH,
}

# Quotations and close official wording, attached only when a downloaded
# record matches year + category + name. Not used to create records.
SOURCED_NOTES = [
    {
        "year": 1964,
        "category": "literature",
        "name": "Jean-Paul Sartre",
        "code": "official_declined_wording",
        "message": (
            "Nobel Prize facts page: “Jean-Paul Sartre, awarded the 1964 Nobel Prize "
            "in Literature, declined the prize because he had consistently declined all official honours.”"
        ),
        "sources": [FACTS_URL, "https://www.nobelprize.org/prizes/literature/1964/sartre/facts/"],
    },
    {
        "year": 1973,
        "category": "peace",
        "name": "Le Duc Tho",
        "code": "official_decline_wording_differs_across_pages",
        "message": (
            "Two official pages describe this decline differently. Facts page: Le Duc Tho "
            "“said that he was not in a position to accept the Nobel Peace Prize, citing the "
            "situation in Vietnam as his reason.” His facts page says “Le Duc Tho declined the "
            "Nobel Peace Prize” and, in the biographical note, that he “refused to accept it, "
            "on the grounds that his opposite number had violated the truce.” Both wordings are "
            "retained. This archive does not pick one."
        ),
        "sources": [
            FACTS_URL,
            "https://www.nobelprize.org/prizes/peace/1973/tho/facts/",
        ],
    },
    {
        "year": 1938,
        "category": "chemistry",
        "name": "Richard Kuhn",
        "code": "forced_to_decline_facts_page",
        "message": (
            "Nobel Prize facts page: Adolf Hitler forbade three German laureates, including "
            "Richard Kuhn, from accepting the prize. They could later receive the diploma and "
            "medal, but not the prize amount. The API prize status, when present, is shown "
            "separately and is not rewritten to match this sentence."
        ),
        "sources": [FACTS_URL, "https://www.nobelprize.org/nobel_prizes/chemistry/laureates/1938/index.html"],
    },
    {
        "year": 1939,
        "category": "chemistry",
        "name": "Adolf Butenandt",
        "code": "forced_to_decline_facts_page",
        "message": (
            "Nobel Prize facts page: Adolf Hitler forbade three German laureates, including "
            "Adolf Butenandt, from accepting the prize. They could later receive the diploma and "
            "medal, but not the prize amount. The API prize status, when present, is shown "
            "separately and is not rewritten to match this sentence."
        ),
        "sources": [FACTS_URL, "https://www.nobelprize.org/nobel_prizes/chemistry/laureates/1939/index.html"],
    },
    {
        "year": 1939,
        "category": "medicine",
        "name": "Gerhard Domagk",
        "code": "forced_to_decline_facts_page",
        "message": (
            "Nobel Prize facts page: Adolf Hitler forbade three German laureates, including "
            "Gerhard Domagk, from accepting the prize. They could later receive the diploma and "
            "medal, but not the prize amount. The API prize status, when present, is shown "
            "separately and is not rewritten to match this sentence."
        ),
        "sources": [FACTS_URL, "https://www.nobelprize.org/nobel_prizes/medicine/laureates/1939/index.html"],
    },
    {
        "year": 1958,
        "category": "literature",
        "name": "Boris Pasternak",
        "code": "facts_page_decline_vs_api_status",
        "message": (
            "Nobel Prize facts page: Boris Pasternak initially accepted the 1958 literature prize "
            "but was later coerced by the authorities of the Soviet Union to decline it. "
            "The API record retrieved for this laureate used prizeStatus “restricted”, not “declined”. "
            "Both are shown. This archive does not collapse them into one label."
        ),
        "sources": [FACTS_URL, "https://api.nobelprize.org/2/laureate/629"],
    },
    {
        "year": 1961,
        "category": "peace",
        "name": "Dag Hammarskjöld",
        "code": "posthumous_facts_page",
        "message": (
            "Nobel Prize facts page: before 1974 the prize was awarded posthumously twice, "
            "including to Dag Hammarskjöld, Nobel Peace Prize 1961."
        ),
        "sources": [FACTS_URL],
    },
    {
        "year": 1931,
        "category": "literature",
        "name": "Erik Axel Karlfeldt",
        "code": "posthumous_facts_page",
        "message": (
            "Nobel Prize facts page: before 1974 the prize was awarded posthumously twice, "
            "including to Erik Axel Karlfeldt, Nobel Prize in Literature 1931."
        ),
        "sources": [FACTS_URL],
    },
    {
        "year": 2011,
        "category": "medicine",
        "name": "Ralph Steinman",
        "code": "died_before_announcement_remained_laureate",
        "message": (
            "Nobel Prize facts page: after the 2011 medicine announcement it was discovered that "
            "Ralph Steinman had died three days earlier. The Board of the Nobel Foundation concluded "
            "he should remain a laureate because the Nobel Assembly had announced the prize without "
            "knowing of his death."
        ),
        "sources": [FACTS_URL],
    },
]


def en(value):
    """English string from an API multilingual object, or the string itself."""
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, dict):
        for key in ("en", "se", "no"):
            item = value.get(key)
            if isinstance(item, str) and item.strip():
                return item.strip()
    return None


def clean_ws(value):
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def clean_motivation(value):
    if value is None:
        return None
    text = str(value).replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        text = text[1:-1].strip()
    text = re.sub(r"[ \t]*\n[ \t]*", " ", text)
    text = re.sub(r"[ \t]+", " ", text).strip()
    return text or None


_APOSTROPHES = "’´`'ʼ′‛ˈ"


def fold(value):
    text = clean_ws(value) or ""
    for char in _APOSTROPHES:
        text = text.replace(char, "'")
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("–", "-").replace("—", "-")
    text = text.casefold()
    text = re.sub(r"\s+", " ", text)
    return text


def match_fold(value):
    """Comparison form. Strips diacritics. Does not rewrite a displayed name."""
    text = fold(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9' ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def texts_equivalent(left, right):
    return fold(clean_motivation(left)) == fold(clean_motivation(right))


def portion_from_share(share):
    """v1 `share` is the denominator: 1, 2, 3, or 4. It is not a count of prizes."""
    if share is None or share == "":
        return None
    try:
        number = int(share)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    if number == 1:
        return "1"
    return f"1/{number}"


def portion_value(portion):
    if portion is None:
        return None
    text = str(portion).strip()
    if text == "1":
        return 1.0
    if "/" in text:
        num, den = text.split("/", 1)
        try:
            return float(num) / float(den)
        except ValueError:
            return None
    try:
        return float(text)
    except ValueError:
        return None


def nomination_list_url(category, year):
    meta = CATEGORIES[category]
    if meta["nom_prize"] is None:
        return None
    return f"{ARCHIVE_LIST}?prize={meta['nom_prize']}&year={year}"


def summary_url(category, year):
    return f"https://www.nobelprize.org/prizes/{CATEGORIES[category]['slug']}/{year}/summary/"


def prize_api_url(category, year):
    return f"https://api.nobelprize.org/2/nobelPrize/{CATEGORIES[category]['api']}/{year}"


def laureate_api_url(laureate_id):
    return f"https://api.nobelprize.org/2/laureate/{laureate_id}"


def laureate_facts_url(laureate_id):
    return f"https://www.nobelprize.org/laureate/{laureate_id}"


def archive_status_for(category, year, ingested):
    meta = CATEGORIES[category]
    if category == "economics":
        return "not_in_public_archive"
    if meta["archive_from"] is None:
        return "not_in_public_archive"
    if year < meta["archive_from"] or year > 1975:
        return "sealed_or_not_published"
    if category == "medicine" and year > meta["archive_through"]:
        if ingested:
            return "ingested_outside_homepage_window"
        return "not_released_by_awarding_institution"
    if year > meta["archive_through"]:
        return "sealed_or_not_published"
    if ingested:
        return "ingested"
    return "not_ingested"


class NominationListParser(HTMLParser):
    """Parse a nomination-archive list.php table. Does not guess missing cells."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self._row = None
        self._cell = None
        self._link = None

    def handle_starttag(self, tag, attrs):
        attr = {key.lower(): value for key, value in attrs}
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = {"header": tag == "th", "chunks": [], "links": []}
        elif tag == "a" and self._cell is not None:
            self._link = {"href": attr.get("href") or "", "chunks": []}
        elif tag == "br" and self._cell is not None:
            self._cell["chunks"].append("\n")
            if self._link is not None:
                self._link["chunks"].append(" ")

    def handle_endtag(self, tag):
        if tag == "a" and self._link is not None and self._cell is not None:
            text = clean_ws("".join(self._link["chunks"])) or ""
            self._cell["links"].append({"href": self._link["href"], "text": text})
            self._link = None
        elif tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._cell["text"] = clean_ws(" ".join(self._cell["chunks"])) or ""
            self._row.append(self._cell)
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if any(not cell["header"] for cell in self._row):
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell["chunks"].append(data)
        if self._link is not None:
            self._link["chunks"].append(data)


def _abs_archive(href):
    if not href:
        return None
    return urljoin(ARCHIVE_LIST, href)


def _person_from_link(link):
    href = link.get("href") or ""
    match = re.search(r"show_people\.php\?id=(\d+)", href)
    if not match and not (link.get("text") or "").strip():
        return None
    return {
        "name": link.get("text") or "",
        "personId": match.group(1) if match else None,
        "url": _abs_archive(href) if match else None,
    }


def _plain_people(cell):
    """Text in a cell that is not inside a person link."""
    linked = {fold(link.get("text")) for link in cell["links"] if link.get("text")}
    text = cell.get("text") or ""
    if not text:
        return []
    # Links are already captured. If the whole cell text is only those names, skip.
    leftover = text
    for link in cell["links"]:
        if link.get("text"):
            leftover = leftover.replace(link["text"], " ")
    leftover = clean_ws(leftover)
    if not leftover:
        return []
    if fold(leftover) in linked:
        return []
    return [{"name": leftover, "personId": None, "url": None}]


def parse_nomination_list(html, source_url):
    parser = NominationListParser()
    parser.feed(html)
    parser.close()
    stated = None
    count_match = re.search(r"(\d+)\s+nominations?\b", html, re.I)
    if count_match:
        stated = int(count_match.group(1))

    nominations = []
    for row in parser.rows:
        show = None
        show_id = None
        content_cells = []
        for cell in row:
            for link in cell["links"]:
                match = re.search(r"show\.php\?id=(\d+)", link.get("href") or "")
                if match:
                    show_id = match.group(1)
                    show = _abs_archive(link["href"])
            if not any(re.search(r"show\.php\?id=", link.get("href") or "") for link in cell["links"]):
                content_cells.append(cell)
        if not show_id:
            continue
        nominee_cell = content_cells[0] if content_cells else {"links": [], "text": ""}
        nominator_cell = content_cells[1] if len(content_cells) > 1 else {"links": [], "text": ""}
        nominees = [item for item in (_person_from_link(link) for link in nominee_cell["links"]) if item and item["name"]]
        nominators = [item for item in (_person_from_link(link) for link in nominator_cell["links"]) if item and item["name"]]
        nominees.extend(_plain_people(nominee_cell))
        nominators.extend(_plain_people(nominator_cell))
        nominations.append(
            {
                "nominationId": show_id,
                "showUrl": show,
                "nominees": nominees,
                "nominators": nominators,
                "sourceUrl": source_url,
            }
        )
    return {
        "sourceUrl": source_url,
        "statedCount": stated,
        "parsedCount": len(nominations),
        "countMatchesStated": stated is not None and stated == len(nominations),
        "nominations": nominations,
    }


_NAME_STOP = {"von", "van", "de", "del", "der", "den", "la", "le", "di", "da", "dos", "das", "und", "and", "the"}


def _name_tokens(value):
    folded = match_fold(re.sub(r"\([^)]*\)", " ", value or ""))
    return [token for token in re.split(r"[^a-z0-9']+", folded) if len(token) >= 3 and token not in _NAME_STOP]


def _edit_distance(left, right):
    if abs(len(left) - len(right)) > 2:
        return 3
    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        for j, right_char in enumerate(right, start=1):
            current.append(min(
                previous[j] + 1,
                current[j - 1] + 1,
                previous[j - 1] + (left_char != right_char),
            ))
        previous = current
    return previous[-1]


def _near_tokens(left_tokens, right_tokens):
    if not left_tokens or not right_tokens:
        return False
    if _edit_distance(left_tokens[-1], right_tokens[-1]) > 1:
        return False
    if len(left_tokens) == 1 or len(right_tokens) == 1:
        return _edit_distance(left_tokens[-1], right_tokens[-1]) <= 1 and min(len(left_tokens[-1]), len(right_tokens[-1])) >= 6
    others = left_tokens[:-1]
    candidates = right_tokens[:-1]
    return any(_edit_distance(token, candidate) <= 1 for token in others for candidate in candidates)


def name_match_level(laureate_name, nominee_name):
    """Conservative match. A near spelling is not treated as confirmed."""
    left = match_fold(laureate_name)
    right = match_fold(nominee_name)
    if not left or not right:
        return None
    if left == right:
        return "exact" if fold(laureate_name) == fold(nominee_name) else "diacritic"
    left_plain = match_fold(re.sub(r"\([^)]*\)", " ", laureate_name or ""))
    right_plain = match_fold(re.sub(r"\([^)]*\)", " ", nominee_name or ""))
    if left_plain and left_plain == right_plain:
        return "exact_without_parenthetical"
    left_tokens = _name_tokens(laureate_name)
    right_tokens = _name_tokens(nominee_name)
    if left_tokens and right_tokens:
        if set(left_tokens) == set(right_tokens):
            return "token_equal"
        if set(left_tokens) <= set(right_tokens) and left_tokens[-1] == right_tokens[-1]:
            return "contained"
        if set(left_tokens) <= set(right_tokens) or set(right_tokens) <= set(left_tokens):
            return "possible"
    if _near_tokens(left_tokens, right_tokens):
        return "near"
    return None
