const ET = "America/New_York";
const EN = "–";

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]));
}

function safeImage(url) {
  try {
    const parsed = new URL(url);
    const host = parsed.hostname;
    if (parsed.protocol === "https:" && (host === "img.mlbstatic.com" || host.endsWith(".mlbstatic.com"))) {
      return url;
    }
  } catch (_error) {
    return "";
  }
  return "";
}

function safeLink(url) {
  try {
    const parsed = new URL(url);
    const host = parsed.hostname;
    if (parsed.protocol === "https:" && (host === "mlb.com" || host.endsWith(".mlb.com"))) {
      return url;
    }
  } catch (_error) {
    return "";
  }
  return "";
}

function formatWhen(value, options) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("en-US", { timeZone: ET, ...options }).format(date);
}

function gameWhen(game, withTime) {
  if (!withTime || game.startTimeTBD || !game.startTime) {
    const source = game.startTime || `${game.date}T16:00:00Z`;
    return formatWhen(source, { month: "short", day: "numeric" });
  }
  return formatWhen(game.startTime, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

function weekday(game) {
  const source = game.startTime || `${game.date}T16:00:00Z`;
  return formatWhen(source, { weekday: "short" });
}

function place(game) {
  return game.home ? `vs. the ${game.opponent}` : `at the ${game.opponent}`;
}

function diffPhrase(value) {
  const number = Number(value);
  if (number > 0) return `+${number} run differential`;
  if (number < 0) return `−${Math.abs(number)} run differential`;
  return "Even run differential";
}

function signed(value) {
  const number = Number(value);
  if (number > 0) return `+${number}`;
  if (number < 0) return `−${Math.abs(number)}`;
  return "0";
}

function initials(name) {
  return String(name || "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

function avatar(person) {
  const src = safeImage(person.headshot);
  const image = src ? `<img alt="" src="${esc(src)}" onerror="this.remove()">` : "";
  return `<span class="avatar">${image}<span class="fallback" aria-hidden="true">${esc(initials(person.name))}</span></span>`;
}

function lede(data) {
  const record = data.record;
  const parts = [`<span class="record">${esc(`${record.wins}${EN}${record.losses}`)}</span>`];
  if (data.seasonState === "inProgress" && record.streak) parts.push(esc(record.streak));
  parts.push(esc(diffPhrase(record.runDifferential)));
  const next = (data.schedule.upcoming || [])[0];
  if (next && next.status === "Live" && next.score) {
    parts.push(esc(`Live ${place(next)}, ${next.score}`));
  } else if (next) {
    const when = next.startTimeTBD ? "time TBD" : formatWhen(next.startTime, {
      weekday: "short",
      hour: "numeric",
      minute: "2-digit",
      timeZoneName: "short",
    });
    parts.push(esc(`${when} ${place(next)}`));
  } else if (data.seasonState === "complete") {
    parts.push("Season complete");
  }
  return parts.join(" · ");
}

function standingsTable(rows, { full }) {
  const head = full
    ? ["", "Club", "W", "L", "PCT", "GB", "RS", "RA", "Diff", "L10", "Strk", "Home", "Road"]
    : ["", "Club", "W", "L", "GB"];
  const body = rows.map((row) => {
    const club = `<th class="club" scope="row">${esc(row.club)}</th>`;
    const cells = full
      ? [row.rank, club, row.wins, row.losses, row.pct, row.gamesBack, row.runsScored, row.runsAllowed, signed(row.runDifferential), row.lastTen, row.streak, row.home, row.road]
      : [row.rank, club, row.wins, row.losses, row.gamesBack];
    const html = cells.map((cell, index) => (index === 1 ? cell : `<td>${esc(cell)}</td>`)).join("");
    return `<tr class="${row.isGuardians ? "guardians" : ""}">${html}</tr>`;
  }).join("");
  const headers = head.map((label, index) => `<th${index === 1 ? ' class="club"' : ""} scope="col">${esc(label)}</th>`).join("");
  return `<div class="table-scroll"><table class="${full ? "standings" : "compact"}"><thead><tr>${headers}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function wildCardTable(rows) {
  const body = rows.map((row) => {
    const status = row.clinched ? "In" : row.elimination;
    return `<tr class="${row.isGuardians ? "guardians" : ""}">
      <td>${esc(row.rank)}</td>
      <th class="club" scope="row">${esc(row.club)}</th>
      <td>${esc(row.wins)}</td>
      <td>${esc(row.losses)}</td>
      <td>${esc(row.gamesBack)}</td>
      <td>${esc(status)}</td>
    </tr>`;
  }).join("");
  return `<div class="table-scroll"><table class="compact"><thead><tr>
    <th scope="col"></th><th class="club" scope="col">Club</th>
    <th scope="col">W</th><th scope="col">L</th><th scope="col">GB</th><th scope="col">Status</th>
  </tr></thead><tbody>${body}</tbody></table></div>`;
}

function featureHitter(player) {
  if (!player) return `<article class="feature"><p class="empty">No qualified hitters yet.</p></article>`;
  return `<article class="feature">
    <div class="who">${avatar(player)}<div><p class="name">${esc(player.name)}</p><p class="role">${esc(player.position)}</p></div></div>
    <p class="stat"><span>OPS</span>${esc(player.ops)}</p>
    <p class="line">${esc(`${player.avg} AVG · ${player.hr} HR · ${player.rbi} RBI`)}</p>
  </article>`;
}

function featurePitcher(player, stat) {
  if (!player) return `<article class="feature"><p class="empty">No qualified pitchers yet.</p></article>`;
  const saves = stat === "saves";
  const number = saves ? player.sv : player.era;
  const label = saves ? "Saves" : "ERA";
  const line = saves
    ? `${player.era} ERA · ${player.ip} IP · ${player.so} K`
    : `${player.ip} IP · ${player.w}${EN}${player.l} · ${player.so} K`;
  return `<article class="feature">
    <div class="who">${avatar(player)}<div><p class="name">${esc(player.name)}</p><p class="role">${esc(player.role)}</p></div></div>
    <p class="stat"><span>${esc(label)}</span>${esc(number)}</p>
    <p class="line">${esc(line)}</p>
  </article>`;
}

function personRow(name, line) {
  return `<div class="person"><span class="name">${esc(name)}</span><span class="line">${esc(line)}</span></div>`;
}

function hitterLine(player) {
  return `${player.position} · ${player.avg} · ${player.hr} HR · ${player.ops} OPS`;
}

function pitcherLine(player) {
  if (player.role === "RP") return `${player.role} · ${player.sv} SV · ${player.era} ERA · ${player.ip} IP`;
  return `${player.role} · ${player.era} ERA · ${player.ip} IP · ${player.w}${EN}${player.l} · ${player.so} K`;
}

function group(title, rows, lineFor) {
  if (!rows.length) return "";
  return `<h3 class="group-label">${esc(title)}</h3><div class="people">${rows.map((row) => personRow(row.name, lineFor(row))).join("")}</div>`;
}

function pitchers(game) {
  if (game.probable && game.opponentProbable) return `${game.probable} vs. ${game.opponentProbable}`;
  return game.probable || game.opponentProbable || "";
}

function decisions(game) {
  return [
    game.winner ? `W ${game.winner}` : "",
    game.loser ? `L ${game.loser}` : "",
    game.save ? `S ${game.save}` : "",
  ].filter(Boolean).join(" · ");
}

function clock(game) {
  if (game.startTimeTBD || !game.startTime) return "TBD";
  return formatWhen(game.startTime, { hour: "numeric", minute: "2-digit", timeZoneName: "short" });
}

function gameMeta(game) {
  const series = [game.series, game.gameNumber > 1 ? `Game ${game.gameNumber}` : ""].filter(Boolean).join(" ");
  if (game.result) return [decisions(game), game.venue, series].filter(Boolean);
  return [pitchers(game), game.venue, series].filter(Boolean);
}

function gameRow(game, featured) {
  const mark = game.result
    ? `<span class="result ${esc(game.result)}">${esc(game.result)}</span>`
    : `<span class="day">${esc(weekday(game))}</span>`;
  const right = game.result ? (game.score || "") : clock(game);
  const title = featured ? game.opponent : place(game);
  const meta = featured
    ? [game.home ? "Home" : "Away", ...gameMeta(game)].filter(Boolean)
    : gameMeta(game);
  return `<article class="game${featured ? " next" : ""}">
    <p class="when">${mark}<span>${esc(gameWhen(game, false))}</span></p>
    <div>
      <p class="opp">${esc(title)}</p>
      <p class="meta">${esc(meta.join(" · "))}</p>
    </div>
    <p class="score${game.result === "L" ? " loss" : ""}">${esc(right)}</p>
  </article>`;
}

function storyDate(value) {
  return formatWhen(value, { month: "short", day: "numeric" });
}

function renderNews(stories) {
  if (!stories.length) {
    document.getElementById("news-body").innerHTML = `<p class="empty">No headlines in the latest snapshot.</p>`;
    return;
  }
  const [lead, ...rest] = stories;
  const image = safeImage(lead.image);
  const by = [lead.author, storyDate(lead.published)].filter(Boolean).join(" · ");
  const leadInner = `<div><p class="eyebrow">${esc(lead.source || "MLB.com")}</p><h3>${esc(lead.title)}</h3><p class="by">${esc(by)}</p></div>${image ? `<img alt="" src="${esc(image)}">` : ""}`;
  const href = safeLink(lead.url);
  const leadHtml = href
    ? `<a class="lead" href="${esc(href)}" target="_blank" rel="noopener noreferrer">${leadInner}</a>`
    : `<div class="lead">${leadInner}</div>`;
  const list = rest.map((story) => {
    const when = storyDate(story.published);
    const inner = `<span><h3>${esc(story.title)}</h3>${story.author ? `<p class="by">${esc(story.author)}</p>` : ""}</span><time datetime="${esc(story.published)}">${esc(when)}</time>`;
    const link = safeLink(story.url);
    return link
      ? `<a class="story" href="${esc(link)}" target="_blank" rel="noopener noreferrer">${inner}</a>`
      : `<div class="story">${inner}</div>`;
  }).join("");
  document.getElementById("news-body").innerHTML = `${leadHtml}<div class="stories">${list}</div>`;
}

function render(data) {
  document.title = `${String(data.heroLine || "Guardians").replace(/\.$/, "")} — Guardians`;
  document.getElementById("hero-kicker").textContent = `${data.team.division} · ${data.season}`;
  document.getElementById("hero-line").textContent = data.heroLine;
  document.getElementById("hero-meta").innerHTML = lede(data);

  const updated = formatWhen(data.generatedAt, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
  document.getElementById("nav-time").dateTime = data.generatedAt;
  document.getElementById("nav-time").textContent = updated ? `Updated ${updated}` : "";
  document.getElementById("footer-updated").textContent = updated ? `Updated ${updated}.` : "";

  const playoff = data.playoff;
  document.getElementById("race-summary").textContent = playoff.summary;
  document.getElementById("race-figure").textContent = playoff.figure;
  document.getElementById("race-figure-label").textContent = playoff.figureLabel;
  document.getElementById("race-facts").innerHTML = `
    <div><dt>Division</dt><dd>${esc(playoff.divisionFact)}</dd></div>
    <div><dt>Wild card</dt><dd>${esc(playoff.wildCardFact)}</dd></div>
    <div><dt>Games left</dt><dd>${esc(playoff.gamesRemaining)}</dd></div>`;
  document.getElementById("race-tables").innerHTML = `
    <div class="race-boards">
      <div>
        <h3 class="table-label">AL Central</h3>
        ${standingsTable(playoff.division, { full: false })}
      </div>
      <div>
        <h3 class="table-label">Wild card</h3>
        ${wildCardTable(playoff.wildCard)}
      </div>
    </div>`;

  document.getElementById("division-name").textContent = data.division.name;
  document.getElementById("division-table").innerHTML = standingsTable(playoff.division, { full: true });
  document.getElementById("season-series").innerHTML = (data.division.seasonSeries || []).map((series) => `
    <div><p class="num">${esc(`${series.wins}${EN}${series.losses}`)}</p><p class="club">${esc(series.club)}</p></div>`).join("");

  const players = data.players;
  const featured = players.featured || {};
  document.getElementById("player-features").innerHTML = `<div class="features">${featureHitter(featured.hitter)}${featurePitcher(featured.pitcher, featured.pitcherStat)}</div>`;
  document.getElementById("leader-strip").innerHTML = [
    ["AVG", players.leaders.avg],
    ["HR", players.leaders.hr],
    ["RBI", players.leaders.rbi],
    ["SB", players.leaders.sb],
    ["K", players.leaders.so],
    ["SV", players.leaders.saves],
  ].filter(([, leader]) => leader).map(([label, leader]) => `
    <div><p class="k">${label}</p><p class="v">${esc(leader.value)}</p><p class="n">${esc(leader.name)}</p></div>`).join("");

  document.getElementById("player-lists").innerHTML = [
    group("Hitting", players.hitters || [], hitterLine),
    group("Starting pitching", players.starters || [], pitcherLine),
    group("Relief pitching", players.relievers || [], pitcherLine),
  ].join("");

  const upcoming = data.schedule.upcoming || [];
  const recent = data.schedule.recent || [];
  document.querySelector("#schedule h2").textContent = upcoming.length ? "The next games" : "Recent games";
  const upcomingHtml = upcoming.length
    ? `<h3 class="block-label">Upcoming</h3>${upcoming.map((game, index) => gameRow(game, index === 0)).join("")}`
    : `<p class="empty">No games scheduled.</p>`;
  const recentHtml = recent.length
    ? `<h3 class="block-label">Recent</h3>${recent.map((game) => gameRow(game, false)).join("")}`
    : "";
  document.getElementById("schedule-body").innerHTML = upcomingHtml + recentHtml;
  renderNews(data.headlines || []);
}

function watchSections() {
  const links = [...document.querySelectorAll(".nav nav a")];
  const sections = links.map((link) => document.querySelector(link.getAttribute("href"))).filter(Boolean);
  if (!("IntersectionObserver" in window)) return;
  const spy = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      links.forEach((link) => link.removeAttribute("aria-current"));
      const current = document.querySelector(`.nav nav a[href="#${entry.target.id}"]`);
      if (current) current.setAttribute("aria-current", "true");
    });
  }, { rootMargin: "-45% 0px -45% 0px" });
  sections.forEach((section) => spy.observe(section));
  window.setTimeout(() => {
    document.querySelectorAll(".reveal:not(.in)").forEach((block) => block.classList.add("in"));
  }, 2500);

  const motion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const blocks = [...document.querySelectorAll(".reveal")];
  if (motion || !("IntersectionObserver" in window)) {
    blocks.forEach((block) => block.classList.add("in"));
    return;
  }
  const reveal = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add("in");
      reveal.unobserve(entry.target);
    });
  }, { threshold: 0.12 });
  blocks.forEach((block) => reveal.observe(block));
}

function bindHero() {
  const hero = document.querySelector(".hero");
  const image = document.querySelector(".hero-media img");
  const veil = document.querySelector(".hero-veil");
  if (!hero || !image || !veil) return;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
  const paint = () => {
    if (reduce.matches) {
      image.style.transform = "none";
      veil.style.opacity = "0";
      return;
    }
    const travel = Math.max(hero.offsetHeight - window.innerHeight, 1);
    const progress = Math.min(1, Math.max(0, -hero.getBoundingClientRect().top / travel));
    const fade = Math.max(0, (progress - 0.4) / 0.6);
    image.style.transform = `scale(${(1.12 - progress * 0.12).toFixed(4)})`;
    veil.style.opacity = String((fade * 0.84).toFixed(4));
  };
  let frame = 0;
  paint();
  window.addEventListener("scroll", () => {
    if (frame) return;
    frame = window.requestAnimationFrame(() => {
      frame = 0;
      paint();
    });
  }, { passive: true });
  window.addEventListener("resize", paint);
}

async function init() {
  bindHero();
  try {
    const response = await fetch("data/snapshot.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`Snapshot request failed (${response.status})`);
    render(await response.json());
    watchSections();
  } catch (_error) {
    document.getElementById("hero-line").textContent = "The scoreboard is unavailable.";
    document.getElementById("hero-meta").textContent = "The latest snapshot did not load.";
  }
}

init();
