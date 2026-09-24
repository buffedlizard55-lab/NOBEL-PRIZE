(function () {
  "use strict";

  const main = document.getElementById("main");
  const dialog = document.getElementById("detail");
  const detailBody = document.getElementById("detail-body");
  const search = document.getElementById("q");
  const PAGE = 40;

  const state = {
    catalog: null,
    view: "browse",
    query: "",
    category: "all",
    from: 1901,
    to: 2025,
    awarded: "all",
    flagsOnly: false,
    flagSeverity: "review",
    page: 0,
    prizeKey: null,
    laureateId: null,
  };

  function fold(value) {
    return String(value || "")
      .normalize("NFKC")
      .replace(/[’´`]/g, "'")
      .replace(/[–—]/g, "-")
      .replace(/\([^)]*\)/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
  }

  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function money(value) {
    if (value == null || value === "") return "";
    return new Intl.NumberFormat("en-SE").format(value) + " SEK";
  }

  function prizeByKey(key) {
    return state.catalog.prizes.find((prize) => prize.key === key);
  }

  function laureateById(id) {
    return state.catalog.laureates.find((person) => person.id === id);
  }

  function maxYear() {
    return (state.catalog && state.catalog.meta.latestAwardYearInSources) || 2025;
  }

  function parseHash() {
    const raw = location.hash.replace(/^#/, "") || "browse";
    const [view, arg] = raw.split("/");
    state.view = ["browse", "laureates", "analysis", "flags", "method", "prize", "laureate"].includes(view) ? view : "browse";
    state.prizeKey = state.view === "prize" ? arg : null;
    state.laureateId = state.view === "laureate" ? arg : null;
    if (state.view === "prize" || state.view === "laureate") state.view = "browse";
  }

  function setHash(hash) {
    if (location.hash !== hash) location.hash = hash;
    else render();
  }

  function matchesQuery(prize) {
    const q = fold(state.query);
    if (!q) return true;
    if (String(prize.year).includes(q)) return true;
    if (fold(prize.categoryLabel).includes(q) || fold(prize.category).includes(q)) return true;
    if (fold(prize.overallMotivation).includes(q)) return true;
    for (const row of prize.laureates) {
      if (fold(row.displayName).includes(q) || fold(row.motivation).includes(q) || fold((row.affiliations || []).join(" ")).includes(q)) return true;
    }
    for (const nominee of (prize.nomination && prize.nomination.nominees) || []) {
      if (fold(nominee.name).includes(q)) return true;
    }
    return false;
  }

  function filteredPrizes() {
    return state.catalog.prizes.filter((prize) => {
      if (state.category !== "all" && prize.category !== state.category) return false;
      if (prize.year < state.from || prize.year > state.to) return false;
      if (state.awarded === "awarded" && !prize.awarded) return false;
      if (state.awarded === "unawarded" && prize.awarded) return false;
      if (state.flagsOnly && !state.catalog.flags.some((flag) => flag.prizeKey === prize.key && flag.severity === "review")) return false;
      return matchesQuery(prize);
    });
  }

  function statusLabel(status) {
    const labels = {
      ingested: "Nominee list stored from the official archive",
      not_ingested: "List not stored in this build — open the official page",
      not_in_public_archive: "Not in the public nomination archive",
      not_released_by_awarding_institution: "Not released by the awarding institution",
      sealed_or_not_published: "Still sealed or not yet published",
      parse_count_mismatch: "Stored list does not match the page's own count",
      ingested_outside_homepage_window: "Stored, though the homepage window did not include this year",
    };
    return labels[status] || status || "Unknown";
  }

  function badge(code) {
    if (!code) return "";
    const severity = code === "integrity" || String(code).includes("mismatch") ? "integrity" : code === "info" || code === "not_in_alfred_nobels_will" ? "info" : "review";
    return `<span class="badge ${severity}">${esc(code)}</span>`;
  }

  function safeHref(href) {
    const text = String(href || "");
    return /^https?:\/\//i.test(text) || text.startsWith("#") || text.startsWith("data/");
  }

  function link(href, label) {
    if (!href || !safeHref(href)) return "";
    return `<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${esc(label)}</a>`;
  }

  function renderNav() {
    const current = location.hash.startsWith("#prize") || location.hash.startsWith("#laureate") || !location.hash ? "browse" : location.hash.slice(1).split("/")[0];
    document.querySelectorAll(".views a").forEach((anchor) => {
      anchor.setAttribute("aria-current", anchor.dataset.view === current ? "page" : "false");
    });
  }

  function renderFilters() {
    const categories = [{ id: "all", label: "All subjects" }].concat(state.catalog.categories.map((item) => ({ id: item.id, label: item.label })));
    return `
      <aside class="filters">
        <h2>Subject</h2>
        <div class="chip-list">
          ${categories.map((item) => `<button type="button" class="chip" data-category="${esc(item.id)}" aria-pressed="${state.category === item.id}">${esc(item.label)}</button>`).join("")}
        </div>
        <h2>Year</h2>
        <div class="years">
          <label>From <input id="from" type="number" min="1901" max="${maxYear()}" value="${state.from}"></label>
          <label>To <input id="to" type="number" min="1901" max="${maxYear()}" value="${state.to}"></label>
        </div>
        <h2>Award</h2>
        <div class="chip-list">
          ${["all", "awarded", "unawarded"].map((item) => `<button type="button" class="chip" data-awarded="${item}" aria-pressed="${state.awarded === item}">${item === "all" ? "Awarded and not awarded" : item === "awarded" ? "Awarded only" : "Not awarded"}</button>`).join("")}
        </div>
        <button type="button" class="check" data-flags="1" aria-pressed="${state.flagsOnly}">Show flagged records only</button>
      </aside>`;
  }

  function prizeQuote(prize) {
    const motivations = prize.laureates.map((row) => row.motivation).filter(Boolean);
    const unique = Array.from(new Set(motivations));
    if (unique.length === 1) return `<p class="quote">“${esc(unique[0])}”</p>`;
    if (unique.length > 1) {
      return prize.laureates.map((row) => `<p><strong>${esc(row.displayName || "Laureate")}.</strong> ${row.motivation ? `<span class="quote">“${esc(row.motivation)}”</span>` : "No motivation text in the downloaded record."}</p>`).join("");
    }
    return prize.overallMotivation ? `<p class="quote">${esc(prize.overallMotivation)}</p>` : "";
  }

  function prizeCard(prize) {
    const names = prize.laureates.map((row) => row.displayName).filter(Boolean).join(", ") || "No laureate";
    const reviews = state.catalog.flags.filter((flag) => flag.prizeKey === prize.key && flag.severity === "review").length;
    return `
      <article class="card">
        <p class="kicker">${esc(prize.categoryFullName)}${prize.inAlfredNobelsWill ? "" : " · not in Alfred Nobel’s will"}</p>
        <div class="card-top">
          <h3 class="names">${esc(names)}</h3>
          <div>${reviews ? `<span class="badge review">${reviews} to review</span>` : ""}</div>
        </div>
        ${prizeQuote(prize)}
        <div class="meta-row">
          <span>${prize.awarded ? "Awarded" : "Not awarded"}</span>
          ${prize.dateAwarded ? `<span>Date awarded ${esc(prize.dateAwarded)}</span>` : ""}
          ${prize.prizeAmount != null ? `<span>${esc(money(prize.prizeAmount))}</span>` : ""}
          <span>${esc(statusLabel(prize.nomination.status))}${prize.nomination.statedCount != null ? ` · ${prize.nomination.parsedCount == null ? "" : prize.nomination.parsedCount + " stored / "}${prize.nomination.statedCount} stated` : ""}</span>
        </div>
        <div class="link-row">
          <a href="#prize/${esc(prize.key)}">Open record</a>
          ${link(prize.links.summary, "Official summary")}
          ${link(prize.links.apiPrize, "API record")}
          ${link(prize.links.nominationList, "Nomination list")}
        </div>
      </article>`;
  }

  function renderBrowse() {
    const prizes = filteredPrizes();
    const start = state.page * PAGE;
    const slice = prizes.slice(start, start + PAGE);
    const counts = state.catalog.meta.counts;
    // Keep year headings correct when a year group spans two pages.
    let year = start > 0 ? prizes[start - 1].year : null;
    const cards = slice.map((prize) => {
      const heading = prize.year !== year ? `<h2 class="group-year">${prize.year}</h2>` : "";
      year = prize.year;
      return heading + prizeCard(prize);
    }).join("");
    const pages = Math.max(1, Math.ceil(prizes.length / PAGE));
    main.innerHTML = `
      <div class="stats">
        <span class="stat"><strong>${counts.awardedPrizeRecords}</strong> awarded</span>
        <span class="stat"><strong>${counts.unawardedPrizeRecords}</strong> not awarded</span>
        <span class="stat"><strong>${counts.laureateEntities}</strong> laureate records</span>
        <span class="stat"><strong>${prizes.length}</strong> matching</span>
      </div>
      <div class="warning">${esc(state.catalog.meta.notAnnounced.note)} <a href="${esc(state.catalog.meta.notAnnounced.source)}">Source</a></div>
      <div class="layout">
        ${renderFilters()}
        <section>
          ${cards || `<p class="empty">No records match these filters.</p>`}
          <div class="pager">
            <button type="button" id="prev" ${state.page === 0 ? "disabled" : ""}>Previous</button>
            <span>Page ${state.page + 1} of ${pages}</span>
            <button type="button" id="next" ${state.page + 1 >= pages ? "disabled" : ""}>Next</button>
          </div>
        </section>
      </div>`;
  }

  function renderLaureates() {
    const q = fold(state.query);
    const people = state.catalog.laureates.filter((person) => {
      if (!q) return true;
      return fold(person.displayName).includes(q) || fold(person.birthPlace).includes(q) || (person.prizes || []).some((key) => key.includes(q));
    });
    const slice = people.slice(state.page * PAGE, state.page * PAGE + PAGE);
    const pages = Math.max(1, Math.ceil(people.length / PAGE));
    main.innerHTML = `
      <div class="stats"><span class="stat"><strong>${people.length}</strong> matching laureate records</span></div>
      <section>
        ${slice.map((person) => `
          <article class="card">
            <h2 class="names">${esc(person.displayName || "Unnamed record")}</h2>
            <div class="meta-row">
              ${person.isOrganization ? "<span>Organization</span>" : person.gender ? `<span>${esc(person.gender)}</span>` : "<span>Gender not recorded</span>"}
              ${person.birthDate ? `<span>Born ${esc(person.birthDate)}</span>` : ""}
              ${person.deathDate ? `<span>Died ${esc(person.deathDate)}</span>` : ""}
              <span>${(person.prizes || []).length} prize record${person.prizes.length === 1 ? "" : "s"}</span>
            </div>
            <div class="link-row">
              <a href="#laureate/${esc(person.id)}">Open record</a>
              ${link(person.factsUrl, "Official facts")}
              ${link(person.apiUrl, "API record")}
            </div>
          </article>`).join("") || `<p class="empty">No laureates match.</p>`}
        <div class="pager">
          <button type="button" id="prev" ${state.page === 0 ? "disabled" : ""}>Previous</button>
          <span>Page ${state.page + 1} of ${pages}</span>
          <button type="button" id="next" ${state.page + 1 >= pages ? "disabled" : ""}>Next</button>
        </div>
      </section>`;
  }

  function renderAnalysis() {
    const categories = state.catalog.categories;
    const rows = categories.map((category) => {
      const prizes = state.catalog.prizes.filter((prize) => prize.category === category.id);
      const awarded = prizes.filter((prize) => prize.awarded);
      const slots = awarded.reduce((sum, prize) => sum + prize.laureates.length, 0);
      const female = awarded.reduce((sum, prize) => sum + prize.laureates.filter((row) => {
        const person = laureateById(row.id);
        return person && person.gender === "female";
      }).length, 0);
      const orgs = awarded.reduce((sum, prize) => sum + prize.laureates.filter((row) => row.isOrganization).length, 0);
      return `<tr>
        <td><a href="#browse" data-jump="${esc(category.id)}">${esc(category.label)}</a></td>
        <td>${awarded.length}</td>
        <td>${prizes.length - awarded.length}</td>
        <td>${slots}</td>
        <td>${female}</td>
        <td>${orgs}</td>
        <td>${category.inWill ? "Yes" : "No"}</td>
      </tr>`;
    }).join("");
    const decades = {};
    state.catalog.prizes.forEach((prize) => {
      if (!prize.awarded) return;
      const decade = Math.floor(prize.year / 10) * 10;
      decades[decade] = decades[decade] || {};
      decades[decade][prize.category] = (decades[decade][prize.category] || 0) + 1;
    });
    const decadeRows = Object.keys(decades).sort().map((decade) => {
      const cells = categories.map((category) => `<td>${decades[decade][category.id] || 0}</td>`).join("");
      return `<tr><td>${decade}s</td>${cells}</tr>`;
    }).join("");
    const factsCheck = state.catalog.meta.officialFactsCrossCheck || {};
    const expected = factsCheck.expected || {};
    const expectedByCategory = expected.by_category || {};
    const factsRows = categories.map((category) => {
      const prizesInCatalog = state.catalog.prizes.filter((prize) => prize.category === category.id && prize.awarded).length;
      const slotsInCatalog = state.catalog.prizes
        .filter((prize) => prize.category === category.id && prize.awarded)
        .reduce((sum, prize) => sum + prize.laureates.length, 0);
      const officialCat = expectedByCategory[category.id] || {};
      const prizesMatch = officialCat.prizes === prizesInCatalog;
      const slotsMatch = officialCat.slots === slotsInCatalog;
      return `<tr>
        <td>${esc(category.label)}</td>
        <td>${prizesInCatalog}</td>
        <td>${officialCat.prizes == null ? "—" : officialCat.prizes}${prizesMatch ? "" : " ⚠"}</td>
        <td>${slotsInCatalog}</td>
        <td>${officialCat.slots == null ? "—" : officialCat.slots}${slotsMatch ? "" : " ⚠"}</td>
      </tr>`;
    }).join("");
    const archiveTotals = state.catalog.meta.archiveTotals || {};
    const storedTotals = state.catalog.meta.storedNominationTotals || {};
    const totalRows = categories
      .filter((category) => storedTotals[category.id])
      .map((category) => {
        const official = (archiveTotals[category.id] || {}).nominations;
        const item = storedTotals[category.id];
        const windowText = `${(archiveTotals[category.id] || {}).from}–${(archiveTotals[category.id] || {}).through}`;
        return `<tr>
          <td>${esc(category.label)}</td>
          <td>${windowText}</td>
          <td>${official == null ? "—" : official}</td>
          <td>${item.stated}</td>
          <td>${item.stored}</td>
          <td>${item.stored === official ? "Equal" : `Differs by ${Math.abs((official || 0) - item.stored)} — flagged`}</td>
        </tr>`;
      }).join("");
    const storedGrand = Object.values(storedTotals).reduce((acc, item) => acc + item.stored, 0);
    main.innerHTML = `
      <section class="method">
        <h2>By subject</h2>
        <p>These counts are computed from the downloaded catalog. They are not a second official statistic. Compare them with the <a href="${esc(state.catalog.meta.factsUrl)}">Nobel Prize facts page</a>. Gender is shown only when the official API recorded it.</p>
        <div class="warning">${esc(state.catalog.meta.nominationCountIsNotAVote)}</div>
        <table>
          <thead><tr><th>Subject</th><th>Awarded</th><th>Not awarded</th><th>Laureate slots</th><th>Slots recorded female</th><th>Organization slots</th><th>In the 1895 will</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
        <h3>Awarded prizes by decade</h3>
        <table>
          <thead><tr><th>Decade</th>${categories.map((category) => `<th>${esc(category.label)}</th>`).join("")}</tr></thead>
          <tbody>${decadeRows}</tbody>
        </table>
        <h3>Cross-check against the official facts page</h3>
        <p>The counts this archive computed, next to the numbers on the <a href="${esc(factsCheck.source || state.catalog.meta.factsUrl)}">Nobel Prize facts page</a> retrieved ${esc(factsCheck.retrieved || "2026-09-24")}. A ⚠ means the two numbers disagree and the row is flagged. They agree in this build.</p>
        <table>
          <thead><tr><th>Subject</th><th>Catalog: awarded prizes</th><th>Facts page: prizes</th><th>Catalog: laureate slots</th><th>Facts page: laureates</th></tr></thead>
          <tbody>${factsRows}</tbody>
        </table>
        <h3>Nomination archive: stored rows vs official totals</h3>
        <p>“Page-stated” is the sum of each downloaded year page's own count. “Stored rows” is the number of Show-link rows the pages actually contained; only those rows are in this archive. The official table total is from the <a href="${esc(archiveTotals.source || state.catalog.meta.archiveHome)}">archive homepage</a>.</p>
        <table>
          <thead><tr><th>Subject</th><th>Published window</th><th>Official table total</th><th>Page-stated total</th><th>Stored rows</th><th>Check</th></tr></thead>
          <tbody>${totalRows}
            <tr><td>All subjects</td><td>—</td><td>${archiveTotals.table_total == null ? "—" : archiveTotals.table_total}</td><td>—</td><td>${storedGrand}</td><td>${storedGrand === archiveTotals.table_total ? "Equal" : `Differs by ${Math.abs((archiveTotals.table_total || 0) - storedGrand)} — flagged`}</td></tr>
          </tbody>
        </table>
        <p>Economic sciences has no nomination rows: the public archive has no economics category, and the 1969 probe page returned 0. The advanced search page separately states a total of ${archiveTotals.search_page_total == null ? "—" : archiveTotals.search_page_total} nominations. Both official totals are kept; they disagree.</p>
      </section>`;
    main.querySelectorAll("[data-jump]").forEach((anchor) => {
      anchor.addEventListener("click", (event) => {
        event.preventDefault();
        state.category = anchor.dataset.jump;
        state.page = 0;
        setHash("#browse");
      });
    });
  }

  function renderFlags() {
    const flags = state.catalog.flags.filter((flag) => {
      if (state.flagSeverity !== "all" && flag.severity !== state.flagSeverity) return false;
      return !state.query || fold(flag.message + " " + flag.code + " " + (flag.prizeKey || "")).includes(fold(state.query));
    });
    const counts = { review: 0, integrity: 0, info: 0 };
    state.catalog.flags.forEach((flag) => { counts[flag.severity] = (counts[flag.severity] || 0) + 1; });
    const slice = flags.slice(state.page * 30, state.page * 30 + 30);
    const pages = Math.max(1, Math.ceil(flags.length / 30));
    main.innerHTML = `
      <section class="method">
        <h2>Flags for review</h2>
        <p>A flag is a disagreement, a gap, or a scope note. It is not a correction, and missing names were not filled in. Full text: <a href="data/FLAGS.md">FLAGS.md</a>.</p>
        <div class="chip-list" style="flex-direction:row;flex-wrap:wrap">
          ${["review", "integrity", "info", "all"].map((item) => `<button type="button" class="chip" data-severity="${item}" aria-pressed="${state.flagSeverity === item}">${item === "all" ? "All" : item} ${item === "all" ? state.catalog.flags.length : counts[item] || 0}</button>`).join("")}
        </div>
        <p>${flags.length} shown.</p>
        ${slice.map((flag) => `
          <article class="card">
            <p class="kicker">${esc(flag.id || "")} · ${esc(flag.severity)}</p>
            <h3>${esc(flag.code)}</h3>
            <p>${esc(flag.message)}</p>
            <div class="link-row">
              ${flag.prizeKey ? `<a href="#prize/${esc(flag.prizeKey)}">Open prize</a>` : ""}
              ${(flag.sources || []).map((source) => link(source, "Source")).join("")}
            </div>
          </article>`).join("")}
        <div class="pager">
          <button type="button" id="prev" ${state.page === 0 ? "disabled" : ""}>Previous</button>
          <span>Page ${state.page + 1} of ${pages}</span>
          <button type="button" id="next" ${state.page + 1 >= pages ? "disabled" : ""}>Next</button>
        </div>
      </section>`;
  }

  function renderMethod() {
    const meta = state.catalog.meta;
    main.innerHTML = `
      <article class="method">
        <h2>How this was checked</h2>
        <p class="callout">This is an independent archive. It is not affiliated with, endorsed by, or sponsored by Nobel Prize Outreach or the Nobel Foundation. Nobel Prize names are used only to identify the source of the records.</p>
        <p>Built ${esc(meta.builtAt || "unknown")}. Source retrieval timestamp: ${esc(meta.fetchRetrievedAt || "not recorded in this build")}.</p>
        <h3>What a row is allowed to say</h3>
        <p>Every prize and laureate row comes from the official API. The reason a prize was given is the motivation text published with that prize. The archive does not write a comparative essay about why one project beat another. The awarding institutions do not publish that ranking.</p>
        <p>${esc(meta.nominationCountIsNotAVote)} <a href="${esc(meta.archiveManual)}">Nomination archive manual</a>.</p>
        <h3>Who else was considered</h3>
        <p>Other candidates are included only when a nomination-archive list page was downloaded and parsed. If the list was not stored, the prize still links to the official list. Sealed years, medicine years after 1953, and economic sciences are labeled as gaps. A zero on the economics probe page is not treated as “nobody was nominated.”</p>
        <p>The archive homepage table totalled ${meta.archiveTotals.table_total} nominations. The advanced search page said ${meta.archiveTotals.search_page_total}. Those official totals disagree and are both kept. <a href="${esc(meta.archiveHome)}">Homepage</a> · <a href="${esc(meta.archiveTotals.search_page)}">Search page</a>.</p>
        <p>This build stores ${Object.values(meta.storedNominationTotals || {}).reduce((sum, item) => sum + item.stored, 0)} nomination rows from the downloaded list pages. Subject-by-subject comparisons against the official table totals, with every difference flagged, are on the <a href="#analysis">By subject</a> page.</p>
        <h3>Official sources</h3>
        <ul>
          ${(meta.sources || []).map((source) => `<li><a href="${esc(source)}">${esc(source)}</a></li>`).join("")}
          <li><a href="${esc(meta.willUrl)}">Alfred Nobel’s will</a> — the 2018 English translation is quoted only by linking, not reproduced in full.</li>
          <li><a href="${esc(meta.termsUrl)}">API terms of use</a>. The data is offered under CC0, but the terms prevail. This site does not alter motivations or censor records.</li>
          <li><a href="${esc(meta.statutesUrl)}">Statutes of the Nobel Foundation</a>.</li>
        </ul>
        <h3>Line-by-line review</h3>
        <p>Open a prize, then open its official summary and API record. The CSV files are the review copies: <a href="data/prizes.csv">prizes.csv</a>, <a href="data/laureates.csv">laureates.csv</a>, <a href="data/nominations.csv">nominations.csv</a>.</p>
        <h3>Medicine list pages that disagree with themselves</h3>
        <p>Some physiology or medicine list pages state more nominations than they contain Show links. Every linked row is stored. The difference is flagged. Those missing names are not in the downloaded HTML, so they are not in this archive.</p>
        <h3>What this build does not know</h3>
        <ul>
          <li>2026 prizes had not been announced on 24 September 2026. <a href="${esc(meta.notAnnounced.source)}">Physics list page</a>.</li>
          <li>Nominator motivations live on individual nomination pages. Those 20,000-plus pages are linked, not bulk-copied, so this archive does not overload the source.</li>
          <li>Physics and chemistry nominations can be omitted while a nominee is alive. A missing name is not proof that no nomination existed.</li>
          <li>API v1 sometimes stores names in a different order from API v2. When both exist, v2 is displayed and the difference is flagged.</li>
        </ul>
      </article>`;
  }

  function nameMatchNote(row) {
    const match = row.nominationNameMatch;
    if (!match || match.level === "exact" || match.level === "none" && !(match.otherYearSpellings || []).length) return "";
    if (match.level === "diacritic" || match.level === "exact_without_parenthetical" || match.level === "token_equal" || match.level === "contained") {
      return `<p>Official list spelling: ${esc((match.publishedNames || [])[0] || "")}. Shown name is the API name. The names were not rewritten.</p>`;
    }
    if (match.level === "possible" || match.level === "near") {
      return `<p>Not an exact list match. Closest published spelling: ${esc((match.publishedNames || [])[0] || "")}. Not merged.</p>`;
    }
    const other = (match.otherYearSpellings || []).join("; ");
    return other ? `<p>Not on this year’s stored list. A similar spelling in another year was not moved here: ${esc(other)}.</p>` : `<p>Not found on this year’s stored nomination list. No name was added.</p>`;
  }

  function awardedNominee(prize, nominee) {
    const target = fold(nominee.name);
    return prize.laureates.some((row) => fold(row.displayName) === target);
  }

  function openPrize(key) {
    const prize = prizeByKey(key);
    if (!prize) return;
    const flags = state.catalog.flags.filter((flag) => flag.prizeKey === key);
    const nominees = (prize.nomination && prize.nomination.nominees) || [];
    detailBody.innerHTML = `
      <div class="detail-head">
        <div>
          <p class="kicker">${esc(prize.categoryFullName)} ${prize.year}</p>
          <h2>${prize.awarded ? "Awarded" : "Not awarded"}</h2>
        </div>
        <button type="button" class="close" id="close-detail">Close</button>
      </div>
      <div class="detail-body">
        <section class="section">
          <h3>Official reason the prize was given</h3>
          ${prize.overallMotivation ? `<p><strong>Prize-level motivation:</strong> ${esc(prize.overallMotivation)}</p>` : ""}
          ${prize.laureates.map((row) => `
            <div class="person">
              <h4>${esc(row.displayName || "Unnamed")}</h4>
              <p class="quote">${row.motivation ? `“${esc(row.motivation)}”` : "No motivation text in the downloaded record."}</p>
              <div class="meta-row">
                <span>Portion ${esc(row.portion || "not recorded")}</span>
                <span>API status ${esc(row.prizeStatus || "not in downloaded laureate file")}</span>
                ${(row.affiliations || []).map((item) => `<span>${esc(item)}</span>`).join("")}
              </div>
              ${row.motivationSwedish ? `<p>Swedish motivation, as published: ${esc(row.motivationSwedish)}</p>` : ""}
              ${nameMatchNote(row)}
              <div class="link-row">
                ${link(row.factsUrl, "Official facts")}
                ${link(row.apiUrl, "Laureate API")}
                <a href="#laureate/${esc(row.id)}">Person record</a>
              </div>
            </div>`).join("")}
          <p class="meta-row">
            ${prize.dateAwarded ? `<span>Date awarded ${esc(prize.dateAwarded)}</span>` : ""}
            ${prize.prizeAmount != null ? `<span>Amount ${esc(money(prize.prizeAmount))}</span>` : ""}
            ${prize.prizeAmountAdjusted != null ? `<span>API adjusted amount ${esc(money(prize.prizeAmountAdjusted))}</span>` : ""}
          </p>
        </section>
        <section class="section">
          <h3>Why this rather than other work</h3>
          <p>${esc(prize.selection.statement)}</p>
          <p><a href="${esc(prize.selection.sources[0])}">Nomination archive manual</a></p>
        </section>
        <section class="section">
          <h3>Others considered</h3>
          <p>${esc(statusLabel(prize.nomination.status))}. ${esc(prize.nomination.note || "")}</p>
          ${prize.nomination.statedCount != null ? `<p>Page-stated nominations: ${prize.nomination.statedCount}. Parsed rows: ${prize.nomination.parsedCount == null ? "not stored" : prize.nomination.parsedCount}. A count is not a vote.</p>` : ""}
          ${nominees.length ? `<ul class="nominee-list">${nominees.map((nominee) => `<li>${nominee.url ? `<a href="${esc(nominee.url)}">${esc(nominee.name)}</a>` : esc(nominee.name)} · ${nominee.nominations} published nomination${nominee.nominations === 1 ? "" : "s"}${awardedNominee(prize, nominee) ? " · exact name match to a laureate" : ""}</li>`).join("")}</ul>` : `<p>No nominee names are stored for this prize. ${link(prize.links.nominationList, "Open the official list")}</p>`}
          <div class="link-row">${link(prize.links.nominationList, "Official nomination list")}</div>
        </section>
        <section class="section">
          <h3>Check this line</h3>
          <div class="link-row">
            ${link(prize.links.summary, "Prize summary")}
            ${link(prize.links.apiPrize, "Prize API")}
            ${link(prize.links.categoryList, "Official category list")}
          </div>
        </section>
        ${flags.length ? `<section class="section"><h3>Flags</h3>${flags.map((flag) => `<p>${badge(flag.severity)} ${esc(flag.message)}</p>`).join("")}</section>` : ""}
      </div>`;
    dialog.showModal();
    document.getElementById("close-detail").focus();
  }

  function openLaureate(id) {
    const person = laureateById(id);
    if (!person) return;
    const prizes = (person.prizes || []).map(prizeByKey).filter(Boolean);
    detailBody.innerHTML = `
      <div class="detail-head">
        <div>
          <p class="kicker">${person.isOrganization ? "Organization" : "Person"}</p>
          <h2>${esc(person.displayName || "Unnamed record")}</h2>
        </div>
        <button type="button" class="close" id="close-detail">Close</button>
      </div>
      <div class="detail-body">
        <div class="meta-row">
          ${person.gender ? `<span>${esc(person.gender)}</span>` : "<span>Gender not recorded</span>"}
          ${person.birthDate ? `<span>Born ${esc(person.birthDate)}${person.birthPlace ? ", " + esc(person.birthPlace) : ""}</span>` : ""}
          ${person.deathDate ? `<span>Died ${esc(person.deathDate)}${person.deathPlace ? ", " + esc(person.deathPlace) : ""}</span>` : ""}
        </div>
        <div class="link-row">
          ${link(person.factsUrl, "Official facts")}
          ${link(person.apiUrl, "API record")}
          ${person.wikipediaFromOfficialApi ? link(person.wikipediaFromOfficialApi, "Wikipedia link from the official API") : ""}
          ${person.wikidataFromOfficialApi ? link(person.wikidataFromOfficialApi, "Wikidata link from the official API") : ""}
        </div>
        <section class="section">
          <h3>Prize records</h3>
          ${prizes.map((prize) => {
            const row = prize.laureates.find((item) => item.id === person.id) || {};
            return `<div class="person"><h4>${prize.year} ${esc(prize.categoryLabel)}</h4><p class="quote">${row.motivation ? `“${esc(row.motivation)}”` : ""}</p><a href="#prize/${esc(prize.key)}">Open prize</a></div>`;
          }).join("")}
        </section>
      </div>`;
    dialog.showModal();
    document.getElementById("close-detail").focus();
  }

  function render() {
    if (!state.catalog) return;
    renderNav();
    const hashView = location.hash.replace(/^#/, "").split("/")[0] || "browse";
    if (hashView === "laureates") renderLaureates();
    else if (hashView === "analysis") renderAnalysis();
    else if (hashView === "flags") renderFlags();
    else if (hashView === "method") renderMethod();
    else renderBrowse();
    if (state.prizeKey) openPrize(state.prizeKey);
    if (state.laureateId) openLaureate(state.laureateId);
    bind();
  }

  function bind() {
    main.querySelectorAll("[data-category]").forEach((button) => {
      button.addEventListener("click", () => {
        state.category = button.dataset.category;
        state.page = 0;
        render();
      });
    });
    main.querySelectorAll("[data-severity]").forEach((button) => {
      button.addEventListener("click", () => {
        state.flagSeverity = button.dataset.severity;
        state.page = 0;
        render();
      });
    });
    main.querySelectorAll("[data-awarded]").forEach((button) => {
      button.addEventListener("click", () => {
        state.awarded = button.dataset.awarded;
        state.page = 0;
        render();
      });
    });
    const flags = main.querySelector("[data-flags]");
    if (flags) flags.addEventListener("click", () => { state.flagsOnly = !state.flagsOnly; state.page = 0; render(); });
    const from = document.getElementById("from");
    const to = document.getElementById("to");
    const clampYear = (raw, fallback) => {
      const value = Math.round(Number(raw));
      if (!Number.isFinite(value)) return fallback;
      return Math.min(Math.max(value, 1901), maxYear());
    };
    if (from) from.addEventListener("change", () => {
      state.from = Math.min(clampYear(from.value, 1901), state.to);
      state.page = 0;
      render();
    });
    if (to) to.addEventListener("change", () => {
      state.to = Math.max(clampYear(to.value, maxYear()), state.from);
      state.page = 0;
      render();
    });
    const prev = document.getElementById("prev");
    const next = document.getElementById("next");
    if (prev) prev.addEventListener("click", () => { state.page = Math.max(0, state.page - 1); render(); });
    if (next) next.addEventListener("click", () => { state.page += 1; render(); });
  }

  document.getElementById("search-form").addEventListener("submit", (event) => event.preventDefault());
  search.addEventListener("input", () => {
    state.query = search.value;
    state.page = 0;
    render();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "/" && document.activeElement !== search) {
      event.preventDefault();
      search.focus();
    }
  });
  dialog.addEventListener("close", () => {
    if (state.keepDetailHash) return;
    if (location.hash.startsWith("#prize") || location.hash.startsWith("#laureate")) {
      history.replaceState(null, "", "#browse");
      state.prizeKey = null;
      state.laureateId = null;
    }
  });
  dialog.addEventListener("click", (event) => {
    if (event.target.id === "close-detail") dialog.close();
  });
  window.addEventListener("hashchange", () => {
    state.keepDetailHash = true;
    if (dialog.open) dialog.close();
    state.keepDetailHash = false;
    parseHash();
    render();
  });

  fetch("data/catalog.json")
    .then((response) => {
      if (!response.ok) throw new Error("Catalog not found");
      return response.json();
    })
    .then((catalog) => {
      state.catalog = catalog;
      const years = catalog.prizes.map((prize) => prize.year);
      if (years.length) {
        state.from = Math.min.apply(null, years);
        state.to = Math.max.apply(null, years);
      }
      document.getElementById("lede").textContent = `Through ${catalog.meta.latestAwardYearInSources || "the downloaded years"}. Every row links to nobelprize.org for review.`;
      parseHash();
      render();
    })
    .catch(() => {
      main.innerHTML = `
        <article class="method">
          <h2>Catalog not in this build yet</h2>
          <p>The site is ready, but <code>data/catalog.json</code> has not been generated. The download script reads the official API and nomination archive. It does not invent missing rows.</p>
          <p>On a network that can reach nobelprize.org, run <code>python scripts/fetch_official.py && python scripts/build_catalog.py && python scripts/verify_catalog.py</code>.</p>
          <p>Read <a href="README.md">README.md</a> for the known limits, including the 50-year nomination seal.</p>
        </article>`;
    });
})();
